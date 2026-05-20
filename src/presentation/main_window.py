# src/presentation/main_window.py

"""
Файл: src/presentation/main_window.py
Описание: Главное окно приложения. Каркас навигации, меню, статус-бара и настраиваемой панели логов.
Архитектура: Presentation слой. Реализует строгую инъекцию зависимостей и нативный UX.
"""
from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QMainWindow,
    QMenuBar,
    QMenu,
    QStatusBar,
    QTabWidget,
    QDockWidget,
    QPlainTextEdit,
    QMessageBox,
    QWidget,
)

# Forward reference для избежания циклических импортов на этапе сборки
from src.presentation.controllers.task_controller import TaskController


class MainWindow(QMainWindow):
    """Главное окно приложения SkedGenie Desktop.

    Содержит:
    - QTabWidget (центр навигации)
    - QMenuBar (минимальный набор действий)
    - QStatusBar (краткие статусные сообщения)
    - QDockWidget (лог-панель с возможностью скрытия)
    """

    request_close_with_save = Signal()

    def __init__(self, task_controller: Optional[TaskController] = None, parent=None):
        super().__init__(parent)
        self._controller = task_controller
        self._logger = logging.getLogger(__name__)

        self._setup_window_properties()
        self._setup_central_widget()
        self._setup_menu_bar()
        self._setup_status_bar()
        self._setup_log_dock()
        self._connect_signals()

        self._logger.info("MainWindow initialized successfully.")

    def _setup_window_properties(self) -> None:
        """Базовая настройка окна."""
        self.setWindowTitle("SkedGenie Desktop")
        self.resize(1280, 850)
        # Нативный стиль вкладок без лишних границ
        self.setDocumentMode(True) if hasattr(self, "setDocumentMode") else None

    def _setup_central_widget(self) -> None:
        """Инициализация центрального виджета с вкладками."""
        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.setTabPosition(QTabWidget.North)
        self.tab_widget.setTabsClosable(False)
        self.setCentralWidget(self.tab_widget)

        # Заглушки вкладок (будут заполнены виджетами в Итерации 1-2)
        self.tab_widget.addTab(QWidget(), "Задачи")
        self.tab_widget.addTab(QWidget(), "Сотрудники")
        self.tab_widget.addTab(QWidget(), "Задействования")
        self.tab_widget.addTab(QWidget(), "График")

    def _setup_menu_bar(self) -> None:
        """Создание минимального меню согласно требованиям."""
        menubar = self.menuBar()

        # Файл
        file_menu = menubar.addMenu("&Файл")
        exit_action = QAction("Выход", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Правка (заготовка под ActionStack)
        edit_menu = menubar.addMenu("&Правка")
        self.undo_action = QAction("Отменить", self)
        self.undo_action.setShortcut("Ctrl+Z")
        self.undo_action.setEnabled(False)
        edit_menu.addAction(self.undo_action)

        self.redo_action = QAction("Повторить", self)
        self.redo_action.setShortcut("Ctrl+Shift+Z")
        self.redo_action.setEnabled(False)
        edit_menu.addAction(self.redo_action)

        # Вид
        view_menu = menubar.addMenu("&Вид")
        self.toggle_log_action = QAction("Показать/Скрыть панель логов", self)
        self.toggle_log_action.setCheckable(True)
        self.toggle_log_action.setChecked(False)
        view_menu.addAction(self.toggle_log_action)

        # Сервис
        service_menu = menubar.addMenu("&Сервис")
        settings_action = QAction("Настройки", self)
        settings_action.triggered.connect(self._on_settings_requested)
        service_menu.addAction(settings_action)

        # Справка
        help_menu = menubar.addMenu("&Справка")
        about_action = QAction("О приложении", self)
        about_action.triggered.connect(self._on_about_requested)
        help_menu.addAction(about_action)

    def _setup_status_bar(self) -> None:
        """Инициализация строки состояния для кратких сообщений."""
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Готово к работе", 2500)

    def _setup_log_dock(self) -> None:
        """Настройка плавающей/стыкуемой панели логов."""
        self.log_dock = QDockWidget("Лог операций", self)
        self.log_dock.setObjectName("LogDock")
        self.log_dock.setFeatures(QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetMovable)
        self.log_dock.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.RightDockWidgetArea)

        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.log_dock.setWidget(self.log_text)

        self.addDockWidget(Qt.BottomDockWidgetArea, self.log_dock)
        self.log_dock.hide()  # Скрыта по умолчанию для чистого интерфейса

    def _connect_signals(self) -> None:
        """Связка действий интерфейса с обработчиками."""
        self.toggle_log_action.toggled.connect(self._toggle_log_visibility)
        self.log_dock.visibilityChanged.connect(self.toggle_log_action.setChecked)

    def _toggle_log_visibility(self, visible: bool) -> None:
        """Переключение видимости панели логов."""
        self.log_dock.setVisible(visible)
        state = "Показана" if visible else "Скрыта"
        self.status_bar.showMessage(f"Панель логов: {state}", 1500)

    def update_undo_redo_state(self, can_undo: bool, can_redo: bool) -> None:
        """Обновление доступности действий Отмена/Повтор извне (Controller/SessionManager)."""
        self.undo_action.setEnabled(can_undo)
        self.redo_action.setEnabled(can_redo)

    def log_message(self, message: str, level: str = "INFO") -> None:
        """Публичный метод для записи в UI-лог. Уровень для будущего цветового кодирования."""
        self.log_text.appendPlainText(f"[{level}] {message}")

    # --- Обработчики заглушек ---
    def _on_settings_requested(self) -> None:
        self.status_bar.showMessage("Модуль настроек будет реализован в Итерации 2", 3000)
        QMessageBox.information(self, "Настройки", "Раздел настроек находится в разработке.")

    def _on_about_requested(self) -> None:
        QMessageBox.about(
            self, "О SkedGenie",
            "SkedGenie Desktop v0.1-alpha\n"
            "Десктопный планировщик смен и нарядов.\n"
            "Архитектура: Onion/Clean. Ядро: asyncio + SQLAlchemy Async.\n"
            "© 2026"
        )

    def close_event(self, event) -> None:
        """Обработка закрытия окна с подтверждением."""
        reply = QMessageBox.question(
            self, "Выход",
            "Завершить работу? Все несохранённые изменения сессии будут потеряны.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._logger.info("User confirmed application exit.")
            event.accept()
        else:
            event.ignore()

