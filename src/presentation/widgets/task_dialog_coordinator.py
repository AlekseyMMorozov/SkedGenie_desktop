# src/presentation/widgets/task_dialog_coordinator.py
"""
Координатор диалогов задач планирования.

Ответственность:
    - Управление жизненным циклом TaskDialog (создание/редактирование).
    - Загрузка сотрудников и шаблонов задействований для выбора в диалоге.
    - Диспетчеризация сохранения через TaskController (template_ids хранятся
      в самой задаче как JSON-поле).
    - Обработка ошибок (DuplicateTaskNameError) с повторным открытием диалога.
    - Выполнение операций через AsyncBridge + TaskController.

Примечание:
    Связь «задача ↔ шаблон задействования» (Вариант A) реализована через
    поле ``template_ids`` в :class:`PlanningTask`. Отдельной M2M-синхронизации
    не требуется — данные сохраняются вместе с задачей.
"""
from __future__ import annotations

import logging
from tkinter import messagebox
from typing import Callable, List, Optional, Union
from uuid import UUID

import customtkinter as ctk

from src.application.schemas.employee_schemas import EmployeeReadSchema
from src.application.schemas.engagement_schemas import EngagementTemplateReadSchema
from src.application.schemas.task_schemas import (
    TaskCreateSchema,
    TaskReadSchema,
    TaskUpdateSchema,
)
from src.core.logging_config import log_ui_event, log_user_action, log_user_error
from src.domain.tasks.task_exceptions import DuplicateTaskNameError
from src.presentation.async_bridge import AsyncBridge
from src.presentation.controllers.employee_controller import EmployeeController
from src.presentation.controllers.engagement_template_controller import (
    EngagementTemplateController,
)
from src.presentation.controllers.task_controller import TaskController
from src.presentation.dialogs.task_dialog import TaskDialog


