# src/infrastructure/db/models/engagement_orm_model.py
from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, ForeignKey, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.async_database_session import Base

# Ассоциативная таблица для связи Many-to-Many с задачами планирования
# ИСПРАВЛЕНО: tasks -> planning_tasks
engagement_tasks = Table(
    "engagement_tasks",
    Base.metadata,
    Column("engagement_id", ForeignKey("engagements.id", ondelete="CASCADE"), primary_key=True),
    Column("task_id", ForeignKey("planning_tasks.id", ondelete="CASCADE"), primary_key=True),  # ✅ Было "tasks.id"
)


class EngagementORMModel(Base):
    """Экземпляр задействования (запись в графике)."""
    __tablename__ = "engagements"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    employee_id: Mapped[UUID] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    template_id: Mapped[UUID] = mapped_column(ForeignKey("engagement_templates.id", ondelete="RESTRICT"), nullable=False)

    start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Локальные переопределения
    short_name_override: Mapped[str | None] = mapped_column(String(10), nullable=True)
    color_override: Mapped[str | None] = mapped_column(String(7), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<Engagement(id={self.id}, employee={self.employee_id}, start={self.start_at})>"
