# src/application/schemas/engagement_schemas.py
"""Схемы Pydantic для CRUD операций над задействованиями."""

from __future__ import annotations

from datetime import datetime, time
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.domain.engagements.engagement_type_model import DurationType


# --- Engagement Type Schemas ---

class EngagementTypeCreateSchema(BaseModel):
    """Схема создания типа задействования."""
    name: str = Field(..., min_length=1, max_length=100)
    category: str = Field(..., min_length=1, max_length=50)
    color_hex: str = Field(..., pattern=r'^#[0-9A-Fa-f]{6}$')
    duration_type: DurationType = Field(default=DurationType.SHORT)
    default_start_time: time = Field(default=time(8, 0))
    default_duration_hours: float = Field(gt=0)
    min_duration_hours: float = Field(ge=0)
    max_duration_hours: float = Field(gt=0)
    allow_overlap: bool = Field(default=False)

    @field_validator('name', 'category')
    @classmethod
    def _strip_whitespace(cls, v: str) -> str:
        return v.strip()


class EngagementTypeUpdateSchema(BaseModel):
    """Схема обновления типа задействования."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    category: Optional[str] = Field(None, min_length=1, max_length=50)
    color_hex: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')
    duration_type: Optional[DurationType] = None
    default_start_time: Optional[time] = None
    default_duration_hours: Optional[float] = Field(None, gt=0)
    min_duration_hours: Optional[float] = Field(None, ge=0)
    max_duration_hours: Optional[float] = Field(None, gt=0)
    allow_overlap: Optional[bool] = None

    @field_validator('name', 'category')
    @classmethod
    def _strip_whitespace(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if v else v


class EngagementTypeReadSchema(BaseModel):
    """Схема чтения типа задействования."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    category: str
    color_hex: str
    duration_type: DurationType
    default_start_time: time
    default_duration_hours: float
    min_duration_hours: float
    max_duration_hours: float
    allow_overlap: bool


# --- Engagement Template Schemas ---

class EngagementTemplateCreateSchema(BaseModel):
    """Схема создания шаблона задействования."""
    type_id: UUID
    name: str = Field(..., min_length=1, max_length=100)
    short_name: str = Field(..., min_length=1, max_length=10)
    custom_color_hex: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')

    @field_validator('name', 'short_name')
    @classmethod
    def _strip_whitespace(cls, v: str) -> str:
        return v.strip()


class EngagementTemplateUpdateSchema(BaseModel):
    """Схема обновления шаблона задействования."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    short_name: Optional[str] = Field(None, min_length=1, max_length=10)
    custom_color_hex: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')

    @field_validator('name', 'short_name')
    @classmethod
    def _strip_whitespace(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if v else v


class EngagementTemplateReadSchema(BaseModel):
    """Схема чтения шаблона задействования."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type_id: UUID
    name: str
    short_name: str
    custom_color_hex: Optional[str]


# --- Engagement (Instance) Schemas ---

class EngagementCreateSchema(BaseModel):
    """Схема создания экземпляра задействования."""
    employee_id: UUID
    template_id: UUID
    task_ids: List[UUID] = Field(default_factory=list)
    start_at: datetime
    end_at: datetime
    short_name_override: Optional[str] = Field(None, max_length=10)
    color_override: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')
    comment: Optional[str] = Field(None, max_length=500)

    @field_validator('comment')
    @classmethod
    def _strip_comment(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if v else v


class EngagementUpdateSchema(BaseModel):
    """Схема обновления экземпляра задействования."""
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    short_name_override: Optional[str] = Field(None, max_length=10)
    color_override: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')
    comment: Optional[str] = Field(None, max_length=500)

    @field_validator('comment')
    @classmethod
    def _strip_comment(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if v else v


class EngagementReadSchema(BaseModel):
    """Схема чтения экземпляра задействования."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    template_id: UUID
    task_ids: List[UUID]
    start_at: datetime
    end_at: datetime
    short_name_override: Optional[str]
    color_override: Optional[str]
    comment: Optional[str]
    duration_hours: float

