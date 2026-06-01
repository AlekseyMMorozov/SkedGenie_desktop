# src/presentation/dialogs/employee_dialog_coordinator.py
"""
Координатор диалогов сотрудников и CRUD-операций.

Ответственность:
    - Управление жизненным циклом EmployeeDialog (создание/карточка).
    - Диспетчеризация сохранения (создание vs обновление).
    - Выполнение операций через AsyncBridge + EmployeeController.
    - Обработка ошибок с повторным открытием диалогов.
    - Сохранение введённых данных для предзаполнения при ошибках.
    - Управление задачами и задействованиями (шаблонами) сотрудника.

Границы:
    - НЕ содержит UI-компонентов (только управляет диалогами).
    - НЕ принимает решений о валидации — делегирует Pydantic-схемам.
"""
from __future__ import annotations

import logging
from tkinter import messagebox
from typing import Callable, Optional, Union
from uuid import UUID

import customtkinter as ctk

from src.application.schemas.employee_schemas import (
    EmployeeCreateSchema, EmployeeReadSchema, EmployeeUpdateSchema,
)
from src.application.schemas.engagement_schemas import EngagementTemplateReadSchema
from src.application.schemas.task_schemas import TaskReadSchema
from src.core.logging_config import log_ui_event, log_user_action, log_user_error
from src.domain.employees.employee_exceptions import DuplicateEmployeeError
from src.presentation.async_bridge import AsyncBridge
from src.presentation.controllers.employee_controller import EmployeeController
from src.presentation.controllers.engagement_template_controller import EngagementTemplateController
from src.presentation.controllers.task_controller import TaskController
from src.presentation.dialogs.employee_dialog import EmployeeDialog
from src.presentation.dialogs.employee_tasks_dialog import EmployeeTasksDialog
from src.presentation.dialogs.engagement_template_select_dialog import EngagementTemplateSelectDialog


