# src/domain/employees/employee_exceptions.py
"""
Исключения предметной области сотрудников.

Иерархия:
    - :class:`EmployeeDomainError` — базовое исключение.
    - :class:`InvalidEmployeeNameError` — некорректное ФИО.
    - :class:`DuplicateEmployeeError` — дубликат email или табельного номера.
    - :class:`EmployeeInUseError` — попытка удалить сотрудника,
      используемого в задачах планирования.
"""
from __future__ import annotations

from uuid import UUID


class EmployeeDomainError(Exception):
    """Базовое исключение для ошибок предметной области сотрудников."""


class InvalidEmployeeNameError(EmployeeDomainError):
    """ФИО сотрудника не соответствует правилам валидации."""


class DuplicateEmployeeError(EmployeeDomainError):
    """Попытка создать сотрудника с уже существующими email или табельным номером.

    Attributes:
        duplicate_field: Поле-причина конфликта ('email' или 'tab_number').
        duplicate_value: Значение, вызвавшее конфликт.
    """

    def __init__(self, duplicate_field: str, duplicate_value: str) -> None:
        self.duplicate_field = duplicate_field
        self.duplicate_value = duplicate_value
        super().__init__(
            f"Сотрудник с {duplicate_field}='{duplicate_value}' уже существует"
        )


class EmployeeInUseError(EmployeeDomainError):
    """Попытка удалить сотрудника, используемого в задачах планирования.

    Attributes:
        employee_id: ID сотрудника.
        employee_name: Отображаемое имя сотрудника (для сообщения).
        task_count: Количество задач, в которых используется сотрудник.
    """

    def __init__(
        self,
        employee_id: UUID,
        employee_name: str,
        task_count: int,
    ) -> None:
        self.employee_id = employee_id
        self.employee_name = employee_name
        self.task_count = task_count
        super().__init__(
            f"Сотрудник '{employee_name}' используется в {task_count} "
            f"задачах планирования. Удаление невозможно без предварительного "
            f"исключения из задач или архивации."
        )
