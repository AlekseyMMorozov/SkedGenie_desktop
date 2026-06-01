# src/presentation/dialogs/employee_dialog.py
"""
Унифицированный диалог сотрудника: создание / просмотр / редактирование.

Режимы:
    - create: пустая форма, поля активны, кнопка «Сохранить».
    - view:   заполненная форма, поля НЕАКТИВНЫ, кнопка «Изменить».
    - edit:   заполненная форма, поля активны, кнопка «Сохранить изменения».

Особенности:
    - Кнопки закреплены ВВЕРХУ окна (всегда видны).
    - Двухколоночный layout в ScrollableFrame.
    - Безопасный ввод даты через три поля (ДД/ММ/ГГГГ) во всех режимах.
    - Единая валидация через Pydantic-схемы + перехват доменных исключений.
    - Кнопка "Задачи" для просмотра связей (только view/edit).
"""
from __future__ import annotations

import logging
import re
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
    """Универсальный диалог сотрудника (создание / просмотр / редактирование)."""

    _WINDOW_WIDTH: int = 720
    _WINDOW_HEIGHT: int = 500
    _PAD_X: int = 12
    _PAD_Y: int = 6

    def __init__(
            self,
            master: ctk.CTk,
            logger: logging.Logger,
            on_save: Callable[
                [Optional[UUID], Union[EmployeeCreateSchema, EmployeeUpdateSchema]], None
            ],
            mode: str = "create",
            employee: Optional[EmployeeReadSchema] = None,
            prefill_data: Optional[dict] = None,
            on_view_tasks: Optional[Callable[[EmployeeReadSchema], None]] = None,
            **kwargs,
    ) -> None:
        super().__init__(master, **kwargs)
        self._logger = logger
        self._on_save = on_save
        self._employee = employee
        self._prefill_data = prefill_data
        self._mode = mode  # "create" | "view" | "edit"
        self._on_view_tasks = on_view_tasks

        # Поля ввода
        self._entry_last_name: ctk.CTkEntry | None = None
        self._entry_first_name: ctk.CTkEntry | None = None
        self._entry_middle_name: ctk.CTkEntry | None = None
        self._entry_birth_day: ctk.CTkEntry | None = None
        self._entry_birth_month: ctk.CTkEntry | None = None
        self._entry_birth_year: ctk.CTkEntry | None = None
        self._entry_position: ctk.CTkEntry | None = None
        self._entry_rank: ctk.CTkEntry | None = None
        self._entry_tab_number: ctk.CTkEntry | None = None
        self._entry_email: ctk.CTkEntry | None = None
        self._entry_phone: ctk.CTkEntry | None = None
        self._entry_notes: ctk.CTkTextbox | None = None
        self._switch_is_active: ctk.CTkSwitch | None = None

        # Кнопки (для динамического переключения)
        self._btn_primary: ctk.CTkButton | None = None
        self._btn_secondary: ctk.CTkButton | None = None
        self._btn_tasks: ctk.CTkButton | None = None

        self._setup_window()
        self._create_widgets()

        # ✅ Применяем тему после создания виджетов
        self._apply_theme_to_self()

        self._populate_fields()
        self._apply_mode()

        log_ui_event(
            self._logger,
            widget="EmployeeDialog",
            event="OPENED",
            data=f"mode={self._mode}, "
                 f"employee_id={self._employee.id if self._employee else None}, "
                 f"has_prefill={prefill_data is not None}",
        )

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
            self._update_borders(self, border_color)
        else:
            self.configure(fg_color="#FFFFFF")
            self._update_borders(self, "#C0C0C0")

    def _update_borders(self, widget, border_color: str) -> None:
        """Рекурсивно добавляет границы полям ввода."""
        try:
            w_class = widget.__class__.__name__
            if w_class in ("CTkEntry", "CTkTextbox", "CTkComboBox"):
                widget.configure(border_width=1, border_color=border_color)

            for child in widget.winfo_children():
                self._update_borders(child, border_color)
        except Exception:
            pass

    def _setup_window(self) -> None:
        titles = {"create": "Новый сотрудник", "view": "Карточка сотрудника", "edit": "Редактирование"}
        self.title(titles.get(self._mode, "Сотрудник"))
        self.geometry(f"{self._WINDOW_WIDTH}x{self._WINDOW_HEIGHT}")
        self.resizable(True, True)
        self.minsize(580, 400)
        self.transient(self.master)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

    # ------------------------------------------------------------------
    # Widgets creation
    # ------------------------------------------------------------------
    def _create_widgets(self) -> None:
        """Кнопки ВВЕРХУ + контент внизу с прокруткой."""

        # === ПАНЕЛЬ КНОПОК (ВСЕГДА ВВЕРХУ) ===
        button_panel = ctk.CTkFrame(self, fg_color=("gray85", "gray25"), height=50)
        button_panel.pack(fill="x", side="top", padx=0, pady=0)
        button_panel.pack_propagate(False)

        separator = ctk.CTkFrame(self, height=2, fg_color=("gray70", "gray40"))
        separator.pack(fill="x", side="top", padx=0, pady=0)

        btn_inner = ctk.CTkFrame(button_panel, fg_color="transparent")
        btn_inner.pack(expand=True, fill="both", padx=self._PAD_X, pady=8)

        # Левая группа кнопок
        left_buttons_frame = ctk.CTkFrame(btn_inner, fg_color="transparent")
        left_buttons_frame.pack(side="left", fill="y")

        self._btn_secondary = ctk.CTkButton(
            left_buttons_frame, text="Отмена", command=self._on_cancel,
            fg_color="gray40", hover_color="gray30", height=32, width=100,
        )
        self._btn_secondary.pack(side="left", padx=(0, 5))

        # Кнопка "Задачи" (только для view/edit)
        if self._employee and self._on_view_tasks:
            self._btn_tasks = ctk.CTkButton(
                left_buttons_frame, text="Задачи", command=self._on_view_tasks_click,
                fg_color="#1f538d", hover_color="#1a4575", height=32, width=100,
            )
            self._btn_tasks.pack(side="left", padx=(0, 5))

        # Правая группа кнопок
        right_buttons_frame = ctk.CTkFrame(btn_inner, fg_color="transparent")
        right_buttons_frame.pack(side="right", fill="y")

        self._btn_primary = ctk.CTkButton(
            right_buttons_frame, text="Сохранить", command=self._on_primary_click,
            height=32, width=160,
        )
        self._btn_primary.pack(side="right")

        # === ОСНОВНОЙ КОНТЕНТ (С ПРОКРУТКОЙ) ===
        scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll_frame.pack(fill="both", expand=True, padx=0, pady=0)

        content = ctk.CTkFrame(scroll_frame, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=self._PAD_X, pady=self._PAD_Y)

        # --- Левая колонка ---
        left_col = ctk.CTkFrame(content, fg_color="transparent")
        left_col.pack(side="left", fill="both", expand=True, padx=(0, self._PAD_X // 2))

        ctk.CTkLabel(left_col, text="Личные данные", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w",
                                                                                                    pady=(0, 4))
        self._entry_last_name = self._add_field(left_col, "Фамилия *", placeholder="Иванов")
        self._entry_first_name = self._add_field(left_col, "Имя *", placeholder="Иван")
        self._entry_middle_name = self._add_field(left_col, "Отчество", placeholder="Иванович")

        # Дата рождения (три поля)
        birth_frame = ctk.CTkFrame(left_col, fg_color="transparent")
        birth_frame.pack(fill="x", pady=self._PAD_Y)
        ctk.CTkLabel(birth_frame, text="Дата рождения", font=ctk.CTkFont(size=12)).pack(anchor="w")
        date_row = ctk.CTkFrame(birth_frame, fg_color="transparent")
        date_row.pack(fill="x", pady=(2, 0))

        self._entry_birth_day = ctk.CTkEntry(date_row, width=40, placeholder_text="ДД")
        self._entry_birth_day.pack(side="left", padx=(0, 4))
        self._entry_birth_day.bind("<KeyRelease>",
                                   lambda e: self._auto_tab(e, self._entry_birth_day, self._entry_birth_month, 2))
        self._entry_birth_day.bind("<FocusOut>", lambda e: self._pad_date_field(self._entry_birth_day, 2))

        ctk.CTkLabel(date_row, text="/").pack(side="left")

        self._entry_birth_month = ctk.CTkEntry(date_row, width=40, placeholder_text="ММ")
        self._entry_birth_month.pack(side="left", padx=(4, 4))
        self._entry_birth_month.bind("<KeyRelease>",
                                     lambda e: self._auto_tab(e, self._entry_birth_month, self._entry_birth_year, 2))
        self._entry_birth_month.bind("<FocusOut>", lambda e: self._pad_date_field(self._entry_birth_month, 2))

        ctk.CTkLabel(date_row, text="/").pack(side="left")

        self._entry_birth_year = ctk.CTkEntry(date_row, width=60, placeholder_text="ГГГГ")
        self._entry_birth_year.pack(side="left", padx=(4, 0))
        self._entry_birth_year.bind("<FocusOut>", lambda e: self._pad_date_field(self._entry_birth_year, 4))

        # Контакты
        ctk.CTkLabel(left_col, text="Контакты", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", pady=(8, 4))
        self._entry_email = self._add_field(left_col, "Email", placeholder="example@mail.ru")
        self._entry_phone = self._add_field(left_col, "Телефон", placeholder="+7 (999) 000-00-00")

        # --- Правая колонка ---
        right_col = ctk.CTkFrame(content, fg_color="transparent")
        right_col.pack(side="right", fill="both", expand=True, padx=(self._PAD_X // 2, 0))

        ctk.CTkLabel(right_col, text="Работа", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", pady=(0, 4))
        self._entry_position = self._add_field(right_col, "Должность", placeholder="Инженер")
        self._entry_rank = self._add_field(right_col, "Звание", placeholder="Старший лейтенант")
        self._entry_tab_number = self._add_field(right_col, "Табельный номер", placeholder="ТН-001")

        status_frame = ctk.CTkFrame(right_col, fg_color="transparent")
        status_frame.pack(fill="x", pady=self._PAD_Y)
        ctk.CTkLabel(status_frame, text="Статус", font=ctk.CTkFont(size=12)).pack(anchor="w")
        self._switch_is_active = ctk.CTkSwitch(status_frame, text="Активен", onvalue=True, offvalue=False)
        self._switch_is_active.pack(anchor="w", pady=(2, 0))

        ctk.CTkLabel(right_col, text="Заметки", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", pady=(8, 4))
        self._entry_notes = ctk.CTkTextbox(right_col, height=120, font=ctk.CTkFont(size=12))
        self._entry_notes.pack(fill="both", expand=True, pady=(0, self._PAD_Y))

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------
    def _add_field(self, parent: ctk.CTkFrame, label: str, placeholder: str = "") -> ctk.CTkEntry:
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", pady=self._PAD_Y)
        ctk.CTkLabel(frame, text=label, font=ctk.CTkFont(size=12)).pack(anchor="w")
        entry = ctk.CTkEntry(frame, placeholder_text=placeholder, font=ctk.CTkFont(size=12))
        entry.pack(fill="x", pady=(2, 0))
        return entry

    @staticmethod
    def _auto_tab(event, current_entry: ctk.CTkEntry, next_entry: ctk.CTkEntry, max_len: int) -> None:
        text = current_entry.get()
        filtered = re.sub(r"\D", "", text)
        if filtered != text:
            current_entry.delete(0, "end")
            current_entry.insert(0, filtered)
        if len(filtered) >= max_len and next_entry is not None:
            next_entry.focus_set()

    @staticmethod
    def _pad_date_field(entry: ctk.CTkEntry, expected_len: int) -> None:
        text = re.sub(r"\D", "", entry.get())
        if text:
            entry.delete(0, "end")
            entry.insert(0, text.zfill(expected_len))

    def _parse_birth_date(self) -> Optional[date]:
        day_str = re.sub(r"\D", "", self._entry_birth_day.get()) if self._entry_birth_day else ""
        month_str = re.sub(r"\D", "", self._entry_birth_month.get()) if self._entry_birth_month else ""
        year_str = re.sub(r"\D", "", self._entry_birth_year.get()) if self._entry_birth_year else ""

        if not day_str and not month_str and not year_str:
            return None
        if not day_str or not month_str or not year_str:
            raise ValueError("Заполните дату полностью: день, месяц и год")
        try:
            return date(int(year_str), int(month_str), int(day_str))
        except ValueError as exc:
            raise ValueError(f"Некорректная дата: {exc}") from exc

    # ------------------------------------------------------------------
    # Mode management
    # ------------------------------------------------------------------
    def _apply_mode(self) -> None:
        """Применение режима: настройка кнопок и блокировка полей."""
        readonly = self._mode == "view"

        # Блокировка / разблокировка всех полей
        all_entries = [
            self._entry_last_name, self._entry_first_name, self._entry_middle_name,
            self._entry_birth_day, self._entry_birth_month, self._entry_birth_year,
            self._entry_position, self._entry_rank, self._entry_tab_number,
            self._entry_email, self._entry_phone,
        ]
        for entry in all_entries:
            if entry is not None:
                if readonly:
                    entry.configure(state="disabled")
                else:
                    entry.configure(state="normal")

        if self._entry_notes is not None:
            if readonly:
                self._entry_notes.configure(state="disabled")
            else:
                self._entry_notes.configure(state="normal")

        if self._switch_is_active is not None:
            if readonly:
                self._switch_is_active.configure(state="disabled")
            else:
                self._switch_is_active.configure(state="normal")

        # Настройка кнопок
        if self._mode == "view":
            self._btn_primary.configure(text="Изменить", command=self._on_edit_click)
            self._btn_secondary.configure(text="Закрыть")
            if self._btn_tasks:
                self._btn_tasks.configure(state="normal")
        elif self._mode == "edit":
            self._btn_primary.configure(text="Сохранить изменения", command=self._on_save_click)
            self._btn_secondary.configure(text="Отмена", command=self._on_cancel)
            if self._btn_tasks:
                self._btn_tasks.configure(state="normal")
        else:  # create
            self._btn_primary.configure(text="Сохранить", command=self._on_save_click)
            self._btn_secondary.configure(text="Отмена", command=self._on_cancel)
            if self._btn_tasks:
                self._btn_tasks.configure(state="disabled")

    def _on_view_tasks_click(self) -> None:
        """Обработчик кнопки 'Задачи'."""
        if self._employee and self._on_view_tasks:
            log_ui_event(self._logger, widget="EmployeeDialog", event="VIEW_TASKS_CLICKED",
                         data=f"employee_id={self._employee.id}")
            self._on_view_tasks(self._employee)

    def _on_edit_click(self) -> None:
        """Переключение из view в edit."""
        self._mode = "edit"
        self.title("Редактирование")
        self._apply_mode()
        log_ui_event(self._logger, widget="EmployeeDialog", event="SWITCH_TO_EDIT",
                     data=f"employee_id={self._employee.id if self._employee else None}")

    def _on_primary_click(self) -> None:
        """Диспетчер основной кнопки (зависит от режима)."""
        if self._mode == "view":
            self._on_edit_click()
        else:
            self._on_save_click()

    # ------------------------------------------------------------------
    # Populate fields
    # ------------------------------------------------------------------
    def _populate_fields(self) -> None:
        if self._employee:
            self._populate_from_employee()
        elif self._prefill_data:
            self._populate_from_prefill()
        else:
            if self._switch_is_active:
                self._switch_is_active.select()

    def _populate_from_employee(self) -> None:
        emp = self._employee
        if self._entry_last_name:
            self._entry_last_name.insert(0, emp.last_name or "")
        if self._entry_first_name:
            self._entry_first_name.insert(0, emp.first_name or "")
        if self._entry_middle_name:
            self._entry_middle_name.insert(0, emp.middle_name or "")
        if emp.birth_date:
            if self._entry_birth_day:
                self._entry_birth_day.insert(0, str(emp.birth_date.day).zfill(2))
            if self._entry_birth_month:
                self._entry_birth_month.insert(0, str(emp.birth_date.month).zfill(2))
            if self._entry_birth_year:
                self._entry_birth_year.insert(0, str(emp.birth_date.year))
        if self._entry_position:
            self._entry_position.insert(0, emp.position or "")
        if self._entry_rank:
            self._entry_rank.insert(0, emp.rank or "")
        if self._entry_tab_number:
            self._entry_tab_number.insert(0, emp.tab_number or "")
        if self._entry_email:
            self._entry_email.insert(0, emp.email or "")
        if self._entry_phone:
            self._entry_phone.insert(0, emp.phone or "")
        if self._entry_notes and emp.notes:
            self._entry_notes.insert("1.0", emp.notes)
        if self._switch_is_active:
            if emp.is_active:
                self._switch_is_active.select()
            else:
                self._switch_is_active.deselect()

    def _populate_from_prefill(self) -> None:
        data = self._prefill_data or {}
        mapping = {
            "last_name": self._entry_last_name,
            "first_name": self._entry_first_name,
            "middle_name": self._entry_middle_name,
            "position": self._entry_position,
            "rank": self._entry_rank,
            "tab_number": self._entry_tab_number,
            "email": self._entry_email,
            "phone": self._entry_phone,
        }
        for key, entry in mapping.items():
            if entry and key in data and data[key]:
                entry.insert(0, str(data[key]))

        bd = data.get("birth_date")
        if isinstance(bd, date):
            if self._entry_birth_day:
                self._entry_birth_day.insert(0, str(bd.day).zfill(2))
            if self._entry_birth_month:
                self._entry_birth_month.insert(0, str(bd.month).zfill(2))
            if self._entry_birth_year:
                self._entry_birth_year.insert(0, str(bd.year))

        if self._entry_notes and data.get("notes"):
            self._entry_notes.insert("1.0", str(data["notes"]))

        if self._switch_is_active:
            if data.get("is_active", True):
                self._switch_is_active.select()
            else:
                self._switch_is_active.deselect()

    # ------------------------------------------------------------------
    # Save / Cancel
    # ------------------------------------------------------------------
    def _on_save_click(self) -> None:
        """Сбор данных, нормализация, валидация, вызов on_save."""
        try:
            birth_date = self._parse_birth_date()
        except ValueError as exc:
            messagebox.showwarning("Ошибка ввода", str(exc), parent=self)
            log_ui_event(self._logger, widget="EmployeeDialog", event="VALIDATION_ERROR", data=f"birth_date: {exc}")
            return

        notes_text = ""
        if self._entry_notes:
            notes_text = self._entry_notes.get("1.0", "end").strip()

        raw_last_name = self._entry_last_name.get().strip() if self._entry_last_name else ""
        raw_first_name = self._entry_first_name.get().strip() if self._entry_first_name else ""
        raw_middle_name = self._entry_middle_name.get().strip() if self._entry_middle_name else ""
        raw_position = self._entry_position.get().strip() if self._entry_position else ""
        raw_rank = self._entry_rank.get().strip() if self._entry_rank else ""
        raw_tab_number = self._entry_tab_number.get().strip() if self._entry_tab_number else ""
        raw_email = self._entry_email.get().strip() if self._entry_email else ""
        raw_phone = self._entry_phone.get().strip() if self._entry_phone else ""

        # Нормализация: пустые строки опциональных полей → None
        common_data = {
            "last_name": raw_last_name,
            "first_name": raw_first_name,
            "middle_name": raw_middle_name or None,
            "birth_date": birth_date,
            "position": raw_position or None,
            "rank": raw_rank or None,
            "tab_number": raw_tab_number or None,
            "email": raw_email or None,
            "phone": raw_phone or None,
            "notes": notes_text or None,
            "is_active": self._switch_is_active.get() if self._switch_is_active else True,
        }

        try:
            if self._mode == "edit" and self._employee:
                schema = EmployeeUpdateSchema(id=self._employee.id, **common_data)
                self._on_save(self._employee.id, schema)
            else:
                schema = EmployeeCreateSchema(**common_data)
                self._on_save(None, schema)

            log_ui_event(
                self._logger, widget="EmployeeDialog", event="SAVE_CLICKED",
                data=f"mode={self._mode}, employee_id={self._employee.id if self._employee else None}",
            )
            self.destroy()

        except ValidationError as exc:
            errors = []
            for error in exc.errors():
                field = " → ".join(str(loc) for loc in error["loc"])
                msg = error["msg"]
                errors.append(f"• {field}: {msg}")
            messagebox.showwarning("Проверьте введённые данные", "\n".join(errors), parent=self)
            log_ui_event(self._logger, widget="EmployeeDialog", event="VALIDATION_ERROR", data=str(exc))

        except Exception as exc:
            messagebox.showerror("Ошибка сохранения", str(exc), parent=self)
            log_ui_event(self._logger, widget="EmployeeDialog", event="SAVE_ERROR", data=str(exc))

    def _on_cancel(self) -> None:
        log_ui_event(self._logger, widget="EmployeeDialog", event="CANCELLED", data=f"mode={self._mode}")
        self.destroy()
