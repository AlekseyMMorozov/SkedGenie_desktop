# src/presentation/widgets/employee_dialog_coordinator.py
"""
Координатор диалогов сотрудников и CRUD-операций.

Ответственность:
    - Управление жизненным циклом EmployeeDialog (создание).
    - Управление жизненным циклом EmployeeCardDialog (просмотр + inline-редактирование).
    - Диспетчеризация сохранения (создание vs обновление).
    - Выполнение операций через AsyncBridge + EmployeeController.
    - Обработка ошибок с повторным открытием диалогов.
    - Сохранение введённых данных для предзаполнения при ошибках.

Границы:
    - НЕ содержит UI-компонентов (только управляет диалогами).
    - НЕ отображает таблицы — делегирует виджету через callback.
    - НЕ принимает решений о валидации — делегирует Pydantic-схемам.
"""
from __future__ import annotations

import logging
from tkinter import messagebox
from typing import Callable, Optional, Union
from uuid import UUID

import customtkinter as ctk

from src.application.schemas.employee_schemas import (
    EmployeeCreateSchema,
    EmployeeReadSchema,
    EmployeeUpdateSchema,
)
from src.core.logging_config import log_ui_event, log_user_action, log_user_error
from src.domain.employees.employee_exceptions import DuplicateEmployeeError
from src.presentation.async_bridge import AsyncBridge
from src.presentation.controllers.employee_controller import EmployeeController
from src.presentation.dialogs.employee_dialog import EmployeeDialog