class EmployeeDialogCoordinator:
    """Координатор диалогов сотрудников и CRUD-операций."""

    def __init__(
        self,
        master: ctk.CTk,
        controller: EmployeeController,
        bridge: AsyncBridge,
        logger: logging.Logger,
        on_success: Callable[[], None],
        task_controller: Optional[TaskController] = None,
        engagement_template_controller: Optional[EngagementTemplateController] = None,
    ) -> None:
        self._master = master
        self._controller = controller
        self._bridge = bridge
        self._logger = logger
        self._on_success = on_success
        self._task_controller = task_controller
        self._engagement_template_controller = engagement_template_controller
        self._active_tasks_dialog: Optional[EmployeeTasksDialog] = None

    # ------------------------------------------------------------------
    # Открытие диалогов
    # ------------------------------------------------------------------
    def open_create_dialog(self) -> None:
        dialog = EmployeeDialog(
            master=self._master, logger=self._logger,
            on_save=self._dispatch_save, mode="create",
        )
        dialog.focus_set()

    def open_card_dialog(self, employee: EmployeeReadSchema) -> None:
        on_view_tasks = (
            lambda emp: self.open_tasks_dialog(emp) if self._task_controller else None
        )
        on_view_engagements = (
            lambda emp: self.open_engagements_dialog(emp)
            if self._engagement_template_controller else None
        )
        dialog = EmployeeDialog(
            master=self._master, logger=self._logger,
            on_save=self._on_card_save, mode="view", employee=employee,
            on_view_tasks=on_view_tasks,
            on_view_engagements=on_view_engagements,
        )
        dialog.focus_set()

    # ------------------------------------------------------------------
    # Управление задачами сотрудника
    # ------------------------------------------------------------------
    def open_tasks_dialog(self, employee: EmployeeReadSchema) -> None:
        if not self._task_controller:
            messagebox.showerror("Ошибка", "Контроллер задач не инициализирован.", parent=self._master)
            return
        self._bridge.run(
            self._task_controller.get_tasks_by_employee(employee.id),
            on_success=lambda tasks: self._show_tasks_dialog(employee, tasks),
            on_error=lambda exc: messagebox.showerror("Ошибка", f"Не удалось загрузить задачи: {exc}", parent=self._master),
        )

    def _show_tasks_dialog(self, employee: EmployeeReadSchema, tasks: list[TaskReadSchema]) -> None:
        self._active_tasks_dialog = EmployeeTasksDialog(
            master=self._master, logger=self._logger,
            employee_id=employee.id, employee_name=employee.display_name,
            tasks=tasks,
            on_remove_from_task=self._handle_remove_from_task,
            on_add_to_task=self._handle_add_to_task,
        )
        self._active_tasks_dialog.focus_set()

    def _handle_remove_from_task(self, employee_id: UUID, task_id: UUID) -> None:
        self._bridge.run(
            self._controller.remove_from_task(employee_id, task_id),
            on_success=lambda r: self._on_remove_from_task_success(r, employee_id, task_id),
            on_error=lambda exc: messagebox.showerror("Ошибка", f"Не удалось удалить: {exc}", parent=self._master),
        )

    def _on_remove_from_task_success(self, removed: bool, employee_id: UUID, task_id: UUID) -> None:
        if removed:
            log_user_action(self._logger, "Сотрудник удален из задачи", f"emp={employee_id}, task={task_id}")
            if self._active_tasks_dialog:
                self._active_tasks_dialog.remove_task_from_list(task_id)
            messagebox.showinfo("Успех", "Сотрудник исключен из задачи.", parent=self._master)

    def _handle_add_to_task(self, employee_id: UUID) -> None:
        if not self._task_controller:
            return
        self._bridge.run(
            self._task_controller.get_all_tasks(),
            on_success=lambda tasks: self._open_task_select_dialog(employee_id, tasks),
            on_error=lambda exc: messagebox.showerror("Ошибка", f"Не удалось загрузить задачи: {exc}", parent=self._master),
        )

    def _open_task_select_dialog(self, employee_id: UUID, all_tasks: list[TaskReadSchema]) -> None:
        available = [t for t in all_tasks if employee_id not in (t.employee_ids or [])]
        if not available:
            messagebox.showinfo("Нет задач", "Сотрудник уже во всех задачах.", parent=self._master)
            return
        dialog = _TaskSelectDialog(master=self._master, logger=self._logger, tasks=available)
        self._master.wait_window(dialog)
        selected = dialog.get_result()
        if selected:
            self._execute_add_employee_to_task(employee_id, selected)

    def _execute_add_employee_to_task(self, employee_id: UUID, task_id: UUID) -> None:
        if not self._task_controller:
            return
        self._bridge.run(
            self._task_controller.add_employee_to_task(employee_id, task_id),
            on_success=lambda a: self._on_add_to_task_success(a, employee_id, task_id),
            on_error=lambda exc: messagebox.showerror("Ошибка", f"Не удалось добавить: {exc}", parent=self._master),
        )

    def _on_add_to_task_success(self, added: bool, employee_id: UUID, task_id: UUID) -> None:
        if added:
            log_user_action(self._logger, "Сотрудник добавлен в задачу", f"emp={employee_id}, task={task_id}")
            if self._active_tasks_dialog and self._task_controller:
                self._bridge.run(
                    self._task_controller.get_task_by_id(task_id),
                    on_success=lambda t: self._active_tasks_dialog.add_task_to_list(t) if t else None,
                    on_error=lambda e: self._logger.error("Failed to reload task: %s", e),
                )
            messagebox.showinfo("Успех", "Сотрудник добавлен в задачу.", parent=self._master)
        else:
            messagebox.showinfo("Информация", "Сотрудник уже состоит в этой задаче.", parent=self._master)

    # ------------------------------------------------------------------
    # Управление задействованиями (шаблонами) сотрудника
    # ------------------------------------------------------------------
    def open_engagements_dialog(self, employee: EmployeeReadSchema) -> None:
        """Открытие диалога управления шаблонами задействований сотрудника."""
        if not self._engagement_template_controller:
            messagebox.showerror("Ошибка", "Контроллер шаблонов не инициализирован.", parent=self._master)
            return
        self._bridge.run(
            self._engagement_template_controller.get_all(),
            on_success=lambda tpl: self._show_engagements_dialog(employee, tpl),
            on_error=lambda exc: messagebox.showerror("Ошибка", f"Не удалось загрузить шаблоны: {exc}", parent=self._master),
        )

    def _show_engagements_dialog(
        self, employee: EmployeeReadSchema, templates: list[EngagementTemplateReadSchema],
    ) -> None:
        current_ids = list(employee.engagement_ids or [])
        dialog = EngagementTemplateSelectDialog(
            master=self._master, logger=self._logger,
            templates=templates, selected_ids=current_ids,
        )
        self._master.wait_window(dialog)
        new_ids = dialog.get_result()
        if new_ids is None or set(new_ids) == set(current_ids):
            return
        self._apply_engagement_diff(employee.id, current_ids, new_ids)

    def _apply_engagement_diff(
        self, employee_id: UUID, old_ids: list[UUID], new_ids: list[UUID],
    ) -> None:
        to_add = set(new_ids) - set(old_ids)
        to_remove = set(old_ids) - set(new_ids)
        self._bridge.run(
            self._sync_engagements(employee_id, to_add, to_remove),
            on_success=lambda _: self._on_engagement_sync_success(employee_id, len(to_add), len(to_remove)),
            on_error=lambda exc: messagebox.showerror("Ошибка", f"Синхронизация не удалась: {exc}", parent=self._master),
        )

    async def _sync_engagements(
        self, employee_id: UUID, to_add: set[UUID], to_remove: set[UUID],
    ) -> None:
        for tid in to_add:
            await self._controller.add_engagement_template(employee_id, tid)
        for tid in to_remove:
            await self._controller.remove_engagement_template(employee_id, tid)

    def _on_engagement_sync_success(self, employee_id: UUID, added: int, removed: int) -> None:
        log_user_action(self._logger, "ENGAGEMENTS_SYNCED", f"emp={employee_id}, +{added}/-{removed}")
        messagebox.showinfo("Успех", f"Задействования обновлены (+{added}/-{removed}).", parent=self._master)
        self._on_success()

    # ------------------------------------------------------------------
    # Диспетчеризация сохранения (из EmployeeDialog)
    # ------------------------------------------------------------------
    def _dispatch_save(
        self, employee_id: Optional[UUID], schema: Union[EmployeeCreateSchema, EmployeeUpdateSchema],
    ) -> None:
        if employee_id is None:
            self._execute_create(schema, attempt=1)
        else:
            self._execute_update(employee_id, schema)

    def _on_card_save(self, employee_id: UUID, schema: EmployeeUpdateSchema) -> None:
        self._execute_update(employee_id, schema)

    def _execute_create(self, schema: EmployeeCreateSchema, attempt: int) -> None:
        self._bridge.run(
            self._controller.create_employee(schema),
            on_success=self._on_create_success,
            on_error=lambda exc: self._on_create_error(exc, schema, attempt),
        )

    def _on_create_success(self, employee: EmployeeReadSchema) -> None:
        log_user_action(self._logger, "CREATE_EMPLOYEE", f"Created '{employee.display_name}'")
        messagebox.showinfo("Успех", f"Сотрудник '{employee.display_name}' создан.", parent=self._master)
        self._on_success()

    def _on_create_error(self, exc: Exception, schema: EmployeeCreateSchema, attempt: int) -> None:
        self._logger.exception("Failed to create employee")
        log_user_error(self._logger, "CREATE_EMPLOYEE", str(exc))
        if isinstance(exc, DuplicateEmployeeError):
            messagebox.showerror("Дубликат", f"{exc.duplicate_field}: {exc.duplicate_value}", parent=self._master)
            if attempt < 2:
                self._reopen_dialog_with_prefill(None, schema.model_dump())
        else:
            messagebox.showerror("Ошибка", str(exc), parent=self._master)

    def _execute_update(self, employee_id: UUID, schema: EmployeeUpdateSchema) -> None:
        self._bridge.run(
            self._controller.update_employee(employee_id, schema),
            on_success=self._on_update_success,
            on_error=lambda exc: self._on_update_error(exc, employee_id, schema),
        )

    def _on_update_success(self, employee: EmployeeReadSchema) -> None:
        log_user_action(self._logger, "UPDATE_EMPLOYEE", f"Updated '{employee.display_name}'")
        messagebox.showinfo("Успех", f"Сотрудник '{employee.display_name}' обновлён.", parent=self._master)
        self._on_success()

    def _on_update_error(self, exc: Exception, employee_id: UUID, schema: EmployeeUpdateSchema) -> None:
        self._logger.exception("Failed to update employee")
        log_user_error(self._logger, "UPDATE_EMPLOYEE", str(exc))
        if isinstance(exc, DuplicateEmployeeError):
            messagebox.showerror("Дубликат", f"{exc.duplicate_field}: {exc.duplicate_value}", parent=self._master)
        else:
            messagebox.showerror("Ошибка", str(exc), parent=self._master)

    def _reopen_dialog_with_prefill(self, employee: Optional[EmployeeReadSchema], prefill_data: dict) -> None:
        log_ui_event(self._logger, "EmployeeDialogCoordinator", "REOPEN_PREFILL")
        dialog = EmployeeDialog(
            master=self._master, logger=self._logger,
            on_save=self._dispatch_save, employee=employee, prefill_data=prefill_data,
        )
        dialog.focus()


class _TaskSelectDialog(ctk.CTkToplevel):
    """Вспомогательный диалог для выбора одной задачи из списка."""

    def __init__(self, master, logger, tasks: list[TaskReadSchema]):
        super().__init__(master)
        self._logger = logger
        self._tasks = tasks
        self._result: Optional[UUID] = None
        self.title("Выберите задачу")
        self.geometry("400x300")
        self.transient(master)
        self.grab_set()

        listbox_frame = ctk.CTkFrame(self)
        listbox_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self._listbox = ctk.CTkScrollableFrame(listbox_frame)
        self._listbox.pack(fill="both", expand=True)

        for task in tasks:
            btn = ctk.CTkButton(
                self._listbox, text=f"{task.name} ({task.period_type})",
                command=lambda tid=task.id: self._select(tid),
            )
            btn.pack(fill="x", pady=2)
        ctk.CTkButton(self, text="Отмена", command=self.destroy).pack(pady=(0, 10))

    def _select(self, task_id: UUID):
        self._result = task_id
        self.destroy()

    def get_result(self) -> Optional[UUID]:
        return self._result
