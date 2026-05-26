"""
Файл: src/application/schemas/task_schemas.py
Описание: Pydantic-схемы для DTO задачи планирования.
Архитектура: Application слой. Валидация на границе домена.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.domain.tasks.planning_task_model import PeriodType


class TaskCreateSchema(BaseModel):
    """Схема создания задачи планирования.

    Обязательные поля: только name и period_type.
    Остальные поля могут быть добавлены позже при редактировании.
    """
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    name: str = Field(..., min_length=1, max_length=255, description="Название задачи")
    period_type: PeriodType = Field(..., description="Тип периода планирования")

    # Опциональные поля (добавляются позже)
    anchor_date: Optional[date] = Field(default=None, description="Базовая дата для расчёта периодов")
    employee_ids: Optional[List[UUID]] = Field(default=None, description="ID сотрудников, закреплённых за задачей")
    duty_type_ids: Optional[List[UUID]] = Field(default=None, description="ID типов задействований для задачи")
    reference_id: Optional[str] = Field(default=None, max_length=255, description="Внешний идентификатор/ссылка")


class TaskUpdateSchema(BaseModel):
    """Схема обновления задачи планирования.

    Все поля опциональны — обновляются только переданные значения.
    """
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID = Field(..., description="Уникальный идентификатор задачи")

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    period_type: Optional[PeriodType] = Field(default=None)
    anchor_date: Optional[date] = Field(default=None)
    employee_ids: Optional[List[UUID]] = Field(default=None)
    duty_type_ids: Optional[List[UUID]] = Field(default=None)
    reference_id: Optional[str] = Field(default=None, max_length=255)


class TaskReadSchema(BaseModel):
    """Схема чтения задачи планирования (для отображения в UI)."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    period_type: str  # Строковое значение для удобства отображения
    anchor_date: Optional[date] = None
    employee_ids: Optional[List[UUID]] = None
    duty_type_ids: Optional[List[UUID]] = None
    reference_id: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

