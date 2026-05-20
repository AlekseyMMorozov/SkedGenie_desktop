# main.py

"""
Файл: main.py
Описание: Composition Root приложения. Инициализация логирования, асинхронной БД,
          DI-контейнера, сборка UI-графов и запуск цикла событий Qt.
Архитектура: Composition Root / Presentation слой. Единственная точка зависимости от инфраструктуры.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

# Infrastructure
from src.infrastructure.db.async_database_session import init_db, get_session_factory
from src.infrastructure.repositories.task_repository import TaskSQLAlchemyRepository

# Presentation
from src.presentation.main_window import MainWindow
from src.presentation.controllers.task_controller import TaskController
from src.presentation.widgets.task_manager_widget import TaskManagerWidget

# --- Конфигурация ---
DB_URL = "sqlite+aiosqlite:///./data/skedgenie.db"
DEV_MODE = True
LOG_LEVEL = logging.DEBUG if DEV_MODE else logging.INFO


def setup_logging() -> None:
    """Базовая настройка логирования для всего приложения."""
    logging.basicConfig(
        level=LOG_LEVEL,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


async def bootstrap(app: QApplication) -> None:
    """Асинхронная инициализация зависимостей и монтирование UI."""
    logger = logging.getLogger("bootstrap")

    # 1. Инициализация БД
    logger.info("Initializing database...")
    Path("data").mkdir(exist_ok=True)
    await init_db(dev_reset=DEV_MODE)

    # 2. Создание репозитория и контроллера (DI)
    logger.info("Creating repository & controller...")
    session_factory = get_session_factory(database_url=DB_URL)
    repo = TaskSQLAlchemyRepository(session_factory=session_factory)
    controller = TaskController(repository=repo)

    # 3. Сборка интерфейса
    logger.info("Assembling UI composition...")
    main_window = MainWindow(task_controller=controller)

    # Интеграция виджета задач в первую вкладку
    task_widget = TaskManagerWidget(controller=controller)
    main_window.tab_widget.removeTab(0)  # Удаляем заглушку
    main_window.tab_widget.insertTab(0, task_widget, "Задачи планирования")

    # 4. Связка сигналов контроллера с лог-панелью главного окна
    controller.operation_succeeded.connect(lambda msg: main_window.log_message(msg, "INFO"))
    controller.operation_failed.connect(lambda err: main_window.log_message(err, "ERROR"))

    # Обновление состояния Undo/Redo (заглушка для Итерации 4)
    controller.operation_succeeded.connect(lambda _: main_window.update_undo_redo_state(False, False))

    # 5. Первичная загрузка данных
    controller.load_tasks()

    main_window.show()
    logger.info("Application bootstrap completed successfully.")


def main() -> None:
    setup_logging()
    logger = logging.getLogger("main")

    try:
        app = QApplication(sys.argv)
        app.setApplicationName("SkedGenie Desktop")
        app.setApplicationVersion("0.1.0-alpha")
        app.setOrganizationName("SkedGenie")

        # Запуск асинхронной инициализации в отдельном цикле до старта Qt
        asyncio.run(bootstrap(app))

        logger.info("Starting Qt event loop...")
        sys.exit(app.exec())
    except Exception as exc:
        logger.critical(f"Fatal startup error: {exc}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

