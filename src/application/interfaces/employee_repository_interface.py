# src/application/interfaces/employee_repository_interface.py
"""
Интерфейс репозитория для работы с сотрудниками.

Определяет контракт для CRUD-операций над :class:`Employee`,
который должен быть реализован в Infrastructure-слое (например,
:class:`EmployeeSQLAlchemyRepository`).

Application-слой зависит только от этого интерфейса, не от конкретной
реализации (принцип инверсии зависимостей).

Примечания по архитектуре:
    - ``get_all()`` возвращает всех сотрудников, включая архивных
      (``is_active=False``). Для получения только активных используйте
      :meth:`get_active_only`.
    - ``exists_by_email`` / ``exists_by_tab_number`` принимают
      ``exclude_id`` для поддержки проверки дубликатов при обновлении
      (сотрудник не должен конфликтовать сам с собой).
    - CASCADE-удаление сотрудника из :class:`PlanningTask.employee_ids`
      реализуется в :class:`ITaskRepository` (метод
      ``remove_employee_from_all_tasks``), а не здесь — это соответствует
      принципу единственной ответственности (SRP): репозиторий сотрудников
      не должен знать о таблице задач.
    - Связи с шаблонами задействований (``engagement_template_ids``)
      хранятся как JSON-поле внутри сотрудника. Управление связями
      реализовано через точечные методы (add/remove/count).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from src.domain.employees.employee_model import Employee


class IEmployeeRepository(ABC):
    """Абстрактный интерфейс репозитория сотрудников.

    Все методы асинхронные для поддержки неблокирующих операций с БД.
    """

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------
    @abstractmethod
    async def get_by_id(self, employee_id: UUID) -> Optional[Employee]:
        """Получить сотрудника по ID.

        Args:
            employee_id: UUID сотрудника.

        Returns:
            :class:`Employee` или ``None``, если не найден.
        """
        ...

    @abstractmethod
    async def get_all(self) -> List[Employee]:
        """Получить список всех сотрудников (включая архивных).

        Returns:
            Список :class:`Employee` (может быть пустым).
            Порядок не гарантируется — сортировка выполняется в Presentation.
        """
        ...

    @abstractmethod
    async def get_active_only(self) -> List[Employee]:
        """Получить список только активных сотрудников.

        Используется в модулях планирования для отображения доступных
        сотрудников (архивные не участвуют в планировании).

        Returns:
            Список активных :class:`Employee`.
        """
        ...

    # ------------------------------------------------------------------
    # Existence checks (для защиты от дубликатов)
    # ------------------------------------------------------------------
    @abstractmethod
    async def exists_by_email(
        self,
        email: str,
        exclude_id: Optional[UUID] = None,
    ) -> bool:
        """Проверить существование сотрудника с указанным email.

        Args:
            email: Email для проверки (уже нормализован: lowercase + strip).
            exclude_id: UUID сотрудника, которого нужно исключить из проверки
                (используется при обновлении, чтобы сотрудник не конфликтовал
                сам с собой).

        Returns:
            ``True``, если сотрудник с таким email существует.
        """
        ...

    @abstractmethod
    async def exists_by_tab_number(
        self,
        tab_number: str,
        exclude_id: Optional[UUID] = None,
    ) -> bool:
        """Проверить существование сотрудника с указанным табельным номером.

        Args:
            tab_number: Табельный номер для проверки (уже нормализован:
                uppercase + strip).
            exclude_id: UUID сотрудника, которого нужно исключить из проверки.

        Returns:
            ``True``, если сотрудник с таким табельным номером существует.
        """
        ...

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------
    @abstractmethod
    async def create(self, employee: Employee) -> Employee:
        """Создать нового сотрудника.

        Args:
            employee: Domain-объект сотрудника.

        Returns:
            Созданный сотрудник с присвоенным ID (если не был задан).

        Raises:
            sqlalchemy.exc.IntegrityError: При нарушении UNIQUE-ограничений
                (email / tab_number). Контроллер должен перехватить и
                преобразовать в :class:`DuplicateEmployeeError`.
        """
        ...

    @abstractmethod
    async def update(self, employee: Employee) -> Employee:
        """Обновить существующего сотрудника.

        Args:
            employee: Domain-объект сотрудника с обновлёнными данными.
                ID должен совпадать с существующей записью.

        Returns:
            Обновлённый сотрудник.

        Raises:
            sqlalchemy.exc.IntegrityError: При нарушении UNIQUE-ограничений.
        """
        ...

    @abstractmethod
    async def delete(self, employee_id: UUID) -> None:
        """Физически удалить сотрудника из БД.

        **Важно:** этот метод НЕ выполняет CASCADE-удаление из
        :class:`PlanningTask.employee_ids`. Перед вызовом контроллер
        должен:
            1. Проверить использование через
               :meth:`ITaskRepository.count_tasks_using_employee`.
            2. При использовании — запросить подтверждение у пользователя.
            3. Вызвать :meth:`ITaskRepository.remove_employee_from_all_tasks`
               для очистки ссылок.
            4. Только после этого вызвать этот метод.

        Args:
            employee_id: UUID сотрудника для удаления.
        """
        ...

    # ------------------------------------------------------------------
    # Operations on employee ↔ engagement template links
    # ------------------------------------------------------------------
    @abstractmethod
    async def add_engagement_template(
        self,
        employee_id: UUID,
        template_id: UUID,
    ) -> bool:
        """Добавить шаблон задействования сотруднику.

        Args:
            employee_id: UUID сотрудника.
            template_id: UUID шаблона задействования.

        Returns:
            ``True``, если шаблон был успешно добавлен;
            ``False``, если он уже был в списке.

        Raises:
            ValueError: Если сотрудник с указанным ID не найден.
        """
        ...

    @abstractmethod
    async def remove_engagement_template(
        self,
        employee_id: UUID,
        template_id: UUID,
    ) -> bool:
        """Удалить шаблон задействования у сотрудника.

        Args:
            employee_id: UUID сотрудника.
            template_id: UUID шаблона задействования.

        Returns:
            ``True``, если шаблон был успешно удалён;
            ``False``, если его не было в списке.

        Raises:
            ValueError: Если сотрудник с указанным ID не найден.
        """
        ...

    @abstractmethod
    async def count_employees_using_engagement_template(
        self,
        template_id: UUID,
    ) -> int:
        """Подсчитать количество сотрудников, использующих данный шаблон.

        Используется для защиты от удаления шаблона, который активно
        используется сотрудниками (аналог
        :meth:`ITaskRepository.count_tasks_using_employee`).

        Args:
            template_id: UUID шаблона задействования.

        Returns:
            Количество сотрудников, у которых данный шаблон есть в
            ``engagement_template_ids``.
        """
        ...

    @abstractmethod
    async def remove_engagement_template_from_all_employees(
        self,
        template_id: UUID,
    ) -> int:
        """Удалить шаблон задействования у всех сотрудников (каскадно).

        Вызывается при удалении самого шаблона
        (:class:`EngagementTemplate`) для очистки ссылок во всех
        записях сотрудников.

        Args:
            template_id: UUID удаляемого шаблона.

        Returns:
            Количество затронутых записей сотрудников.
        """
        ...

    @abstractmethod
    async def get_employees_by_engagement_template(
        self,
        template_id: UUID,
    ) -> List[Employee]:
        """Получить всех сотрудников, у которых есть данный шаблон.

        Args:
            template_id: UUID шаблона задействования.

        Returns:
            Список :class:`Employee`, содержащих ``template_id``
            в своём ``engagement_template_ids``.
        """
        ...
