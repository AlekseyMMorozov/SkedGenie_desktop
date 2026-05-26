# src/presentation/dialogs/employee_dialog.py
"""
Универсальный диалог создания и редактирования сотрудника.

Режимы работы:
    - employee=None → режим создания, возвращает EmployeeCreateSchema
    - employee=EmployeeReadSchema → режим редактирования, возвращает EmployeeUpdateSchema

Унифицированный колбэк on_save:
    on_save(employee_id: Optional[UUID], schema: Union[EmployeeCreateSchema, EmployeeUpdateSchema])

Ответственность:
    - Сбор данных из UI-полей.
    - Валидация через Pydantic-схемы (EmployeeCreateSchema/EmployeeUpdateSchema).
    - Обработка ошибок валидации с отображением пользователю.
    - Логирование UI-событий через log_ui_event.

Границы:
    - НЕ выполняет persistence — делегирует контроллеру через коллбэк.
    - НЕ обращается к БД напрямую.
    - НЕ содержит бизнес-логики — только UI и валидация.

Примечание:
    Поле engagement_ids (many-to-many с Engagements) временно скрыто,
    так как Engagement как Domain-модель ещё не реализован.
    Будет добавлено после создания EngagementController.
"""
from __future__ import annotations

import logging
from datetime import date
from tkinter import messagebox
from typing import Callable, Optional, Union
from uuid import UUID

import customtkinter as ctk
from pydantic import ValidationError

from src.application.schemas.employee_schemas import (
    EmployeeCreateSchema,
    EmployeeReadSchema,
    EmployeeUpdateSchema,
)
from src.core.logging_config import log_ui_event


