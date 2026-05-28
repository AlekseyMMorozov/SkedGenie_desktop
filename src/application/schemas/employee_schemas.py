"""
Pydantic-схемы для DTO сотрудников.

Архитектура: Application слой. Валидация на границе Domain:
    - :class:`EmployeeCreateSchema` — создание нового сотрудника.
    - :class:`EmployeeUpdateSchema` — частичное обновление существующего.
    - :class:`EmployeeReadSchema` — DTO для отображения в UI (включает
      вычисленные ``display_name`` и ``full_name``).

Симметрично :mod:`src.application.schemas.task_schemas`.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.domain.employees.employee_exceptions import InvalidEmployeeNameError

# Простой regex для email (без зависимости email-validator).
_EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)


class EmployeeCreateSchema(BaseModel):
    """Схема создания сотрудника.

    Обязательные поля: ``last_name``, ``first_name``.
    Отчество (``middle_name``) опционально.
    Остальные поля могут быть заполнены позже при редактировании.

    Новый сотрудник создаётся активным по умолчанию (is_active=True).
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    # ФИО (обязательные)
    last_name: str = Field(
        ..., min_length=1, max_length=100,
        description="Фамилия",
    )
    first_name: str = Field(
        ..., min_length=1, max_length=100,
        description="Имя",
    )
    middle_name: Optional[str] = Field(
        default=None, max_length=100,
        description="Отчество",
    )

    # Служебные данные (опциональные)
    position: Optional[str] = Field(
        default=None, max_length=200,
        description="Должность",
    )
    rank: Optional[str] = Field(
        default=None, max_length=100,
        description="Звание",
    )
    tab_number: Optional[str] = Field(
        default=None, max_length=50,
        description="Табельный номер",
    )
    email: Optional[str] = Field(
        default=None, max_length=200,
        description="Электронная почта",
    )
    phone: Optional[str] = Field(
        default=None, max_length=50,
        description="Телефон",
    )
    birth_date: Optional[date] = Field(
        default=None,
        description="Дата рождения",
    )

    # Заметки
    notes: Optional[str] = Field(
        default=None, max_length=2000,
        description="Произвольные заметки",
    )

    # Допуски к видам задействований
    engagement_ids: Optional[List[UUID]] = Field(
        default=None,
        description="ID видов задействований, к которым допущен сотрудник",
    )

    # Статус активности (новый сотрудник активен по умолчанию)
    is_active: bool = Field(
        default=True,
        description="Активен ли сотрудник (по умолчанию True)",
    )

    # ------------------------------------------------------------------
    # Валидаторы
    # ------------------------------------------------------------------
    @field_validator("last_name", "first_name", "middle_name")
    @classmethod
    def _strip_and_validate_name(cls, value: Optional[str], info) -> Optional[str]:
        """Нормализация и проверка полей ФИО."""
        if value is None:
            return value
        value = value.strip()
        if not value:
            field_name = info.field_name
            label = {
                "last_name": "Фамилия",
                "first_name": "Имя",
                "middle_name": "Отчество",
            }.get(field_name, field_name)
            raise InvalidEmployeeNameError(
                f"{label} не может быть пустой строкой"
            )
        return value

    @field_validator("tab_number")
    @classmethod
    def _normalize_tab_number(cls, value: Optional[str]) -> Optional[str]:
        """Нормализация табельного номера: trim + uppercase."""
        if value is None:
            return None
        value = value.strip().upper()
        return value if value else None

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: Optional[str]) -> Optional[str]:
        """Проверка формата email (если заполнен)."""
        if value is None:
            return None
        value = value.strip().lower()
        if not value:
            return None
        if not _EMAIL_REGEX.match(value):
            raise ValueError(f"Некорректный формат email: {value!r}")
        return value

    @field_validator("phone")
    @classmethod
    def _normalize_phone(cls, value: Optional[str]) -> Optional[str]:
        """Нормализация телефона: только trim (формат не фиксируем)."""
        if value is None:
            return None
        value = value.strip()
        return value if value else None

    @field_validator("birth_date")
    @classmethod
    def _validate_birth_date(cls, value: Optional[date]) -> Optional[date]:
        """Дата рождения не может быть в будущем."""
        if value is None:
            return None
        if value > date.today():
            raise ValueError(
                f"Дата рождения не может быть в будущем: {value.isoformat()}"
            )
        return value


class EmployeeUpdateSchema(BaseModel):
    """Схема частичного обновления сотрудника.

    Обязательное поле: только ``id``. Все остальные опциональны —
    обновляются только переданные значения.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID = Field(..., description="Уникальный идентификатор сотрудника")

    last_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    first_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    middle_name: Optional[str] = Field(default=None, max_length=100)

    position: Optional[str] = Field(default=None, max_length=200)
    rank: Optional[str] = Field(default=None, max_length=100)
    tab_number: Optional[str] = Field(default=None, max_length=50)
    email: Optional[str] = Field(default=None, max_length=200)
    phone: Optional[str] = Field(default=None, max_length=50)
    birth_date: Optional[date] = Field(default=None)

    is_active: Optional[bool] = Field(
        default=None,
        description="Активен ли сотрудник (False — в архиве)",
    )
    notes: Optional[str] = Field(default=None, max_length=2000)

    engagement_ids: Optional[List[UUID]] = Field(
        default=None,
        description="Полный список допусков (заменяет предыдущий)",
    )

    # Переиспользуем валидаторы из CreateSchema для единообразия
    @field_validator("last_name", "first_name", "middle_name")
    @classmethod
    def _strip_and_validate_name(cls, value: Optional[str], info) -> Optional[str]:
        if value is None:
            return value
        value = value.strip()
        if not value:
            field_name = info.field_name
            label = {
                "last_name": "Фамилия",
                "first_name": "Имя",
                "middle_name": "Отчество",
            }.get(field_name, field_name)
            raise InvalidEmployeeNameError(
                f"{label} не может быть пустой строкой"
            )
        return value

    @field_validator("tab_number")
    @classmethod
    def _normalize_tab_number(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip().upper()
        return value if value else None

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip().lower()
        if not value:
            return None
        if not _EMAIL_REGEX.match(value):
            raise ValueError(f"Некорректный формат email: {value!r}")
        return value

    @field_validator("phone")
    @classmethod
    def _normalize_phone(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        return value if value else None

    @field_validator("birth_date")
    @classmethod
    def _validate_birth_date(cls, value: Optional[date]) -> Optional[date]:
        if value is None:
            return None
        if value > date.today():
            raise ValueError(
                f"Дата рождения не может быть в будущем: {value.isoformat()}"
            )
        return value


class EmployeeReadSchema(BaseModel):
    """Схема чтения сотрудника (для отображения в UI).

    Включает вычисленные поля:
        - ``display_name``: короткое имя для графика (например, "Иванов И.С.").
        - ``full_name``: полное ФИО (например, "Иванов Иван Сергеевич").

    UI не должен вычислять эти поля самостоятельно — получает готовые.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    last_name: str
    first_name: str
    middle_name: Optional[str] = None

    # Вычисляемые поля (заполняются из Domain Employee)
    display_name: str
    full_name: Optional[str] = Field(
        default=None,
        description="Полное ФИО ('Фамилия Имя Отчество'). "
                    "Если не передано явно — вычисляется в контроллере.",
    )

    position: Optional[str] = None
    rank: Optional[str] = None
    tab_number: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    birth_date: Optional[date] = None

    is_active: bool = True
    notes: Optional[str] = None

    engagement_ids: Optional[List[UUID]] = None

    created_at: datetime
    updated_at: Optional[datetime] = None
