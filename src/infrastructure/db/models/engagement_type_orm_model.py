# src/infrastructure/db/models/engagement_type_orm_model.py
"""ORM-модель типа задействования."""
from __future__ import annotations

from datetime import time
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Float, String, Time
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.async_database_session import Base


class EngagementTypeORMModel(Base):
    """Тип задействования (правила и настройки по умолчанию)."""
    __tablename__ = "engagement_types"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    color_hex: Mapped[str] = mapped_column(String(7), nullable=False)

    duration_type: Mapped[str] = mapped_column(String(10), nullable=False, default="short")

    # Правила времени
    default_start_time: Mapped[time] = mapped_column(Time, nullable=False, default=time(8, 0))
    default_duration_hours: Mapped[float] = mapped_column(Float, nullable=False)

    # Ограничения
    min_duration_hours: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    max_duration_hours: Mapped[float] = mapped_column(Float, nullable=False)

    # Поведение
    allow_overlap: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    def __repr__(self) -> str:
        return f"<EngagementType(id={self.id}, name='{self.name}', category='{self.category}')>"