class EmployeeDialog(ctk.CTkToplevel):
    """Модальный диалог для создания или редактирования сотрудника."""

    def __init__(
        self,
        master: ctk.CTk,
        logger: logging.Logger,
        on_save: Callable[
            [Optional[UUID], Union[EmployeeCreateSchema, EmployeeUpdateSchema]], None
        ],
        employee: Optional[EmployeeReadSchema] = None,
        prefill_data: Optional[dict] = None,
        **kwargs,
    ) -> None:
        """Инициализация диалога.

        Args:
            master: родительское окно (MainWindow).
            logger: логгер для записи событий.
            on_save: коллбэк, вызываемый при сохранении.
                     Принимает (employee_id, schema).
            employee: существующий сотрудник для редактирования или None для создания.
            prefill_data: данные для предзаполнения полей (при повторном открытии после ошибки).
            **kwargs: дополнительные параметры для CTkToplevel.
        """
        super().__init__(master, **kwargs)
        self._logger = logger
        self._on_save = on_save
        self._employee = employee
        self._prefill_data = prefill_data
        self._is_edit_mode = employee is not None

        self._setup_window()
        self._create_widgets()

        log_ui_event(
            self._logger,
            widget="EmployeeDialog",
            event="OPENED",
            data=f"mode={'edit' if self._is_edit_mode else 'create'}, employee_id={employee.id if employee else None}, has_prefill={bool(prefill_data)}",
        )

    # ------------------------------------------------------------------
    # Настройка окна
    # ------------------------------------------------------------------
    def _setup_window(self) -> None:
        """Настроить размеры, позицию и модальность окна."""
        self.title(
            "Редактирование сотрудника" if self._is_edit_mode else "Создание сотрудника"
        )
        self.geometry("600x700")
        self.resizable(False, False)

        # Модальность: блокируем взаимодействие с родительским окном
        self.transient(self.master)
        self.grab_set()

        # Центрирование относительно родителя
        self.update_idletasks()
        parent_x = self.master.winfo_rootx()
        parent_y = self.master.winfo_rooty()
        parent_width = self.master.winfo_width()
        parent_height = self.master.winfo_height()

        dialog_width = 600
        dialog_height = 700

        x = parent_x + (parent_width - dialog_width) // 2
        y = parent_y + (parent_height - dialog_height) // 2

        self.geometry(f"+{x}+{y}")

    # ------------------------------------------------------------------
    # Создание виджетов
    # ------------------------------------------------------------------
    def _create_widgets(self) -> None:
        """Создать все UI-компоненты диалога."""
        # Основной контейнер с отступами
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Прокручиваемая область для полей
        scrollable_frame = ctk.CTkScrollableFrame(main_frame)
        scrollable_frame.pack(fill="both", expand=True)

        # === Секция: ФИО ===
        name_frame = ctk.CTkFrame(scrollable_frame, fg_color="transparent")
        name_frame.pack(fill="x", pady=(0, 15))

        ctk.CTkLabel(name_frame, text="Фамилия *", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w"
        )
        self._last_name_entry = ctk.CTkEntry(name_frame, placeholder_text="Иванов")
        self._last_name_entry.pack(fill="x", pady=(5, 10))

        ctk.CTkLabel(name_frame, text="Имя *", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w"
        )
        self._first_name_entry = ctk.CTkEntry(name_frame, placeholder_text="Иван")
        self._first_name_entry.pack(fill="x", pady=(5, 10))

        ctk.CTkLabel(name_frame, text="Отчество").pack(anchor="w")
        self._middle_name_entry = ctk.CTkEntry(
            name_frame, placeholder_text="Иванович (необязательно)"
        )
        self._middle_name_entry.pack(fill="x", pady=(5, 0))

        # === Секция: Работа ===
        work_frame = ctk.CTkFrame(scrollable_frame, fg_color="transparent")
        work_frame.pack(fill="x", pady=(0, 15))

        ctk.CTkLabel(work_frame, text="Должность").pack(anchor="w")
        self._position_entry = ctk.CTkEntry(
            work_frame, placeholder_text="Инженер (необязательно)"
        )
        self._position_entry.pack(fill="x", pady=(5, 10))

        ctk.CTkLabel(work_frame, text="Табельный номер").pack(anchor="w")
        self._tab_number_entry = ctk.CTkEntry(
            work_frame, placeholder_text="12345 (необязательно, уникальный)"
        )
        self._tab_number_entry.pack(fill="x", pady=(5, 0))

        # === Секция: Контакты ===
        contact_frame = ctk.CTkFrame(scrollable_frame, fg_color="transparent")
        contact_frame.pack(fill="x", pady=(0, 15))

        ctk.CTkLabel(contact_frame, text="Email").pack(anchor="w")
        self._email_entry = ctk.CTkEntry(
            contact_frame, placeholder_text="ivanov@example.com (необязательно, уникальный)"
        )
        self._email_entry.pack(fill="x", pady=(5, 10))

        ctk.CTkLabel(contact_frame, text="Телефон").pack(anchor="w")
        self._phone_entry = ctk.CTkEntry(
            contact_frame, placeholder_text="+7 (999) 123-45-67 (необязательно)"
        )
        self._phone_entry.pack(fill="x", pady=(5, 10))

        ctk.CTkLabel(contact_frame, text="Дата рождения").pack(anchor="w")
        self._birth_date_entry = ctk.CTkEntry(
            contact_frame, placeholder_text="ГГГГ-ММ-ДД (необязательно)"
        )
        self._birth_date_entry.pack(fill="x", pady=(5, 0))

        # === Секция: Статус ===
        status_frame = ctk.CTkFrame(scrollable_frame, fg_color="transparent")
        status_frame.pack(fill="x", pady=(0, 15))

        self._is_active_var = ctk.BooleanVar(value=True)
        self._is_active_switch = ctk.CTkSwitch(
            status_frame,
            text="Активен (участвует в планировании)",
            variable=self._is_active_var,
        )
        self._is_active_switch.pack(anchor="w")

        # === Секция: Заметки ===
        notes_frame = ctk.CTkFrame(scrollable_frame, fg_color="transparent")
        notes_frame.pack(fill="x", pady=(0, 15))

        ctk.CTkLabel(notes_frame, text="Заметки").pack(anchor="w")
        self._notes_textbox = ctk.CTkTextbox(notes_frame, height=100)
        self._notes_textbox.pack(fill="x", pady=(5, 0))

        # === Кнопки действий ===
        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack(fill="x", pady=(15, 0))

        cancel_button = ctk.CTkButton(
            button_frame, text="Отмена", command=self._on_cancel, fg_color="gray"
        )
        cancel_button.pack(side="right", padx=(10, 0))

        save_button = ctk.CTkButton(
            button_frame, text="Сохранить", command=self._on_save_click
        )
        save_button.pack(side="right")

        # Заполнение полей
        self._populate_fields()

    def _populate_fields(self) -> None:
        """Заполнить поля данными существующего сотрудника или предзаполненными данными."""
        # Приоритет: prefill_data > employee > пустые поля
        if self._prefill_data:
            self._populate_from_prefill()
        elif self._is_edit_mode and self._employee:
            self._populate_from_employee()

    def _populate_from_employee(self) -> None:
        """Заполнить поля данными существующего сотрудника (режим редактирования)."""
        emp = self._employee
        self._last_name_entry.insert(0, emp.last_name or "")
        self._first_name_entry.insert(0, emp.first_name or "")
        self._middle_name_entry.insert(0, emp.middle_name or "")
        self._position_entry.insert(0, emp.position or "")
        self._tab_number_entry.insert(0, emp.tab_number or "")
        self._email_entry.insert(0, emp.email or "")
        self._phone_entry.insert(0, emp.phone or "")
        if emp.birth_date:
            self._birth_date_entry.insert(0, emp.birth_date.isoformat())
        self._is_active_var.set(emp.is_active)
        if emp.notes:
            self._notes_textbox.insert("1.0", emp.notes)

    def _populate_from_prefill(self) -> None:
        """Заполнить поля предзаполненными данными (при повторном открытии после ошибки)."""
        data = self._prefill_data
        self._last_name_entry.insert(0, data.get("last_name") or "")
        self._first_name_entry.insert(0, data.get("first_name") or "")
        self._middle_name_entry.insert(0, data.get("middle_name") or "")
        self._position_entry.insert(0, data.get("position") or "")
        self._tab_number_entry.insert(0, data.get("tab_number") or "")
        self._email_entry.insert(0, data.get("email") or "")
        self._phone_entry.insert(0, data.get("phone") or "")
        birth_date = data.get("birth_date")
        if birth_date:
            if isinstance(birth_date, date):
                self._birth_date_entry.insert(0, birth_date.isoformat())
            else:
                self._birth_date_entry.insert(0, str(birth_date))
        self._is_active_var.set(data.get("is_active", True))
        notes = data.get("notes")
        if notes:
            self._notes_textbox.insert("1.0", notes)

    # ------------------------------------------------------------------
    # Обработчики событий
    # ------------------------------------------------------------------
    def _on_save_click(self) -> None:
        """Обработать нажатие кнопки 'Сохранить'."""
        try:
            # Сбор данных из полей
            data = {
                "last_name": self._last_name_entry.get().strip(),
                "first_name": self._first_name_entry.get().strip(),
                "middle_name": self._middle_name_entry.get().strip() or None,
                "position": self._position_entry.get().strip() or None,
                "tab_number": self._tab_number_entry.get().strip() or None,
                "email": self._email_entry.get().strip() or None,
                "phone": self._phone_entry.get().strip() or None,
                "birth_date": self._parse_birth_date(),
                "is_active": self._is_active_var.get(),
                "notes": self._notes_textbox.get("1.0", "end-1c").strip() or None,
                "engagement_ids": [],  # Заглушка: будет реализовано позже
            }

            # Валидация и создание схемы
            if self._is_edit_mode and self._employee:
                schema = EmployeeUpdateSchema(**data)
                employee_id = self._employee.id
            else:
                schema = EmployeeCreateSchema(**data)
                employee_id = None

            # Вызов коллбэка
            self._on_save(employee_id, schema)

            log_ui_event(
                self._logger,
                widget="EmployeeDialog",
                event="SAVE_CLICKED",
                data=f"mode={'edit' if self._is_edit_mode else 'create'}, employee_id={employee_id}",
            )

            # Закрытие диалога
            self.destroy()

        except ValidationError as e:
            # Ошибка валидации Pydantic
            errors = []
            for error in e.errors():
                field = " → ".join(str(loc) for loc in error["loc"])
                msg = error["msg"]
                errors.append(f"{field}: {msg}")

            error_message = "\n".join(errors)
            messagebox.showerror(
                "Ошибка валидации",
                f"Пожалуйста, исправьте следующие ошибки:\n\n{error_message}",
                parent=self,
            )
            log_ui_event(
                self._logger,
                widget="EmployeeDialog",
                event="VALIDATION_ERROR",
                data=error_message,
            )

        except Exception as exc:
            # Непредвиденная ошибка
            messagebox.showerror(
                "Ошибка",
                f"Произошла непредвиденная ошибка:\n{exc}",
                parent=self,
            )
            self._logger.exception("Unexpected error in EmployeeDialog._on_save_click")

    def _parse_birth_date(self) -> Optional[date]:
        """Распарсить дату рождения из текстового поля."""
        date_str = self._birth_date_entry.get().strip()
        if not date_str:
            return None

        try:
            # Ожидаемый формат: ГГГГ-ММ-ДД (ISO 8601)
            return date.fromisoformat(date_str)
        except ValueError:
            # Pydantic-валидатор обработает эту ошибку
            return date_str  # Передаём строку, пусть Pydantic выбросит ValidationError

    def _on_cancel(self) -> None:
        """Обработать нажатие кнопки 'Отмена'."""
        log_ui_event(
            self._logger,
            widget="EmployeeDialog",
            event="CANCELLED",
            data=f"mode={'edit' if self._is_edit_mode else 'create'}",
        )
        self.destroy()
