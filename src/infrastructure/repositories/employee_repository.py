# src/infrastructure/repositories/employee_repository.py
"""
SQLAlchemy-реализация репозитория сотрудников.

Предоставляет асинхронный доступ к БД (SQLite/PostgreSQL) через
:mod:`sqlalchemy.ext.asyncio`. Отвечает за маппинг между
Domain-объектами (:class:`Employee`) и ORM-моделями
(:class:`EmployeeORMModel`).

Ключевые особенности:
    - ``engagement_ids`` хранится как JSON-строка в БД и сериализуется
      при каждом преобразовании Domain ↔ ORM.
    - Условные UNIQUE-ограничения на ``email`` и ``tab_number`` enforced
      на уровне БД. При нарушении SQLAlchemy бросит ``IntegrityError``,
      который контроллер должен преобразовать в
      :class:`DuplicateEmployeeError`.
    - ``get_active_only`` использует индекс ``ix_employee_is_active``
      для эффективного запроса.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import delete, exists, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.application.interfaces.employee_repository_interface import (
    IEmployeeRepository,
)
from src.domain.employees.employee_model import Employee
from src.infrastructure.db.models.employee_orm_model import EmployeeORMModel


class EmployeeSQLAlchemyRepository(IEmployeeRepository):
    """SQLAlchemy-реализация репозитория сотрудников.

    Attributes:
        _session_factory: Фабрика асинхронных сессий SQLAlchemy.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """Инициализация репозитория.

        Args:
            session_factory: Фабрика асинхронных сессий SQLAlchemy.
        """
        self._session_factory = session_factory

    # ------------------------------------------------------------------
    # Маппинг Domain ↔ ORM
    # ------------------------------------------------------------------
    @staticmethod
    def _to_orm(domain: Employee) -> EmployeeORMModel:
        """Employee → EmployeeORMModel.

        Args:
            domain: Domain-объект сотрудника.

        Returns:
            ORM-модель для сохранения в БД.
        """
        return EmployeeORMModel(
            id=domain.id,
            last_name=domain.last_name,
            first_name=domain.first_name,
            middle_name=domain.middle_name,
            display_name=domain.display_name,
            position=domain.position,
            rank=domain.rank,
            tab_number=domain.tab_number,
            email=domain.email,
            phone=domain.phone,
            birth_date=domain.birth_date,
            is_active=domain.is_active,
            notes=domain.notes,
            engagement_ids=json.dumps(
                [str(uid) for uid in (domain.engagement_ids or [])]
            ),
            created_at=domain.created_at,
            updated_at=domain.updated_at,
        )

    @staticmethod
    def _to_domain(orm: EmployeeORMModel) -> Employee:
        """EmployeeORMModel → Employee.

        Args:
            orm: ORM-модель из БД.

        Returns:
            Domain-объект сотрудника.
        """
        return Employee(
            id=orm.id,
            last_name=orm.last_name,
            first_name=orm.first_name,
            middle_name=orm.middle_name,
            # display_name передаётся явно — пересчитывать не нужно,
            # т.к. он уже корректно вычислен при создании в Domain
            # и сохранён в БД.
            display_name=orm.display_name,
            position=orm.position,
            rank=orm.rank,
            tab_number=orm.tab_number,
            email=orm.email,
            phone=orm.phone,
            birth_date=orm.birth_date,
            is_active=orm.is_active,
            notes=orm.notes,
            engagement_ids=[
                UUID(uid)
                for uid in json.loads(orm.engagement_ids or "[]")
            ],
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------
    async def get_by_id(self, employee_id: UUID) -> Optional[Employee]:
        """Получить сотрудника по ID."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(EmployeeORMModel).where(
                    EmployeeORMModel.id == employee_id
                )
            )
            orm = result.scalar_one_or_none()
            return self._to_domain(orm) if orm else None

    async def get_all(self) -> List[Employee]:
        """Получить список всех сотрудников (включая архивных)."""
        async with self._session_factory() as session:
            result = await session.execute(select(EmployeeORMModel))
            orm_list = result.scalars().all()
            return [self._to_domain(orm) for orm in orm_list]

    async def get_active_only(self) -> List[Employee]:
        """Получить список только активных сотрудников.

        Использует индекс ``ix_employee_is_active`` для эффективного
        фильтра.
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(EmployeeORMModel).where(
                    EmployeeORMModel.is_active == True  # noqa: E712
                )
            )
            orm_list = result.scalars().all()
            return [self._to_domain(orm) for orm in orm_list]

    # ------------------------------------------------------------------
    # Existence checks (защита от дубликатов)
    # ------------------------------------------------------------------
    async def exists_by_email(
        self,
        email: str,
        exclude_id: Optional[UUID] = None,
    ) -> bool:
        """Проверить существование сотрудника с указанным email.

        Использует эффективный запрос ``EXISTS`` вместо загрузки записей.
        Учитывает, что в БД email хранится в lowercase (нормализация
        в :class:`EmployeeCreateSchema`).
        """
        if not email:
            return False

        async with self._session_factory() as session:
            conditions = [EmployeeORMModel.email == email]
            if exclude_id is not None:
                conditions.append(EmployeeORMModel.id != exclude_id)

            stmt = select(exists().where(*conditions))
            result = await session.execute(stmt)
            return bool(result.scalar_one())

    async def exists_by_tab_number(
        self,
        tab_number: str,
        exclude_id: Optional[UUID] = None,
    ) -> bool:
        """Проверить существование сотрудника с указанным табельным номером.

        Учитывает, что табельный номер в БД хранится в uppercase
        (нормализация в :class:`EmployeeCreateSchema`).
        """
        if not tab_number:
            return False

        async with self._session_factory() as session:
            conditions = [EmployeeORMModel.tab_number == tab_number]
            if exclude_id is not None:
                conditions.append(EmployeeORMModel.id != exclude_id)

            stmt = select(exists().where(*conditions))
            result = await session.execute(stmt)
            return bool(result.scalar_one())

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------
    async def create(self, employee: Employee) -> Employee:
        """Создать нового сотрудника.

        При нарушении UNIQUE-ограничений (email/tab_number) SQLAlchemy
        бросит :class:`sqlalchemy.exc.IntegrityError` — контроллер должен
        перехватить и преобразовать в :class:`DuplicateEmployeeError`.
        """
        async with self._session_factory() as session:
            orm = self._to_orm(employee)
            session.add(orm)
            await session.commit()
            await session.refresh(orm)
            return self._to_domain(orm)

    async def update(self, employee: Employee) -> Employee:
        """Обновить существующего сотрудника.

        Полностью заменяет все поля ORM из Domain-объекта (partial-update
        выполняется контроллером через ``model_copy(update=...)``).
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(EmployeeORMModel).where(
                    EmployeeORMModel.id == employee.id
                )
            )
            orm = result.scalar_one()

            # Полная замена всех полей
            orm.last_name = employee.last_name
            orm.first_name = employee.first_name
            orm.middle_name = employee.middle_name
            orm.display_name = employee.display_name
            orm.position = employee.position
            orm.rank = employee.rank
            orm.tab_number = employee.tab_number
            orm.email = employee.email
            orm.phone = employee.phone
            orm.birth_date = employee.birth_date
            orm.is_active = employee.is_active
            orm.notes = employee.notes
            orm.engagement_ids = json.dumps(
                [str(uid) for uid in (employee.engagement_ids or [])]
            )
            orm.updated_at = datetime.utcnow()

            await session.commit()
            await session.refresh(orm)
            return self._to_domain(orm)

    async def delete(self, employee_id: UUID) -> None:
        """Физически удалить сотрудника из БД.

        **Не выполняет** CASCADE-удаление из
        :class:`PlanningTask.employee_ids` — это ответственность
        :class:`ITaskRepository.remove_employee_from_all_tasks`.
        """
        async with self._session_factory() as session:
            await session.execute(
                delete(EmployeeORMModel).where(
                    EmployeeORMModel.id == employee_id
                )
            )
            await session.commit()

