# src/presentation/controllers/task_controller.py
"""
Контроллер для CRUD-операций над задачами планирования.

Предоставляет тонкий фасад над :class:`ITaskRepository`, отвечающий за:
    - Преобразование ``Schema ↔ PlanningTask`` (изоляция UI от Domain).
    - Проверку уникальности названия задачи перед созданием/обновлением.
    - Логирование пользовательских действий через :func:`log_user_action`.
    - Обработку исключений (:class:`TaskDomainError`, :class:`SQLAlchemyError`)
      с пробросом в UI для отображения ошибок пользователю.
    - Возврат :class:`TaskReadSchema` (DTO) для отображения в таблице.

Все методы асинхронные — вызываются через :class:`AsyncBridge` из GUI-потока.
"""
from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError

from src.application.interfaces.task_repository_interface import ITaskRepository
from src.application.schemas.task_schemas import (
    TaskCreateSchema,
    TaskReadSchema,
    TaskUpdateSchema,
)
from src.core.logging_config import log_user_action, log_user_error
from src.domain.tasks.planning_task_model import PlanningTask
from src.domain.tasks.task_exceptions import (
    TaskDomainError,
    DuplicateTaskNameError,
)


class TaskController:
    """Контроллер для управления задачами планирования.

    Оборачивает репозиторий, добавляя логирование пользовательских действий,
    проверку уникальности названия и преобразование между DTO
    (:class:`TaskCreateSchema`, :class:`TaskReadSchema`) и Domain-объектами
    (:class:`PlanningTask`).

    Attributes:
        _repository: Репозиторий для работы с задачами (через интерфейс).
        _logger: Логгер для событий контроллера.
    """

    def __init__(
        self,
        repository: ITaskRepository,
        logger: logging.Logger,
    ) -> None:
        """Инициализация контроллера.

        Args:
            repository: Репозиторий задач (реализация :class:`ITaskRepository`).
            logger: Логгер для событий контроллера.
        """
        self._repository = repository
        self._logger = logger

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------
    async def get_all_tasks(self) -> list[TaskReadSchema]:
        """Получить список всех задач планирования."""
        self._logger.debug("TaskController: запрос списка всех задач")
        try:
            tasks = await self._repository.get_all()
            result = [TaskReadSchema.model_validate(task) for task in tasks]
            self._logger.debug(
                "TaskController: получено %d задач",
                len(result),
            )
            return result
        except SQLAlchemyError as exc:
            log_user_error(
                self._logger,
                "Получение списка задач",
                f"Ошибка БД: {exc}",
            )
            raise
        except Exception as exc:
            self._logger.error(
                "TaskController: непредвиденная ошибка при получении задач: %s",
                exc,
                exc_info=True,
            )
            log_user_error(
                self._logger,
                "Получение списка задач",
                f"Непредвиденная ошибка: {exc}",
            )
            raise

    async def get_task_by_id(
        self,
        task_id: UUID,
    ) -> Optional[TaskReadSchema]:
        """Получить задачу по ID."""
        self._logger.debug(
            "TaskController: запрос задачи по ID=%s",
            task_id,
        )
        try:
            task = await self._repository.get_by_id(task_id)
            if task is None:
                self._logger.warning(
                    "TaskController: задача с ID=%s не найдена",
                    task_id,
                )
                return None
            result = TaskReadSchema.model_validate(task)
            self._logger.debug(
                "TaskController: задача получена: %s",
                result.name,
            )
            return result
        except SQLAlchemyError as exc:
            log_user_error(
                self._logger,
                "Получение задачи по ID",
                f"ID={task_id}, Ошибка БД: {exc}",
            )
            raise
        except Exception as exc:
            self._logger.error(
                "TaskController: непредвиденная ошибка при получении задачи: %s",
                exc,
                exc_info=True,
            )
            log_user_error(
                self._logger,
                "Получение задачи по ID",
                f"ID={task_id}, Непредвиденная ошибка: {exc}",
            )
            raise

    # ------------------------------------------------------------------
    # Create operation
    # ------------------------------------------------------------------

    async def create_task(
            self,
            schema: TaskCreateSchema,
    ) -> TaskReadSchema:
        """Создать новую задачу планирования.

        Проверяет уникальность названия перед созданием.

        Args:
            schema: Схема создания задачи (:class:`TaskCreateSchema`).

        Returns:
            Созданная задача в виде :class:`TaskReadSchema`.

        Raises:
            DuplicateTaskNameError: Задача с таким названием уже существует.
            TaskDomainError: Ошибка валидации Domain-модели.
            SQLAlchemyError: Ошибка при работе с БД.
        """
        log_user_action(
            self._logger,
            "Создание задачи",
            f"Имя: {schema.name}, Период: {schema.period_type.value}",
        )
        self._logger.debug(
            "TaskController: создание задачи из схемы: %s",
            schema.model_dump(),
        )

        try:
            # Проверка уникальности названия
            if await self._repository.exists_by_name(schema.name):
                raise DuplicateTaskNameError(schema.name)

            # Преобразование Schema → Domain
            # period_start и period_end НЕ передаются — они рассчитываются
            # автоматически в PlanningTask._calculate_period_bounds
            task = PlanningTask(
                name=schema.name,
                period_type=schema.period_type,
                anchor_date=schema.anchor_date,
                employee_ids=schema.employee_ids or [],
                duty_type_ids=schema.duty_type_ids or [],
                reference_id=schema.reference_id,
            )

            # Вызов репозитория
            created_task = await self._repository.create(task)

            # Преобразование Domain → DTO
            result = TaskReadSchema.model_validate(created_task)

            log_user_action(
                self._logger,
                "Задача создана",
                f"ID: {result.id}, Имя: {result.name}",
            )
            self._logger.debug(
                "TaskController: задача успешно создана: %s",
                result.id,
            )
            return result

        except DuplicateTaskNameError:
            raise
        except TaskDomainError as exc:
            self._logger.warning(
                "TaskController: ошибка валидации Domain: %s",
                exc,
            )
            log_user_error(
                self._logger,
                "Создание задачи",
                f"Ошибка валидации: {exc}",
            )
            raise
        except SQLAlchemyError as exc:
            log_user_error(
                self._logger,
                "Создание задачи",
                f"Ошибка БД: {exc}",
            )
            raise
        except Exception as exc:
            self._logger.error(
                "TaskController: непредвиденная ошибка при создании задачи: %s",
                exc,
                exc_info=True,
            )
            log_user_error(
                self._logger,
                "Создание задачи",
                f"Непредвиденная ошибка: {exc}",
            )
            raise

    # ------------------------------------------------------------------
    # Update operation
    # ------------------------------------------------------------------
    async def update_task(
        self,
        task_id: UUID,
        schema: TaskUpdateSchema,
    ) -> TaskReadSchema:
        """Обновить существующую задачу планирования.

        Проверяет уникальность названия (если оно изменяется).

        Args:
            task_id: UUID задачи для обновления.
            schema: Схема обновления (:class:`TaskUpdateSchema`, все поля опциональны).

        Returns:
            Обновлённая задача в виде :class:`TaskReadSchema`.

        Raises:
            DuplicateTaskNameError: Задача с новым названием уже существует.
            TaskDomainError: Ошибка валидации Domain-модели.
            SQLAlchemyError: Ошибка при работе с БД.
        """
        log_user_action(
            self._logger,
            "Обновление задачи",
            f"ID: {task_id}, Изменения: {schema.model_dump(exclude_unset=True)}",
        )
        self._logger.debug(
            "TaskController: обновление задачи ID=%s, схема: %s",
            task_id,
            schema.model_dump(exclude_unset=True),
        )

        try:
            # Получение существующей задачи
            existing_task = await self._repository.get_by_id(task_id)
            if existing_task is None:
                error_msg = f"Задача с ID={task_id} не найдена"
                self._logger.warning("TaskController: %s", error_msg)
                log_user_error(self._logger, "Обновление задачи", error_msg)
                raise ValueError(error_msg)

            # Применение изменений (только переданные поля)
            update_data = schema.model_dump(exclude_unset=True)

            # Проверка уникальности названия (если оно изменяется)
            if "name" in update_data and update_data["name"] != existing_task.name:
                if await self._repository.exists_by_name(
                    update_data["name"],
                    exclude_id=task_id,
                ):
                    raise DuplicateTaskNameError(update_data["name"])

            updated_task = existing_task.model_copy(update=update_data)

            # Вызов репозитория
            saved_task = await self._repository.update(updated_task)

            # Преобразование Domain → DTO
            result = TaskReadSchema.model_validate(saved_task)

            log_user_action(
                self._logger,
                "Задача обновлена",
                f"ID: {result.id}, Имя: {result.name}",
            )
            self._logger.debug(
                "TaskController: задача успешно обновлена: %s",
                result.id,
            )
            return result

        except DuplicateTaskNameError:
            raise  # Пробрасываем без дополнительного логирования
        except TaskDomainError as exc:
            self._logger.warning(
                "TaskController: ошибка валидации Domain: %s",
                exc,
            )
            log_user_error(
                self._logger,
                "Обновление задачи",
                f"ID={task_id}, Ошибка валидации: {exc}",
            )
            raise
        except SQLAlchemyError as exc:
            log_user_error(
                self._logger,
                "Обновление задачи",
                f"ID={task_id}, Ошибка БД: {exc}",
            )
            raise
        except Exception as exc:
            self._logger.error(
                "TaskController: непредвиденная ошибка при обновлении задачи: %s",
                exc,
                exc_info=True,
            )
            log_user_error(
                self._logger,
                "Обновление задачи",
                f"ID={task_id}, Непредвиденная ошибка: {exc}",
            )
            raise

    # ------------------------------------------------------------------
    # Delete operation
    # ------------------------------------------------------------------
    async def delete_task(self, task_id: UUID) -> None:
        """Удалить задачу планирования."""
        log_user_action(
            self._logger,
            "Удаление задачи",
            f"ID: {task_id}",
        )
        self._logger.debug(
            "TaskController: удаление задачи ID=%s",
            task_id,
        )

        try:
            await self._repository.delete(task_id)
            log_user_action(
                self._logger,
                "Задача удалена",
                f"ID: {task_id}",
            )
            self._logger.debug(
                "TaskController: задача успешно удалена: %s",
                task_id,
            )
        except SQLAlchemyError as exc:
            log_user_error(
                self._logger,
                "Удаление задачи",
                f"ID={task_id}, Ошибка БД: {exc}",
            )
            raise
        except Exception as exc:
            self._logger.error(
                "TaskController: непредвиденная ошибка при удалении задачи: %s",
                exc,
                exc_info=True,
            )
            log_user_error(
                self._logger,
                "Удаление задачи",
                f"ID={task_id}, Непредвиденная ошибка: {exc}",
            )
            raise
