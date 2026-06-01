# src/main.py
"""
Точка входа в приложение SkedGenie.

Отвечает за:
    - Инициализацию системы логирования (консоль + файл).
    - Загрузку пользовательских настроек (размер шрифта, тема).
    - Применение темы CustomTkinter (глобально, до создания окна).
    - Инициализацию базы данных (создание таблиц при первом запуске).
    - Создание инфраструктуры (session_factory, repository, controller).
    - Запуск главного окна с DI-компонентами.
    - Подключение GUI-хэндлера логирования и привязку его к панели логов.
    - Graceful shutdown при закрытии.
"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import customtkinter as ctk

from src.application.services.employee_link_service import EmployeeLinkService
from src.application.services.engagement_color_service import EngagementColorService
from src.core.logging_config import (
    setup_logging,
    get_logger,
    attach_gui_handler,
)
from src.infrastructure.db.async_database_session import (
    init_db,
    get_session_factory,
)
from src.infrastructure.repositories.employee_repository import EmployeeSQLAlchemyRepository
from src.infrastructure.repositories.engagement_template_repository import EngagementTemplateSQLAlchemyRepository
from src.infrastructure.repositories.engagement_type_repository import EngagementTypeSQLAlchemyRepository
from src.infrastructure.repositories.task_repository import TaskSQLAlchemyRepository
from src.presentation.controllers.employee_controller import EmployeeController
from src.presentation.controllers.engagement_template_controller import EngagementTemplateController
from src.presentation.controllers.engagement_type_controller import EngagementTypeController
from src.presentation.controllers.task_controller import TaskController
from src.presentation.main_window import MainWindow
from src.presentation.settings import Settings, AppSettings

# Константы
DATABASE_URL: str = "sqlite+aiosqlite:///./data/skedgenie.db"
DEV_RESET_DB: bool = False  # True для разработки (пересоздание БД при каждом запуске)
SETTINGS_PATH: Path = Path("data/settings.json")


def main() -> None:
    """Главная функция запуска приложения."""
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
    settings_manager = None
    try:
        logger.info("Этап 2: Загрузка настроек...")
        settings_manager = Settings(SETTINGS_PATH, logger=logger)
        app_settings = settings_manager.load()

        ui = app_settings.ui
        logger.debug(
            "Настройки: font_size=%s, appearance=%s, color_theme=%s",
            ui.font_size.name,
            app_settings.appearance_mode,
            app_settings.color_theme,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Не удалось загрузить настройки, используются дефолтные: %s",
            exc,
        )
        app_settings = AppSettings()

    # ------------------------------------------------------------------
    # Этап 3: Применение темы CustomTkinter (без FontManager)
    # ------------------------------------------------------------------
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

        # --- Общая session_factory ---
        session_factory = get_session_factory(DATABASE_URL)
        logger.debug("session_factory создана")

        # --- Task-ветка ---
        task_repository = TaskSQLAlchemyRepository(session_factory)
        task_controller = TaskController(task_repository, logger)
        logger.debug("TaskController создан")

        # --- Employee-ветка ---
        employee_repository = EmployeeSQLAlchemyRepository(session_factory)
        employee_link_service = EmployeeLinkService(
            employee_repository=employee_repository,
            task_repository=task_repository,
            logger=logger,
        )
        employee_controller = EmployeeController(
            employee_repository=employee_repository,
            link_service=employee_link_service,
            logger=logger,
        )
        logger.debug("EmployeeController создан")

        # --- Engagement Type & Template ветка (для Варианта A) ---
        engagement_type_repository = EngagementTypeSQLAlchemyRepository(session_factory)
        engagement_template_repository = EngagementTemplateSQLAlchemyRepository(session_factory)

        color_service = EngagementColorService(logger)

        engagement_type_controller = EngagementTypeController(
            repository=engagement_type_repository,
            color_service=color_service,
            logger=logger,
        )
        engagement_template_controller = EngagementTemplateController(
            repository=engagement_template_repository,
            logger=logger,
        )
        logger.debug("Engagement Type & Template Controllers созданы")

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
            employee_controller=employee_controller,
            engagement_type_controller=engagement_type_controller,
            engagement_template_controller=engagement_template_controller,
            color_service=color_service,
            logger=logger,
            settings=settings_manager,
        )

        # ✅ КРИТИЧНО: привязываем обработчик закрытия окна
        window._setup_closing_handler()

        logger.info("Главное окно создано")
    except Exception as exc:
        logger.critical(
            "Критическая ошибка при создании главного окна: %s",
            exc,
            exc_info=True,
        )
        sys.exit(1)

    # ------------------------------------------------------------------
    # Этап 7: Создание GUI-хэндлера и привязка к панели логов
    # ------------------------------------------------------------------
    try:
        logger.debug("Этап 7: Создание GUI-хэндлера и привязка к панели логов...")
        attach_gui_handler(window)
        window.attach_log_handler()
        logger.info("GUI-хэндлер логирования создан и привязан к панели")
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
        # Тест потокобезопасности
        def test_gui_update():
            logger.info("✓ тест GUI пройден")

        window.after(200, test_gui_update)
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

        # ✅ Для Windows: гарантируем чистый выход процесса
        if sys.platform == "win32":
            import os
            os._exit(0)
        else:
            sys.exit(0)


if __name__ == "__main__":
    main()
