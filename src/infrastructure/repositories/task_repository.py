# src/infrastructure/repositories/task_repository.py
"""
SQLAlchemy-реализация репозитория задач планирования.

Предоставляет асинхронный доступ к БД (SQLite/PostgreSQL) через
:mod:`sqlalchemy.ext.asyncio`. Отвечает за маппинг между
Domain-объектами (:class:`PlanningTask`) и ORM-моделями (:class:`TaskORMModel`).
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from sqlalchemy import select, delete, exists
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
        """Domain → ORM. Поля: anchor_date↔reference_date, duty_type_ids↔engagement_ids."""
        return TaskORMModel(
            id=domain.id,
            name=domain.name,
            period_type=domain.period_type.value,
            reference_date=domain.anchor_date,  # anchor_date → reference_date
            period_start=domain.period_start,
            period_end=domain.period_end,
            employee_ids=json.dumps([str(uid) for uid in (domain.employee_ids or [])]),
            engagement_ids=json.dumps([str(eid) for eid in (domain.duty_type_ids or [])]),
            # duty_type_ids → engagement_ids
            reference_id=domain.reference_id,  # ← НОВОЕ
            created_at=domain.created_at,
            updated_at=domain.updated_at,
        )

    @staticmethod
    def _to_domain(orm: TaskORMModel) -> PlanningTask:
        """ORM → Domain. Обратный маппинг имён полей."""
        return PlanningTask(
            id=orm.id,
            name=orm.name,
            period_type=PeriodType(orm.period_type),
            anchor_date=orm.reference_date,  # reference_date → anchor_date
            period_start=orm.period_start,
            period_end=orm.period_end,
            employee_ids=[UUID(uid) for uid in json.loads(orm.employee_ids or "[]")],
            duty_type_ids=[UUID(eid) for eid in json.loads(orm.engagement_ids or "[]")],
            # engagement_ids → duty_type_ids
            reference_id=orm.reference_id,  # ← НОВОЕ
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )

    # ------------------------------------------------------------------
    # CRUD operations
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
        """Проверить существование задачи с указанным названием.

        Использует эффективный запрос ``EXISTS`` вместо загрузки всех записей.
        """
        async with self._session_factory() as session:
            stmt = select(exists().where(TaskORMModel.name == name))
            if exclude_id is not None:
                stmt = select(
                    exists().where(
                        TaskORMModel.name == name,
                        TaskORMModel.id != exclude_id,
                    )
                )
            result = await session.execute(stmt)
            return result.scalar_one()

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

            # Обновление полей (с правильным маппингом имён)
            orm.name = task.name
            orm.period_type = task.period_type.value
            orm.reference_date = task.anchor_date  # ← ИСПРАВЛЕНО: anchor_date, не reference_date
            orm.period_start = task.period_start
            orm.period_end = task.period_end
            orm.employee_ids = json.dumps([str(uid) for uid in (task.employee_ids or [])])  # ← защита от None
            orm.engagement_ids = json.dumps([str(eid) for eid in (task.duty_type_ids or [])])  # ← ИСПРАВЛЕНО: duty_type_ids
            orm.reference_id = task.reference_id  # ← ДОБАВЛЕНО: новое поле
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
