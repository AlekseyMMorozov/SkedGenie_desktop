# src/domain/engagements/engagement_model.py
from __future__ import annotations
from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, model_validator


class Engagement(BaseModel):
    """
    Спланированное задействование сотрудника.
    """
    id: UUID = Field(default_factory=uuid4)
    employee_id: UUID
    template_id: UUID  # Ссылка на шаблон (роль)
    task_ids: List[UUID] = Field(default_factory=list, description="Список ID задач-графиков")

    start_at: datetime
    end_at: datetime

    # Локальные переопределения
    short_name_override: Optional[str] = Field(None, max_length=10)
    color_override: Optional[str] = Field(None)
    comment: Optional[str] = None

    @model_validator(mode='after')
    def validate_time_order(self) -> 'Engagement':
        if self.end_at <= self.start_at:
            raise ValueError("Время окончания должно быть строго позже времени начала")
        return self

    @property
    def duration_hours(self) -> float:
        return (self.end_at - self.start_at).total_seconds() / 3600

