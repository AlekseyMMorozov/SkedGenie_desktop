# src/presentation/dialogs/engagement_dialog.py
"""Объединенный диалог создания/редактирования Задействования."""
from __future__ import annotations

import logging
import re
from datetime import time
from tkinter import messagebox
from typing import Callable, List, Optional
from uuid import UUID

import customtkinter as ctk
from pydantic import ValidationError

from src.application.schemas.engagement_schemas import (
    EngagementTemplateCreateSchema,
    EngagementTemplateReadSchema,
    EngagementTemplateUpdateSchema,
    EngagementTypeCreateSchema,
    EngagementTypeReadSchema,
    EngagementTypeUpdateSchema,
)
from src.application.services.engagement_color_service import EngagementColorService
from src.domain.engagements.engagement_type_model import DurationType
from src.presentation.async_bridge import AsyncBridge
from src.presentation.controllers.engagement_template_controller import EngagementTemplateController
from src.presentation.controllers.engagement_type_controller import EngagementTypeController


class EngagementDialog(ctk.CTkToplevel):
    """Единый диалог для управления Задействованием (Тип + Шаблон)."""

    RECURRENCE_OPTIONS = ["Произвольно", "Ежедневно", "Еженедельно", "Ежемесячно"]
    HEX_PATTERN = re.compile(r'^#[0-9A-Fa-f]{6}$')

    # Маппинг для отображения русских названий в ComboBox
    DURATION_TYPE_LABELS = {
        DurationType.LONG.value: "Длительный",
        DurationType.DAILY.value: "Суточный",
        DurationType.SHORT.value: "Короткий"
    }

    # Обратный маппинг: Русское название -> Внутреннее значение
    LABEL_TO_DURATION_TYPE = {v: k for k, v in DURATION_TYPE_LABELS.items()}

    def __init__(
            self,
            master: ctk.CTk,
            logger: logging.Logger,
            mode: str,
            type_controller: EngagementTypeController,
            template_controller: EngagementTemplateController,
            bridge: AsyncBridge,
            on_success: Callable[[], None],
            color_service: EngagementColorService,
            template: Optional[EngagementTemplateReadSchema] = None,
            engagement_type: Optional[EngagementTypeReadSchema] = None,
            available_types: Optional[List[EngagementTypeReadSchema]] = None,
            **kwargs,
    ) -> None:
        super().__init__(master, **kwargs)
        self._logger = logger
        self._mode = mode
        self._type_controller = type_controller
        self._template_controller = template_controller
        self._bridge = bridge
        self._on_success = on_success
        self._color_service = color_service
        self._template = template
        self._engagement_type = engagement_type
        self._available_types = available_types or []

        self._setup_window()
        self._create_widgets()

        # ✅ Применяем тему после создания виджетов
        self._apply_theme_to_self()

        if self._mode == "edit":
            self._populate_fields()
        else:
            # Предзаполнение по умолчанию
            self._start_hour_entry.insert(0, "08")
            self._start_min_entry.insert(0, "00")
            self._end_hour_entry.insert(0, "11")
            self._end_min_entry.insert(0, "00")

            # Генерация уникального цвета для нового типа
            existing_colors = [t.color_hex for t in self._available_types if t.color_hex]
            try:
                new_color = self._color_service.generate_unique_color(existing_colors)
                self._color_entry.delete(0, "end")
                self._color_entry.insert(0, new_color)
            except Exception as e:
                self._logger.warning(f"Не удалось сгенерировать уникальный цвет: {e}")

            self._update_duration_label()

        # Инициализация состояния видимости полей
        self._on_duration_type_change(None)

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
            # Fallback на безопасный светлый оттенок
            self.configure(fg_color="#F5F5F5")
            self._update_borders(self, "#C0C0C0")

    def _update_borders(self, widget, border_color: str) -> None:
        """Рекурсивно добавляет границы полям ввода."""
        try:
            w_class = widget.__class__.__name__
            if w_class in ("CTkEntry", "CTkComboBox", "CTkTextbox"):
                widget.configure(border_width=1, border_color=border_color)

            for child in widget.winfo_children():
                self._update_borders(child, border_color)
        except Exception:
            pass

    def _setup_window(self) -> None:
        title = "Новое задействование" if self._mode == "create" else "Изменить задействование"
        self.title(title)
        self.geometry("700x550")
        self.resizable(False, False)
        self.transient(self.master)

    def _create_widgets(self) -> None:
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(15, 10))
        ctk.CTkButton(btn_frame, text="Сохранить", width=120, command=self._on_save_click).pack(side="right",
                                                                                                padx=(5, 0))
        ctk.CTkButton(btn_frame, text="Отмена", width=120, fg_color="gray40", hover_color="gray30",
                      command=self.destroy).pack(side="right")

        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        grid = ctk.CTkFrame(container, fg_color="transparent")
        grid.pack(fill="x", expand=True)
        grid.grid_columnconfigure(0, weight=1)
        grid.grid_columnconfigure(1, weight=1)

        # Левая колонка
        left_col = ctk.CTkFrame(grid, fg_color="transparent")
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=5)

        ctk.CTkLabel(left_col, text="Параметры типа", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w",
                                                                                                     pady=(0, 5))

        ctk.CTkLabel(left_col, text="Группа / Тип").pack(anchor="w")
        type_controls = ctk.CTkFrame(left_col, fg_color="transparent")
        type_controls.pack(fill="x", pady=(2, 5))
        type_names = list(dict.fromkeys([t.category for t in self._available_types]))
        self._category_combo = ctk.CTkComboBox(type_controls, values=type_names, state="readonly")
        self._category_combo.pack(side="left", fill="x", expand=True, padx=(0, 5))
        ctk.CTkButton(type_controls, text="+", width=30, command=self._open_new_type_dialog).pack(side="right")

        ctk.CTkLabel(left_col, text="Тип длительности").pack(anchor="w", pady=(5, 0))
        display_values = list(self.DURATION_TYPE_LABELS.values())
        self._duration_combo = ctk.CTkComboBox(
            left_col,
            values=display_values,
            state="readonly",
            command=self._on_duration_type_change
        )
        self._duration_combo.pack(fill="x", pady=(2, 5))
        self._duration_combo.set(self.DURATION_TYPE_LABELS[DurationType.SHORT.value])

        ctk.CTkLabel(left_col, text="Цвет (HEX)").pack(anchor="w", pady=(5, 0))
        self._color_entry = ctk.CTkEntry(left_col, placeholder_text="#4CAF50")
        self._color_entry.pack(fill="x", pady=(2, 0))
        self._color_entry.insert(0, "#4CAF50")

        self._recurrence_frame = ctk.CTkFrame(left_col, fg_color="transparent")
        ctk.CTkLabel(self._recurrence_frame, text="Периодичность").pack(anchor="w")
        self._recurrence_combo = ctk.CTkComboBox(
            self._recurrence_frame, values=self.RECURRENCE_OPTIONS, state="readonly"
        )
        self._recurrence_combo.pack(fill="x", pady=(2, 0))
        self._recurrence_combo.set("Произвольно")

        # Правая колонка
        right_col = ctk.CTkFrame(grid, fg_color="transparent")
        right_col.grid(row=0, column=1, sticky="nsew", padx=(10, 0), pady=5)

        ctk.CTkLabel(right_col, text="Время", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", pady=(0, 5))

        self._time_frame = ctk.CTkFrame(right_col, fg_color="transparent")

        start_row = ctk.CTkFrame(self._time_frame, fg_color="transparent")
        start_row.pack(fill="x", pady=(0, 5))
        ctk.CTkLabel(start_row, text="Начало:", width=60).pack(side="left")
        self._start_hour_entry = ctk.CTkEntry(start_row, width=40, placeholder_text="ЧЧ")
        self._start_hour_entry.pack(side="left", padx=(0, 3))
        self._start_hour_entry.bind("<KeyRelease>", lambda e: self._update_duration_label())
        ctk.CTkLabel(start_row, text=":").pack(side="left")
        self._start_min_entry = ctk.CTkEntry(start_row, width=40, placeholder_text="ММ")
        self._start_min_entry.pack(side="left", padx=(3, 0))
        self._start_min_entry.bind("<KeyRelease>", lambda e: self._update_duration_label())

        end_row = ctk.CTkFrame(self._time_frame, fg_color="transparent")
        end_row.pack(fill="x", pady=(0, 5))
        ctk.CTkLabel(end_row, text="Конец:", width=60).pack(side="left")
        self._end_hour_entry = ctk.CTkEntry(end_row, width=40, placeholder_text="ЧЧ")
        self._end_hour_entry.pack(side="left", padx=(0, 3))
        self._end_hour_entry.bind("<KeyRelease>", lambda e: self._update_duration_label())
        ctk.CTkLabel(end_row, text=":").pack(side="left")
        self._end_min_entry = ctk.CTkEntry(end_row, width=40, placeholder_text="ММ")
        self._end_min_entry.pack(side="left", padx=(3, 0))
        self._end_min_entry.bind("<KeyRelease>", lambda e: self._update_duration_label())

        self._duration_label = ctk.CTkLabel(
            self._time_frame, text="Длительность: —",
            font=ctk.CTkFont(size=12, weight="bold"), text_color="#1565C0"
        )
        self._duration_label.pack(anchor="w", pady=(0, 10))

        self._right_col_separator = ctk.CTkFrame(right_col, height=1, fg_color="gray50")
        self._right_col_separator.pack(fill="x", pady=5)

        ctk.CTkLabel(right_col, text="Детали задействования", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w",
                                                                                                             pady=(5,
                                                                                                                   5))

        ctk.CTkLabel(right_col, text="Полное название *").pack(anchor="w")
        self._name_entry = ctk.CTkEntry(right_col, placeholder_text="Наряд по КПП")
        self._name_entry.pack(fill="x", pady=(2, 5))

        ctk.CTkLabel(right_col, text="Краткое имя *").pack(anchor="w")
        self._short_name_entry = ctk.CTkEntry(right_col, placeholder_text="КПП")
        self._short_name_entry.pack(fill="x", pady=(2, 0))

    def _on_duration_type_change(self, event=None) -> None:
        label = self._duration_combo.get()
        dtype = self.LABEL_TO_DURATION_TYPE.get(label, DurationType.SHORT.value)

        if hasattr(self, '_time_frame'):
            self._time_frame.pack_forget()
        if hasattr(self, '_recurrence_frame'):
            self._recurrence_frame.pack_forget()

        if dtype == DurationType.LONG.value:
            pass
        elif dtype == DurationType.DAILY.value:
            if hasattr(self, '_time_frame') and hasattr(self, '_right_col_separator'):
                self._time_frame.pack(fill="x", pady=(0, 5), before=self._right_col_separator)
            if hasattr(self, '_recurrence_frame'):
                self._recurrence_frame.pack(fill="x", pady=(10, 0), side="top", anchor="w")
        else:
            if hasattr(self, '_time_frame') and hasattr(self, '_right_col_separator'):
                self._time_frame.pack(fill="x", pady=(0, 5), before=self._right_col_separator)

        self._update_duration_label()

    def _update_duration_label(self) -> None:
        label = self._duration_combo.get()
        dtype = self.LABEL_TO_DURATION_TYPE.get(label, DurationType.SHORT.value)

        if dtype == DurationType.LONG.value:
            if hasattr(self, '_duration_label'):
                self._duration_label.configure(
                    text="Длительность: определяется при планировании",
                    text_color="#1565C0"
                )
            return

        if not hasattr(self, '_start_hour_entry'):
            return

        start_t = self._parse_time_from_entries(self._start_hour_entry, self._start_min_entry)
        end_t = self._parse_time_from_entries(self._end_hour_entry, self._end_min_entry)

        if not start_t or not end_t:
            if hasattr(self, '_duration_label'):
                self._duration_label.configure(
                    text="Длительность: введите корректное время",
                    text_color="gray"
                )
            return

        start_mins = start_t.hour * 60 + start_t.minute
        end_mins = end_t.hour * 60 + end_t.minute

        if dtype == DurationType.DAILY.value:
            end_mins += 24 * 60
        else:
            if end_mins < start_mins:
                end_mins += 24 * 60
            elif end_mins == start_mins:
                if hasattr(self, '_duration_label'):
                    self._duration_label.configure(
                        text="⚠ Время начала и конца совпадают",
                        text_color="#D32F2F"
                    )
                return

        duration_h = (end_mins - start_mins) / 60.0
        hours = int(duration_h)
        minutes = int(round((duration_h - hours) * 60))

        if minutes > 0:
            text = f"Длительность: {hours}ч {minutes}мин"
        else:
            text = f"Длительность: {hours}ч"

        if hasattr(self, '_duration_label'):
            self._duration_label.configure(text=text, text_color="#1565C0")

    def _open_new_type_dialog(self) -> None:
        # Используем цвет текущего диалога для input dialog
        current_fg = self.cget("fg_color")
        dialog = ctk.CTkInputDialog(
            text="Введите название новой группы:",
            title="Новая группа",
            fg_color=current_fg
        )
        new_category = dialog.get_input()
        if new_category and new_category.strip():
            current_values = list(self._category_combo.cget("values"))
            clean_name = new_category.strip()
            if clean_name not in current_values:
                current_values.append(clean_name)
                self._category_combo.configure(values=current_values)
            self._category_combo.set(clean_name)

    def _populate_fields(self) -> None:
        if self._engagement_type:
            et = self._engagement_type
            categories = list(self._category_combo.cget("values"))
            if et.category not in categories:
                categories.append(et.category)
                self._category_combo.configure(values=categories)
            self._category_combo.set(et.category)

            dt_value = et.duration_type.value
            ru_label = self.DURATION_TYPE_LABELS.get(dt_value, self.DURATION_TYPE_LABELS[DurationType.SHORT.value])
            self._duration_combo.set(ru_label)

            if et.default_start_time:
                self._start_hour_entry.insert(0, f"{et.default_start_time.hour:02d}")
                self._start_min_entry.insert(0, f"{et.default_start_time.minute:02d}")
                start_mins = et.default_start_time.hour * 60 + et.default_start_time.minute
                end_mins = start_mins + int(et.default_duration_hours * 60)
                end_h = (end_mins // 60) % 24
                end_m = end_mins % 60
                self._end_hour_entry.insert(0, f"{end_h:02d}")
                self._end_min_entry.insert(0, f"{end_m:02d}")

            self._color_entry.delete(0, "end")
            self._color_entry.insert(0, et.color_hex)

        if self._template:
            self._name_entry.insert(0, self._template.name)
            self._short_name_entry.insert(0, self._template.short_name)
            if self._template.custom_color_hex:
                self._color_entry.delete(0, "end")
                self._color_entry.insert(0, self._template.custom_color_hex)

    def _parse_time_from_entries(self, hour_entry: ctk.CTkEntry, min_entry: ctk.CTkEntry) -> Optional[time]:
        try:
            h_str = hour_entry.get().strip()
            m_str = min_entry.get().strip()
            if not h_str or not m_str:
                return None
            h = int(h_str)
            m = int(m_str)
            if not (0 <= h <= 23 and 0 <= m <= 59):
                return None
            return time(h, m)
        except (ValueError, TypeError):
            return None

    def _validate_color(self) -> str:
        color = self._color_entry.get().strip()
        if not color or not self.HEX_PATTERN.match(color):
            return "#4CAF50"
        return color

    def _find_type_by_category(self, category: str) -> Optional[EngagementTypeReadSchema]:
        for t in self._available_types:
            if t.category == category:
                return t
        return None

    def _on_save_click(self) -> None:
        name_val = self._name_entry.get().strip()
        short_name_val = self._short_name_entry.get().strip()
        errors = []

        # Получаем актуальный цвет границ из темы
        root = self.winfo_toplevel()
        reset_color = "#C0C0C0"
        if hasattr(root, '_theme_colors'):
            reset_color = root._theme_colors.get("border_color", "#C0C0C0")

        if not name_val:
            errors.append("• Полное название")
            self._name_entry.configure(border_color="red")
        else:
            self._name_entry.configure(border_color=reset_color)

        if not short_name_val:
            errors.append("• Краткое имя")
            self._short_name_entry.configure(border_color="red")
        else:
            self._short_name_entry.configure(border_color=reset_color)

        selected_category = self._category_combo.get()
        if not selected_category:
            errors.append("• Группа / Тип")

        if errors:
            messagebox.showwarning(
                "Заполните обязательные поля",
                "Следующие поля обязательны:\n" + "\n".join(errors),
                parent=self
            )
            return

        try:
            label = self._duration_combo.get()
            dtype = self.LABEL_TO_DURATION_TYPE.get(label, DurationType.SHORT.value)
            valid_color = self._validate_color()

            type_data = {
                "name": selected_category,
                "category": selected_category,
                "duration_type": dtype,
                "color_hex": valid_color,
                "allow_overlap": False,
            }

            if dtype == DurationType.LONG.value:
                type_data["default_start_time"] = time(0, 0)
                type_data["default_duration_hours"] = 24.0
                type_data["min_duration_hours"] = 48.0
                type_data["max_duration_hours"] = 8760.0
            else:
                start_t = self._parse_time_from_entries(self._start_hour_entry, self._start_min_entry)
                end_t = self._parse_time_from_entries(self._end_hour_entry, self._end_min_entry)

                if not start_t or not end_t:
                    messagebox.showwarning("Ошибка", "Некорректное время начала или конца (формат ЧЧ:ММ)", parent=self)
                    return

                type_data["default_start_time"] = start_t
                start_mins = start_t.hour * 60 + start_t.minute
                end_mins = end_t.hour * 60 + end_t.minute

                if dtype == DurationType.DAILY.value:
                    end_mins += 24 * 60
                else:
                    if end_mins < start_mins:
                        end_mins += 24 * 60
                    elif end_mins == start_mins:
                        messagebox.showwarning("Ошибка", "Время начала и конца совпадают", parent=self)
                        return

                duration_h = (end_mins - start_mins) / 60.0
                type_data["default_duration_hours"] = duration_h

                if dtype == DurationType.DAILY.value:
                    type_data["min_duration_hours"] = 18.0
                    type_data["max_duration_hours"] = 30.0
                else:
                    type_data["min_duration_hours"] = 0.5
                    type_data["max_duration_hours"] = 18.0

            template_data = {
                "name": name_val,
                "short_name": short_name_val,
                "custom_color_hex": None,
            }

            if self._mode == "create":
                self._execute_create(type_data, template_data, selected_category)
            else:
                self._execute_update(type_data, template_data, selected_category)

        except ValueError as e:
            messagebox.showwarning("Ошибка ввода", str(e), parent=self)

    def _execute_create(self, type_data: dict, template_data: dict, category: str):
        async def _save():
            existing_type = self._find_type_by_category(category)
            if existing_type:
                type_id = existing_type.id
            else:
                type_schema = EngagementTypeCreateSchema(**type_data)
                created_type = await self._type_controller.create(type_schema)
                type_id = created_type.id

            tmpl_schema = EngagementTemplateCreateSchema(type_id=type_id, **template_data)
            await self._template_controller.create(tmpl_schema)
            return True

        self._bridge.run(
            _save(),
            on_success=lambda _: self._handle_success(),
            on_error=lambda e: messagebox.showerror("Ошибка", str(e), parent=self)
        )

    def _execute_update(self, type_data: dict, template_data: dict, category: str):
        async def _save():
            existing_type = self._find_type_by_category(category)
            if existing_type:
                type_id = existing_type.id
                if self._engagement_type and self._engagement_type.id == existing_type.id:
                    type_schema = EngagementTypeUpdateSchema(**type_data)
                    await self._type_controller.update(existing_type.id, type_schema)
            else:
                type_schema = EngagementTypeCreateSchema(**type_data)
                created = await self._type_controller.create(type_schema)
                type_id = created.id

            if self._template:
                tmpl_schema = EngagementTemplateUpdateSchema(**template_data)
                await self._template_controller.update(self._template.id, tmpl_schema)
            return True

        self._bridge.run(
            _save(),
            on_success=lambda _: self._handle_success(),
            on_error=lambda e: messagebox.showerror("Ошибка", str(e), parent=self)
        )

    def _handle_success(self):
        self.after(0, self._on_success)
        self.destroy()
