# src/infrastructure/repositories/engagement_type_repository.py
"""SQLAlchemy-репозиторий типов задействований."""
from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy import delete, exists, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.application.interfaces.engagement_type_repository_interface import IEngagementTypeRepository
from src.domain.engagements.engagement_type_model import DurationType, EngagementType
from src.infrastructure.db.models.engagement_type_orm_model import EngagementTypeORMModel


class EngagementTypeSQLAlchemyRepository(IEngagementTypeRepository):
    """Реализация репозитория типов задействований на SQLAlchemy."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    @staticmethod
    def _to_orm(domain: EngagementType) -> EngagementTypeORMModel:
        return EngagementTypeORMModel(
            id=domain.id,
            name=domain.name,
            category=domain.category,
            color_hex=domain.color_hex,
            duration_type=domain.duration_type.value,
            default_start_time=domain.default_start_time,
            default_duration_hours=domain.default_duration_hours,
            min_duration_hours=domain.min_duration_hours,
            max_duration_hours=domain.max_duration_hours,
            allow_overlap=domain.allow_overlap,
        )

    @staticmethod
    def _to_domain(orm: EngagementTypeORMModel) -> EngagementType:
        return EngagementType(
            id=orm.id,
            name=orm.name,
            category=orm.category,
            color_hex=orm.color_hex,
            duration_type=DurationType(orm.duration_type),
            default_start_time=orm.default_start_time,
            default_duration_hours=orm.default_duration_hours,
            min_duration_hours=orm.min_duration_hours,
            max_duration_hours=orm.max_duration_hours,
            allow_overlap=orm.allow_overlap,
        )

    async def get_by_id(self, type_id: UUID) -> Optional[EngagementType]:
        async with self._session_factory() as session:
            orm = await session.get(EngagementTypeORMModel, type_id)
            return self._to_domain(orm) if orm else None

    async def get_all(self) -> List[EngagementType]:
        async with self._session_factory() as session:
            result = await session.execute(select(EngagementTypeORMModel).order_by(EngagementTypeORMModel.name))
            return [self._to_domain(row) for row in result.scalars().all()]

    async def exists_by_name(self, name: str, exclude_id: Optional[UUID] = None) -> bool:
        async with self._session_factory() as session:
            stmt = select(exists().where(EngagementTypeORMModel.name == name))
            if exclude_id:
                stmt = select(exists().where(
                    EngagementTypeORMModel.name == name,
                    EngagementTypeORMModel.id != exclude_id,
                ))
            result = await session.execute(stmt)
            return result.scalar_one()

    async def create(self, engagement_type: EngagementType) -> EngagementType:
        async with self._session_factory() as session:
            orm = self._to_orm(engagement_type)
            session.add(orm)
            await session.commit()
            await session.refresh(orm)
            return self._to_domain(orm)

    async def update(self, engagement_type: EngagementType) -> EngagementType:
        async with self._session_factory() as session:
            orm = await session.get(EngagementTypeORMModel, engagement_type.id)
            if not orm:
                raise ValueError(f"EngagementType {engagement_type.id} not found")
            updated = self._to_orm(engagement_type)
            for key, value in updated.__dict__.items():
                if key != "_sa_instance_state":
                    setattr(orm, key, value)
            await session.commit()
            await session.refresh(orm)
            return self._to_domain(orm)

    async def delete(self, type_id: UUID) -> None:
        async with self._session_factory() as session:
            await session.execute(delete(EngagementTypeORMModel).where(EngagementTypeORMModel.id == type_id))
            await session.commit()
