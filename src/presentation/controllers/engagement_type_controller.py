# src/presentation/controllers/engagement_type_controller.py
"""Контроллер типов задействований."""
from __future__ import annotations

import logging
from typing import List, Optional
from uuid import UUID

from src.application.interfaces.engagement_type_repository_interface import IEngagementTypeRepository
from src.application.schemas.engagement_schemas import (
    EngagementTypeCreateSchema,
    EngagementTypeReadSchema,
    EngagementTypeUpdateSchema,
)
from src.application.services.engagement_color_service import EngagementColorService
from src.core.logging_config import log_user_action, log_user_error
from src.domain.engagements.engagement_exceptions import DuplicateEngagementNameError
from src.domain.engagements.engagement_type_model import EngagementType


class EngagementTypeController:
    """Управление типами задействований (правилами)."""

    def __init__(
        self,
        repository: IEngagementTypeRepository,
        color_service: EngagementColorService,
        logger: logging.Logger,
    ) -> None:
        self._repository = repository
        self._color_service = color_service
        self._logger = logger

    async def get_all(self) -> List[EngagementTypeReadSchema]:
        try:
            types = await self._repository.get_all()
            return [self._to_read_schema(t) for t in types]
        except Exception as exc:
            log_user_error(self._logger, "get_all_engagement_types", str(exc))
            raise

    async def get_by_id(self, type_id: UUID) -> Optional[EngagementTypeReadSchema]:
        try:
            domain = await self._repository.get_by_id(type_id)
            return self._to_read_schema(domain) if domain else None
        except Exception as exc:
            log_user_error(self._logger, "get_engagement_type_by_id", str(exc))
            raise

    async def create(self, schema: EngagementTypeCreateSchema) -> EngagementTypeReadSchema:
        try:
            if await self._repository.exists_by_name(schema.name):
                raise DuplicateEngagementNameError(schema.name)

            existing = await self._repository.get_all()
            existing_colors = [t.color_hex for t in existing]
            color = schema.color_hex or self._color_service.generate_unique_color(existing_colors)

            domain = EngagementType(
                name=schema.name,
                category=schema.category,
                color_hex=color,
                duration_type=schema.duration_type,
                default_start_time=schema.default_start_time,
                default_duration_hours=schema.default_duration_hours,
                min_duration_hours=schema.min_duration_hours,
                max_duration_hours=schema.max_duration_hours,
                allow_overlap=schema.allow_overlap,
            )
            created = await self._repository.create(domain)
            log_user_action(self._logger, "create_engagement_type", f"id={created.id}, name={created.name}")
            return self._to_read_schema(created)
        except DuplicateEngagementNameError:
            raise
        except Exception as exc:
            log_user_error(self._logger, "create_engagement_type", str(exc))
            raise

    async def update(self, type_id: UUID, schema: EngagementTypeUpdateSchema) -> EngagementTypeReadSchema:
        try:
            domain = await self._repository.get_by_id(type_id)
            if not domain:
                raise ValueError(f"EngagementType {type_id} not found")

            if schema.name and await self._repository.exists_by_name(schema.name, exclude_id=type_id):
                raise DuplicateEngagementNameError(schema.name)

            update_data = schema.model_dump(exclude_unset=True)
            updated = domain.model_copy(update=update_data)
            saved = await self._repository.update(updated)
            log_user_action(self._logger, "update_engagement_type", f"id={saved.id}")
            return self._to_read_schema(saved)
        except (DuplicateEngagementNameError, ValueError):
            raise
        except Exception as exc:
            log_user_error(self._logger, "update_engagement_type", str(exc))
            raise

    async def delete(self, type_id: UUID) -> None:
        try:
            await self._repository.delete(type_id)
            log_user_action(self._logger, "delete_engagement_type", f"id={type_id}")
        except Exception as exc:
            log_user_error(self._logger, "delete_engagement_type", str(exc))
            raise

    @staticmethod
    def _to_read_schema(domain: EngagementType) -> EngagementTypeReadSchema:
        return EngagementTypeReadSchema.model_validate(domain)
