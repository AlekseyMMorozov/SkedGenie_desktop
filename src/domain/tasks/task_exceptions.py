# src/domain/tasks/task_exceptions.py
"""
Исключения предметной области задач планирования.

Предоставляет иерархию исключений для ошибок валидации Domain-моделей:
    - :class:`TaskDomainError` — базовое исключение для всех ошибок Domain.
    - :class:`InvalidTaskNameError` — некорректное имя задачи.
    - :class:`InvalidTaskPeriodError` — некорректный период планирования.
    - :class:`EmptyTaskReferenceError` — отсутствие опорной даты или границ периода.
    - :class:`DuplicateTaskNameError` — попытка создать задачу с уже существующим названием.
"""
from __future__ import annotations


class TaskDomainError(Exception):
    """Базовое исключение для ошибок предметной области задач."""
    pass


class InvalidTaskNameError(TaskDomainError):
    """Имя задачи не соответствует правилам валидации."""
    pass


class InvalidTaskPeriodError(TaskDomainError):
    """Период планирования некорректен (например, end < start)."""
    pass


class EmptyTaskReferenceError(TaskDomainError):
    """Отсутствует опорная дата или границы периода."""
    pass


class DuplicateTaskNameError(TaskDomainError):
    """Попытка создать или обновить задачу с уже существующим названием.

    Attributes:
        duplicate_name: Название, которое вызвало конфликт.
    """

    def __init__(self, duplicate_name: str) -> None:
        self.duplicate_name = duplicate_name
        super().__init__(
            f"Задача с названием '{duplicate_name}' уже существует"
        )
