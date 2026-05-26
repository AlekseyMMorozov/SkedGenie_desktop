# src/presentation/dialogs/employee_card_dialog.py
"""
Диалог просмотра и редактирования карточки сотрудника.

Режимы работы:
    - mode="view" → read-only отображение всех полей, кнопки "Изменить" и "Закрыть".
    - mode="edit" → редактируемые поля, кнопки "Сохранить" и "Отмена".

Переключение режимов:
    Inline через пересборку main_frame. Старый контент уничтожается,
    новый создаётся с нужным параметром `editable`. Такой подход
    надёжнее, чем манипуляции с pack(after=...) по индексам.

Ответственность:
    - Отображение полной информации о сотруднике.
    - Inline переключение между режимами view и edit.
    - Сбор данных из редактируемых виджетов через widgets_registry.
    - Валидация через EmployeeUpdateSchema.
    - Логирование UI-событий.

Границы:
    - НЕ выполняет persistence — делегирует через callback on_save.
    - НЕ обращается к БД напрямую.
    - НЕ изменяет исходный EmployeeReadSchema (работает с копией данных).
"""
from __future__ import annotations

import logging
from datetime import date
from tkinter import messagebox
from typing import Callable, Optional
from uuid import UUID

import customtkinter as ctk
from pydantic import ValidationError

from src.application.schemas.employee_schemas import (
    EmployeeReadSchema,
    EmployeeUpdateSchema,
)
from src.core.logging_config import log_ui_event
from src.presentation.font_manager import get_font_manager
from src.presentation.widgets.employee_card_sections import (
    EditableWidget,
    create_contact_section,
    create_engagement_section,
    create_header_section,
    create_metadata_section,
    create_notes_section,
    create_personal_section,
    create_work_section,
)


