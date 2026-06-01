# src/presentation/dialogs/settings_dialog.py
"""
Диалог настроек интерфейса.

Позволяет безопасно изменять:
    - Цветовую схему (предопределенные пресеты).
    - Размер шрифта (Small/Medium/Large).

Все изменения применяются мгновенно для предпросмотра,
но сохраняются в JSON только при нажатии «Сохранить».
"""
from __future__ import annotations

import logging
from typing import Callable, Optional

import customtkinter as ctk

from src.presentation.font_manager import FontSize
from src.presentation.settings import COLOR_PRESETS, AppSettings, Settings


class SettingsDialog(ctk.CTkToplevel):
    """Окно настроек внешнего вида."""

    def __init__(
            self,
            master: ctk.CTk,
            settings: Settings,
            logger: logging.Logger,
            on_preview: Callable[[str, FontSize], None],
            **kwargs,
    ) -> None:
        super().__init__(master, **kwargs)
        self._settings = settings
        self._logger = logger
        self._on_preview = on_preview

        # Запоминаем исходные значения для отмены
        current = settings.get_current().ui
        self._original_preset = current.color_preset
        self._original_font = current.font_size

        # Текущие (предпросмотр) значения
        self._current_preset: str = self._original_preset
        self._current_font: FontSize = self._original_font

        self._setup_window()
        self._create_widgets()
        self._restore_state()

        # Применяем тему к самому диалогу сразу после создания виджетов
        self._apply_theme_to_self()

    def _setup_window(self) -> None:
        self.title("Настройки интерфейса")
        self.resizable(False, False)
        self.transient(self.master)
        self.grab_set()

        # Центрирование
        self.update_idletasks()
        w, h = 400, 380
        x = self.master.winfo_x() + (self.master.winfo_width() - w) // 2
        y = self.master.winfo_y() + (self.master.winfo_height() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _apply_theme_to_self(self) -> None:
        """Применяет цвета темы к самому диалогу для визуального отделения."""
        # Пытаемся получить цвета из главного окна
        root = self.winfo_toplevel()
        if hasattr(root, '_theme_colors'):
            colors = root._theme_colors
            dialog_bg = colors.get("dialog_bg", "#FFFFFF")
            border_color = colors.get("border_color", "#C0C0C0")

            # Устанавливаем фон диалога
            self.configure(fg_color=dialog_bg)

            # Добавляем рамку вокруг всего содержимого для контраста
            # Так как CTkToplevel не имеет border_width, оборачиваем контент в Frame с границей
            # Но проще задать фон и надеяться на контраст с app_bg.
            # Для гарантии можно добавить тень или просто использовать отличный от белого цвет.
        else:
            # Fallback на дефолтный пресет
            preset = COLOR_PRESETS.get(self._current_preset, COLOR_PRESETS["default"])
            self.configure(fg_color=preset["dialog"])

    def _create_widgets(self) -> None:
        # Основной фрейм с небольшим отступом и, опционально, границей
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # --- Секция цветов ---
        ctk.CTkLabel(main_frame, text="Цветовая схема", font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 10))

        self._color_vars = ctk.StringVar(value=self._current_preset)
        colors_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        colors_frame.pack(fill="x", pady=(0, 20))

        for key, preset in COLOR_PRESETS.items():
            row = ctk.CTkFrame(colors_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)

            ctk.CTkRadioButton(
                row, text=preset["name"], variable=self._color_vars, value=key,
                command=lambda k=key: self._on_color_change(k),
            ).pack(side="left")

            # Мини-превью цветов
            preview = ctk.CTkFrame(row, width=40, height=20, corner_radius=4,
                                   fg_color=preset["app"], border_width=1, border_color="gray70")
            preview.pack(side="right", padx=(10, 0))
            inner = ctk.CTkFrame(preview, width=20, height=16, corner_radius=2, fg_color=preset["dialog"])
            inner.place(relx=0.5, rely=0.5, anchor="center")

        # --- Секция шрифтов ---
        ctk.CTkLabel(main_frame, text="Размер шрифта", font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 10))

        self._font_seg = ctk.CTkSegmentedButton(
            main_frame, values=["SMALL", "MEDIUM", "LARGE"],
            command=self._on_font_change,
        )
        self._font_seg.pack(anchor="w", pady=(0, 30))

        # --- Кнопки ---
        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.pack(fill="x", side="bottom")

        ctk.CTkButton(btn_frame, text="Сохранить", width=100, command=self._on_save).pack(side="right", padx=(5, 0))
        ctk.CTkButton(btn_frame, text="Отмена", width=100, fg_color="gray40", command=self._on_cancel).pack(
            side="right")

    def _restore_state(self) -> None:
        self._color_vars.set(self._current_preset)
        self._font_seg.set(self._current_font.name)

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------
    def _on_color_change(self, preset_key: str) -> None:
        self._current_preset = preset_key
        self._apply_preview()
        # Обновляем фон самого диалога при смене пресета в предпросмотре
        self._apply_theme_to_self()

    def _on_font_change(self, value: str) -> None:
        try:
            self._current_font = FontSize[value]
        except KeyError:
            self._current_font = FontSize.MEDIUM
        self._apply_preview()

    def _apply_preview(self) -> None:
        """Мгновенное применение для предпросмотра."""
        self._on_preview(self._current_preset, self._current_font)

    def _on_save(self) -> None:
        self._settings.update_ui_settings(self._current_preset, self._current_font)
        self._logger.info("SettingsDialog: настройки сохранены")
        self.destroy()

    def _on_cancel(self) -> None:
        # Возврат к исходным значениям
        if self._current_preset != self._original_preset or self._current_font != self._original_font:
            self._on_preview(self._original_preset, self._original_font)
        self.destroy()
