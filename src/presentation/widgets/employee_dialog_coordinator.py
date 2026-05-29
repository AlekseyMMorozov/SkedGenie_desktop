# src/presentation/dialogs/employee_dialog_coordinator.py
"""
Координатор диалогов сотрудников и CRUD-операций.

Ответственность:
    - Управление жизненным циклом EmployeeDialog (создание).
    - Управление жизненным циклом EmployeeCardDialog (просмотр + inline-редактирование).
    - Диспетчеризация сохранения (создание vs обновление).
    - Выполнение операций через AsyncBridge + EmployeeController.
    - Обработка ошибок с повторным открытием диалогов.
    - Сохранение введённых данных для предзаполнения при ошибках.
    - Открытие диалога управления задачами сотрудника.

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
from src.application.schemas.task_schemas import TaskReadSchema
from src.core.logging_config import log_ui_event, log_user_action, log_user_error
from src.domain.employees.employee_exceptions import DuplicateEmployeeError
from src.presentation.async_bridge import AsyncBridge
from src.presentation.controllers.employee_controller import EmployeeController
from src.presentation.controllers.task_controller import TaskController
from src.presentation.dialogs.employee_dialog import EmployeeDialog
from src.presentation.dialogs.employee_tasks_dialog import EmployeeTasksDialog


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
    ) -> None:
        """Инициализация координатора.

        Args:
            master: родительское окно для диалогов.
            controller: EmployeeController для CRUD-операций.
            bridge: AsyncBridge для выполнения async-операций.
            logger: логгер для записи событий.
            on_success: callback, вызываемый после успешной операции
                       (обычно refresh виджета).
            task_controller: TaskController для операций с задачами (опционально).
        """
        self._master = master
        self._controller = controller
        self._bridge = bridge
        self._logger = logger
        self._on_success = on_success
        self._task_controller = task_controller

        # Ссылка на активный диалог задач для обновления UI
        self._active_tasks_dialog: Optional[EmployeeTasksDialog] = None

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
        # Передаем callback для открытия задач, если контроллер задач доступен
        on_view_tasks = None
        if self._task_controller:
            on_view_tasks = lambda emp: self.open_tasks_dialog(emp)

        dialog = EmployeeDialog(
            master=self._master,
            logger=self._logger,
            on_save=self._on_card_save,
            mode="view",
            employee=employee,
            on_view_tasks=on_view_tasks,
        )
        dialog.focus_set()

    def open_tasks_dialog(self, employee: EmployeeReadSchema) -> None:
        """Открытие диалога управления задачами сотрудника."""
        if not self._task_controller:
            messagebox.showerror("Ошибка", "Контроллер задач не инициализирован.", parent=self._master)
            return

        self._bridge.run(
            self._task_controller.get_tasks_by_employee(employee.id),
            on_success=lambda tasks: self._show_tasks_dialog(employee, tasks),
            on_error=lambda exc: messagebox.showerror("Ошибка", f"Не удалось загрузить задачи: {exc}",
                                                      parent=self._master),
        )

    def _show_tasks_dialog(self, employee: EmployeeReadSchema, tasks: list[TaskReadSchema]) -> None:
        """Отображение диалога задач после загрузки данных."""
        self._active_tasks_dialog = EmployeeTasksDialog(
            master=self._master,
            logger=self._logger,
            employee_id=employee.id,
            employee_name=employee.display_name,
            tasks=tasks,
            on_remove_from_task=self._handle_remove_from_task,
            on_add_to_task=self._handle_add_to_task,  # ✅ Передаем callback добавления
        )
        self._active_tasks_dialog.focus_set()

    # ------------------------------------------------------------------
    # Операции с задачами сотрудника
    # ------------------------------------------------------------------
    def _handle_remove_from_task(self, employee_id: UUID, task_id: UUID) -> None:
        """Обработчик удаления сотрудника из задачи (запуск async операции)."""
        self._bridge.run(
            self._controller.remove_from_task(employee_id, task_id),
            on_success=lambda removed: self._on_remove_from_task_success(removed, employee_id, task_id),
            on_error=lambda exc: messagebox.showerror("Ошибка", f"Не удалось удалить сотрудника из задачи: {exc}",
                                                      parent=self._master),
        )

    def _on_remove_from_task_success(self, removed: bool, employee_id: UUID, task_id: UUID) -> None:
        """Успешное удаление сотрудника из задачи."""
        if removed:
            log_user_action(
                self._logger,
                "Сотрудник удален из задачи",
                f"Employee: {employee_id}, Task: {task_id}"
            )
            if self._active_tasks_dialog:
                self._active_tasks_dialog.remove_task_from_list(task_id)
                messagebox.showinfo("Успех", "Сотрудник успешно исключен из задачи.", parent=self._master)
            else:
                messagebox.showinfo("Успех", "Сотрудник успешно исключен из задачи.", parent=self._master)

    def _handle_add_to_task(self, employee_id: UUID) -> None:
        """Обработчик кнопки 'Добавить в задачу'. Открывает диалог выбора задач."""
        if not self._task_controller:
            return

        # Загружаем все задачи, чтобы пользователь мог выбрать
        self._bridge.run(
            self._task_controller.get_all_tasks(),
            on_success=lambda tasks: self._open_task_select_dialog(employee_id, tasks),
            on_error=lambda exc: messagebox.showerror("Ошибка", f"Не удалось загрузить задачи: {exc}",
                                                      parent=self._master),
        )

    def _open_task_select_dialog(self, employee_id: UUID, all_tasks: list[TaskReadSchema]) -> None:
        """Открывает диалог выбора задачи для добавления сотрудника."""

        available_tasks = [t for t in all_tasks if employee_id not in (t.employee_ids or [])]

        if not available_tasks:
            messagebox.showinfo("Нет доступных задач", "Сотрудник уже добавлен во все существующие задачи.",
                                parent=self._master)
            return

        dialog = _TaskSelectDialog(
            master=self._master,
            logger=self._logger,
            tasks=available_tasks,
        )
        self._master.wait_window(dialog)

        selected_task_id = dialog.get_result()
        if selected_task_id:
            self._execute_add_employee_to_task(employee_id, selected_task_id)

    def _execute_add_employee_to_task(self, employee_id: UUID, task_id: UUID) -> None:
        """Запуск async-добавления сотрудника в задачу."""
        if not self._task_controller:
            return

        self._bridge.run(
            self._task_controller.add_employee_to_task(employee_id, task_id),
            on_success=lambda added: self._on_add_to_task_success(added, employee_id, task_id),
            on_error=lambda exc: messagebox.showerror("Ошибка", f"Не удалось добавить сотрудника в задачу: {exc}",
                                                      parent=self._master),
        )

    def _on_add_to_task_success(self, added: bool, employee_id: UUID, task_id: UUID) -> None:
        """Успешное добавление сотрудника в задачу."""
        if added:
            log_user_action(
                self._logger,
                "Сотрудник добавлен в задачу",
                f"Employee: {employee_id}, Task: {task_id}"
            )
            # Обновляем UI диалога задач
            if self._active_tasks_dialog and self._task_controller:
                # Перезагружаем задачу, чтобы получить актуальные данные для отображения
                self._bridge.run(
                    self._task_controller.get_task_by_id(task_id),
                    on_success=lambda task: self._active_tasks_dialog.add_task_to_list(task) if task else None,
                    on_error=lambda e: self._logger.error("Failed to reload task for UI update: %s", e),
                )
                messagebox.showinfo("Успех", "Сотрудник успешно добавлен в задачу.", parent=self._master)
            else:
                messagebox.showinfo("Успех", "Сотрудник успешно добавлен в задачу.", parent=self._master)
        else:
            messagebox.showinfo("Информация", "Сотрудник уже состоит в этой задаче.", parent=self._master)

    # ------------------------------------------------------------------
    # Диспетчеризация сохранения (из EmployeeDialog)
    # ------------------------------------------------------------------
    def _dispatch_save(
            self,
            employee_id: Optional[UUID],
            schema: Union[EmployeeCreateSchema, EmployeeUpdateSchema],
    ) -> None:
        """Диспетчеризировать сохранение (создание или обновление)."""
        if employee_id is None:
            self._execute_create(schema, attempt=1)
        else:
            self._execute_update(employee_id, schema)

    def _on_card_save(
            self,
            employee_id: UUID,
            schema: EmployeeUpdateSchema,
    ) -> None:
        """Обработать сохранение из карточки сотрудника."""
        self._execute_update(employee_id, schema)

    # ------------------------------------------------------------------
    # Выполнение создания / обновления сотрудника
    # ------------------------------------------------------------------
    def _execute_create(self, schema: EmployeeCreateSchema, attempt: int) -> None:
        self._bridge.run(
            self._controller.create_employee(schema),
            on_success=self._on_create_success,
            on_error=lambda exc: self._on_create_error(exc, schema, attempt),
        )

    def _on_create_success(self, employee: EmployeeReadSchema) -> None:
        log_user_action(self._logger, action="CREATE_EMPLOYEE", details=f"Created '{employee.display_name}'")
        messagebox.showinfo("Успех", f"Сотрудник '{employee.display_name}' успешно создан.", parent=self._master)
        self._on_success()

    def _on_create_error(self, exc: Exception, schema: EmployeeCreateSchema, attempt: int) -> None:
        self._logger.exception("Failed to create employee")
        log_user_error(self._logger, action="CREATE_EMPLOYEE", error=str(exc))
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
        log_user_action(self._logger, action="UPDATE_EMPLOYEE", details=f"Updated '{employee.display_name}'")
        messagebox.showinfo("Успех", f"Сотрудник '{employee.display_name}' обновлён.", parent=self._master)
        self._on_success()

    def _on_update_error(self, exc: Exception, employee_id: UUID, schema: EmployeeUpdateSchema) -> None:
        self._logger.exception("Failed to update employee")
        log_user_error(self._logger, action="UPDATE_EMPLOYEE", error=str(exc))
        if isinstance(exc, DuplicateEmployeeError):
            messagebox.showerror("Дубликат", f"{exc.duplicate_field}: {exc.duplicate_value}", parent=self._master)
        else:
            messagebox.showerror("Ошибка", str(exc), parent=self._master)

    def _reopen_dialog_with_prefill(self, employee: Optional[EmployeeReadSchema], prefill_data: dict) -> None:
        log_ui_event(self._logger, widget="EmployeeDialogCoordinator", event="REOPEN_PREFILL")
        dialog = EmployeeDialog(
            master=self._master,
            logger=self._logger,
            on_save=self._dispatch_save,
            employee=employee,
            prefill_data=prefill_data,
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
                self._listbox,
                text=f"{task.name} ({task.period_type})",
                command=lambda tid=task.id: self._select(tid)
            )
            btn.pack(fill="x", pady=2)

        ctk.CTkButton(self, text="Отмена", command=self.destroy).pack(pady=(0, 10))

    def _select(self, task_id: UUID):
        self._result = task_id
        self.destroy()

    def get_result(self) -> Optional[UUID]:
        return self._result