class EmployeeCardDialog(ctk.CTkToplevel):
    """Модальный диалог просмотра и редактирования карточки сотрудника."""

    def __init__(
        self,
        master: ctk.CTk,
        logger: logging.Logger,
        employee: EmployeeReadSchema,
        on_save: Callable[[UUID, EmployeeUpdateSchema], None],
        mode: str = "view",
        **kwargs,
    ) -> None:
        """Инициализация диалога.

        Args:
            master: Родительское окно.
            logger: Логгер для записи событий.
            employee: Данные сотрудника для отображения.
            on_save: Callback для сохранения изменений (employee_id, schema).
            mode: Начальный режим ("view" или "edit").
            **kwargs: Дополнительные параметры для CTkToplevel.
        """
        super().__init__(master, **kwargs)
        self._logger = logger
        self._employee = employee
        self._on_save = on_save
        self._mode = mode
        self._fm = get_font_manager()

        # Реестр редактируемых виджетов (заполняется при editable=True)
        self._editable_widgets: dict[str, EditableWidget] = {}

        # Корневой контейнер (пересоздаётся при смене режима)
        self._main_frame: Optional[ctk.CTkFrame] = None

        self._setup_window()
        self._build_ui()

        log_ui_event(
            self._logger,
            widget="EmployeeCardDialog",
            event="OPENED",
            data=f"employee_id={employee.id}, mode={mode}",
        )

    # ------------------------------------------------------------------
    # Настройка окна
    # ------------------------------------------------------------------
    def _setup_window(self) -> None:
        """Настроить размеры, позицию и модальность окна."""
        self.title(f"Карточка сотрудника: {self._employee.get_full_name()}")
        self.geometry("700x800")
        self.resizable(False, True)

        # Модальность
        self.transient(self.master)
        self.grab_set()

        # Центрирование
        self.update_idletasks()
        parent_x = self.master.winfo_rootx()
        parent_y = self.master.winfo_rooty()
        parent_width = self.master.winfo_width()
        parent_height = self.master.winfo_height()

        dialog_width = 700
        dialog_height = 800

        x = parent_x + (parent_width - dialog_width) // 2
        y = parent_y + (parent_height - dialog_height) // 2

        self.geometry(f"+{x}+{y}")

    # ------------------------------------------------------------------
    # Построение UI
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Построить или перестроить весь UI диалога.

        Уничтожает предыдущий main_frame (если есть) и создаёт новый.
        Используется как при первичной инициализации, так и при
        inline-переключении режимов view ↔ edit.
        """
        # Уничтожение предыдущего контента
        if self._main_frame is not None:
            self._main_frame.destroy()
            self._main_frame = None

        # Очистка реестра виджетов
        self._editable_widgets = {}

        # Основной контейнер
        self._main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Прокручиваемая область для секций
        scrollable_frame = ctk.CTkScrollableFrame(self._main_frame)
        scrollable_frame.pack(fill="both", expand=True)

        # === Заголовок (всегда read-only) ===
        create_header_section(scrollable_frame, self._employee, self._fm)

        # === Персональные данные ===
        _, personal_widgets = create_personal_section(
            scrollable_frame,
            self._employee,
            self._fm,
            editable=(self._mode == "edit"),
        )
        self._editable_widgets.update(personal_widgets)

        # === Контакты ===
        _, contact_widgets = create_contact_section(
            scrollable_frame,
            self._employee,
            self._fm,
            editable=(self._mode == "edit"),
        )
        self._editable_widgets.update(contact_widgets)

        # === Работа ===
        _, work_widgets = create_work_section(
            scrollable_frame,
            self._employee,
            self._fm,
            editable=(self._mode == "edit"),
        )
        self._editable_widgets.update(work_widgets)

        # === Допуски (всегда read-only) ===
        create_engagement_section(
            scrollable_frame,
            self._employee.engagement_ids,
            self._fm,
        )

        # === Заметки ===
        _, notes_widgets = create_notes_section(
            scrollable_frame,
            self._employee.notes,
            self._fm,
            editable=(self._mode == "edit"),
        )
        self._editable_widgets.update(notes_widgets)

        # === Метаданные (всегда read-only) ===
        create_metadata_section(scrollable_frame, self._employee, self._fm)

        # === Кнопки действий ===
        button_frame = ctk.CTkFrame(self._main_frame, fg_color="transparent")
        button_frame.pack(fill="x", pady=(15, 0))

        self._create_action_buttons(button_frame)

    def _create_action_buttons(self, button_frame: ctk.CTkFrame) -> None:
        """Создать кнопки действий в зависимости от режима."""
        if self._mode == "view":
            # Режим просмотра: кнопка "Изменить" + "Закрыть"
            close_button = ctk.CTkButton(
                button_frame,
                text="Закрыть",
                command=self._on_close,
                fg_color="gray",
            )
            close_button.pack(side="right", padx=(10, 0))

            edit_button = ctk.CTkButton(
                button_frame,
                text="Изменить",
                command=self._on_edit_click,
            )
            edit_button.pack(side="right")
        else:
            # Режим редактирования: "Сохранить" + "Отмена"
            cancel_button = ctk.CTkButton(
                button_frame,
                text="Отмена",
                command=self._on_cancel,
                fg_color="gray",
            )
            cancel_button.pack(side="right", padx=(10, 0))

            save_button = ctk.CTkButton(
                button_frame,
                text="Сохранить",
                command=self._on_save_click,
            )
            save_button.pack(side="right")

    # ------------------------------------------------------------------
    # Переключение режимов
    # ------------------------------------------------------------------
    def _switch_mode(self, new_mode: str) -> None:
        """Переключить режим и перестроить UI.

        Args:
            new_mode: Новый режим ("view" или "edit").
        """
        if new_mode == self._mode:
            return

        self._mode = new_mode
        log_ui_event(
            self._logger,
            widget="EmployeeCardDialog",
            event=f"SWITCH_TO_{new_mode.upper()}_MODE",
            data=f"employee_id={self._employee.id}",
        )
        self._build_ui()

    # ------------------------------------------------------------------
    # Обработчики событий
    # ------------------------------------------------------------------
    def _on_edit_click(self) -> None:
        """Переключить диалог в режим редактирования."""
        self._switch_mode("edit")

    def _on_cancel(self) -> None:
        """Вернуться в режим просмотра (отменить изменения)."""
        self._switch_mode("view")

    def _on_save_click(self) -> None:
        """Обработать нажатие кнопки 'Сохранить'."""
        try:
            # Сбор данных из редактируемых полей
            data = self._collect_editable_data()

            # Валидация через Pydantic
            schema = EmployeeUpdateSchema(**data)

            # Вызов callback
            self._on_save(self._employee.id, schema)

            log_ui_event(
                self._logger,
                widget="EmployeeCardDialog",
                event="SAVE_CLICKED",
                data=f"employee_id={self._employee.id}",
            )

            # Закрытие диалога
            self.destroy()

        except ValidationError as e:
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
                widget="EmployeeCardDialog",
                event="VALIDATION_ERROR",
                data=error_message,
            )

        except Exception as exc:
            messagebox.showerror(
                "Ошибка",
                f"Произошла непредвиденная ошибка:\n{exc}",
                parent=self,
            )
            self._logger.exception("Unexpected error in EmployeeCardDialog._on_save_click")

    def _collect_editable_data(self) -> dict:
        """Собрать данные из редактируемых полей.

        Использует реестр `_editable_widgets` для доступа к текущим
        значениям Entry/Textbox. Поля, отсутствующие в реестре (режим
        read-only), берутся из исходного `_employee`.

        Returns:
            Словарь с данными для EmployeeUpdateSchema.
        """
        def get_entry_value(key: str, current_value: Optional[str]) -> Optional[str]:
            """Получить значение из entry по ключу или вернуть текущее."""
            widget = self._editable_widgets.get(key)
            if widget is None:
                return current_value
            if isinstance(widget, ctk.CTkEntry):
                value = widget.get().strip()
                return value if value else None
            if isinstance(widget, ctk.CTkTextbox):
                value = widget.get("1.0", "end-1c").strip()
                return value if value else None
            return current_value

        # Дата рождения — особая обработка (строка → date)
        birth_date_value: Optional[date] = self._employee.birth_date
        birth_widget = self._editable_widgets.get("birth_date")
        if birth_widget is not None and isinstance(birth_widget, ctk.CTkEntry):
            raw = birth_widget.get().strip()
            if not raw:
                birth_date_value = None
            else:
                try:
                    birth_date_value = date.fromisoformat(raw)
                except ValueError:
                    # Передаём строку — пусть Pydantic выбросит ValidationError
                    birth_date_value = raw  # type: ignore[assignment]

        return {
            "last_name": self._employee.last_name,
            "first_name": self._employee.first_name,
            "middle_name": self._employee.middle_name,
            "position": get_entry_value("position", self._employee.position),
            "tab_number": get_entry_value("tab_number", self._employee.tab_number),
            "email": get_entry_value("email", self._employee.email),
            "phone": get_entry_value("phone", self._employee.phone),
            "birth_date": birth_date_value,
            "notes": get_entry_value("notes", self._employee.notes),
        }

    def _on_close(self) -> None:
        """Закрыть диалог."""
        log_ui_event(
            self._logger,
            widget="EmployeeCardDialog",
            event="CLOSED",
            data=f"employee_id={self._employee.id}",
        )
        self.destroy()
