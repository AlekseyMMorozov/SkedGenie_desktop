# src/infrastructure/repositories/task_repository.py
"""
SQLAlchemy-реализация репозитория задач планирования.

Предоставляет асинхронный доступ к БД (SQLite/PostgreSQL) через
:mod:`sqlalchemy.ext.asyncio`. Отвечает за маппинг между
Domain-объектами (:class:`PlanningTask`) и ORM-моделями (:class:`TaskORMModel`).

Примечание по связям с сотрудниками:
    Поле ``employee_ids`` хранится в БД как JSON-строка. Поскольку нет
    кросс-диалектного SQL-оператора "array contains" для JSON, поиск и
    модификация связей выполняются через загрузку записей и обработку
    в Python. Это надёжно и готово к миграции на PostgreSQL (где можно
    будет оптимизировать через ``jsonb @>``).
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import delete, exists, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.application.interfaces.task_repository_interface import ITaskRepository
from src.domain.tasks.planning_task_model import PlanningTask, PeriodType
from src.infrastructure.db.models.task_orm_model import TaskORMModel


class TaskSQLAlchemyRepository(ITaskRepository):
    """SQLAlchemy-реализация репозитория задач планирования.

    Attributes:
        _session_factory: Фабрика асинхронных сессий SQLAlchemy.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        """Инициализация репозитория.

        Args:
            session_factory: Фабрика асинхронных сессий SQLAlchemy.
        """
        self._session_factory = session_factory

    # ------------------------------------------------------------------
    # Маппинг Domain ↔ ORM
    # ------------------------------------------------------------------
    @staticmethod
    def _to_orm(domain: PlanningTask) -> TaskORMModel:
        """Domain → ORM."""
        return TaskORMModel(
            id=domain.id,
            name=domain.name,
            period_type=domain.period_type.value,
            reference_date=domain.anchor_date,
            period_start=domain.period_start,
            period_end=domain.period_end,
            employee_ids=json.dumps(
                [str(uid) for uid in (domain.employee_ids or [])]
            ),
            engagement_ids=json.dumps(
                [str(eid) for eid in (domain.duty_type_ids or [])]
            ),
            reference_id=domain.reference_id,
            created_at=domain.created_at,
            updated_at=domain.updated_at,
        )

    @staticmethod
    def _to_domain(orm: TaskORMModel) -> PlanningTask:
        """ORM → Domain."""
        return PlanningTask(
            id=orm.id,
            name=orm.name,
            period_type=PeriodType(orm.period_type),
            anchor_date=orm.reference_date,
            period_start=orm.period_start,
            period_end=orm.period_end,
            employee_ids=[
                UUID(uid) for uid in json.loads(orm.employee_ids or "[]")
            ],
            duty_type_ids=[
                UUID(eid) for eid in json.loads(orm.engagement_ids or "[]")
            ],
            reference_id=orm.reference_id,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )

    # ------------------------------------------------------------------
    # Helpers для работы со связями "задача ↔ сотрудник"
    # ------------------------------------------------------------------
    @staticmethod
    def _orm_contains_employee(orm: TaskORMModel, employee_id: UUID) -> bool:
        """Проверяет, содержит ли задача UUID сотрудника в ``employee_ids``."""
        try:
            ids: list[str] = json.loads(orm.employee_ids or "[]")
        except (json.JSONDecodeError, TypeError):
            return False
        target = str(employee_id)
        return target in ids

    @staticmethod
    def _remove_employee_from_orm(
        orm: TaskORMModel,
        employee_id: UUID,
    ) -> bool:
        """Удаляет UUID сотрудника из JSON-поля ``employee_ids`` ORM-объекта.

        Args:
            orm: ORM-модель задачи (модифицируется на месте).
            employee_id: UUID сотрудника.

        Returns:
            ``True``, если сотрудник был в списке и удалён;
            ``False``, если его там не было.
        """
        try:
            ids: list[str] = json.loads(orm.employee_ids or "[]")
        except (json.JSONDecodeError, TypeError):
            return False

        target = str(employee_id)
        if target not in ids:
            return False

        ids = [uid for uid in ids if uid != target]
        orm.employee_ids = json.dumps(ids)
        orm.updated_at = datetime.utcnow()
        return True

    # ------------------------------------------------------------------
    # Базовые CRUD-операции
    # ------------------------------------------------------------------
    async def get_by_id(self, task_id: UUID) -> Optional[PlanningTask]:
        """Получить задачу по ID."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(TaskORMModel).where(TaskORMModel.id == task_id)
            )
            orm = result.scalar_one_or_none()
            return self._to_domain(orm) if orm else None

    async def get_all(self) -> List[PlanningTask]:
        """Получить список всех задач."""
        async with self._session_factory() as session:
            result = await session.execute(select(TaskORMModel))
            orm_list = result.scalars().all()
            return [self._to_domain(orm) for orm in orm_list]

    async def exists_by_name(
        self,
        name: str,
        exclude_id: UUID | None = None,
    ) -> bool:
        """Проверить существование задачи с указанным названием."""
        async with self._session_factory() as session:
            conditions = [TaskORMModel.name == name]
            if exclude_id is not None:
                conditions.append(TaskORMModel.id != exclude_id)

            stmt = select(exists().where(*conditions))
            result = await session.execute(stmt)
            return bool(result.scalar_one())

    async def create(self, task: PlanningTask) -> PlanningTask:
        """Создать новую задачу."""
        async with self._session_factory() as session:
            orm = self._to_orm(task)
            session.add(orm)
            await session.commit()
            await session.refresh(orm)
            return self._to_domain(orm)

    async def update(self, task: PlanningTask) -> PlanningTask:
        """Обновить существующую задачу."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(TaskORMModel).where(TaskORMModel.id == task.id)
            )
            orm = result.scalar_one()

            orm.name = task.name
            orm.period_type = task.period_type.value
            orm.reference_date = task.anchor_date
            orm.period_start = task.period_start
            orm.period_end = task.period_end
            orm.employee_ids = json.dumps(
                [str(uid) for uid in (task.employee_ids or [])]
            )
            orm.engagement_ids = json.dumps(
                [str(eid) for eid in (task.duty_type_ids or [])]
            )
            orm.reference_id = task.reference_id
            orm.updated_at = datetime.utcnow()

            await session.commit()
            await session.refresh(orm)
            return self._to_domain(orm)

    async def delete(self, task_id: UUID) -> None:
        """Удалить задачу по ID."""
        async with self._session_factory() as session:
            await session.execute(
                delete(TaskORMModel).where(TaskORMModel.id == task_id)
            )
            await session.commit()

    # ------------------------------------------------------------------
    # Операции со связями "задача ↔ сотрудник"
    # ------------------------------------------------------------------
    async def count_tasks_using_employee(self, employee_id: UUID) -> int:
        """Подсчитать количество задач, использующих сотрудника.

        Реализовано через загрузку всех задач и фильтрацию в Python —
        это надёжно и не зависит от диалекта БД. Оптимизация через
        SQL-операторы (``jsonb @>`` в PostgreSQL) может быть добавлена
        позже при необходимости.
        """
        async with self._session_factory() as session:
            result = await session.execute(select(TaskORMModel))
            orm_list = result.scalars().all()

            count = sum(
                1 for orm in orm_list
                if self._orm_contains_employee(orm, employee_id)
            )
            return count

    async def remove_employee_from_all_tasks(self, employee_id: UUID) -> int:
        """Удалить сотрудника из всех задач, где он упомянут."""
        async with self._session_factory() as session:
            result = await session.execute(select(TaskORMModel))
            orm_list = result.scalars().all()

            removed_count = 0
            for orm in orm_list:
                if self._remove_employee_from_orm(orm, employee_id):
                    removed_count += 1

            if removed_count > 0:
                await session.commit()

            return removed_count

    async def remove_employee_from_task(
        self,
        employee_id: UUID,
        task_id: UUID,
    ) -> bool:
        """Удалить сотрудника из конкретной задачи."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(TaskORMModel).where(TaskORMModel.id == task_id)
            )
            orm = result.scalar_one_or_none()

            if orm is None:
                raise ValueError(
                    f"Задача с ID={task_id} не найдена"
                )

            removed = self._remove_employee_from_orm(orm, employee_id)
            if removed:
                await session.commit()
            return removed
