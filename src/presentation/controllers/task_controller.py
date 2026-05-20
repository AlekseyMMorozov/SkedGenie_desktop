# src/presentation/controllers/task_controller.py

"""
Файл: src/presentation/controllers/task_controller.py
Описание: Контроллер-посредник между Presentation (UI) и Application/Infrastructure.
          Запускает асинхронные CRUD-операции в фоновых потоках, транслирует результаты
          в Qt-сигналы и управляет локальным кэшем DTO для быстрого доступа UI.
Архитектура: Presentation слой. Не содержит ORM-кода. Использует DI для ITaskRepository.
"""
from __future__ import annotations

import asyncio
import logging
import threading
from typing import List, Optional
from uuid import UUID

from PySide6.QtCore import QObject, Signal

from src.application.interfaces.task_repository_interface import ITaskRepository
from src.application.schemas.task_schemas import TaskCreateSchema, TaskUpdateSchema, TaskReadSchema
from src.domain.tasks.planning_task_model import PlanningTask
from src.domain.tasks.task_exceptions import TaskDomainError


class TaskController(QObject):
    """Контроллер управления задачами планирования.

    Связывает асинхронный репозиторий с синхронным UI через Qt-сигналы.
    Гарантирует, что блокирующие/асинхронные операции не замораживают интерфейс.
    """

    tasks_loaded = Signal(list)  # List[TaskReadSchema]
    operation_succeeded = Signal(str)  # Краткое сообщение об успехе
    operation_failed = Signal(str)  # Текст ошибки для отображения

    def __init__(self, repository: ITaskRepository, parent=None):
        super().__init__(parent)
        self._repo = repository
        self._logger = logging.getLogger(__name__)
        self._cache: List[TaskReadSchema] = []

    # --- Публичные методы (вызываются из UI) ---
    def load_tasks(self) -> None:
        """Запрос на загрузку всех задач."""
        self._dispatch_async(self._execute_load_all, success_msg="Задачи обновлены")

    def create_task(self, schema: TaskCreateSchema) -> None:
        """Запрос на создание новой задачи."""
        self._dispatch_async(self._execute_create, schema, success_msg="Задача успешно создана")

    def update_task(self, schema: TaskUpdateSchema) -> None:
        """Запрос на обновление существующей задачи."""
        self._dispatch_async(self._execute_update, schema, success_msg="Задача обновлена")

    def delete_task(self, task_id: UUID) -> None:
        """Запрос на удаление задачи."""
        self._dispatch_async(self._execute_delete, task_id, success_msg="Задача удалена")

    # --- Вспомогательные методы для кэша и маппинга ---
    def get_cached_task(self, task_id: UUID) -> Optional[TaskReadSchema]:
        """Возвращает задачу из кэша без обращения к БД."""
        for task in self._cache:
            if task.id == task_id:
                return task
        return None

    def _update_cache(self, tasks: List[PlanningTask]) -> None:
        """Обновляет локальный кэш DTO."""
        self._cache = [self._map_to_schema(t) for t in tasks]

    @staticmethod
    def _map_to_schema(domain: PlanningTask) -> TaskReadSchema:
        """Конвертирует доменную модель в DTO для Presentation."""
        return TaskReadSchema(
            id=domain.id,
            name=domain.name,
            period_type=domain.period_type.value,
            period_start=domain.period_start,
            period_end=domain.period_end,
            reference_id=domain.reference_id,
            created_at=domain.created_at,
            updated_at=domain.updated_at,
        )

    # --- Асинхронные операции (выполняются в фоне) ---
    async def _execute_load_all(self) -> List[PlanningTask]:
        tasks = await self._repo.get_all()
        self._update_cache(tasks)
        return tasks

    async def _execute_create(self, schema: TaskCreateSchema) -> None:
        domain_task = PlanningTask(
            name=schema.name,
            period_type=schema.period_type,
            period_start=schema.period_start,
            period_end=schema.period_end,
            reference_id=schema.reference_id,
        )
        await self._repo.create(domain_task)

    async def _execute_update(self, schema: TaskUpdateSchema) -> None:
        cached = self.get_cached_task(schema.id)
        if not cached:
            raise TaskDomainError("Задача не найдена в кэше или уже удалена.")

        # Создаём обновлённый экземпляр, сохраняя системные поля
        domain_task = PlanningTask(
            id=schema.id,
            name=schema.name or cached.name,
            period_type=schema.period_type or cached.period_type,
            period_start=schema.period_start or cached.period_start,
            period_end=schema.period_end or cached.period_end,
            reference_id=schema.reference_id,
            created_at=cached.created_at,
            updated_at=cached.updated_at,
        )
        await self._repo.update(domain_task)

    async def _execute_delete(self, task_id: UUID) -> None:
        await self._repo.delete(task_id)

    # --- Диспетчер фоновых задач ---
    def _dispatch_async(self, coro_func, *args, success_msg: str = "Готово") -> None:
        """Запускает асинхронную функцию в изолированном потоке и эмитит Qt-сигналы."""

        def runner():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(coro_func(*args))
                loop.close()

                if coro_func == self._execute_load_all:
                    schemas = [self._map_to_schema(t) for t in result]
                    self.tasks_loaded.emit(schemas)

                self.operation_succeeded.emit(success_msg)
                self._logger.info(success_msg)
            except TaskDomainError as e:
                self._logger.warning(f"Domain error in controller: {e}")
                self.operation_failed.emit(str(e))
            except Exception as e:
                self._logger.exception("Unexpected error in async dispatch")
                self.operation_failed.emit(f"Внутренняя ошибка: {e}")

        threading.Thread(target=runner, daemon=True).start()
