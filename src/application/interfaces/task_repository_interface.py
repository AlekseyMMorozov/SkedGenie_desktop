# src/application/interfaces/task_repository_interface.py
"""
Интерфейс репозитория для работы с задачами планирования.

Определяет контракт для CRUD-операций над :class:`PlanningTask`,
который должен быть реализован в Infrastructure-слое (например,
:class:`TaskSQLAlchemyRepository`).

Application-слой зависит только от этого интерфейса, не от конкретной
реализации (принцип инверсии зависимостей).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.tasks.planning_task_model import PlanningTask


class ITaskRepository(ABC):
    """Абстрактный интерфейс репозитория задач планирования.

    Все методы асинхронные для поддержки неблокирующих операций с БД.
    """

    @abstractmethod
    async def get_by_id(self, task_id: UUID) -> PlanningTask | None:
        """Получить задачу по ID.

        Args:
            task_id: UUID задачи.

        Returns:
            :class:`PlanningTask` или ``None``, если не найдена.
        """
        ...

    @abstractmethod
    async def get_all(self) -> list[PlanningTask]:
        """Получить список всех задач планирования.

        Returns:
            Список :class:`PlanningTask` (может быть пустым).
        """
        ...

    @abstractmethod
    async def exists_by_name(self, name: str, exclude_id: UUID | None = None) -> bool:
        """Проверить существование задачи с указанным названием.

        Args:
            name: Название задачи для проверки.
            exclude_id: UUID задачи, которую нужно исключить из проверки
                (используется при обновлении, чтобы задача не конфликтовала сама с собой).

        Returns:
            ``True``, если задача с таким названием существует, иначе ``False``.
        """
        ...

    @abstractmethod
    async def create(self, task: PlanningTask) -> PlanningTask:
        """Создать новую задачу планирования.

        Args:
            task: Domain-объект задачи.

        Returns:
            Созданная задача с присвоенным ID.
        """
        ...

    @abstractmethod
    async def update(self, task: PlanningTask) -> PlanningTask:
        """Обновить существующую задачу планирования.

        Args:
            task: Domain-объект задачи с обновлёнными данными.

        Returns:
            Обновлённая задача.
        """
        ...

    @abstractmethod
    async def delete(self, task_id: UUID) -> None:
        """Удалить задачу планирования по ID.

        Args:
            task_id: UUID задачи для удаления.
        """
        ...
