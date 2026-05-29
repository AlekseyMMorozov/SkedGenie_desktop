# src/application/interfaces/task_repository_interface.py
"""
Интерфейс репозитория для работы с задачами планирования.

Определяет контракт для CRUD-операций над :class:`PlanningTask`,
который должен быть реализован в Infrastructure-слое (например,
:class:`TaskSQLAlchemyRepository`).

Application-слой зависит только от этого интерфейса, не от конкретной
реализации (принцип инверсии зависимостей).

Примечание по связям с сотрудниками:
    В :class:`PlanningTask` поле ``employee_ids`` хранит список UUID
    сотрудников, закреплённых за задачей. При удалении сотрудника
    через меню "Сотрудники" необходим CASCADE-обход всех задач для
    очистки ссылок. Соответствующие методы:
        - :meth:`count_tasks_using_employee` — подсчёт задач
        - :meth:`remove_employee_from_all_tasks` — массовое удаление
        - :meth:`remove_employee_from_task` — точечное удаление
        - :meth:`add_employee_to_task` — точечное добавление
    Это реализация SRP: репозиторий задач отвечает за свои данные,
    репозиторий сотрудников — за свои.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List
from uuid import UUID

from src.domain.tasks.planning_task_model import PlanningTask


class ITaskRepository(ABC):
    """Абстрактный интерфейс репозитория задач планирования.

    Все методы асинхронные для поддержки неблокирующих операций с БД.
    """

    # ------------------------------------------------------------------
    # Базовые CRUD-операции
    # ------------------------------------------------------------------
    @abstractmethod
    async def get_by_id(self, task_id: UUID) -> PlanningTask | None:
        """Получить задачу по ID."""
        ...

    @abstractmethod
    async def get_all(self) -> List[PlanningTask]:
        """Получить список всех задач планирования."""
        ...

    @abstractmethod
    async def exists_by_name(
        self,
        name: str,
        exclude_id: UUID | None = None,
    ) -> bool:
        """Проверить существование задачи с указанным названием."""
        ...

    @abstractmethod
    async def create(self, task: PlanningTask) -> PlanningTask:
        """Создать новую задачу планирования."""
        ...

    @abstractmethod
    async def update(self, task: PlanningTask) -> PlanningTask:
        """Обновить существующую задачу планирования."""
        ...

    @abstractmethod
    async def delete(self, task_id: UUID) -> None:
        """Удалить задачу планирования по ID."""
        ...

    # ------------------------------------------------------------------
    # Операции со связями "задача ↔ сотрудник"
    # ------------------------------------------------------------------
    @abstractmethod
    async def count_tasks_using_employee(self, employee_id: UUID) -> int:
        """Подсчитать количество задач, в которых указан сотрудник."""
        ...

    @abstractmethod
    async def remove_employee_from_all_tasks(self, employee_id: UUID) -> int:
        """Удалить сотрудника из всех задач, где он упомянут."""
        ...

    @abstractmethod
    async def remove_employee_from_task(
        self,
        employee_id: UUID,
        task_id: UUID,
    ) -> bool:
        """Удалить сотрудника из конкретной задачи."""
        ...

    @abstractmethod
    async def add_employee_to_task(
        self,
        employee_id: UUID,
        task_id: UUID,
    ) -> bool:
        """Добавить сотрудника в конкретную задачу.

        Args:
            employee_id: UUID сотрудника.
            task_id: UUID задачи.

        Returns:
            ``True``, если сотрудник был успешно добавлен;
            ``False``, если он уже был в задаче.

        Raises:
            ValueError: Если задача с указанным ID не найдена.
        """
        ...

    @abstractmethod
    async def get_tasks_by_employee(self, employee_id: UUID) -> List[PlanningTask]:
        """Получить список задач, в которых участвует сотрудник."""
        ...
