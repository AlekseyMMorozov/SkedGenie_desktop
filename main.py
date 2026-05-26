# main.py
"""
Точка входа в приложение SkedGenie.

Отвечает за:
    - Инициализацию системы логирования (консоль + файл).
    - Загрузку пользовательских настроек (размер шрифта, тема).
    - Применение темы CustomTkinter (глобально, до создания окна).
    - Инициализацию базы данных (создание таблиц при первом запуске).
    - Создание инфраструктуры (session_factory, repository, controller).
    - Запуск главного окна с DI-компонентами.
    - Graceful shutdown при закрытии.
"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import customtkinter as ctk

from src.core.logging_config import (
    setup_logging,
    get_logger,
    attach_gui_handler,
)
from src.infrastructure.db.async_database_session import (
    init_db,
    get_session_factory,
)
from src.infrastructure.repositories.task_repository import TaskSQLAlchemyRepository
from src.presentation.controllers.task_controller import TaskController
from src.presentation.main_window import MainWindow
from src.presentation.settings import Settings


# Константы
DATABASE_URL: str = "sqlite+aiosqlite:///./data/skedgenie.db"
DEV_RESET_DB: bool = True  # True для разработки (пересоздание БД при каждом запуске)
SETTINGS_PATH: Path = Path("data/settings.json")


def main() -> None:
    """Главная функция запуска приложения.

    Последовательность инициализации:
        1. Настройка логирования (консоль + файл, без GUI).
        2. Загрузка пользовательских настроек (размер шрифта, тема).
        3. Применение темы CustomTkinter (глобально, без Tk-корня).
        4. Инициализация БД (создание таблиц).
        5. Создание инфраструктуры (session_factory → repository → controller).
        6. Создание главного окна (создаёт AsyncBridge и FontManager внутри).
        7. Подключение GUI-хэндлера логирования.
        8. Запуск mainloop.
    """
    # ------------------------------------------------------------------
    # Этап 1: Инициализация логирования (без GUI)
    # ------------------------------------------------------------------
    setup_logging(
        log_level=logging.DEBUG,
        log_file="logs/app.log",
        console_output=True,
        file_output=True,
    )
    logger = get_logger("main")
    logger.info("=== Запуск SkedGenie ===")
    logger.debug("Этап 1: Логирование инициализировано")

    # ------------------------------------------------------------------
    # Этап 2: Загрузка пользовательских настроек
    # ------------------------------------------------------------------
    try:
        logger.info("Этап 2: Загрузка настроек...")
        settings_manager = Settings(SETTINGS_PATH, logger=logger)
        app_settings = settings_manager.load()

        logger.debug(
            "Настройки: font_size=%s, appearance=%s, color_theme=%s",
            app_settings.font_size.name,
            app_settings.appearance_mode,
            app_settings.color_theme,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Не удалось загрузить настройки, используются дефолтные: %s",
            exc,
        )
        from src.presentation.settings import AppSettings
        app_settings = AppSettings()

    # ------------------------------------------------------------------
    # Этап 3: Применение темы CustomTkinter (без FontManager)
    # ------------------------------------------------------------------
    # ВАЖНО: FontManager создаётся внутри MainWindow, так как CTkFont
    # требует инициализированный Tk-интерпретатор (default root window).
    # Здесь применяем только глобальные настройки темы — они работают
    # без Tk-корня.
    try:
        logger.info("Этап 3: Применение темы CustomTkinter...")

        ctk.set_appearance_mode(app_settings.appearance_mode)
        ctk.set_default_color_theme(app_settings.color_theme)

        logger.info(
            "Тема применена (appearance=%s, color_theme=%s)",
            app_settings.appearance_mode,
            app_settings.color_theme,
        )
    except Exception as exc:
        logger.critical(
            "Критическая ошибка при применении темы: %s",
            exc,
            exc_info=True,
        )
        sys.exit(1)

    # ------------------------------------------------------------------
    # Этап 4: Инициализация базы данных
    # ------------------------------------------------------------------
    try:
        logger.info("Этап 4: Инициализация базы данных...")
        logger.debug("DATABASE_URL: %s", DATABASE_URL)
        logger.debug("DEV_RESET_DB: %s", DEV_RESET_DB)

        asyncio.run(init_db(dev_reset=DEV_RESET_DB))

        logger.info("База данных успешно инициализирована")
    except Exception as exc:
        logger.critical(
            "Критическая ошибка при инициализации БД: %s",
            exc,
            exc_info=True,
        )
        sys.exit(1)

    # ------------------------------------------------------------------
    # Этап 5: Создание инфраструктуры
    # ------------------------------------------------------------------
    try:
        logger.info("Этап 5: Создание инфраструктуры...")

        session_factory = get_session_factory(DATABASE_URL)
        logger.debug("session_factory создана")

        repository = TaskSQLAlchemyRepository(session_factory)
        logger.debug("TaskSQLAlchemyRepository создан")

        task_controller = TaskController(repository, logger)
        logger.debug("TaskController создан")

        logger.info("Инфраструктура успешно создана")
    except Exception as exc:
        logger.critical(
            "Критическая ошибка при создании инфраструктуры: %s",
            exc,
            exc_info=True,
        )
        sys.exit(1)

    # ------------------------------------------------------------------
    # Этап 6: Создание главного окна
    # ------------------------------------------------------------------
    try:
        logger.info("Этап 6: Создание главного окна...")

        window = MainWindow(
            task_controller=task_controller,
            logger=logger,
            settings=settings_manager,
        )
        logger.info("Главное окно создано")
    except Exception as exc:
        logger.critical(
            "Критическая ошибка при создании главного окна: %s",
            exc,
            exc_info=True,
        )
        sys.exit(1)

    # ------------------------------------------------------------------
    # Этап 7: Подключение GUI-хэндлера логирования
    # ------------------------------------------------------------------
    try:
        logger.debug("Этап 7: Подключение GUI-хэндлера логирования...")
        attach_gui_handler(window)
        logger.info("GUI-хэндлер логирования подключён")
    except Exception as exc:
        logger.error(
            "Ошибка при подключении GUI-хэндлера (некритично): %s",
            exc,
            exc_info=True,
        )

    # ------------------------------------------------------------------
    # Этап 8: Запуск главного цикла
    # ------------------------------------------------------------------
    logger.info("Этап 8: Запуск mainloop")
    try:
        window.run()
    except Exception as exc:
        logger.critical(
            "Критическая ошибка в mainloop: %s",
            exc,
            exc_info=True,
        )
        sys.exit(1)
    finally:
        logger.info("=== SkedGenie завершён ===")


if __name__ == "__main__":
    main()
