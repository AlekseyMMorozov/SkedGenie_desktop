# src/infrastructure/repositories/engagement_template_repository.py
"""SQLAlchemy-репозиторий шаблонов задействований."""
from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy import delete, exists, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.application.interfaces.engagement_template_repository_interface import IEngagementTemplateRepository
from src.domain.engagements.engagement_template_model import EngagementTemplate
from src.infrastructure.db.models.engagement_template_orm_model import EngagementTemplateORMModel


class EngagementTemplateSQLAlchemyRepository(IEngagementTemplateRepository):
    """Реализация репозитория шаблонов задействований на SQLAlchemy."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    @staticmethod
    def _to_orm(domain: EngagementTemplate) -> EngagementTemplateORMModel:
        return EngagementTemplateORMModel(
            id=domain.id,
            type_id=domain.type_id,
            name=domain.name,
            short_name=domain.short_name,
            custom_color_hex=domain.custom_color_hex,
        )

    @staticmethod
    def _to_domain(orm: EngagementTemplateORMModel) -> EngagementTemplate:
        return EngagementTemplate(
            id=orm.id,
            type_id=orm.type_id,
            name=orm.name,
            short_name=orm.short_name,
            custom_color_hex=orm.custom_color_hex,
        )

    async def get_by_id(self, template_id: UUID) -> Optional[EngagementTemplate]:
        async with self._session_factory() as session:
            orm = await session.get(EngagementTemplateORMModel, template_id)
            return self._to_domain(orm) if orm else None

    async def get_by_type_id(self, type_id: UUID) -> List[EngagementTemplate]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(EngagementTemplateORMModel)
                .where(EngagementTemplateORMModel.type_id == type_id)
                .order_by(EngagementTemplateORMModel.name)
            )
            return [self._to_domain(row) for row in result.scalars().all()]

    async def get_all(self) -> List[EngagementTemplate]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(EngagementTemplateORMModel).order_by(EngagementTemplateORMModel.name)
            )
            return [self._to_domain(row) for row in result.scalars().all()]

    async def exists_by_name(self, name: str, exclude_id: Optional[UUID] = None) -> bool:
        async with self._session_factory() as session:
            conditions = [EngagementTemplateORMModel.name == name]
            if exclude_id:
                conditions.append(EngagementTemplateORMModel.id != exclude_id)
            stmt = select(exists().where(*conditions))
            result = await session.execute(stmt)
            return result.scalar_one()

    async def create(self, template: EngagementTemplate) -> EngagementTemplate:
        async with self._session_factory() as session:
            orm = self._to_orm(template)
            session.add(orm)
            await session.commit()
            await session.refresh(orm)
            return self._to_domain(orm)

    async def update(self, template: EngagementTemplate) -> EngagementTemplate:
        async with self._session_factory() as session:
            orm = await session.get(EngagementTemplateORMModel, template.id)
            if not orm:
                raise ValueError(f"EngagementTemplate {template.id} not found")
            updated = self._to_orm(template)
            for key, value in updated.__dict__.items():
                if key != "_sa_instance_state":
                    setattr(orm, key, value)
            await session.commit()
            await session.refresh(orm)
            return self._to_domain(orm)

    async def delete(self, template_id: UUID) -> None:
        async with self._session_factory() as session:
            await session.execute(
                delete(EngagementTemplateORMModel).where(EngagementTemplateORMModel.id == template_id)
            )
            await session.commit()
