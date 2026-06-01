# src/presentation/dialogs/engagement_template_select_dialog.py
"""
Диалоговое окно для выбора шаблонов задействований из списка.
Используется внутри TaskDialog для привязки шаблонов к задаче (Вариант A).
"""
from __future__ import annotations

import logging
from typing import List, Optional
from uuid import UUID

import customtkinter as ctk

from src.application.schemas.engagement_schemas import EngagementTemplateReadSchema
from src.core.logging_config import log_ui_event


class EngagementTemplateSelectDialog(ctk.CTkToplevel):
    """Модальный диалог выбора шаблонов задействований с чекбоксами."""

    def __init__(
        self,
        master: ctk.CTk,
        logger: logging.Logger,
        templates: List[EngagementTemplateReadSchema],
        selected_ids: Optional[List[UUID]] = None,
        **kwargs,
    ) -> None:
        super().__init__(master, **kwargs)
        self._logger = logger
        self._templates = templates
        self._result_ids = set(selected_ids or [])
        self._checkboxes: dict[UUID, ctk.BooleanVar] = {}
        self._result: Optional[List[UUID]] = None

        self._setup_window()
        self._create_widgets()

    def _setup_window(self) -> None:
        self.title("Выбор шаблонов задействований")
        self.geometry("460x380")
        self.resizable(False, False)
        self.transient(self.master)
        self.grab_set()
        self.focus_force()

    def _create_widgets(self) -> None:
        hint = ctk.CTkLabel(
            self,
            text="Отметьте шаблоны, которые будут доступны в рамках задачи:",
            anchor="w",
        )
        hint.pack(fill="x", padx=15, pady=(10, 5))

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=15, pady=(0, 10))

        for tpl in self._templates:
            var = ctk.BooleanVar(value=tpl.id in self._result_ids)
            display_text = f"{tpl.name}"
            if tpl.short_name:
                display_text += f" ({tpl.short_name})"
            cb = ctk.CTkCheckBox(scroll, text=display_text, variable=var)
            cb.pack(anchor="w", pady=3)
            self._checkboxes[tpl.id] = var

        if not self._templates:
            empty_label = ctk.CTkLabel(
                scroll, text="Нет доступных шаблонов", text_color="gray",
            )
            empty_label.pack(pady=20)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=(0, 10))

        ctk.CTkButton(
            btn_frame, text="Отмена", fg_color="gray40", hover_color="gray30",
            command=self._on_cancel,
        ).pack(side="left", fill="x", expand=True, padx=(0, 5))

        ctk.CTkButton(
            btn_frame, text="Применить", command=self._on_apply,
        ).pack(side="left", fill="x", expand=True, padx=(5, 0))

    def _on_apply(self) -> None:
        log_ui_event(self._logger, "EngagementTemplateSelectDialog.btn_apply", "click")
        self._result = [uid for uid, var in self._checkboxes.items() if var.get()]
        self.destroy()

    def _on_cancel(self) -> None:
        log_ui_event(self._logger, "EngagementTemplateSelectDialog.btn_cancel", "click")
        self._result = None
        self.destroy()

    def get_result(self) -> Optional[List[UUID]]:
        """Возвращает список выбранных ID или None при отмене."""
        return self._result
