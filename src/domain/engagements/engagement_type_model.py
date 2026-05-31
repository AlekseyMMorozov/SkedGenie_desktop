# src/domain/engagements/engagement_type_model.py
from __future__ import annotations
from datetime import time
from enum import Enum
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, field_validator


class DurationType(str, Enum):
    LONG = "long"  # Длительный (сутки)
    DAILY = "daily"  # Суточный (24ч +/-)
    SHORT = "short"  # Короткий (< 18ч)

    @property
    def localized(self) -> str:
        return {
            self.LONG: "Длительный",
            self.DAILY: "Суточный",
            self.SHORT: "Короткий"
        }[self]


class EngagementType(BaseModel):
    """
    Тип задействования — набор общих правил для группы шаблонов.
    Например: 'Суточные наряды', 'Отпуска', 'Учеба'.
    """
    id: UUID = Field(default_factory=uuid4)
    name: str = Field(..., min_length=1, description="Название типа (группы)")
    category: str = Field(..., min_length=1, description="Логическая группа для UI")
    color_hex: str = Field(..., description="Базовый цвет для всех шаблонов этого типа")

    duration_type: DurationType = Field(default=DurationType.SHORT)

    # Правила времени
    default_start_time: time = Field(default=time(8, 0), description="Стандартное время начала")
    default_duration_hours: float = Field(gt=0, description="Стандартная длительность в часах")

    # Ограничения (для валидации экземпляров)
    min_duration_hours: float = Field(ge=0, description="Минимально допустимая длительность")
    max_duration_hours: float = Field(gt=0, description="Максимально допустимая длительность")

    # Поведение
    allow_overlap: bool = Field(default=False, description="Разрешены ли наложения")

    @field_validator('color_hex')
    @classmethod
    def validate_color(cls, v: str) -> str:
        if not isinstance(v, str) or not v.startswith('#') or len(v) != 7:
            raise ValueError("Цвет должен быть в формате HEX (#RRGGBB)")
        try:
            int(v[1:], 16)
        except ValueError:
            raise ValueError("Некорректное HEX-значение цвета")
        return v.upper()
