"""
Файл: src/infrastructure/db/models/task_orm_model.py
Описание: ORM-модель для сущности PlanningTask.
Архитектура: Infrastructure слой. Изолирована от Domain через репозиторий.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID, uuid4  # ← Добавили uuid4

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.async_database_session import Base


class TaskORMModel(Base):
    """ORM-представление задачи планирования."""

    __tablename__ = "planning_tasks"

    # ✅ ИСПРАВЛЕНО: uuid4 — функция генерации нового UUID
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    period_type: Mapped[str] = mapped_column(String(50), nullable=False)
    period_start: Mapped[date] = mapped_column(nullable=False)
    period_end: Mapped[date] = mapped_column(nullable=False)
    reference_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<TaskORMModel(id={self.id}, name='{self.name}')>"

