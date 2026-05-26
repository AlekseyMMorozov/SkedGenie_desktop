"""
Файл: src/domain/tasks/planning_task_model.py
Описание: Доменная модель задачи планирования.
Архитектура: Domain слой. Чистая бизнес-логика, без зависимостей от инфраструктуры.
"""
from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Optional, List
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator, ConfigDict

from src.domain.tasks.task_exceptions import (
    EmptyTaskReferenceError,
    InvalidTaskNameError,
    InvalidTaskPeriodError,
)

# Маппинг для отображения периодов на русском в UI
PERIOD_TYPE_RU: dict[str, str] = {
    "WEEK": "Неделя",
    "MONTH": "Месяц",
    "QUARTER": "Квартал",
    "YEAR": "Год",
    "CUSTOM": "Произвольный",
}


class PeriodType(str, Enum):
    """Типы периодов планирования."""
    WEEK = "WEEK"
    MONTH = "MONTH"
    QUARTER = "QUARTER"
    YEAR = "YEAR"
    CUSTOM = "CUSTOM"

    @property
    def localized(self) -> str:
        """Возвращает локализованное название периода."""
        return PERIOD_TYPE_RU.get(self.value, self.value)


class PlanningTask(BaseModel):
    """Доменная сущность: Задача планирования.

    Контейнер для настройки параметров планирования:
    - название и тип периода (обязательные)
    - опционально: сотрудники, типы дежурств, базовая дата
    - автоматически рассчитываемые: period_start, period_end
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: UUID = Field(default_factory=uuid4)
    name: str = Field(..., min_length=1, max_length=255)
    period_type: PeriodType = Field(...)

    # Опциональные поля (могут быть добавлены позже)
    anchor_date: Optional[date] = Field(default=None)
    employee_ids: Optional[List[UUID]] = Field(default=None)
    duty_type_ids: Optional[List[UUID]] = Field(default=None)
    reference_id: Optional[str] = Field(default=None, max_length=255)

    # Автоматически рассчитываемые границы периода
    period_start: Optional[date] = Field(default=None)
    period_end: Optional[date] = Field(default=None)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default=None)

    @model_validator(mode='after')
    def _calculate_period_bounds(self) -> 'PlanningTask':
        """Рассчитывает period_start/period_end после валидации полей."""
        # Если уже заданы — не пересчитываем
        if self.period_start and self.period_end:
            return self

        anchor = self.anchor_date or date.today()

        if self.period_type == PeriodType.WEEK:
            start = anchor - timedelta(days=anchor.weekday())
            object.__setattr__(self, 'period_start', start)
            object.__setattr__(self, 'period_end', start + timedelta(days=6))
        elif self.period_type == PeriodType.MONTH:
            object.__setattr__(self, 'period_start', anchor.replace(day=1))
            last_day = calendar.monthrange(anchor.year, anchor.month)[1]
            object.__setattr__(self, 'period_end', anchor.replace(day=last_day))
        elif self.period_type == PeriodType.QUARTER:
            quarter_month = ((anchor.month - 1) // 3) * 3 + 1
            start = anchor.replace(month=quarter_month, day=1)
            end_month = min(quarter_month + 2, 12)
            last_day = calendar.monthrange(anchor.year, end_month)[1]
            object.__setattr__(self, 'period_start', start)
            object.__setattr__(self, 'period_end', anchor.replace(month=end_month, day=last_day))
        elif self.period_type == PeriodType.YEAR:
            object.__setattr__(self, 'period_start', anchor.replace(month=1, day=1))
            object.__setattr__(self, 'period_end', anchor.replace(month=12, day=31))
        elif self.period_type == PeriodType.CUSTOM:
            # Для произвольного периода — заглушки, которые перезапишутся при создании планов
            object.__setattr__(self, 'period_start', anchor)
            object.__setattr__(self, 'period_end', anchor + timedelta(days=30))

        return self

    @model_validator(mode='after')
    def _validate_name_and_references(self) -> 'PlanningTask':
        """Валидация имени и ссылочных полей."""
        if not self.name.strip():
            raise InvalidTaskNameError("Название задачи не может быть пустым.")
        if self.reference_id is not None and not self.reference_id.strip():
            raise EmptyTaskReferenceError("reference_id не может быть пустой строкой.")
        return self

    def clone(self) -> 'PlanningTask':
        """Создаёт копию задачи с новым ID (для шаблонов)."""
        return self.model_copy(update={'id': uuid4(), 'created_at': datetime.utcnow()})

