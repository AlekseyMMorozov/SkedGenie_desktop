# src/infrastructure/db/models/employee_orm_model.py
"""
ORM-модель сотрудника для SQLAlchemy.

Определяет структуру таблицы ``employees`` в БД (SQLite/PostgreSQL).
Изолирована от Domain-модели (:class:`Employee`) — маппинг выполняется
в репозитории (:class:`EmployeeSQLAlchemyRepository`).

Ключевые особенности:
    - Условные UNIQUE-ограничения на ``email`` и ``tab_number``
      (срабатывают только если значение не NULL) через
      ``Index(sqlite_where=...)``.
    - ``engagement_ids`` хранится как JSON-строка (согласованно с
      :class:`TaskORMModel`). Позже может быть вынесено в отдельную
      many-to-many таблицу при реализации Engagement.
    - ``display_name`` хранится в БД для быстрого чтения без
      повторного вычисления в Domain.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Date, DateTime, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.async_database_session import Base


class EmployeeORMModel(Base):
    """ORM-модель сотрудника.

    Attributes:
        __tablename__: Имя таблицы в БД.
        id: Первичный ключ (UUID, генерируется автоматически).
        last_name: Фамилия (обязательно).
        first_name: Имя (обязательно).
        middle_name: Отчество (опционально).
        display_name: Представление для графика (вычисляется в Domain).
        position: Должность.
        rank: Звание (опционально).
        tab_number: Табельный номер (уникально, если не NULL).
        email: Электронная почта (уникально, если не NULL).
        phone: Телефон.
        birth_date: Дата рождения.
        is_active: Статус активности (False — в архиве).
        notes: Произвольные заметки.
        engagement_ids: JSON-строка со списком UUID задействований.
        created_at: Дата и время создания записи.
        updated_at: Дата и время последнего обновления.
    """

    __tablename__ = "employees"

    # Идентификация
    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )
    last_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    first_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    middle_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    display_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    # Служебные данные
    position: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
    )
    rank: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    tab_number: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    email: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
    )
    phone: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    birth_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )

    # Статус и заметки
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Допуски к видам задействований (JSON-строка со списком UUID)
    engagement_ids: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="[]",
    )

    # Метки времени
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

    # Условные UNIQUE-индексы: уникально только если значение не NULL.
    __table_args__ = (
        Index(
            "uq_employee_email_notnull",
            "email",
            unique=True,
            sqlite_where=text("email IS NOT NULL"),
        ),
        Index(
            "uq_employee_tab_number_notnull",
            "tab_number",
            unique=True,
            sqlite_where=text("tab_number IS NOT NULL"),
        ),
        # Индекс для быстрого получения только активных сотрудников.
        Index("ix_employee_is_active", "is_active"),
    )

    def __repr__(self) -> str:
        """Строковое представление для отладки."""
        status = "active" if self.is_active else "archived"
        return (
            f"<EmployeeORMModel(id={self.id}, "
            f"display_name='{self.display_name}', "
            f"status={status})>"
        )
