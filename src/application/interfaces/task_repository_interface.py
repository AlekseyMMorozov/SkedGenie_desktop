# src/application/interfaces/task_repository_interface.py

"""Абстрактный интерфейс репозитория для работы с задачами планирования."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.tasks.planning_task_model import PlanningTask


class ITaskRepository(ABC):
    """Контракт слоя репозитория для доменной сущности PlanningTask.

    Определяет асинхронные операции CRUD, работающие исключительно
    с Pydantic-моделями. Позволяет заменять инфраструктуру хранения
    без изменения бизнес-логики и сервисного слоя.
    """

    @abstractmethod
    async def get_by_id(self, task_id: UUID) -> PlanningTask | None:
        """Получить задачу планирования по уникальному идентификатору."""
        pass

    @abstractmethod
    async def get_all(self) -> list[PlanningTask]:
        """Получить отсортированный список всех задач планирования."""
        pass

    @abstractmethod
    async def create(self, task: PlanningTask) -> PlanningTask:
        """Сохранить новую задачу в хранилище и вернуть сохранённую версию."""
        pass

    @abstractmethod
    async def update(self, task: PlanningTask) -> PlanningTask:
        """Обновить существующую задачу в хранилище и вернуть результат."""
        pass

    @abstractmethod
    async def delete(self, task_id: UUID) -> None:
        """Удалить задачу планирования по идентификатору."""
        pass
