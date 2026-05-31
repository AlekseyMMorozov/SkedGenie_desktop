# src/application/interfaces/engagement_type_repository_interface.py
"""Интерфейс репозитория типов задействований."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from src.domain.engagements.engagement_type_model import EngagementType


class IEngagementTypeRepository(ABC):
    """Контракт доступа к типам задействований."""

    @abstractmethod
    async def get_by_id(self, type_id: UUID) -> Optional[EngagementType]:
        """Получить тип по ID."""

    @abstractmethod
    async def get_all(self) -> List[EngagementType]:
        """Получить все типы задействований."""

    @abstractmethod
    async def exists_by_name(self, name: str, exclude_id: Optional[UUID] = None) -> bool:
        """Проверить существование типа по имени."""

    @abstractmethod
    async def create(self, engagement_type: EngagementType) -> EngagementType:
        """Создать новый тип задействования."""

    @abstractmethod
    async def update(self, engagement_type: EngagementType) -> EngagementType:
        """Обновить существующий тип."""

    @abstractmethod
    async def delete(self, type_id: UUID) -> None:
        """Удалить тип задействования."""
