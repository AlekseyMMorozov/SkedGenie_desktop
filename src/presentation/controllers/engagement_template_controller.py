# src/presentation/controllers/engagement_template_controller.py
"""Контроллер шаблонов задействований."""
from __future__ import annotations

import logging
from typing import List, Optional
from uuid import UUID

from src.application.interfaces.engagement_template_repository_interface import IEngagementTemplateRepository
from src.application.schemas.engagement_schemas import (
    EngagementTemplateCreateSchema,
    EngagementTemplateReadSchema,
    EngagementTemplateUpdateSchema,
)
from src.core.logging_config import log_user_action, log_user_error
from src.domain.engagements.engagement_exceptions import DuplicateEngagementNameError
from src.domain.engagements.engagement_template_model import EngagementTemplate


class EngagementTemplateController:
    """Управление шаблонами задействований (ролями/видами работ)."""

    def __init__(
        self,
        repository: IEngagementTemplateRepository,
        logger: logging.Logger,
    ) -> None:
        self._repository = repository
        self._logger = logger

    async def get_all(self) -> List[EngagementTemplateReadSchema]:
        try:
            templates = await self._repository.get_all()
            return [EngagementTemplateReadSchema.model_validate(t) for t in templates]
        except Exception as exc:
            log_user_error(self._logger, "get_all_engagement_templates", str(exc))
            raise

    async def get_by_type_id(self, type_id: UUID) -> List[EngagementTemplateReadSchema]:
        try:
            templates = await self._repository.get_by_type_id(type_id)
            return [EngagementTemplateReadSchema.model_validate(t) for t in templates]
        except Exception as exc:
            log_user_error(self._logger, "get_templates_by_type", str(exc))
            raise

    async def get_by_id(self, template_id: UUID) -> Optional[EngagementTemplateReadSchema]:
        try:
            domain = await self._repository.get_by_id(template_id)
            return EngagementTemplateReadSchema.model_validate(domain) if domain else None
        except Exception as exc:
            log_user_error(self._logger, "get_engagement_template_by_id", str(exc))
            raise

    async def create(self, schema: EngagementTemplateCreateSchema) -> EngagementTemplateReadSchema:
        try:
            if await self._repository.exists_by_name(schema.name):
                raise DuplicateEngagementNameError(schema.name)

            domain = EngagementTemplate(
                type_id=schema.type_id,
                name=schema.name,
                short_name=schema.short_name,
                custom_color_hex=schema.custom_color_hex,
            )
            created = await self._repository.create(domain)
            log_user_action(self._logger, "create_engagement_template", f"id={created.id}, name={created.name}")
            return EngagementTemplateReadSchema.model_validate(created)
        except DuplicateEngagementNameError:
            raise
        except Exception as exc:
            log_user_error(self._logger, "create_engagement_template", str(exc))
            raise

    async def update(self, template_id: UUID, schema: EngagementTemplateUpdateSchema) -> EngagementTemplateReadSchema:
        try:
            domain = await self._repository.get_by_id(template_id)
            if not domain:
                raise ValueError(f"EngagementTemplate {template_id} not found")

            if schema.name and await self._repository.exists_by_name(schema.name, exclude_id=template_id):
                raise DuplicateEngagementNameError(schema.name)

            update_data = schema.model_dump(exclude_unset=True)
            updated = domain.model_copy(update=update_data)
            saved = await self._repository.update(updated)
            log_user_action(self._logger, "update_engagement_template", f"id={saved.id}")
            return EngagementTemplateReadSchema.model_validate(saved)
        except (DuplicateEngagementNameError, ValueError):
            raise
        except Exception as exc:
            log_user_error(self._logger, "update_engagement_template", str(exc))
            raise

    async def delete(self, template_id: UUID) -> None:
        try:
            await self._repository.delete(template_id)
            log_user_action(self._logger, "delete_engagement_template", f"id={template_id}")
        except Exception as exc:
            log_user_error(self._logger, "delete_engagement_template", str(exc))
            raise
