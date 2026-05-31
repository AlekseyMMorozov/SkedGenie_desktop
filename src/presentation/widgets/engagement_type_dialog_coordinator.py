# src/presentation/widgets/engagement_type_dialog_coordinator.py
"""Координатор диалога типов задействований."""
from __future__ import annotations

import logging
from tkinter import messagebox
from typing import Callable, Optional, Union
from uuid import UUID

import customtkinter as ctk

from src.application.schemas.engagement_schemas import (
    EngagementTypeCreateSchema,
    EngagementTypeReadSchema,
    EngagementTypeUpdateSchema,
)
from src.core.logging_config import log_ui_event, log_user_action, log_user_error
from src.domain.engagements.engagement_exceptions import DuplicateEngagementNameError
from src.presentation.async_bridge import AsyncBridge
from src.presentation.controllers.engagement_type_controller import EngagementTypeController
from src.presentation.dialogs.engagement_type_dialog import EngagementTypeDialog


class EngagementTypeDialogCoordinator:
    """Управление жизненным циклом диалога типа задействования."""

    def __init__(
        self,
        master: ctk.CTk,
        controller: EngagementTypeController,
        bridge: AsyncBridge,
        logger: logging.Logger,
        on_success: Callable[[], None],
    ) -> None:
        self._master = master
        self._controller = controller
        self._bridge = bridge
        self._logger = logger
        self._on_success = on_success

    def open_create_dialog(self) -> None:
        """Открыть диалог создания нового типа."""
        log_ui_event(self._logger, "EngagementTypeDialogCoordinator", "open_create", "")
        EngagementTypeDialog(
            master=self._master,
            logger=self._logger,
            on_save=self._dispatch_save,
            mode="create",
        )

    def open_edit_dialog(self, engagement_type: EngagementTypeReadSchema) -> None:
        """Открыть диалог редактирования типа."""
        log_ui_event(self._logger, "EngagementTypeDialogCoordinator", "open_edit", f"id={engagement_type.id}")
        EngagementTypeDialog(
            master=self._master,
            logger=self._logger,
            on_save=self._dispatch_save,
            mode="edit",
            engagement_type=engagement_type,
        )

    def open_view_dialog(self, engagement_type: EngagementTypeReadSchema) -> None:
        """Открыть диалог просмотра типа (только чтение)."""
        log_ui_event(self._logger, "EngagementTypeDialogCoordinator", "open_view", f"id={engagement_type.id}")
        EngagementTypeDialog(
            master=self._master,
            logger=self._logger,
            on_save=lambda *_: None,
            mode="view",
            engagement_type=engagement_type,
        )

    def _dispatch_save(
        self,
        type_id: Optional[UUID],
        schema: Union[EngagementTypeCreateSchema, EngagementTypeUpdateSchema],
    ) -> None:
        if type_id is None:
            self._execute_create(schema)
        else:
            self._execute_update(type_id, schema)

    def _execute_create(self, schema: EngagementTypeCreateSchema) -> None:
        self._bridge.run(
            self._controller.create(schema),
            on_success=self._on_create_success,
            on_error=lambda exc: self._on_create_error(exc, schema),
        )

    def _on_create_success(self, created: EngagementTypeReadSchema) -> None:
        log_user_action(self._logger, "create_engagement_type_success", f"id={created.id}, name={created.name}")
        self._on_success()

    def _on_create_error(self, exc: Exception, schema: EngagementTypeCreateSchema) -> None:
        if isinstance(exc, DuplicateEngagementNameError):
            messagebox.showwarning("Ошибка", f"Тип '{exc.name}' уже существует", parent=self._master)
        else:
            log_user_error(self._logger, "create_engagement_type", str(exc))
            messagebox.showerror("Ошибка", f"Не удалось создать тип: {exc}", parent=self._master)

    def _execute_update(self, type_id: UUID, schema: EngagementTypeUpdateSchema) -> None:
        self._bridge.run(
            self._controller.update(type_id, schema),
            on_success=self._on_update_success,
            on_error=lambda exc: self._on_update_error(exc, type_id),
        )

    def _on_update_success(self, updated: EngagementTypeReadSchema) -> None:
        log_user_action(self._logger, "update_engagement_type_success", f"id={updated.id}")
        self._on_success()

    def _on_update_error(self, exc: Exception, type_id: UUID) -> None:
        if isinstance(exc, DuplicateEngagementNameError):
            messagebox.showwarning("Ошибка", f"Тип '{exc.name}' уже существует", parent=self._master)
        else:
            log_user_error(self._logger, "update_engagement_type", str(exc))
            messagebox.showerror("Ошибка", f"Не удалось обновить тип: {exc}", parent=self._master)
