# src/presentation/widgets/settings_widget.py
"""
Виджет вкладки "Настройки".

Предоставляет интерфейс для настройки внешнего вида приложения:
    - Выбор цветовой схемы (безопасные пресеты).
    - Выбор размера шрифта.
Изменения применяются мгновенно для предпросмотра,
но сохраняются в JSON только при нажатии «Сохранить».
"""
from __future__ import annotations

import logging
from typing import Callable

import customtkinter as ctk

from src.presentation.font_manager import FontSize
from src.presentation.settings import COLOR_PRESETS, Settings


class SettingsWidget(ctk.CTkFrame):
    """Страница настроек интерфейса."""

    def __init__(
            self,
            master: ctk.CTkFrame,
            settings: Settings,
            logger: logging.Logger,
            on_theme_changed: Callable[[str, FontSize], None],
            **kwargs,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self._settings = settings
        self._logger = logger
        self._on_theme_changed = on_theme_changed

        # Запоминаем исходные значения для отслеживания изменений
        current = settings.get_current().ui
        self._saved_preset = current.color_preset
        self._saved_font = current.font_size

        self._create_widgets()

    def _create_widgets(self) -> None:
        # Заголовок страницы
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 10))

        ctk.CTkLabel(
            header, text="Настройки интерфейса",
            font=("Segoe UI", 24, "bold"), anchor="w",
        ).pack(side="left")

        # Кнопка сохранения (справа в заголовке)
        self._btn_save = ctk.CTkButton(
            header, text="💾 Сохранить", width=120, height=36,
            command=self._on_save_click, state="disabled",
        )
        self._btn_save.pack(side="right")

        # Статус-бар (под заголовком)
        self._status_label = ctk.CTkLabel(
            self, text="", font=("Segoe UI", 12), text_color="gray50", anchor="w",
        )
        self._status_label.pack(fill="x", padx=20, pady=(0, 20))

        # Контейнер для настроек
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=40, anchor="nw")

        # --- Секция цветов ---
        ctk.CTkLabel(
            content, text="Цветовая схема",
            font=("Segoe UI", 16, "bold"), anchor="w",
        ).pack(anchor="w", pady=(0, 15))

        self._color_var = ctk.StringVar(value=self._saved_preset)
        colors_frame = ctk.CTkFrame(content, fg_color="transparent")
        colors_frame.pack(fill="x", pady=(0, 30))

        for key, preset in COLOR_PRESETS.items():
            row = ctk.CTkFrame(colors_frame, fg_color="transparent")
            row.pack(fill="x", pady=4)

            ctk.CTkRadioButton(
                row, text=preset["name"], variable=self._color_var, value=key,
                font=("Segoe UI", 14),
                command=lambda k=key: self._on_setting_changed(k, None),
            ).pack(side="left", padx=(10, 0))

            # Мини-превью
            preview = ctk.CTkFrame(
                row, width=60, height=30, corner_radius=6,
                fg_color=preset["app"], border_width=1, border_color="gray70",
            )
            preview.pack(side="right", padx=(10, 10))
            inner = ctk.CTkFrame(
                preview, width=30, height=22, corner_radius=4,
                fg_color=preset["dialog"],
            )
            inner.place(relx=0.5, rely=0.5, anchor="center")

        # --- Секция шрифтов ---
        ctk.CTkLabel(
            content, text="Размер шрифта",
            font=("Segoe UI", 16, "bold"), anchor="w",
        ).pack(anchor="w", pady=(0, 15))

        self._font_seg = ctk.CTkSegmentedButton(
            content, values=["SMALL", "MEDIUM", "LARGE"],
            font=("Segoe UI", 14), height=40,
            command=lambda v: self._on_setting_changed(None, v),
        )
        self._font_seg.set(self._saved_font.name)
        self._font_seg.pack(anchor="w", pady=(0, 20))

        # --- Информация ---
        info_text = (
            "💡 Изменения применяются мгновенно для предпросмотра.\n"
            "Нажмите «Сохранить», чтобы зафиксировать настройки."
        )
        ctk.CTkLabel(
            content, text=info_text,
            font=("Segoe UI", 12), text_color="gray50", anchor="w",
        ).pack(anchor="w", pady=(20, 0))

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------
    def _get_current_values(self) -> tuple[str, FontSize]:
        preset = self._color_var.get()
        try:
            font = FontSize[self._font_seg.get()]
        except KeyError:
            font = FontSize.MEDIUM
        return preset, font

    def _on_setting_changed(self, preset_key: str | None, font_value: str | None) -> None:
        """Обработчик изменения любой настройки (live preview)."""
        preset, font = self._get_current_values()

        # Применяем тему мгновенно
        self._on_theme_changed(preset, font)

        # Проверяем, есть ли несохраненные изменения
        has_changes = (preset != self._saved_preset or font != self._saved_font)
        self._btn_save.configure(state="normal" if has_changes else "disabled")

        if has_changes:
            self._status_label.configure(text="● Есть несохранённые изменения", text_color="#E67E22")
        else:
            self._status_label.configure(text="", text_color="gray50")

    def _on_save_click(self) -> None:
        """Сохранение текущих значений в файл."""
        preset, font = self._get_current_values()
        self._settings.update_ui_settings(preset, font)

        # Обновляем сохраненное состояние
        self._saved_preset = preset
        self._saved_font = font

        self._btn_save.configure(state="disabled")
        self._status_label.configure(text="✓ Настройки сохранены", text_color="#27AE60")
        self._logger.info("SettingsWidget: настройки сохранены (preset=%s, font=%s)", preset, font.name)

        # Сброс статуса через 3 секунды
        self.after(3000, lambda: self._status_label.configure(text="", text_color="gray50"))