class TaskDialogCoordinator:
    """Координатор диалогов задач и CRUD-операций."""

    _MAX_RENAME_ATTEMPTS: int = 10

    def __init__(
        self,
        master: ctk.CTk,
        task_controller: TaskController,
        employee_controller: Optional[EmployeeController],
        engagement_template_controller: EngagementTemplateController,
        bridge: AsyncBridge,
        logger: logging.Logger,
        on_success: Callable[[], None],
    ) -> None:
        """Инициализация координатора.

        Args:
            master: Родительское окно для диалогов.
            task_controller: Контроллер задач.
            employee_controller: Контроллер сотрудников (опционально).
            engagement_template_controller: Контроллер шаблонов задействований.
            bridge: Мост для async-операций.
            logger: Логгер.
            on_success: Callback при успешной операции (обычно refresh таблицы).
        """
        self._master = master
        self._task_controller = task_controller
        self._employee_controller = employee_controller
        self._engagement_template_controller = engagement_template_controller
        self._bridge = bridge
        self._logger = logger
        self._on_success = on_success

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def open_create_dialog(self) -> None:
        """Открытие диалога создания задачи."""
        log_ui_event(self._logger, "TaskDialogCoordinator", "OPEN_CREATE")
        self._load_data_and_open(task=None)

    def open_edit_dialog(self, task: TaskReadSchema) -> None:
        """Открытие диалога редактирования задачи.

        Перед открытием перезапрашивает задачу из БД, чтобы избежать
        работы с устаревшими данными.
        """
        log_ui_event(self._logger, "TaskDialogCoordinator", "OPEN_EDIT", data=str(task.id))

        self._bridge.run(
            coro=self._task_controller.get_task_by_id(task.id),
            on_success=lambda fresh_task: self._load_data_and_open(fresh_task),
            on_error=lambda exc: messagebox.showerror(
                "Ошибка",
                f"Не удалось загрузить актуальные данные задачи: {exc}",
                parent=self._master,
            ),
        )

    # ------------------------------------------------------------------
    # Internal Logic
    # ------------------------------------------------------------------
    def _load_data_and_open(self, task: Optional[TaskReadSchema]) -> None:
        """Загружает сотрудников и шаблоны задействований, затем открывает диалог."""
        async def _fetch() -> tuple[List[EmployeeReadSchema], List[EngagementTemplateReadSchema]]:
            emps = (
                await self._employee_controller.get_active_employees()
                if self._employee_controller
                else []
            )
            templates = await self._engagement_template_controller.get_all()
            return emps, templates

        self._bridge.run(
            coro=_fetch(),
            on_success=lambda data: self._open_task_dialog(task, data[0], data[1]),
            on_error=lambda exc: self._logger.error("Failed to load dialog data: %s", exc),
        )

    def _open_task_dialog(
        self,
        task: Optional[TaskReadSchema],
        employees: List[EmployeeReadSchema],
        templates: List[EngagementTemplateReadSchema],
    ) -> None:
        """Создаёт и показывает TaskDialog."""
        dialog = TaskDialog(
            master=self._master,
            logger=self._logger,
            on_save=self._dispatch_save,
            task=task,
            available_employees=employees,
            available_templates=templates,
        )
        dialog.focus_set()

    # ------------------------------------------------------------------
    # Save Dispatching
    # ------------------------------------------------------------------
    def _dispatch_save(
        self,
        task_id: Optional[UUID],
        schema: Union[TaskCreateSchema, TaskUpdateSchema],
    ) -> None:
        """Маршрутизация сохранения.

        Поле ``template_ids`` уже содержится в самой схеме (часть TaskCreateSchema /
        TaskUpdateSchema), отдельная M2M-синхронизация не требуется.
        """
        if task_id is None:
            if not isinstance(schema, TaskCreateSchema):
                self._logger.error("Dispatch save error: expected CreateSchema for new task")
                return
            self._execute_create(schema)
        else:
            if not isinstance(schema, TaskUpdateSchema):
                self._logger.error("Dispatch save error: expected UpdateSchema for existing task")
                return
            self._execute_update(task_id, schema)

    # ------------------------------------------------------------------
    # Create Logic
    # ------------------------------------------------------------------
    def _execute_create(self, schema: TaskCreateSchema, attempt: int = 1) -> None:
        """Запуск создания задачи."""
        if not self._bridge.is_running():
            return

        self._bridge.run(
            coro=self._task_controller.create_task(schema),
            on_success=self._on_create_success,
            on_error=lambda exc, s=schema, a=attempt: self._on_create_error(exc, s, a),
        )

    def _on_create_success(self, task: TaskReadSchema) -> None:
        """Успешное создание."""
        log_user_action(self._logger, "Задача создана", f"ID: {task.id}, Name: {task.name}")
        self._on_success()

    def _on_create_error(
        self, exc: Exception, schema: TaskCreateSchema, attempt: int,
    ) -> None:
        """Обработка ошибки создания."""
        if isinstance(exc, DuplicateTaskNameError):
            if attempt >= self._MAX_RENAME_ATTEMPTS:
                log_user_error(self._logger, "Создание задачи", "Max rename attempts exceeded")
                messagebox.showerror(
                    "Ошибка", "Не удалось подобрать уникальное имя.", parent=self._master,
                )
                self.open_create_dialog()
                return

            suggested_name = f"{exc.duplicate_name} ({attempt + 1})"
            if messagebox.askyesno(
                "Дубликат названия",
                f"Задача '{exc.duplicate_name}' уже существует.\n"
                f"Переименовать в '{suggested_name}'?",
                parent=self._master,
            ):
                new_schema = schema.model_copy(update={"name": suggested_name})
                self._execute_create(new_schema, attempt + 1)
            else:
                self.open_create_dialog()
            return

        log_user_error(self._logger, "Создание задачи", str(exc))
        messagebox.showerror("Ошибка создания", str(exc), parent=self._master)

    # ------------------------------------------------------------------
    # Update Logic
    # ------------------------------------------------------------------
    def _execute_update(self, task_id: UUID, schema: TaskUpdateSchema) -> None:
        """Запуск обновления задачи."""
        if not self._bridge.is_running():
            return

        self._bridge.run(
            coro=self._task_controller.update_task(task_id, schema),
            on_success=self._on_update_success,
            on_error=lambda exc, tid=task_id: self._on_update_error(exc, tid),
        )

    def _on_update_success(self, task: TaskReadSchema) -> None:
        """Успешное обновление."""
        log_user_action(self._logger, "Задача обновлена", f"ID: {task.id}, Name: {task.name}")
        self._on_success()

    def _on_update_error(self, exc: Exception, task_id: UUID) -> None:
        """Обработка ошибки обновления."""
        if isinstance(exc, DuplicateTaskNameError):
            messagebox.showerror(
                "Дубликат названия",
                f"Задача '{exc.duplicate_name}' уже существует.",
                parent=self._master,
            )
            # Reload fresh task data and reopen
            self._bridge.run(
                coro=self._task_controller.get_task_by_id(task_id),
                on_success=self._reopen_edit_dialog,
                on_error=lambda e: self._logger.error("Reload failed: %s", e),
            )
            return

        log_user_error(self._logger, "Обновление задачи", str(exc))
        messagebox.showerror("Ошибка обновления", str(exc), parent=self._master)

    def _reopen_edit_dialog(self, task: Optional[TaskReadSchema]) -> None:
        """Повторное открытие диалога редактирования."""
        if task is None:
            messagebox.showinfo("Задача не найдена", "Задача была удалена.", parent=self._master)
            self._on_success()  # Refresh list
            return
        self.open_edit_dialog(task)
