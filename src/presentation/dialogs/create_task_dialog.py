# src/presentation/dialogs/create_task_dialog.py
"""
Модальное диалоговое окно создания новой задачи планирования.

Предоставляет форму с полями:
    - Название задачи (текстовое поле).
    - Тип периода (выпадающий список из :class:`PeriodType`).
    - Кнопки-заглушки: "Добавить сотрудников", "Добавить задействования".
    - Кнопки управления: "Отмена", "Сохранить".

При сохранении возвращает :class:`TaskCreateSchema` через коллбэк ``on_save``.
Диалог модальный (блокирует главное окно до закрытия).
"""
from __future__ import annotations

import logging
from datetime import date
from tkinter import messagebox
from typing import Callable

import customtkinter as ctk

from src.application.schemas.task_schemas import TaskCreateSchema
from src.core.logging_config import log_ui_event, log_user_action
from src.domain.tasks.planning_task_model import PeriodType


class CreateTaskDialog(ctk.CTkToplevel):
    """Модальный диалог создания задачи планирования.

    Attributes:
        _logger: Логгер для событий диалога.
        _on_save: Коллбэк, вызываемый при успешном сохранении.
        _name_entry: Поле ввода названия задачи.
        _period_combobox: Выпадающий список типов периода.
    """

    def __init__(
        self,
        master: ctk.CTk,
        logger: logging.Logger,
        on_save: Callable[[TaskCreateSchema], None],
        **kwargs,
    ) -> None:
        """Инициализация диалога создания задачи.

        Args:
            master: Родительское окно (главное окно приложения).
            logger: Логгер для событий диалога.
            on_save: Коллбэк, вызываемый при нажатии "Сохранить".
                Принимает :class:`TaskCreateSchema` с данными формы.
            **kwargs: Дополнительные параметры для ``CTkToplevel``.
        """
        super().__init__(master, **kwargs)
        self._logger = logger
        self._on_save = on_save

        self._setup_window()
        self._create_widgets()

        self._logger.debug("CreateTaskDialog: диалог создания задачи открыт")

    def _setup_window(self) -> None:
        """Настройка параметров окна диалога."""
        self.title("Создание задачи планирования")
        self.geometry("500x400")
        self.resizable(False, False)

        # Модальность: блокируем взаимодействие с родительским окном
        self.transient(self.master)
        self.grab_set()

        # Фокус на диалог
        self.focus_force()

        # Обработка закрытия через [X]
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

    def _create_widgets(self) -> None:
        """Создание виджетов формы."""
        # Отступы для всех элементов
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

        self._name_entry = ctk.CTkEntry(
            self,
            placeholder_text="Например: Смена бригады А",
            height=35,
        )
        self._name_entry.pack(fill="x", **padding)
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

        # Получаем локализованные названия типов периода
        period_options = [pt.localized for pt in PeriodType]

        self._period_combobox = ctk.CTkComboBox(
            self,
            values=period_options,
            state="readonly",
            height=35,
        )
        self._period_combobox.set(period_options[0])  # Первый элемент по умолчанию
        self._period_combobox.pack(fill="x", **padding)

        # --------------------------------------------------------------
        # Кнопки-заглушки (сотрудники, задействования)
        # --------------------------------------------------------------
        stubs_frame = ctk.CTkFrame(self, fg_color="transparent")
        stubs_frame.pack(fill="x", **padding)

        self._add_employees_btn = ctk.CTkButton(
            stubs_frame,
            text="Добавить сотрудников",
            command=self._on_add_employees,
        )
        self._add_employees_btn.pack(side="left", expand=True, fill="x", padx=(0, 5))

        self._add_engagements_btn = ctk.CTkButton(
            stubs_frame,
            text="Добавить задействования",
            command=self._on_add_engagements,
        )
        self._add_engagements_btn.pack(side="left", expand=True, fill="x", padx=(5, 0))

        # --------------------------------------------------------------
        # Кнопки управления (Отмена, Сохранить)
        # --------------------------------------------------------------
        buttons_frame = ctk.CTkFrame(self, fg_color="transparent")
        buttons_frame.pack(fill="x", side="bottom", padx=20, pady=(20, 20))

        self._cancel_btn = ctk.CTkButton(
            buttons_frame,
            text="Отмена",
            fg_color="gray",
            hover_color="darkgray",
            command=self._on_cancel,
        )
        self._cancel_btn.pack(side="left", expand=True, fill="x", padx=(0, 5))

        self._save_btn = ctk.CTkButton(
            buttons_frame,
            text="Сохранить",
            command=self._on_save_click,
        )
        self._save_btn.pack(side="left", expand=True, fill="x", padx=(5, 0))

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def _on_add_employees(self) -> None:
        """Обработчик кнопки 'Добавить сотрудников' (заглушка)."""
        log_ui_event(
            self._logger,
            "CreateTaskDialog.btn_add_employees",
            "click",
        )
        messagebox.showinfo(
            "В разработке",
            "Функция добавления сотрудников будет реализована позже.",
            parent=self,
        )

    def _on_add_engagements(self) -> None:
        """Обработчик кнопки 'Добавить задействования' (заглушка)."""
        log_ui_event(
            self._logger,
            "CreateTaskDialog.btn_add_engagements",
            "click",
        )
        messagebox.showinfo(
            "В разработке",
            "Функция добавления задействований будет реализована позже.",
            parent=self,
        )

    def _on_cancel(self) -> None:
        """Обработчик кнопки 'Отмена' и закрытия окна через [X]."""
        log_ui_event(
            self._logger,
            "CreateTaskDialog.btn_cancel",
            "click",
        )
        self._logger.debug("CreateTaskDialog: пользователь отменил создание задачи")
        self.destroy()


    def _on_save_click(self) -> None:
        """Обработчик кнопки 'Сохранить': валидация и возврат результата."""
        log_ui_event(
            self._logger,
            "CreateTaskDialog.btn_save",
            "click",
        )

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

        # Получение выбранного типа периода
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

        # Формирование схемы с правильными именами полей
        schema = TaskCreateSchema(
            name=name,
            period_type=period_type,
            anchor_date=date.today(),  # Опорная дата — сегодня (по умолчанию)
            employee_ids=[],
            duty_type_ids=[],
            reference_id=None,
        )

        log_user_action(
            self._logger,
            "Создание задачи (диалог)",
            f"Название: {name}, Период: {period_type.value}",
        )

        # Вызов коллбэка (передача данных в контроллер)
        try:
            self._on_save(schema)
        except Exception as exc:
            self._logger.error(
                "CreateTaskDialog: ошибка в коллбэке on_save: %s",
                exc,
                exc_info=True,
            )
            messagebox.showerror(
                "Ошибка",
                f"Не удалось создать задачу: {exc}",
                parent=self,
            )
            return

        # Закрытие диалога после успешного сохранения
        self._logger.debug("CreateTaskDialog: задача сохранена, диалог закрыт")
        self.destroy()


