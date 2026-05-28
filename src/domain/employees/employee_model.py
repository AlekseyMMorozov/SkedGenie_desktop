# src/domain/employees/employee_model.py
"""
Доменная модель сотрудника для SkedGenie.

Описывает сущность :class:`Employee` — контейнер персональных данных
сотрудника и его допусков к видам задействований.

Архитектура:
    - Domain-слой, не зависит от Infrastructure (ORM/БД) и Presentation (UI).
    - ``display_name`` вычисляется статично (базовый формат "Фамилия И.О.")
      через :func:`model_validator`. Расширенный формат для разрешения
      конфликтов однофамильцев реализуется в Application-слое
      (:meth:`EmployeeController.resolve_display_names`).
    - Связь с видами задействований хранится как список UUID
      (``engagement_ids``). Сама many-to-many таблица создаётся
      в Infrastructure-слое.

Имена и инициалы:
    - Базовый формат: "Иванов И.С." (фамилия + инициал имени + инициал отчества).
    - Если отчество не указано: "Иванов И." (инициал имени без отчества).
    - Для разрешения конфликтов однофамильцев Application-слой расширяет
      инициал имени до первых букв, дающих различие.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.domain.employees.employee_exceptions import (
    EmployeeDomainError,
    InvalidEmployeeNameError,
)


class Employee(BaseModel):
    """Доменная сущность: Сотрудник.

    Attributes:
        id: Уникальный идентификатор (UUID).
        last_name: Фамилия (обязательно).
        first_name: Имя (обязательно).
        middle_name: Отчество (опционально).
        display_name: Представление для графика (вычисляется автоматически).
        position: Должность.
        rank: Звание (опционально).
        tab_number: Табельный номер.
        email: Электронная почта.
        phone: Телефон.
        birth_date: Дата рождения.
        is_active: Активен ли сотрудник (False — в архиве).
        notes: Произвольные заметки.
        engagement_ids: ID видов задействований, к которым допущен сотрудник.
        created_at: Дата создания записи.
        updated_at: Дата последнего обновления.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Идентификация
    id: UUID = Field(default_factory=uuid4)
    last_name: str = Field(..., min_length=1, max_length=100)
    first_name: str = Field(..., min_length=1, max_length=100)
    middle_name: Optional[str] = Field(default=None, max_length=100)

    # Вычисляемое поле (для графика).
    # Заполняется в _build_display_name после валидации остальных полей.
    display_name: str = Field(default="")

    # Служебные данные
    position: Optional[str] = Field(default=None, max_length=200)
    rank: Optional[str] = Field(default=None, max_length=100)  # ✅ Звание
    tab_number: Optional[str] = Field(default=None, max_length=50)
    email: Optional[str] = Field(default=None, max_length=200)
    phone: Optional[str] = Field(default=None, max_length=50)
    birth_date: Optional[date] = Field(default=None)

    # Статус
    is_active: bool = Field(default=True)
    notes: Optional[str] = Field(default=None, max_length=2000)

    # Допуски к видам задействований (связь many-to-many, хранится в отдельной таблице).
    engagement_ids: List[UUID] = Field(default_factory=list)

    # Метки времени
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default=None)

    @model_validator(mode="after")
    def _validate_and_build(self) -> "Employee":
        """Валидация ФИО и построение базового display_name.

        Выполняется после первичной валидации полей (mode='after').
        """
        # Нормализация пробелов
        last_name = self.last_name.strip()
        first_name = self.first_name.strip()
        middle_name = (
            self.middle_name.strip() if self.middle_name else None
        )

        if not last_name:
            raise InvalidEmployeeNameError(
                "Фамилия сотрудника не может быть пустой"
            )
        if not first_name:
            raise InvalidEmployeeNameError(
                "Имя сотрудника не может быть пустым"
            )

        # Записываем нормализованные значения обратно
        object.__setattr__(self, "last_name", last_name)
        object.__setattr__(self, "first_name", first_name)
        object.__setattr__(self, "middle_name", middle_name)

        # Строим базовый display_name
        object.__setattr__(
            self,
            "display_name",
            self._build_basic_display_name(last_name, first_name, middle_name),
        )

        return self

    @staticmethod
    def _build_basic_display_name(
        last_name: str,
        first_name: str,
        middle_name: Optional[str],
    ) -> str:
        """Построение базового формата "Фамилия И.О.".

        Args:
            last_name: Фамилия (непустая, после strip()).
            first_name: Имя (непустое, после strip()).
            middle_name: Отчество (может быть None или пустой строкой).

        Returns:
            Строка вида "Иванов И.С." или "Иванов И." (без отчества).

        Raises:
            EmployeeDomainError: Если не удалось построить display_name.
        """
        try:
            first_initial = first_name[0].upper()

            if middle_name:
                middle_initial = middle_name[0].upper()
                return f"{last_name} {first_initial}.{middle_initial}."
            else:
                return f"{last_name} {first_initial}."
        except (IndexError, TypeError) as exc:
            raise EmployeeDomainError(
                f"Не удалось построить display_name из "
                f"last_name={last_name!r}, first_name={first_name!r}, "
                f"middle_name={middle_name!r}: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Вспомогательные методы
    # ------------------------------------------------------------------
    def get_full_name(self) -> str:
        """Возвращает полное ФИО сотрудника ("Фамилия Имя Отчество").

        Используется в карточке сотрудника и отчётах.
        """
        parts = [self.last_name, self.first_name]
        if self.middle_name:
            parts.append(self.middle_name)
        return " ".join(parts)

    def toggle_active(self) -> None:
        """Переключает статус активности (активен ↔ в архиве)."""
        object.__setattr__(self, "is_active", not self.is_active)
        object.__setattr__(self, "updated_at", datetime.utcnow())

    def with_updated_display_name(self, new_display_name: str) -> "Employee":
        """Возвращает копию сотрудника с изменённым display_name.

        Используется в Application-слое при разрешении конфликтов
        однофамильцев (``EmployeeController.resolve_display_names``).
        """
        return self.model_copy(update={"display_name": new_display_name})

    def clone(self) -> "Employee":
        """Создаёт копию сотрудника с новым ID (для шаблонов)."""
        return self.model_copy(
            update={"id": uuid4(), "created_at": datetime.utcnow(), "updated_at": None}
        )
