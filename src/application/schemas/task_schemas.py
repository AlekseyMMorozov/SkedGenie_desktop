# src/application/schemas/task_schemas.py
"""Pydantic-схемы (DTO) для передачи данных задач планирования между слоями."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.domain.tasks.planning_task_model import PeriodType


class TaskCreateSchema(BaseModel):
    """Схема данных для создания новой задачи планирования."""
    model_config = ConfigDict(frozen=False)

    name: str = Field(..., min_length=1, description="Название задачи")
    period_type: PeriodType = Field(..., description="Тип планировочного периода")
    anchor_date: date = Field(..., description="Опорная дата, выбранная в календаре")
    custom_start_date: Optional[date] = Field(None, description="Начало периода (только для CUSTOM)")
    custom_end_date: Optional[date] = Field(None, description="Окончание периода (только для CUSTOM)")
    employee_ids: list[UUID] = Field(..., description="Список идентификаторов сотрудников")
    duty_type_ids: list[UUID] = Field(..., description="Список идентификаторов типов задействований")


class TaskUpdateSchema(BaseModel):
    """Схема данных для частичного обновления существующей задачи."""
    model_config = ConfigDict(frozen=False)

    name: Optional[str] = Field(None, min_length=1)
    period_type: Optional[PeriodType] = None
    anchor_date: Optional[date] = None
    custom_start_date: Optional[date] = None
    custom_end_date: Optional[date] = None
    employee_ids: Optional[list[UUID]] = None
    duty_type_ids: Optional[list[UUID]] = None


class TaskReadSchema(BaseModel):
    """Схема данных для чтения и отображения задачи планирования."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    period_type: PeriodType
    anchor_date: date
    custom_start_date: Optional[date]
    custom_end_date: Optional[date]
    start_date: date
    end_date: date
    employee_ids: list[UUID]
    duty_type_ids: list[UUID]
    created_at: datetime
    updated_at: datetime
