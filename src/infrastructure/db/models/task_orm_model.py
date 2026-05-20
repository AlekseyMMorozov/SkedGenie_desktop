# src/infrastructure/db/models/task_orm_model.py

"""SQLAlchemy 2.0 ORM-модель для таблицы planning_tasks."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import DateTime, Date, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.async_database_session import Base


class TaskORMModel(Base):
    """ORM-представление задачи планирования.

    Хранит данные в форматах, совместимых с SQLite. Сложные типы
    (UUID, Enum, списки) сериализуются на уровне маппинга в репозитории.
    При миграции на PostgreSQL достаточно заменить типы колонок без изменения домена.
    """
    __tablename__ = "planning_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="UUID задачи")
    name: Mapped[str] = mapped_column(String, nullable=False, comment="Название задачи")
    period_type: Mapped[str] = mapped_column(String, nullable=False, comment="Тип периода (week/month/year/custom)")
    anchor_date: Mapped[date] = mapped_column(Date, nullable=False, comment="Опорная дата")
    custom_start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, comment="Начало кастомного периода")
    custom_end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, comment="Окончание кастомного периода")
    start_date: Mapped[date] = mapped_column(Date, nullable=False, comment="Фактическая дата начала периода")
    end_date: Mapped[date] = mapped_column(Date, nullable=False, comment="Фактическая дата окончания периода")
    employee_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list, comment="Список UUID сотрудников")
    duty_type_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list, comment="Список UUID типов задействований")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="Время создания записи")
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="Время последнего изменения")

    def __repr__(self) -> str:
        return f"<TaskORMModel(id={self.id}, name='{self.name}')>"

