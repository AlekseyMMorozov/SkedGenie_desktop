# src/domain/engagements/engagement_exceptions.py
"""Исключения домена задействований."""
from __future__ import annotations

from uuid import UUID


class EngagementDomainError(Exception):
    """Базовое исключение домена задействований."""
    pass


class InvalidEngagementDurationError(EngagementDomainError):
    """Ошибка длительности задействования."""

    def __init__(self, duration_hours: float, min_hours: float, max_hours: float) -> None:
        self.duration_hours = duration_hours
        self.min_hours = min_hours
        self.max_hours = max_hours
        super().__init__(
            f"Длительность {duration_hours:.2f}ч выходит за пределы [{min_hours:.2f}ч; {max_hours:.2f}ч]"
        )


class EngagementOverlapError(EngagementDomainError):
    """Ошибка пересечения задействований."""

    def __init__(self, employee_id: UUID, start_at, end_at) -> None:
        self.employee_id = employee_id
        self.start_at = start_at
        self.end_at = end_at
        super().__init__(
            f"Сотрудник {employee_id} уже имеет несовместимое задействование в период "
            f"{start_at.strftime('%d.%m %H:%M')} - {end_at.strftime('%d.%m %H:%M')}"
        )


class DuplicateEngagementNameError(EngagementDomainError):
    """Дублирование названия шаблона или типа задействования."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Задействование с названием '{name}' уже существует.")


class InvalidColorError(EngagementDomainError):
    """Некорректный формат или значение цвета."""

    def __init__(self, color: str, reason: str) -> None:
        self.color = color
        self.reason = reason
        super().__init__(f"Недопустимый цвет '{color}': {reason}")
