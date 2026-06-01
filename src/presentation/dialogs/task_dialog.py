# src/presentation/dialogs/task_dialog.py
"""
Универсальное диалоговое окно для создания и редактирования задачи планирования.

Поддерживает два режима работы:
    - **Создание**: ``task=None``, возвращает :class:`TaskCreateSchema`
      через ``on_save(None, schema)``.
    - **Редактирование**: ``task`` — существующая задача, поля
      предзаполнены, возвращает :class:`TaskUpdateSchema`
      через ``on_save(task.id, schema)``.

Модальное окно (блокирует главное окно до закрытия).
"""
from __future__ import annotations

import logging
from datetime import date
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
from src.core.logging_config import log_ui_event, log_user_action
from src.domain.tasks.planning_task_model import PeriodType
from src.presentation.dialogs.employee_select_dialog import EmployeeSelectDialog
from src.presentation.dialogs.engagement_template_select_dialog import (
    EngagementTemplateSelectDialog,
)


class TaskDialog(ctk.CTkToplevel):
    """Универсальный модальный диалог создания/редактирования задачи."""

    def __init__(
            self,
            master: ctk.CTk,
            logger: logging.Logger,
            on_save: Callable[
                [Optional[UUID], Union[TaskCreateSchema, TaskUpdateSchema]],
                None,
            ],
            task: Optional[TaskReadSchema] = None,
            available_employees: Optional[List[EmployeeReadSchema]] = None,
            available_templates: Optional[List[EngagementTemplateReadSchema]] = None,
            **kwargs,
    ) -> None:
        super().__init__(master, **kwargs)
        self._logger = logger
        self._on_save = on_save
        self._task = task
        self._is_edit_mode = task is not None
        self._available_employees = available_employees or []
        self._available_templates = available_templates or []

        # Инициализация списка сотрудников
        if self._is_edit_mode and task and task.employee_ids:
            self._employee_ids = list(task.employee_ids)
        else:
            self._employee_ids = []

        # Инициализация списка шаблонов задействований (Вариант A)
        if self._is_edit_mode and task and getattr(task, "template_ids", None):
            self._template_ids = list(task.template_ids)
        else:
            self._template_ids = []

        self._setup_window()
        self._create_widgets()

        # Применяем тему после создания виджетов
        self._apply_theme_to_self()

        mode_str = "редактирования" if self._is_edit_mode else "создания"
        self._logger.debug("TaskDialog: диалог %s задачи открыт", mode_str)

    # ------------------------------------------------------------------
    # Theme & Window Setup
    # ------------------------------------------------------------------
    def _apply_theme_to_self(self) -> None:
        """Применяет цвета темы к диалогу и его элементам."""
        root = self.winfo_toplevel()
        if hasattr(root, '_theme_colors'):
            colors = root._theme_colors
            dialog_bg = colors.get("dialog_bg", "#FFFFFF")
            border_color = colors.get("border_color", "#C0C0C0")

            self.configure(fg_color=dialog_bg)

            # Рекурсивное обновление границ полей ввода
            self._update_borders(self, border_color)

    def _update_borders(self, widget, border_color: str) -> None:
        """Добавляет границы полям ввода для визуального отделения."""
        try:
            w_class = widget.__class__.__name__
            if w_class in ("CTkEntry", "CTkComboBox", "CTkTextbox"):
                widget.configure(border_width=1, border_color=border_color)

            for child in widget.winfo_children():
                self._update_borders(child, border_color)
        except Exception:
            pass

    def _setup_window(self) -> None:
        title = (
            "Редактирование задачи"
            if self._is_edit_mode
            else "Создание задачи планирования"
        )
        self.title(title)
        self.geometry("500x480")
        self.resizable(False, False)

        self.transient(self.master)
        self.grab_set()
        self.focus_force()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

    # ------------------------------------------------------------------
    # Widgets
    # ------------------------------------------------------------------
    def _create_widgets(self) -> None:
        padding = {"padx": 20, "pady": 10}

        # Название задачи
        name_label = ctk.CTkLabel(
            self, text="Название задачи:", font=ctk.CTkFont(weight="bold"),
        )
        name_label.pack(fill="x", **padding)

        initial_name = self._task.name if self._is_edit_mode else ""
        placeholder = (
            "Введите новое название"
            if self._is_edit_mode
            else "Например: Смена бригады А"
        )

        self._name_entry = ctk.CTkEntry(
            self, placeholder_text=placeholder, height=35,
        )
        self._name_entry.pack(fill="x", **padding)
        if initial_name:
            self._name_entry.insert(0, initial_name)
        self._name_entry.focus()

        # Тип периода
        period_label = ctk.CTkLabel(
            self, text="Тип периода планирования:", font=ctk.CTkFont(weight="bold"),
        )
        period_label.pack(fill="x", **padding)

        period_options = [pt.localized for pt in PeriodType]
        self._period_combobox = ctk.CTkComboBox(
            self, values=period_options, state="readonly", height=35,
        )

        if self._is_edit_mode and self._task is not None:
            try:
                period_enum = PeriodType(self._task.period_type)
                default_period = period_enum.localized
            except ValueError:
                default_period = period_options[0]
        else:
            default_period = period_options[0]

        self._period_combobox.set(default_period)
        self._period_combobox.pack(fill="x", **padding)

        # Кнопки управления сотрудниками
        emp_frame = ctk.CTkFrame(self, fg_color="transparent")
        emp_frame.pack(fill="x", **padding)

        self._emp_btn = ctk.CTkButton(
            emp_frame,
            text=f"👥 Сотрудники ({len(self._employee_ids)})",
            command=self._on_add_employees,
            anchor="w",
            height=35,
        )
        self._emp_btn.pack(fill="x")

        # Кнопка управления шаблонами задействований (Вариант A)
        tpl_frame = ctk.CTkFrame(self, fg_color="transparent")
        tpl_frame.pack(fill="x", **padding)

        self._tpl_btn = ctk.CTkButton(
            tpl_frame,
            text=f"📋 Задействования ({len(self._template_ids)})",
            command=self._on_add_templates,
            anchor="w",
            height=35,
        )
        self._tpl_btn.pack(fill="x")

        # Кнопки управления
        buttons_frame = ctk.CTkFrame(self, fg_color="transparent")
        buttons_frame.pack(fill="x", side="bottom", padx=20, pady=(20, 20))

        ctk.CTkButton(
            buttons_frame, text="Отмена", fg_color="gray40", hover_color="gray30",
            command=self._on_cancel, width=120,
        ).pack(side="left", expand=True, fill="x", padx=(0, 5))

        ctk.CTkButton(
            buttons_frame, text="Сохранить", command=self._on_save_click, width=120,
        ).pack(side="left", expand=True, fill="x", padx=(5, 0))

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------
    def _on_add_employees(self) -> None:
        log_ui_event(self._logger, "TaskDialog.btn_add_employees", "click")

        if not self._available_employees:
            messagebox.showinfo(
                "Нет сотрудников",
                "Список сотрудников пуст. Сначала добавьте сотрудников в систему.",
                parent=self,
            )
            return

        dialog = EmployeeSelectDialog(
            master=self,
            logger=self._logger,
            employees=self._available_employees,
            selected_ids=self._employee_ids,
        )
        self.wait_window(dialog)

        result = dialog.get_result()
        if result is not None:
            self._employee_ids = result
            self._emp_btn.configure(text=f"👥 Сотрудники ({len(self._employee_ids)})")

    def _on_add_templates(self) -> None:
        log_ui_event(self._logger, "TaskDialog.btn_add_templates", "click")

        if not self._available_templates:
            messagebox.showinfo(
                "Нет шаблонов",
                "Список шаблонов задействований пуст. Сначала создайте шаблоны "
                "во вкладке «Задействования».",
                parent=self,
            )
            return

        dialog = EngagementTemplateSelectDialog(
            master=self,
            logger=self._logger,
            templates=self._available_templates,
            selected_ids=self._template_ids,
        )
        self.wait_window(dialog)

        result = dialog.get_result()
        if result is not None:
            self._template_ids = result
            self._tpl_btn.configure(
                text=f"📋 Шаблоны задействований ({len(self._template_ids)})"
            )

    def _on_cancel(self) -> None:
        log_ui_event(self._logger, "TaskDialog.btn_cancel", "click")
        mode_str = "редактирования" if self._is_edit_mode else "создания"
        self._logger.debug("TaskDialog: пользователь отменил %s задачи", mode_str)
        self.destroy()

    def _on_save_click(self) -> None:
        log_ui_event(self._logger, "TaskDialog.btn_save", "click")

        name = self._name_entry.get().strip()
        if not name:
            messagebox.showerror(
                "Ошибка валидации", "Название задачи не может быть пустым.", parent=self,
            )
            self._name_entry.focus()
            return

        period_localized = self._period_combobox.get()
        period_type = next(
            (pt for pt in PeriodType if pt.localized == period_localized), None,
        )
        if period_type is None:
            messagebox.showerror(
                "Ошибка валидации", f"Некорректный тип периода: {period_localized}", parent=self,
            )
            return

        # Проверка изменений для режима редактирования
        if self._is_edit_mode and self._task is not None:
            employees_changed = set(self._employee_ids) != set(self._task.employee_ids or [])
            templates_changed = set(self._template_ids) != set(
                getattr(self._task, "template_ids", []) or []
            )
            if (
                    name == self._task.name
                    and period_type.value == self._task.period_type
                    and not employees_changed
                    and not templates_changed
            ):
                self._logger.debug("TaskDialog: данные не изменились, закрытие без сохранения")
                self.destroy()
                return

        if self._is_edit_mode and self._task is not None:
            schema = TaskUpdateSchema(
                id=self._task.id,
                name=name,
                period_type=period_type,
                employee_ids=self._employee_ids if self._employee_ids else None,
                template_ids=self._template_ids if self._template_ids else None,
            )
            action_name = "Редактирование задачи (диалог)"
            action_details = (
                f"ID: {self._task.id}, Новое имя: {name}, "
                f"Период: {period_type.value}, "
                f"Сотрудников: {len(self._employee_ids)}, "
                f"Шаблонов: {len(self._template_ids)}"
            )
        else:
            schema = TaskCreateSchema(
                name=name,
                period_type=period_type,
                anchor_date=date.today(),
                employee_ids=self._employee_ids if self._employee_ids else None,
                template_ids=self._template_ids if self._template_ids else None,
                duty_type_ids=[],
                reference_id=None,
            )
            action_name = "Создание задачи (диалог)"
            action_details = (
                f"Название: {name}, Период: {period_type.value}, "
                f"Сотрудников: {len(self._employee_ids)}, "
                f"Шаблонов: {len(self._template_ids)}"
            )

        log_user_action(self._logger, action_name, action_details)

        try:
            task_id = self._task.id if self._is_edit_mode else None
            self._on_save(task_id, schema)
        except Exception as exc:
            self._logger.error("TaskDialog: ошибка в коллбэке on_save: %s", exc, exc_info=True)
            messagebox.showerror("Ошибка", f"Не удалось сохранить задачу: {exc}", parent=self)
            return

        self._logger.debug("TaskDialog: данные сохранены через коллбэк, диалог закрыт")
        self.destroy()
