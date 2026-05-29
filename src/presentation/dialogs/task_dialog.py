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

import customtkinter as ctk

from src.application.schemas.employee_schemas import EmployeeReadSchema
from src.application.schemas.task_schemas import (
    TaskCreateSchema,
    TaskReadSchema,
    TaskUpdateSchema,
)
from src.core.logging_config import log_ui_event, log_user_action
from src.domain.tasks.planning_task_model import PeriodType
from src.presentation.dialogs.employee_select_dialog import EmployeeSelectDialog


class TaskDialog(ctk.CTkToplevel):
    """Универсальный модальный диалог создания/редактирования задачи.

    Attributes:
        _logger: Логгер для событий диалога.
        _on_save: Унифицированный коллбэк сохранения.
        _task: Существующая задача (None для создания).
        _is_edit_mode: Флаг режима редактирования.
        _name_entry: Поле ввода названия.
        _period_combobox: Выпадающий список типов периода.
        _employee_ids: Текущий список ID сотрудников, привязанных к задаче.
        _available_employees: Список всех доступных сотрудников для выбора.
    """

    def __init__(
            self,
            master: ctk.CTk,
            logger: logging.Logger,
            on_save: Callable[
                [Optional, Union[TaskCreateSchema, TaskUpdateSchema]],
                None,
            ],
            task: Optional[TaskReadSchema] = None,
            available_employees: Optional[List[EmployeeReadSchema]] = None,
            **kwargs,
    ) -> None:
        """Инициализация диалога задачи.

        Args:
            master: Родительское окно.
            logger: Логгер для событий диалога.
            on_save: Унифицированный коллбэк, принимающий
                ``(task_id, schema)``. При создании ``task_id=None``,
                ``schema`` — :class:`TaskCreateSchema`. При редактировании
                ``task_id`` — UUID задачи, ``schema`` — :class:`TaskUpdateSchema`.
            task: Существующая задача для редактирования. Если ``None`` —
                режим создания новой задачи.
            available_employees: Список всех активных сотрудников для выбора.
            **kwargs: Дополнительные параметры для ``CTkToplevel``.
        """
        super().__init__(master, **kwargs)
        self._logger = logger
        self._on_save = on_save
        self._task = task
        self._is_edit_mode = task is not None
        self._available_employees = available_employees or []

        # Инициализация списка сотрудников
        if self._is_edit_mode and task and task.employee_ids:
            self._employee_ids = list(task.employee_ids)
        else:
            self._employee_ids = []

        self._setup_window()
        self._create_widgets()

        mode_str = "редактирования" if self._is_edit_mode else "создания"
        self._logger.debug("TaskDialog: диалог %s задачи открыт", mode_str)

    # ------------------------------------------------------------------
    # Настройка окна
    # ------------------------------------------------------------------
    def _setup_window(self) -> None:
        """Настройка параметров окна (заголовок зависит от режима)."""
        title = (
            "Редактирование задачи"
            if self._is_edit_mode
            else "Создание задачи планирования"
        )
        self.title(title)
        self.geometry("500x450")  # Увеличил высоту для кнопки сотрудников
        self.resizable(False, False)

        self.transient(self.master)
        self.grab_set()
        self.focus_force()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

    # ------------------------------------------------------------------
    # Создание виджетов
    # ------------------------------------------------------------------
    def _create_widgets(self) -> None:
        """Создание виджетов формы с учётом режима."""
        padding = {"padx": 20, "pady": 10}

        # --------------------------------------------------------------
        # Название задачи
        # --------------------------------------------------------------
        name_label = ctk.CTkLabel(
            self,
            text="Название задачи:",
            font=ctk.CTkFont(weight="bold"),
        )
        name_label.pack(fill="x", **padding)

        initial_name = self._task.name if self._is_edit_mode else ""
        placeholder = (
            "Введите новое название"
            if self._is_edit_mode
            else "Например: Смена бригады А"
        )

        self._name_entry = ctk.CTkEntry(
            self,
            placeholder_text=placeholder,
            height=35,
        )
        self._name_entry.pack(fill="x", **padding)
        if initial_name:
            self._name_entry.insert(0, initial_name)
        self._name_entry.focus()

        # --------------------------------------------------------------
        # Тип периода
        # --------------------------------------------------------------
        period_label = ctk.CTkLabel(
            self,
            text="Тип периода планирования:",
            font=ctk.CTkFont(weight="bold"),
        )
        period_label.pack(fill="x", **padding)

        period_options = [pt.localized for pt in PeriodType]
        self._period_combobox = ctk.CTkComboBox(
            self,
            values=period_options,
            state="readonly",
            height=35,
        )
        # Значение по умолчанию: из существующей задачи или первый элемент
        if self._is_edit_mode and self._task is not None:
            # TaskReadSchema.period_type — это строковое значение ('WEEK'/'MONTH'/...)
            try:
                period_enum = PeriodType(self._task.period_type)
                default_period = period_enum.localized
            except ValueError:
                default_period = period_options[0]
        else:
            default_period = period_options[0]

        self._period_combobox.set(default_period)
        self._period_combobox.pack(fill="x", **padding)

        # --------------------------------------------------------------
        # Кнопки управления сотрудниками
        # --------------------------------------------------------------
        emp_frame = ctk.CTkFrame(self, fg_color="transparent")
        emp_frame.pack(fill="x", **padding)

        ctk.CTkButton(
            emp_frame,
            text=f"Сотрудники ({len(self._employee_ids)})",
            command=self._on_add_employees,
            anchor="w"
        ).pack(fill="x")

        # --------------------------------------------------------------
        # Кнопки-заглушки (задействования)
        # --------------------------------------------------------------
        stubs_frame = ctk.CTkFrame(self, fg_color="transparent")
        stubs_frame.pack(fill="x", **padding)

        ctk.CTkButton(
            stubs_frame,
            text="Добавить задействования",
            command=self._on_add_engagements,
        ).pack(fill="x")

        # --------------------------------------------------------------
        # Кнопки управления
        # --------------------------------------------------------------
        buttons_frame = ctk.CTkFrame(self, fg_color="transparent")
        buttons_frame.pack(fill="x", side="bottom", padx=20, pady=(20, 20))

        ctk.CTkButton(
            buttons_frame,
            text="Отмена",
            fg_color="gray",
            hover_color="darkgray",
            command=self._on_cancel,
        ).pack(side="left", expand=True, fill="x", padx=(0, 5))

        ctk.CTkButton(
            buttons_frame,
            text="Сохранить",
            command=self._on_save_click,
        ).pack(side="left", expand=True, fill="x", padx=(5, 0))

    # ------------------------------------------------------------------
    # Обработчики событий
    # ------------------------------------------------------------------
    def _on_add_employees(self) -> None:
        """Открытие диалога выбора сотрудников."""
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
            # Обновляем текст кнопки
            for widget in self.winfo_children():
                if isinstance(widget, ctk.CTkFrame):
                    for child in widget.winfo_children():
                        if isinstance(child, ctk.CTkButton) and child.cget("text").startswith("Сотрудники"):
                            child.configure(text=f"Сотрудники ({len(self._employee_ids)})")
                            break

    def _on_add_engagements(self) -> None:
        """Заглушка: 'Добавить задействования'."""
        log_ui_event(self._logger, "TaskDialog.btn_add_engagements", "click")
        messagebox.showinfo(
            "В разработке",
            "Функция добавления задействований будет реализована позже.",
            parent=self,
        )

    def _on_cancel(self) -> None:
        """Обработчик кнопки 'Отмена' и закрытия через [X]."""
        log_ui_event(self._logger, "TaskDialog.btn_cancel", "click")
        mode_str = "редактирования" if self._is_edit_mode else "создания"
        self._logger.debug(
            "TaskDialog: пользователь отменил %s задачи",
            mode_str,
        )
        self.destroy()

    def _on_save_click(self) -> None:
        """Обработчик кнопки 'Сохранить': валидация и вызов on_save."""
        log_ui_event(self._logger, "TaskDialog.btn_save", "click")

        # Валидация названия
        name = self._name_entry.get().strip()
        if not name:
            messagebox.showerror(
                "Ошибка валидации",
                "Название задачи не может быть пустым.",
                parent=self,
            )
            self._name_entry.focus()
            return

        # Получение типа периода
        period_localized = self._period_combobox.get()
        period_type = next(
            (pt for pt in PeriodType if pt.localized == period_localized),
            None,
        )
        if period_type is None:
            messagebox.showerror(
                "Ошибка валидации",
                f"Некорректный тип периода: {period_localized}",
                parent=self,
            )
            return

        # Проверка: реально ли изменились данные при редактировании
        if self._is_edit_mode and self._task is not None:
            # Сравниваем основные поля. employee_ids сравниваем отдельно, если нужно
            # Для простоты, если изменились только сотрудники, считаем изменением
            employees_changed = set(self._employee_ids) != set(self._task.employee_ids or [])

            if (
                    name == self._task.name
                    and period_type.value == self._task.period_type
                    and not employees_changed
            ):
                self._logger.debug(
                    "TaskDialog: данные не изменились, закрытие без сохранения",
                )
                self.destroy()
                return

        # Формирование схемы в зависимости от режима
        if self._is_edit_mode and self._task is not None:
            schema = TaskUpdateSchema(
                id=self._task.id,
                name=name,
                period_type=period_type,
                employee_ids=self._employee_ids if self._employee_ids else None,
            )
            action_name = "Редактирование задачи (диалог)"
            action_details = (
                f"ID: {self._task.id}, Новое имя: {name}, "
                f"Период: {period_type.value}, Сотрудников: {len(self._employee_ids)}"
            )
        else:
            schema = TaskCreateSchema(
                name=name,
                period_type=period_type,
                anchor_date=date.today(),
                employee_ids=self._employee_ids if self._employee_ids else None,
                duty_type_ids=[],
                reference_id=None,
            )
            action_name = "Создание задачи (диалог)"
            action_details = f"Название: {name}, Период: {period_type.value}, Сотрудников: {len(self._employee_ids)}"

        log_user_action(self._logger, action_name, action_details)

        # Вызов коллбэка
        try:
            task_id = self._task.id if self._is_edit_mode else None
            self._on_save(task_id, schema)
        except Exception as exc:  # noqa: BLE001
            self._logger.error(
                "TaskDialog: ошибка в коллбэке on_save: %s",
                exc,
                exc_info=True,
            )
            messagebox.showerror(
                "Ошибка",
                f"Не удалось сохранить задачу: {exc}",
                parent=self,
            )
            return

        self._logger.debug(
            "TaskDialog: данные сохранены через коллбэк, диалог закрыт",
        )
        self.destroy()
