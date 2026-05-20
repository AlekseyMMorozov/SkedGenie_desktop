# src/infrastructure/repositories/task_repository.py
"""Реализация репозитория задач планирования на SQLAlchemy 2.0 Async."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select, delete

from src.application.interfaces.task_repository_interface import ITaskRepository
from src.domain.tasks.planning_task_model import PlanningTask, PeriodType
from src.infrastructure.db.models.task_orm_model import TaskORMModel
from src.infrastructure.db.async_database_session import get_session_factory


class TaskSQLAlchemyRepository(ITaskRepository):
    """Асинхронный репозиторий для CRUD-операций над задачами планирования.

    Выполняет двусторонний маппинг между доменной Pydantic-моделью и SQLAlchemy ORM.
    Использует глобальную фабрику сессий для изоляции транзакций.
    """

    @staticmethod
    def _to_orm(domain: PlanningTask) -> TaskORMModel:
        """Преобразует доменную сущность в ORM-объект для сохранения в БД."""
        return TaskORMModel(
            id=str(domain.id),
            name=domain.name,
            period_type=domain.period_type.value,
            anchor_date=domain.anchor_date,
            custom_start_date=domain.custom_start_date,
            custom_end_date=domain.custom_end_date,
            start_date=domain.start_date,
            end_date=domain.end_date,
            employee_ids=[str(uid) for uid in domain.employee_ids],
            duty_type_ids=[str(uid) for uid in domain.duty_type_ids],
            created_at=domain.created_at,
            updated_at=domain.updated_at,
        )

    @staticmethod
    def _to_domain(orm: TaskORMModel) -> PlanningTask:
        """Преобразует ORM-объект из БД в доменную сущность."""
        return PlanningTask(
            id=UUID(orm.id),
            name=orm.name,
            period_type=PeriodType(orm.period_type),
            anchor_date=orm.anchor_date,
            custom_start_date=orm.custom_start_date,
            custom_end_date=orm.custom_end_date,
            start_date=orm.start_date,
            end_date=orm.end_date,
            employee_ids=[UUID(uid) for uid in orm.employee_ids],
            duty_type_ids=[UUID(uid) for uid in orm.duty_type_ids],
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )

    async def get_by_id(self, task_id: UUID) -> Optional[PlanningTask]:
        async with get_session_factory()() as session:
            stmt = select(TaskORMModel).where(TaskORMModel.id == str(task_id))
            result = await session.execute(stmt)
            orm = result.scalar_one_or_none()
            return self._to_domain(orm) if orm else None

    async def get_all(self) -> list[PlanningTask]:
        async with get_session_factory()() as session:
            stmt = select(TaskORMModel).order_by(TaskORMModel.created_at.desc())
            result = await session.execute(stmt)
            return [self._to_domain(row) for row in result.scalars().all()]

    async def create(self, task: PlanningTask) -> PlanningTask:
        async with get_session_factory()() as session:
            orm = self._to_orm(task)
            session.add(orm)
            await session.commit()
            await session.refresh(orm)
            return self._to_domain(orm)

    async def update(self, task: PlanningTask) -> PlanningTask:
        async with get_session_factory()() as session:
            orm = await session.get(TaskORMModel, str(task.id))
            if orm is None:
                raise ValueError(f"Задача с ID {task.id} не найдена в хранилище")

            # Применяем изменения из доменной модели к ORM-объекту
            for key, value in task.model_dump(exclude={'id', 'created_at'}).items():
                if key == 'period_type':
                    value = value.value
                elif key in ('employee_ids', 'duty_type_ids'):
                    value = [str(uid) for uid in value]
                setattr(orm, key, value)

            orm.updated_at = datetime.now()
            await session.commit()
            await session.refresh(orm)
            return self._to_domain(orm)

    async def delete(self, task_id: UUID) -> None:
        async with get_session_factory()() as session:
            stmt = delete(TaskORMModel).where(TaskORMModel.id == str(task_id))
            await session.execute(stmt)
            await session.commit()

