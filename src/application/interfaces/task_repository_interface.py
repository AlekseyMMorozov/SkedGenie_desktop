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
        """Получить задачу по ID.

        Args:
            task_id: UUID задачи.

        Returns:
            :class:`PlanningTask` или ``None``, если не найдена.
        """
        ...

    @abstractmethod
    async def get_all(self) -> List[PlanningTask]:
        """Получить список всех задач планирования.

        Returns:
            Список :class:`PlanningTask` (может быть пустым).
        """
        ...

    @abstractmethod
    async def exists_by_name(
        self,
        name: str,
        exclude_id: UUID | None = None,
    ) -> bool:
        """Проверить существование задачи с указанным названием.

        Args:
            name: Название задачи для проверки.
            exclude_id: UUID задачи, которую нужно исключить из проверки
                (используется при обновлении).

        Returns:
            ``True``, если задача с таким названием существует.
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

    # ------------------------------------------------------------------
    # Операции со связями "задача ↔ сотрудник"
    # ------------------------------------------------------------------
    @abstractmethod
    async def count_tasks_using_employee(self, employee_id: UUID) -> int:
        """Подсчитать количество задач, в которых указан сотрудник.

        Используется для предупреждения пользователя перед удалением
        сотрудника из БД (CASCADE-удаление из всех задач).

        Args:
            employee_id: UUID сотрудника.

        Returns:
            Количество задач, содержащих ``employee_id`` в ``employee_ids``.
        """
        ...

    @abstractmethod
    async def remove_employee_from_all_tasks(self, employee_id: UUID) -> int:
        """Удалить сотрудника из всех задач, где он упомянут.

        Выполняется CASCADE при удалении сотрудника через меню "Сотрудники".
        Для каждой затронутой задачи обновляется ``updated_at``.

        Args:
            employee_id: UUID сотрудника.

        Returns:
            Количество задач, в которых сотрудник был удалён.
        """
        ...

    @abstractmethod
    async def remove_employee_from_task(
        self,
        employee_id: UUID,
        task_id: UUID,
    ) -> bool:
        """Удалить сотрудника из конкретной задачи.

        Используется при удалении через меню "Задачи" или "График" —
        сотрудник остаётся в БД, но убирается из списка этой задачи.

        Args:
            employee_id: UUID сотрудника.
            task_id: UUID задачи.

        Returns:
            ``True``, если сотрудник был в задаче и удалён;
            ``False``, если его там не было.

        Raises:
            ValueError: Если задача с указанным ID не найдена.
        """
        ...
