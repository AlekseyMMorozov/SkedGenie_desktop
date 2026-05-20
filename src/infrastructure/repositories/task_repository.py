"""
Файл: src/infrastructure/repositories/task_repository.py
Описание: Реализация репозитория для PlanningTask на SQLAlchemy 2.0 Async.
Архитектура: Infrastructure слой. Зависит от Application интерфейсов и ORM-моделей.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.application.interfaces.task_repository_interface import ITaskRepository
from src.domain.tasks.planning_task_model import PlanningTask, PeriodType
from src.infrastructure.db.models.task_orm_model import TaskORMModel


class TaskSQLAlchemyRepository(ITaskRepository):
    """Асинхронный репозиторий для работы с задачами планирования через SQLAlchemy."""

    def __init__(self, session_factory: async_sessionmaker):
        """Инициализация с фабрикой сессий (внедряется из Composition Root)."""
        self._session_factory = session_factory

    @staticmethod
    def _to_orm(domain: PlanningTask) -> TaskORMModel:
        """Конвертация доменной модели в ORM-модель."""
        return TaskORMModel(
            id=domain.id,
            name=domain.name,
            period_type=domain.period_type.value,
            period_start=domain.period_start,
            period_end=domain.period_end,
            reference_id=domain.reference_id,
            created_at=domain.created_at,
            updated_at=domain.updated_at,
        )

    @staticmethod
    def _to_domain(orm: TaskORMModel) -> PlanningTask:
        """Конвертация ORM-модели в доменную модель."""
        return PlanningTask(
            id=orm.id,
            name=orm.name,
            period_type=PeriodType(orm.period_type),
            period_start=orm.period_start,
            period_end=orm.period_end,
            reference_id=orm.reference_id,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )

    async def get_by_id(self, task_id: UUID) -> Optional[PlanningTask]:
        """Получить задачу по ID."""
        async with self._session_factory() as session:
            result = await session.get(TaskORMModel, task_id)
            return self._to_domain(result) if result else None

    async def get_all(self) -> List[PlanningTask]:
        """Получить все задачи, отсортированные по дате создания."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(TaskORMModel).order_by(TaskORMModel.created_at.desc())
            )
            return [self._to_domain(orm) for orm in result.scalars().all()]

    async def create(self, task: PlanningTask) -> PlanningTask:
        """Создать новую задачу."""
        async with self._session_factory() as session:
            orm_task = self._to_orm(task)
            session.add(orm_task)
            await session.commit()
            await session.refresh(orm_task)
            return self._to_domain(orm_task)

    async def update(self, task: PlanningTask) -> PlanningTask:
        """Обновить существующую задачу."""
        async with self._session_factory() as session:
            orm_task = self._to_orm(task)
            orm_task.updated_at = datetime.utcnow()
            await session.merge(orm_task)
            await session.commit()
            await session.refresh(orm_task)
            return self._to_domain(orm_task)

    async def delete(self, task_id: UUID) -> None:
        """Удалить задачу по ID."""
        async with self._session_factory() as session:
            await session.execute(delete(TaskORMModel).where(TaskORMModel.id == task_id))
            await session.commit()

