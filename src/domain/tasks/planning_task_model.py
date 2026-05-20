# src/domain/tasks/planning_task_model.py
"""Доменная модель задачи планирования с авто-расчётом календарных границ периода."""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator

from src.domain.tasks.task_exceptions import (
    EmptyTaskReferenceError,
    InvalidTaskNameError,
    InvalidTaskPeriodError,
)


class PeriodType(str, Enum):
    """Типы планировочных периодов."""
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"
    CUSTOM = "custom"


class PlanningTask(BaseModel):
    """Доменная сущность задачи планирования.

    Автоматически вычисляет границы периода (start_date/end_date) на основе
    выбранного типа и опорной даты (anchor_date). Вычисленные даты материализуются
    для хранения в БД и дальнейшего использования в отчётах.
    """

    id: UUID = Field(default_factory=uuid4, description="Уникальный идентификатор задачи")
    name: str = Field(..., min_length=1, description="Название задачи планирования")
    period_type: PeriodType = Field(..., description="Тип планировочного периода")
    anchor_date: date = Field(..., description="Опорная дата, выбранная пользователем в календаре")
    custom_start_date: Optional[date] = Field(None, description="Начало периода для типа CUSTOM")
    custom_end_date: Optional[date] = Field(None, description="Окончание периода для типа CUSTOM")
    start_date: date = Field(..., description="Фактическая дата начала периода (вычисляется автоматически)")
    end_date: date = Field(..., description="Фактическая дата окончания периода (вычисляется автоматически)")
    employee_ids: list[UUID] = Field(default_factory=list, description="Список ID сотрудников")
    duty_type_ids: list[UUID] = Field(default_factory=list, description="Список ID типов задействований")
    created_at: datetime = Field(default_factory=datetime.now, description="Время создания записи")
    updated_at: datetime = Field(default_factory=datetime.now, description="Время последнего изменения")

    @model_validator(mode="before")
    @classmethod
    def _calculate_period_bounds(cls, data: dict) -> dict:
        """Авто-расчёт start_date/end_date на основе period_type и anchor_date."""
        if not isinstance(data, dict):
            return data

        p_type_raw = data.get("period_type")
        anchor_raw = data.get("anchor_date")

        try:
            period_type = PeriodType(p_type_raw) if isinstance(p_type_raw, str) else p_type_raw
        except (ValueError, TypeError):
            return data  # Ошибку типа обработает валидатор Pydantic

        if not anchor_raw:
            return data

        anchor = date.fromisoformat(anchor_raw) if isinstance(anchor_raw, str) else anchor_raw
        start, end = None, None

        if period_type == PeriodType.WEEK:
            # ISO 8601: неделя начинается с понедельника (0)
            weekday = anchor.weekday()
            start = anchor - timedelta(days=weekday)
            end = start + timedelta(days=6)
        elif period_type == PeriodType.MONTH:
            _, last_day = calendar.monthrange(anchor.year, anchor.month)
            start = date(anchor.year, anchor.month, 1)
            end = date(anchor.year, anchor.month, last_day)
        elif period_type == PeriodType.YEAR:
            start = date(anchor.year, 1, 1)
            end = date(anchor.year, 12, 31)
        elif period_type == PeriodType.CUSTOM:
            c_start = data.get("custom_start_date")
            c_end = data.get("custom_end_date")
            if not c_start or not c_end:
                raise InvalidTaskPeriodError("Для кастомного периода обязательны custom_start_date и custom_end_date")
            c_start = date.fromisoformat(c_start) if isinstance(c_start, str) else c_start
            c_end = date.fromisoformat(c_end) if isinstance(c_end, str) else c_end
            if c_end <= c_start:
                raise InvalidTaskPeriodError("Дата окончания кастомного периода должна быть строго больше даты начала")
            start, end = c_start, c_end

        if start and end:
            data["start_date"] = start
            data["end_date"] = end

        return data

    @model_validator(mode="after")
    def _validate_name_and_references(self) -> "PlanningTask":
        """Валидация имени задачи и обязательных ссылок на сотрудников/типы."""
        if not self.name.strip():
            raise InvalidTaskNameError("Название задачи не может быть пустым или состоять из пробелов")
        self.name = self.name.strip()

        if not self.employee_ids:
            raise EmptyTaskReferenceError("Список сотрудников не может быть пустым")
        if not self.duty_type_ids:
            raise EmptyTaskReferenceError("Список типов задействований не может быть пустым")
        return self

    def clone(self) -> "PlanningTask":
        """Создаёт копию задачи для новой сессии планирования.

        Генерирует новый UUID, сохраняет created_at, сбрасывает updated_at.
        Валидаторы автоматически пересчитают start_date/end_date.
        """
        return PlanningTask(
            name=self.name,
            period_type=self.period_type,
            anchor_date=self.anchor_date,
            custom_start_date=self.custom_start_date,
            custom_end_date=self.custom_end_date,
            employee_ids=list(self.employee_ids),
            duty_type_ids=list(self.duty_type_ids),
            created_at=self.created_at,
            updated_at=datetime.now(),
        )