class EmployeeDialogCoordinator:
    """Координатор диалогов сотрудников и CRUD-операций."""

    def __init__(
        self,
        master: ctk.CTk,
        controller: EmployeeController,
        bridge: AsyncBridge,
        logger: logging.Logger,
        on_success: Callable[[], None],
    ) -> None:
        """Инициализация координатора.

        Args:
            master: родительское окно для диалогов.
            controller: EmployeeController для CRUD-операций.
            bridge: AsyncBridge для выполнения async-операций.
            logger: логгер для записи событий.
            on_success: callback, вызываемый после успешной операции
                       (обычно refresh виджета).
        """
        self._master = master
        self._controller = controller
        self._bridge = bridge
        self._logger = logger
        self._on_success = on_success

    # ------------------------------------------------------------------
    # Открытие диалогов
    # ------------------------------------------------------------------
    def open_create_dialog(self) -> None:
        """Открытие диалога создания сотрудника."""
        dialog = EmployeeDialog(
            master=self._master,
            logger=self._logger,
            on_save=self._dispatch_save,
            mode="create",
        )
        dialog.focus_set()

    def open_card_dialog(self, employee: EmployeeReadSchema) -> None:
        """Открытие карточки сотрудника в режиме просмотра (view)."""
        dialog = EmployeeDialog(
            master=self._master,
            logger=self._logger,
            on_save=self._on_card_save,
            mode="view",
            employee=employee,
        )
        dialog.focus_set()

    # ------------------------------------------------------------------
    # Диспетчеризация сохранения (из EmployeeDialog)
    # ------------------------------------------------------------------
    def _dispatch_save(
        self,
        employee_id: Optional[UUID],
        schema: Union[EmployeeCreateSchema, EmployeeUpdateSchema],
    ) -> None:
        """Диспетчеризировать сохранение (создание или обновление).

        Используется только EmployeeDialog (создание). Обновление
        из карточки идёт через отдельный `_on_card_save`.
        """
        if employee_id is None:
            self._execute_create(schema, attempt=1)
        else:
            self._execute_update(employee_id, schema)

    # ------------------------------------------------------------------
    # Сохранение из EmployeeCardDialog (inline-редактирование)
    # ------------------------------------------------------------------
    def _on_card_save(
        self,
        employee_id: UUID,
        schema: EmployeeUpdateSchema,
    ) -> None:
        """Обработать сохранение из карточки сотрудника.

        Отдельный путь от `_dispatch_save`, т.к. карточка всегда
        работает с существующим сотрудником (UUID гарантированно не None)
        и не требует повторного открытия диалога при ошибке —
        пользователь остаётся в карточке и может исправить данные.

        Args:
            employee_id: UUID обновляемого сотрудника.
            schema: валидированная схема обновления.
        """
        self._execute_update(employee_id, schema)

    # ------------------------------------------------------------------
    # Выполнение создания
    # ------------------------------------------------------------------
    def _execute_create(self, schema: EmployeeCreateSchema, attempt: int) -> None:
        """Выполнить создание сотрудника."""
        self._bridge.run(
            self._controller.create_employee(schema),
            on_success=self._on_create_success,
            on_error=lambda exc: self._on_create_error(exc, schema, attempt),
        )

    def _on_create_success(self, employee: EmployeeReadSchema) -> None:
        """Обработать успешное создание."""
        log_user_action(
            self._logger,
            action="CREATE_EMPLOYEE",
            details=f"Created employee '{employee.display_name}' (ID: {employee.id})",
        )
        messagebox.showinfo(
            "Успех",
            f"Сотрудник '{employee.display_name}' успешно создан.",
            parent=self._master,
        )
        self._on_success()

    def _on_create_error(
        self,
        exc: Exception,
        schema: EmployeeCreateSchema,
        attempt: int,
    ) -> None:
        """Обработать ошибку создания. При DuplicateEmployeeError повторно открывает диалог."""
        self._logger.exception("Failed to create employee")
        log_user_error(
            self._logger,
            action="CREATE_EMPLOYEE",
            error=f"Failed to create employee: {exc}",
        )

        if isinstance(exc, DuplicateEmployeeError):
            messagebox.showerror(
                "Дубликат данных",
                f"Сотрудник с таким {exc.duplicate_field} уже существует:\n{exc.duplicate_value}",
                parent=self._master,
            )
            if attempt < 2:
                self._reopen_dialog_with_prefill(
                    employee=None,
                    prefill_data=schema.model_dump(),
                )
        else:
            messagebox.showerror(
                "Ошибка создания",
                f"Не удалось создать сотрудника:\n{exc}",
                parent=self._master,
            )

    # ------------------------------------------------------------------
    # Выполнение обновления
    # ------------------------------------------------------------------
    def _execute_update(
        self, employee_id: UUID, schema: EmployeeUpdateSchema
    ) -> None:
        """Выполнить обновление сотрудника."""
        self._bridge.run(
            self._controller.update_employee(employee_id, schema),
            on_success=self._on_update_success,
            on_error=lambda exc: self._on_update_error(exc, employee_id, schema),
        )

    def _on_update_success(self, employee: EmployeeReadSchema) -> None:
        """Обработать успешное обновление."""
        log_user_action(
            self._logger,
            action="UPDATE_EMPLOYEE",
            details=f"Updated employee '{employee.display_name}' (ID: {employee.id})",
        )
        messagebox.showinfo(
            "Успех",
            f"Сотрудник '{employee.display_name}' успешно обновлён.",
            parent=self._master,
        )
        self._on_success()

    def _on_update_error(
        self,
        exc: Exception,
        employee_id: UUID,
        schema: EmployeeUpdateSchema,
    ) -> None:
        """Обработать ошибку обновления.

        При дубликате — messagebox с ошибкой (без повторного открытия,
        т.к. пользователь остаётся в диалоге и может исправить данные).
        """
        self._logger.exception("Failed to update employee")
        log_user_error(
            self._logger,
            action="UPDATE_EMPLOYEE",
            error=f"Failed to update employee {employee_id}: {exc}",
        )

        if isinstance(exc, DuplicateEmployeeError):
            messagebox.showerror(
                "Дубликат данных",
                f"Сотрудник с таким {exc.duplicate_field} уже существует:\n{exc.duplicate_value}",
                parent=self._master,
            )
        else:
            messagebox.showerror(
                "Ошибка обновления",
                f"Не удалось обновить сотрудника:\n{exc}",
                parent=self._master,
            )

    # ------------------------------------------------------------------
    # Повторное открытие EmployeeDialog с предзаполнением (только для создания)
    # ------------------------------------------------------------------
    def _reopen_dialog_with_prefill(
        self,
        employee: Optional[EmployeeReadSchema],
        prefill_data: dict,
    ) -> None:
        """Повторно открыть EmployeeDialog с предзаполненными данными."""
        log_ui_event(
            self._logger,
            widget="EmployeeDialogCoordinator",
            event="REOPEN_DIALOG_WITH_PREFILL",
            data=f"employee_id={employee.id if employee else None}, has_prefill={bool(prefill_data)}",
        )

        dialog = EmployeeDialog(
            master=self._master,
            logger=self._logger,
            on_save=self._dispatch_save,
            employee=employee,
            prefill_data=prefill_data,
        )
        dialog.focus()
