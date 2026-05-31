# src/presentation/widgets/engagement_management_widget.py
"""Виджет управления задействованиями (обертка над списком)."""
from __future__ import annotations

import logging

import customtkinter as ctk

from src.application.services.engagement_color_service import EngagementColorService
from src.presentation.async_bridge import AsyncBridge
from src.presentation.controllers.engagement_template_controller import EngagementTemplateController
from src.presentation.controllers.engagement_type_controller import EngagementTypeController
from src.presentation.font_manager import get_font_manager
from src.presentation.widgets.engagement_list_widget import EngagementListWidget


class EngagementManagementWidget(ctk.CTkFrame):
    """Контейнер для списка задействований с заголовком."""

    def __init__(
            self,
            master: ctk.CTk,
            type_controller: EngagementTypeController,
            template_controller: EngagementTemplateController,
            bridge: AsyncBridge,
            logger: logging.Logger,
            color_service: EngagementColorService,
            **kwargs,
    ) -> None:
        super().__init__(master, **kwargs)
        self._type_controller = type_controller
        self._template_controller = template_controller
        self._bridge = bridge
        self._logger = logger
        self._color_service = color_service
        self._create_widgets()

    def _create_widgets(self) -> None:
        fm = get_font_manager()
        title_font = fm.get_font("section_title") if fm else ctk.CTkFont(size=20, weight="bold")

        header = ctk.CTkLabel(
            self, text="Задействования", font=title_font, anchor="w"
        )
        header.pack(fill="x", padx=20, pady=(20, 10))

        # ✅ Передаем color_service в список
        self._list_widget = EngagementListWidget(
            master=self,
            template_controller=self._template_controller,
            type_controller=self._type_controller,
            bridge=self._bridge,
            logger=self._logger,
            color_service=self._color_service,
        )
        self._list_widget.pack(fill="both", expand=True)
