# src/infrastructure/repositories/engagement_repository.py
"""SQLAlchemy-репозиторий экземпляров задействований."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.application.interfaces.engagement_repository_interface import IEngagementRepository
from src.domain.engagements.engagement_model import Engagement
from src.infrastructure.db.models.engagement_orm_model import EngagementORMModel, engagement_tasks


class EngagementSQLAlchemyRepository(IEngagementRepository):
    """Реализация репозитория задействований с поддержкой M2M связи с задачами."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    @staticmethod
    def _to_orm(domain: Engagement) -> EngagementORMModel:
        return EngagementORMModel(
            id=domain.id,
            employee_id=domain.employee_id,
            template_id=domain.template_id,
            start_at=domain.start_at,
            end_at=domain.end_at,
            short_name_override=domain.short_name_override,
            color_override=domain.color_override,
            comment=domain.comment,
        )

    @staticmethod
    def _to_domain(orm: EngagementORMModel, task_ids: List[UUID]) -> Engagement:
        return Engagement(
            id=orm.id,
            employee_id=orm.employee_id,
            template_id=orm.template_id,
            task_ids=task_ids,
            start_at=orm.start_at,
            end_at=orm.end_at,
            short_name_override=orm.short_name_override,
            color_override=orm.color_override,
            comment=orm.comment,
        )

    async def _get_task_ids(self, session: AsyncSession, engagement_id: UUID) -> List[UUID]:
        result = await session.execute(
            select(engagement_tasks.c.task_id).where(
                engagement_tasks.c.engagement_id == engagement_id
            )
        )
        return [row[0] for row in result.all()]

    async def get_by_id(self, engagement_id: UUID) -> Optional[Engagement]:
        async with self._session_factory() as session:
            orm = await session.get(EngagementORMModel, engagement_id)
            if not orm:
                return None
            task_ids = await self._get_task_ids(session, engagement_id)
            return self._to_domain(orm, task_ids)

    async def get_all(self) -> List[Engagement]:
        """Получить все задействования (для диалогов выбора)."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(EngagementORMModel).order_by(EngagementORMModel.start_at)
            )
            engagements = []
            for orm in result.scalars().all():
                task_ids = await self._get_task_ids(session, orm.id)
                engagements.append(self._to_domain(orm, task_ids))
            return engagements

    async def get_by_task_id(self, task_id: UUID) -> List[Engagement]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(EngagementORMModel)
                .join(engagement_tasks, EngagementORMModel.id == engagement_tasks.c.engagement_id)
                .where(engagement_tasks.c.task_id == task_id)
                .order_by(EngagementORMModel.start_at)
            )
            engagements = []
            for orm in result.scalars().all():
                task_ids = await self._get_task_ids(session, orm.id)
                engagements.append(self._to_domain(orm, task_ids))
            return engagements

    async def get_by_employee_id(
        self,
        employee_id: UUID,
        start_at: Optional[datetime] = None,
        end_at: Optional[datetime] = None,
    ) -> List[Engagement]:
        async with self._session_factory() as session:
            conditions = [EngagementORMModel.employee_id == employee_id]
            if start_at:
                conditions.append(EngagementORMModel.end_at > start_at)
            if end_at:
                conditions.append(EngagementORMModel.start_at < end_at)
            result = await session.execute(
                select(EngagementORMModel)
                .where(and_(*conditions))
                .order_by(EngagementORMModel.start_at)
            )
            engagements = []
            for orm in result.scalars().all():
                task_ids = await self._get_task_ids(session, orm.id)
                engagements.append(self._to_domain(orm, task_ids))
            return engagements

    async def find_overlaps(
        self,
        employee_id: UUID,
        start_at: datetime,
        end_at: datetime,
        exclude_id: Optional[UUID] = None,
    ) -> List[Engagement]:
        async with self._session_factory() as session:
            conditions = [
                EngagementORMModel.employee_id == employee_id,
                EngagementORMModel.start_at < end_at,
                EngagementORMModel.end_at > start_at,
            ]
            if exclude_id:
                conditions.append(EngagementORMModel.id != exclude_id)
            result = await session.execute(
                select(EngagementORMModel).where(and_(*conditions))
            )
            overlaps = []
            for orm in result.scalars().all():
                task_ids = await self._get_task_ids(session, orm.id)
                overlaps.append(self._to_domain(orm, task_ids))
            return overlaps

    async def create(self, engagement: Engagement) -> Engagement:
        async with self._session_factory() as session:
            orm = self._to_orm(engagement)
            session.add(orm)
            await session.flush()
            for task_id in engagement.task_ids:
                await session.execute(
                    insert(engagement_tasks).values(engagement_id=engagement.id, task_id=task_id)
                )
            await session.commit()
            await session.refresh(orm)
            return self._to_domain(orm, engagement.task_ids)

    async def update(self, engagement: Engagement) -> Engagement:
        async with self._session_factory() as session:
            orm = await session.get(EngagementORMModel, engagement.id)
            if not orm:
                raise ValueError(f"Engagement {engagement.id} not found")
            updated = self._to_orm(engagement)
            for key, value in updated.__dict__.items():
                if key != "_sa_instance_state":
                    setattr(orm, key, value)
            # Синхронизация M2M связей
            await session.execute(
                delete(engagement_tasks).where(engagement_tasks.c.engagement_id == engagement.id)
            )
            for task_id in engagement.task_ids:
                await session.execute(
                    insert(engagement_tasks).values(engagement_id=engagement.id, task_id=task_id)
                )
            await session.commit()
            await session.refresh(orm)
            return self._to_domain(orm, engagement.task_ids)

    async def delete(self, engagement_id: UUID) -> None:
        async with self._session_factory() as session:
            await session.execute(
                delete(engagement_tasks).where(engagement_tasks.c.engagement_id == engagement_id)
            )
            await session.execute(
                delete(EngagementORMModel).where(EngagementORMModel.id == engagement_id)
            )
            await session.commit()

    async def add_to_task(self, engagement_id: UUID, task_id: UUID) -> bool:
        async with self._session_factory() as session:
            existing = await session.execute(
                select(engagement_tasks).where(
                    engagement_tasks.c.engagement_id == engagement_id,
                    engagement_tasks.c.task_id == task_id,
                )
            )
            if existing.first():
                return False
            await session.execute(
                insert(engagement_tasks).values(engagement_id=engagement_id, task_id=task_id)
            )
            await session.commit()
            return True

    async def remove_from_task(self, engagement_id: UUID, task_id: UUID) -> bool:
        async with self._session_factory() as session:
            result = await session.execute(
                delete(engagement_tasks).where(
                    engagement_tasks.c.engagement_id == engagement_id,
                    engagement_tasks.c.task_id == task_id,
                )
            )
            await session.commit()
            return result.rowcount > 0
