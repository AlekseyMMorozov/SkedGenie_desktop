# src/presentation/settings.py
"""
Управление настройками пользователя для приложения SkedGenie.

Предоставляет класс :class:`Settings` для загрузки и сохранения
пользовательских настроек в JSON-файл (``data/settings.json``).

Поддерживаемые настройки:
    - ``font_size``: Размер шрифта (SMALL/MEDIUM/LARGE).
    - ``appearance_mode``: Тема оформления (System/Light/Dark).
    - ``color_theme``: Цветовая схема (blue/green/dark-blue).

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

from pydantic import BaseModel, ValidationError

from src.presentation.font_manager import FontSize


class AppSettings(BaseModel):
    """Pydantic-модель настроек приложения.

    Attributes:
        font_size: Базовый размер шрифта (SMALL/MEDIUM/LARGE).
        appearance_mode: Тема оформления CustomTkinter (System/Light/Dark).
        color_theme: Цветовая схема CustomTkinter (blue/green/dark-blue).
    """

    font_size: FontSize = FontSize.MEDIUM
    appearance_mode: str = "System"
    color_theme: str = "blue"


class Settings:
    """Менеджер настроек пользователя.

    Отвечает за загрузку, валидацию и сохранение настроек в JSON-файл.
    Хранит актуальное состояние в памяти для быстрого доступа.

    Attributes:
        _settings_path: Путь к файлу настроек.
        _logger: Логгер для событий менеджера.
        _current: Текущие настройки (кэш в памяти).
    """

    def __init__(
            self,
            settings_path: Path,
            logger: Optional[logging.Logger] = None,
    ) -> None:
        """Инициализация менеджера настроек.

        Args:
            settings_path: Путь к файлу настроек (например, ``data/settings.json``).
            logger: Логгер для событий менеджера. Если ``None`` — создаётся
                собственный логгер с именем модуля.
        """
        self._settings_path = Path(settings_path)
        self._logger = logger or logging.getLogger(__name__)
        self._current: AppSettings = AppSettings()

        self._logger.debug(
            "Settings: инициализирован, путь=%s",
            self._settings_path,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def load(self) -> AppSettings:
        """Загрузить настройки из файла.

        Если файл отсутствует или повреждён, возвращает значения по умолчанию
        и логирует предупреждение.

        Returns:
            Загруженные (или дефолтные) настройки.
        """
        if not self._settings_path.exists():
            self._logger.info(
                "Settings: файл %s не найден, используются настройки по умолчанию",
                self._settings_path,
            )
            self._current = AppSettings()
            return self._current

        try:
            with self._settings_path.open("r", encoding="utf-8") as f:
                data = json.load(f)

            # Pydantic валидация
            self._current = AppSettings(**data)
            self._logger.info(
                "Settings: настройки загружены из %s (font_size=%s)",
                self._settings_path,
                self._current.font_size.name,
            )
            return self._current

        except json.JSONDecodeError as exc:
            self._logger.error(
                "Settings: ошибка парсинга JSON в %s: %s. Используются дефолтные настройки.",
                self._settings_path,
                exc,
            )
            self._current = AppSettings()
            return self._current

        except ValidationError as exc:
            self._logger.error(
                "Settings: ошибка валидации в %s: %s. Используются дефолтные настройки.",
                self._settings_path,
                exc,
            )
            self._current = AppSettings()
            return self._current

        except Exception as exc:  # noqa: BLE001
            self._logger.error(
                "Settings: непредвиденная ошибка при загрузке %s: %s",
                self._settings_path,
                exc,
                exc_info=True,
            )
            self._current = AppSettings()
            return self._current

    def save(self, settings: Optional[AppSettings] = None) -> None:
        """Сохранить настройки в файл (атомарно через временный файл).

        Args:
            settings: Настройки для сохранения. Если ``None`` — сохраняются
                текущие настройки из кэша.
        """
        if settings is not None:
            self._current = settings

        try:
            # Создание родительской директории (если не существует)
            self._settings_path.parent.mkdir(parents=True, exist_ok=True)

            # Атомарная запись через временный файл
            data = self._current.model_dump(mode="json")

            # Создаём временный файл в той же директории (для атомарного rename)
            with tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    dir=self._settings_path.parent,
                    delete=False,
                    suffix=".tmp",
            ) as tmp_file:
                json.dump(data, tmp_file, indent=2, ensure_ascii=False)
                tmp_path = Path(tmp_file.name)

            # Атомарная замена (на POSIX-системах; на Windows может потребоваться unlink)
            try:
                tmp_path.replace(self._settings_path)
            except PermissionError:
                # Windows: если файл занят, пробуем удалить и переименовать
                if self._settings_path.exists():
                    self._settings_path.unlink()
                tmp_path.rename(self._settings_path)

            self._logger.info(
                "Settings: настройки сохранены в %s (font_size=%s)",
                self._settings_path,
                self._current.font_size.name,
            )

        except Exception as exc:  # noqa: BLE001
            self._logger.error(
                "Settings: ошибка при сохранении в %s: %s",
                self._settings_path,
                exc,
                exc_info=True,
            )
            raise

    def get_current(self) -> AppSettings:
        """Получить текущие настройки (из кэша в памяти).

        Returns:
            Актуальные настройки.
        """
        return self._current

    def update_font_size(self, new_size: FontSize) -> None:
        """Обновить размер шрифта и сохранить настройки.

        Args:
            new_size: Новый размер шрифта.
        """
        old_size = self._current.font_size
        if new_size is old_size:
            self._logger.debug(
                "Settings: update_font_size пропущен (размер не изменился)",
            )
            return

        self._current = self._current.model_copy(update={"font_size": new_size})
        self.save()
        self._logger.info(
            "Settings: размер шрифта изменён %s → %s",
            old_size.name,
            new_size.name,
        )

    def update_appearance_mode(self, mode: str) -> None:
        """Обновить тему оформления и сохранить настройки.

        Args:
            mode: Новая тема (System/Light/Dark).
        """
        if mode not in ("System", "Light", "Dark"):
            self._logger.warning(
                "Settings: некорректная тема '%s', используется 'System'",
                mode,
            )
            mode = "System"

        self._current = self._current.model_copy(update={"appearance_mode": mode})
        self.save()
        self._logger.info("Settings: тема оформления изменена на %s", mode)

    def update_color_theme(self, theme: str) -> None:
        """Обновить цветовую схему и сохранить настройки.

        Args:
            theme: Новая цветовая схема (blue/green/dark-blue).
        """
        if theme not in ("blue", "green", "dark-blue"):
            self._logger.warning(
                "Settings: некорректная цветовая схема '%s', используется 'blue'",
                theme,
            )
            theme = "blue"

        self._current = self._current.model_copy(update={"color_theme": theme})
        self.save()
        self._logger.info("Settings: цветовая схема изменена на %s", theme)
