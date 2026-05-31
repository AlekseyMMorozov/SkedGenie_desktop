# src/application/interfaces/engagement_template_repository_interface.py
"""Интерфейс репозитория шаблонов задействований."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from src.domain.engagements.engagement_template_model import EngagementTemplate


class IEngagementTemplateRepository(ABC):
    """Контракт доступа к шаблонам задействований."""

    @abstractmethod
    async def get_by_id(self, template_id: UUID) -> Optional[EngagementTemplate]:
        """Получить шаблон по ID."""

    @abstractmethod
    async def get_by_type_id(self, type_id: UUID) -> List[EngagementTemplate]:
        """Получить все шаблоны указанного типа."""

    @abstractmethod
    async def get_all(self) -> List[EngagementTemplate]:
        """Получить все шаблоны."""

    @abstractmethod
    async def exists_by_name(self, name: str, exclude_id: Optional[UUID] = None) -> bool:
        """Проверить существование шаблона по имени."""

    @abstractmethod
    async def create(self, template: EngagementTemplate) -> EngagementTemplate:
        """Создать новый шаблон."""

    @abstractmethod
    async def update(self, template: EngagementTemplate) -> EngagementTemplate:
        """Обновить существующий шаблон."""

    @abstractmethod
    async def delete(self, template_id: UUID) -> None:
        """Удалить шаблон."""
