# src/infrastructure/db/models/engagement_template_orm_model.py
"""ORM-модель шаблона задействования."""
from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.async_database_session import Base


class EngagementTemplateORMModel(Base):
    """Шаблон задействования (конкретная роль/вид работ)."""
    __tablename__ = "engagement_templates"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    type_id: Mapped[UUID] = mapped_column(ForeignKey("engagement_types.id", ondelete="CASCADE"), nullable=False)

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    short_name: Mapped[str] = mapped_column(String(10), nullable=False)

    # Переопределение цвета
    custom_color_hex: Mapped[str | None] = mapped_column(String(7), nullable=True)

    def __repr__(self) -> str:
        return f"<EngagementTemplate(id={self.id}, name='{self.name}', short='{self.short_name}')>"
