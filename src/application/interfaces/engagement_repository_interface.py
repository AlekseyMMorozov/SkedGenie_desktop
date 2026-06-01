# src/application/interfaces/engagement_repository_interface.py
"""Интерфейс репозитория экземпляров задействований."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from src.domain.engagements.engagement_model import Engagement


class IEngagementRepository(ABC):
    """Контракт доступа к экземплярам задействований в графиках."""

    @abstractmethod
    async def get_by_id(self, engagement_id: UUID) -> Optional[Engagement]:
        """Получить задействование по ID."""

    @abstractmethod
    async def get_all(self) -> List[Engagement]:
        """Получить все задействования (для диалогов выбора)."""

    @abstractmethod
    async def get_by_task_id(self, task_id: UUID) -> List[Engagement]:
        """Получить все задействования в рамках задачи-графика."""

    @abstractmethod
    async def get_by_employee_id(
        self,
        employee_id: UUID,
        start_at: Optional[datetime] = None,
        end_at: Optional[datetime] = None,
    ) -> List[Engagement]:
        """Получить задействования сотрудника с опциональной фильтрацией по периоду."""

    @abstractmethod
    async def find_overlaps(
        self,
        employee_id: UUID,
        start_at: datetime,
        end_at: datetime,
        exclude_id: Optional[UUID] = None,
    ) -> List[Engagement]:
        """Найти пересечения по времени для сотрудника."""

    @abstractmethod
    async def create(self, engagement: Engagement) -> Engagement:
        """Создать новое задействование."""

    @abstractmethod
    async def update(self, engagement: Engagement) -> Engagement:
        """Обновить существующее задействование."""

    @abstractmethod
    async def delete(self, engagement_id: UUID) -> None:
        """Удалить задействование."""

    @abstractmethod
    async def add_to_task(self, engagement_id: UUID, task_id: UUID) -> bool:
        """Добавить задействование в задачу-график."""

    @abstractmethod
    async def remove_from_task(self, engagement_id: UUID, task_id: UUID) -> bool:
        """Удалить задействование из задачи-графика."""
