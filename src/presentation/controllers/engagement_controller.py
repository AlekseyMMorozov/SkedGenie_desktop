# src/presentation/controllers/engagement_controller.py
"""Контроллер экземпляров задействований (записей в графике)."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from src.application.interfaces.engagement_repository_interface import IEngagementRepository
from src.application.interfaces.engagement_template_repository_interface import IEngagementTemplateRepository
from src.application.interfaces.engagement_type_repository_interface import IEngagementTypeRepository
from src.application.schemas.engagement_schemas import (
    EngagementCreateSchema,
    EngagementReadSchema,
    EngagementUpdateSchema,
)
from src.core.logging_config import log_user_action, log_user_error
from src.domain.engagements.engagement_exceptions import (
    EngagementOverlapError,
    InvalidEngagementDurationError,
)
from src.domain.engagements.engagement_model import Engagement


class EngagementController:
    """Управление экземплярами задействований в графиках."""

    def __init__(
        self,
        engagement_repo: IEngagementRepository,
        template_repo: IEngagementTemplateRepository,
        type_repo: IEngagementTypeRepository,
        logger: logging.Logger,
    ) -> None:
        self._engagement_repo = engagement_repo
        self._template_repo = template_repo
        self._type_repo = type_repo
        self._logger = logger

    async def get_by_task_id(self, task_id: UUID) -> List[EngagementReadSchema]:
        try:
            engagements = await self._engagement_repo.get_by_task_id(task_id)
            return [self._to_read_schema(e) for e in engagements]
        except Exception as exc:
            log_user_error(self._logger, "get_engagements_by_task", str(exc))
            raise

    async def get_by_employee_id(
        self,
        employee_id: UUID,
        start_at: Optional[datetime] = None,
        end_at: Optional[datetime] = None,
    ) -> List[EngagementReadSchema]:
        try:
            engagements = await self._engagement_repo.get_by_employee_id(employee_id, start_at, end_at)
            return [self._to_read_schema(e) for e in engagements]
        except Exception as exc:
            log_user_error(self._logger, "get_engagements_by_employee", str(exc))
            raise

    async def create(self, schema: EngagementCreateSchema) -> EngagementReadSchema:
        try:
            # Валидация через тип
            template = await self._template_repo.get_by_id(schema.template_id)
            if not template:
                raise ValueError(f"EngagementTemplate {schema.template_id} not found")

            eng_type = await self._type_repo.get_by_id(template.type_id)
            if not eng_type:
                raise ValueError(f"EngagementType {template.type_id} not found")

            duration = (schema.end_at - schema.start_at).total_seconds() / 3600
            if duration < eng_type.min_duration_hours or duration > eng_type.max_duration_hours:
                raise InvalidEngagementDurationError(duration, eng_type.min_duration_hours, eng_type.max_duration_hours)

            if not eng_type.allow_overlap:
                overlaps = await self._engagement_repo.find_overlaps(
                    schema.employee_id, schema.start_at, schema.end_at
                )
                if overlaps:
                    raise EngagementOverlapError(schema.employee_id, schema.start_at, schema.end_at)

            effective_color = schema.color_override or template.get_effective_color(eng_type.color_hex)

            domain = Engagement(
                employee_id=schema.employee_id,
                template_id=schema.template_id,
                task_ids=schema.task_ids,
                start_at=schema.start_at,
                end_at=schema.end_at,
                short_name_override=schema.short_name_override,
                color_override=effective_color,
                comment=schema.comment,
            )
            created = await self._engagement_repo.create(domain)
            log_user_action(self._logger, "create_engagement", f"id={created.id}, employee={created.employee_id}")
            return self._to_read_schema(created)
        except (InvalidEngagementDurationError, EngagementOverlapError, ValueError):
            raise
        except Exception as exc:
            log_user_error(self._logger, "create_engagement", str(exc))
            raise

    async def update(self, engagement_id: UUID, schema: EngagementUpdateSchema) -> EngagementReadSchema:
        try:
            domain = await self._engagement_repo.get_by_id(engagement_id)
            if not domain:
                raise ValueError(f"Engagement {engagement_id} not found")

            update_data = schema.model_dump(exclude_unset=True)
            updated = domain.model_copy(update=update_data)

            # Повторная валидация при изменении времени
            if schema.start_at or schema.end_at:
                template = await self._template_repo.get_by_id(updated.template_id)
                eng_type = await self._type_repo.get_by_id(template.type_id) if template else None
                if eng_type and not eng_type.allow_overlap:
                    overlaps = await self._engagement_repo.find_overlaps(
                        updated.employee_id, updated.start_at, updated.end_at, exclude_id=engagement_id
                    )
                    if overlaps:
                        raise EngagementOverlapError(updated.employee_id, updated.start_at, updated.end_at)

            saved = await self._engagement_repo.update(updated)
            log_user_action(self._logger, "update_engagement", f"id={saved.id}")
            return self._to_read_schema(saved)
        except (EngagementOverlapError, ValueError):
            raise
        except Exception as exc:
            log_user_error(self._logger, "update_engagement", str(exc))
            raise

    async def delete(self, engagement_id: UUID) -> None:
        try:
            await self._engagement_repo.delete(engagement_id)
            log_user_action(self._logger, "delete_engagement", f"id={engagement_id}")
        except Exception as exc:
            log_user_error(self._logger, "delete_engagement", str(exc))
            raise

    async def add_to_task(self, engagement_id: UUID, task_id: UUID) -> bool:
        try:
            result = await self._engagement_repo.add_to_task(engagement_id, task_id)
            if result:
                log_user_action(self._logger, "add_engagement_to_task", f"engagement={engagement_id}, task={task_id}")
            return result
        except Exception as exc:
            log_user_error(self._logger, "add_engagement_to_task", str(exc))
            raise

    async def remove_from_task(self, engagement_id: UUID, task_id: UUID) -> bool:
        try:
            result = await self._engagement_repo.remove_from_task(engagement_id, task_id)
            if result:
                log_user_action(self._logger, "remove_engagement_from_task", f"engagement={engagement_id}, task={task_id}")
            return result
        except Exception as exc:
            log_user_error(self._logger, "remove_engagement_from_task", str(exc))
            raise

    @staticmethod
    def _to_read_schema(domain: Engagement) -> EngagementReadSchema:
        return EngagementReadSchema.model_validate(domain)
