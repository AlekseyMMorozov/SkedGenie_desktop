# src/domain/tasks/task_exceptions.py

"""Исключения доменного слоя для сущности PlanningTask."""

from __future__ import annotations

class TaskDomainError(Exception):
    """Базовое исключение для валидации и инвариантов задачи планирования."""

class InvalidTaskNameError(TaskDomainError):
    """Возникает, если название задачи пустое или содержит только пробелы."""

class InvalidTaskPeriodError(TaskDomainError):
    """Возникает, если period_end <= period_start."""

class EmptyTaskReferenceError(TaskDomainError):
    """Возникает, если списки сотрудников или типов задействований пусты."""
