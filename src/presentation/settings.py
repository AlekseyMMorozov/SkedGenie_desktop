# src/presentation/settings.py
"""
Управление настройками пользователя для приложения SkedGenie.

Предоставляет класс :class:`Settings` для загрузки и сохранения
пользовательских настроек в JSON-файл (``data/settings.json``).

Поддерживаемые настройки:
    - ``ui.color_preset``: Безопасный пресет цветов (app_bg/dialog_bg).
    - ``ui.font_size``: Размер шрифта (SMALL/MEDIUM/LARGE).
    - ``appearance_mode``: Тема оформления (System/Light/Dark).
    - ``color_theme``: Цветовая схема акцентов (blue/green/dark-blue).

Архитектура:
    - Валидация через Pydantic модель :class:`AppSettings`.
    - Атомарное сохранение через временный файл (защита от повреждения).
    - Fallback на значения по умолчанию при отсутствии/повреждении файла.
    - SRP: класс не применяет настройки к UI — это ответственность
      :mod:`main.py` и виджетов.
"""
from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, ValidationError

from src.presentation.font_manager import FontSize

# ------------------------------------------------------------------
# Безопасные цветовые пресеты
# ------------------------------------------------------------------
# app_bg: Фон главного окна (светлее)
# dialog_bg: Фон диалогов (контрастнее, чтобы не сливались)
COLOR_PRESETS = {
    "default": {"name": "Стандартный", "app": "#F3F3F3", "dialog": "#FFFFFF"},
    "soft_gray": {"name": "Мягкий серый", "app": "#E8E8E8", "dialog": "#F5F5F5"},
    "warm_beige": {"name": "Теплый беж", "app": "#F0EBE0", "dialog": "#FAF8F5"},
    "cool_blue": {"name": "Холодный голубой", "app": "#E6EBF0", "dialog": "#F2F5F8"},
    "mint": {"name": "Светлая мята", "app": "#E8F0EC", "dialog": "#F4F9F6"},
}


class UISettings(BaseModel):
    """Настройки интерфейса (цвета, шрифты)."""
    color_preset: str = Field(default="default", description="Ключ цветового пресета")
    font_size: FontSize = Field(default=FontSize.MEDIUM, description="Базовый размер шрифта")


class AppSettings(BaseModel):
    """Pydantic-модель настроек приложения."""
    ui: UISettings = Field(default_factory=UISettings)

    # Legacy поля для обратной совместимости со старыми конфигами
    appearance_mode: str = "System"
    color_theme: str = "blue"


class Settings:
    """Менеджер настроек пользователя."""

    def __init__(
            self,
            settings_path: Path,
            logger: Optional[logging.Logger] = None,
    ) -> None:
        self._settings_path = Path(settings_path)
        self._logger = logger or logging.getLogger(__name__)
        self._current: AppSettings = AppSettings()

        self._logger.debug("Settings: инициализирован, путь=%s", self._settings_path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def load(self) -> AppSettings:
        """Загрузить настройки из файла."""
        if not self._settings_path.exists():
            self._logger.info("Settings: файл %s не найден, используются настройки по умолчанию", self._settings_path)
            self._current = AppSettings()
            return self._current

        try:
            with self._settings_path.open("r", encoding="utf-8") as f:
                data = json.load(f)

            # Миграция старых настроек font_size в ui.font_size
            if "font_size" in data and "ui" not in data:
                data["ui"] = {"font_size": data["font_size"]}

            self._current = AppSettings(**data)
            self._logger.info(
                "Settings: настройки загружены (preset=%s, font=%s)",
                self._current.ui.color_preset,
                self._current.ui.font_size.name,
            )
            return self._current

        except (json.JSONDecodeError, ValidationError) as exc:
            self._logger.error("Settings: ошибка чтения %s: %s. Сброс на дефолт.", self._settings_path, exc)
            self._current = AppSettings()
            return self._current

        except Exception as exc:  # noqa: BLE001
            self._logger.error("Settings: непредвиденная ошибка: %s", exc, exc_info=True)
            self._current = AppSettings()
            return self._current

    def save(self, settings: Optional[AppSettings] = None) -> None:
        """Сохранить настройки атомарно."""
        if settings is not None:
            self._current = settings

        try:
            self._settings_path.parent.mkdir(parents=True, exist_ok=True)
            data = self._current.model_dump(mode="json")

            with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8",
                    dir=self._settings_path.parent, delete=False, suffix=".tmp",
            ) as tmp_file:
                json.dump(data, tmp_file, indent=2, ensure_ascii=False)
                tmp_path = Path(tmp_file.name)

            try:
                tmp_path.replace(self._settings_path)
            except PermissionError:
                if self._settings_path.exists():
                    self._settings_path.unlink()
                tmp_path.rename(self._settings_path)

            self._logger.info("Settings: сохранены в %s", self._settings_path)

        except Exception as exc:  # noqa: BLE001
            self._logger.error("Settings: ошибка сохранения: %s", exc, exc_info=True)
            raise

    def get_current(self) -> AppSettings:
        return self._current

    # ------------------------------------------------------------------
    # UI Helpers
    # ------------------------------------------------------------------
    def get_colors(self) -> dict[str, str]:
        """Возвращает безопасные цвета текущего пресета."""
        preset_key = self._current.ui.color_preset
        preset = COLOR_PRESETS.get(preset_key, COLOR_PRESETS["default"])
        return {"app_bg": preset["app"], "dialog_bg": preset["dialog"]}

    def update_ui_settings(self, color_preset: str, font_size: FontSize) -> None:
        """Обновить настройки UI и сохранить."""
        valid_preset = color_preset if color_preset in COLOR_PRESETS else "default"

        new_ui = self._current.ui.model_copy(update={
            "color_preset": valid_preset,
            "font_size": font_size,
        })
        new_settings = self._current.model_copy(update={"ui": new_ui})
        self.save(new_settings)

        self._logger.info(
            "Settings: UI обновлен (preset=%s, font=%s)",
            valid_preset, font_size.name,
        )

    # ------------------------------------------------------------------
    # Legacy Methods (для совместимости)
    # ------------------------------------------------------------------
    def update_font_size(self, new_size: FontSize) -> None:
        self.update_ui_settings(self._current.ui.color_preset, new_size)

    def update_appearance_mode(self, mode: str) -> None:
        if mode not in ("System", "Light", "Dark"):
            mode = "System"
        self._current = self._current.model_copy(update={"appearance_mode": mode})
        self.save()

    def update_color_theme(self, theme: str) -> None:
        if theme not in ("blue", "green", "dark-blue"):
            theme = "blue"
        self._current = self._current.model_copy(update={"color_theme": theme})
        self.save()
