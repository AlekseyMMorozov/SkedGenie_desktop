# src/domain/engagements/engagement_template_model.py
from __future__ import annotations
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class EngagementTemplate(BaseModel):
    """
    Шаблон задействования — конкретная роль или вид работ.
    Наследует правила от EngagementType.
    """
    id: UUID = Field(default_factory=uuid4)
    type_id: UUID = Field(..., description="ID типа, которому принадлежит шаблон")

    name: str = Field(..., min_length=1, description="Полное название (для списков)")
    short_name: str = Field(..., min_length=1, max_length=10, description="Краткое имя для ячейки графика")

    # Переопределение цвета (если нужно выделить конкретный шаблон)
    custom_color_hex: str | None = Field(None, description="Если None, используется цвет типа")

    def get_effective_color(self, type_color: str) -> str:
        return self.custom_color_hex if self.custom_color_hex else type_color