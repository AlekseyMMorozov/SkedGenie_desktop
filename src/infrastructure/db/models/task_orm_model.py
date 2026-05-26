# src/infrastructure/db/models/task_orm_model.py
"""
ORM-модель задачи планирования для SQLAlchemy.

Определяет структуру таблицы ``planning_tasks`` в БД (SQLite/PostgreSQL).
Изолирована от Domain-модели (:class:`PlanningTask`) — маппинг выполняется
в репозитории (:class:`TaskSQLAlchemyRepository`).
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, Date
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.async_database_session import Base


class TaskORMModel(Base):
    """ORM-модель задачи планирования.

    Attributes:
        __tablename__: Имя таблицы в БД.
        id: Первичный ключ (UUID, генерируется автоматически).
        name: Название задачи (уникальное, не более 255 символов).
        period_type: Тип периода планирования (неделя/месяц/год/кастом).
        reference_date: Опорная дата для расчёта границ периода
            (соответствует ``anchor_date`` в :class:`PlanningTask`).
        period_start: Начало периода планирования (рассчитывается автоматически).
        period_end: Конец периода планирования (рассчитывается автоматически).
        employee_ids: JSON-строка со списком UUID сотрудников.
        engagement_ids: JSON-строка со списком UUID типов задействований
            (соответствует ``duty_type_ids`` в :class:`PlanningTask`).
        reference_id: Внешний идентификатор/ссылка (опционально, до 255 символов).
        created_at: Дата и время создания записи.
        updated_at: Дата и время последнего обновления.
    """

    __tablename__ = "planning_tasks"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,  # Защита от дубликатов на уровне БД
    )
    period_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    reference_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    period_start: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    period_end: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    employee_ids: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="[]",
    )
    engagement_ids: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="[]",
    )
    reference_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        default=None,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    def __repr__(self) -> str:
        """Строковое представление для отладки."""
        return (
            f"<TaskORMModel(id={self.id}, name='{self.name}', "
            f"period_type={self.period_type})>"
        )
