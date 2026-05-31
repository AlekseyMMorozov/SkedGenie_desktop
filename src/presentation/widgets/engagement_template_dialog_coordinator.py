# src/presentation/widgets/engagement_template_dialog_coordinator.py
"""Координатор диалога шаблонов задействований."""
from __future__ import annotations

import logging
from tkinter import messagebox
from typing import Callable, List, Optional, Union
from uuid import UUID

import customtkinter as ctk

from src.application.schemas.engagement_schemas import (
    EngagementTemplateCreateSchema,
    EngagementTemplateReadSchema,
    EngagementTemplateUpdateSchema,
    EngagementTypeReadSchema,
)
from src.core.logging_config import log_ui_event, log_user_action, log_user_error
from src.domain.engagements.engagement_exceptions import DuplicateEngagementNameError
from src.presentation.async_bridge import AsyncBridge
from src.presentation.controllers.engagement_template_controller import EngagementTemplateController
from src.presentation.controllers.engagement_type_controller import EngagementTypeController
from src.presentation.dialogs.engagement_template_dialog import EngagementTemplateDialog


class EngagementTemplateDialogCoordinator:
    """Управление жизненным циклом диалога шаблона задействования."""

    def __init__(
        self,
        master: ctk.CTk,
        template_controller: EngagementTemplateController,
        type_controller: EngagementTypeController,
        bridge: AsyncBridge,
        logger: logging.Logger,
        on_success: Callable[[], None],
    ) -> None:
        self._master = master
        self._template_controller = template_controller
        self._type_controller = type_controller
        self._bridge = bridge
        self._logger = logger
        self._on_success = on_success

    def open_create_dialog(self) -> None:
        """Загрузить типы и открыть диалог создания."""
        log_ui_event(self._logger, "EngagementTemplateDialogCoordinator", "open_create", "")
        self._bridge.run(
            self._type_controller.get_all(),
            on_success=lambda types: self._open_dialog(None, types),
            on_error=lambda exc: self._on_load_types_error(exc),
        )

    def open_edit_dialog(self, template: EngagementTemplateReadSchema) -> None:
        """Загрузить типы и открыть диалог редактирования."""
        log_ui_event(self._logger, "EngagementTemplateDialogCoordinator", "open_edit", f"id={template.id}")
        self._bridge.run(
            self._type_controller.get_all(),
            on_success=lambda types: self._open_dialog(template, types),
            on_error=lambda exc: self._on_load_types_error(exc),
        )

    def open_view_dialog(self, template: EngagementTemplateReadSchema) -> None:
        """Загрузить типы и открыть диалог просмотра."""
        log_ui_event(self._logger, "EngagementTemplateDialogCoordinator", "open_view", f"id={template.id}")
        self._bridge.run(
            self._type_controller.get_all(),
            on_success=lambda types: self._open_dialog(template, types, view_only=True),
            on_error=lambda exc: self._on_load_types_error(exc),
        )

    def _open_dialog(
        self,
        template: Optional[EngagementTemplateReadSchema],
        available_types: List[EngagementTypeReadSchema],
        view_only: bool = False,
    ) -> None:
        mode = "view" if view_only else ("edit" if template else "create")
        EngagementTemplateDialog(
            master=self._master,
            logger=self._logger,
            on_save=self._dispatch_save,
            mode=mode,
            template=template,
            available_types=available_types,
        )

    def _on_load_types_error(self, exc: Exception) -> None:
        log_user_error(self._logger, "load_engagement_types_for_template", str(exc))
        messagebox.showerror("Ошибка", f"Не удалось загрузить типы задействований: {exc}", parent=self._master)

    def _dispatch_save(
        self,
        template_id: Optional[UUID],
        schema: Union[EngagementTemplateCreateSchema, EngagementTemplateUpdateSchema],
    ) -> None:
        if template_id is None:
            self._execute_create(schema)
        else:
            self._execute_update(template_id, schema)

    def _execute_create(self, schema: EngagementTemplateCreateSchema) -> None:
        self._bridge.run(
            self._template_controller.create(schema),
            on_success=self._on_create_success,
            on_error=lambda exc: self._on_create_error(exc, schema),
        )

    def _on_create_success(self, created: EngagementTemplateReadSchema) -> None:
        log_user_action(self._logger, "create_engagement_template_success", f"id={created.id}, name={created.name}")
        self._on_success()

    def _on_create_error(self, exc: Exception, schema: EngagementTemplateCreateSchema) -> None:
        if isinstance(exc, DuplicateEngagementNameError):
            messagebox.showwarning("Ошибка", f"Шаблон '{exc.name}' уже существует", parent=self._master)
        else:
            log_user_error(self._logger, "create_engagement_template", str(exc))
            messagebox.showerror("Ошибка", f"Не удалось создать шаблон: {exc}", parent=self._master)

    def _execute_update(self, template_id: UUID, schema: EngagementTemplateUpdateSchema) -> None:
        self._bridge.run(
            self._template_controller.update(template_id, schema),
            on_success=self._on_update_success,
            on_error=lambda exc: self._on_update_error(exc, template_id),
        )

    def _on_update_success(self, updated: EngagementTemplateReadSchema) -> None:
        log_user_action(self._logger, "update_engagement_template_success", f"id={updated.id}")
        self._on_success()

    def _on_update_error(self, exc: Exception, template_id: UUID) -> None:
        if isinstance(exc, DuplicateEngagementNameError):
            messagebox.showwarning("Ошибка", f"Шаблон '{exc.name}' уже существует", parent=self._master)
        else:
            log_user_error(self._logger, "update_engagement_template", str(exc))
            messagebox.showerror("Ошибка", f"Не удалось обновить шаблон: {exc}", parent=self._master)
