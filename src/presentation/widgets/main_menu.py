# src/presentation/widgets/main_menu.py
"""
Главное меню приложения SkedGenie.

Построение нативного tkinter.Menu со стандартными пунктами:
    - Файл (Выход)
    - Правка (Отменить, Повторить)
    - Вид (Обновить, Очистить логи)
    - Сервис (Настройки, Импорт, Экспорт)
    - Справка (О программе)

Ответственность:
    - Конструирование структуры меню и подменю.
    - Назначение accelerator'ов (отображаемых сочетаний клавиш).
    - Делегирование действий через callback-параметры.

Границы:
    - НЕ обрабатывает действия меню — только вызывает переданные callback'и.
    - НЕ логирует события — это ответственность хэндлеров MainWindow.
    - НЕ привязывает горячие клавиши — это ответственность MainWindow.
    - НЕ зависит от CustomTkinter — использует только стандартный tkinter.

Использование:
    menu = MainMenu(root, logger, on_exit=..., on_refresh=..., ...)
    root.configure(menu=menu.menu)
"""
from __future__ import annotations

import logging
from typing import Callable

import tkinter as tk


class MainMenu:
    """Нативное главное меню приложения.

    Строит иерархию `tk.Menu` и предоставляет его через свойство `menu`
    для установки в окно через `root.configure(menu=menu_instance.menu)`.

    Все действия делегируются через callback-параметры, переданные в конструктор,
    что позволяет тестировать меню изолированно и переиспользовать его
    в других контекстах.
    """

    def __init__(
        self,
        root: tk.Misc,
        logger: logging.Logger,
        *,
        on_exit: Callable[[], None],
        on_undo: Callable[[], None],
        on_redo: Callable[[], None],
        on_refresh: Callable[[], None],
        on_clear_logs: Callable[[], None],
        on_settings: Callable[[], None],
        on_import: Callable[[], None],
        on_export: Callable[[], None],
        on_about: Callable[[], None],
    ) -> None:
        """Инициализация меню.

        Args:
            root: Tk-корень или любой виджет, к которому будет привязано меню.
            logger: Логгер для записи диагностических сообщений.
            on_exit: Callback для 'Файл → Выход'.
            on_undo: Callback для 'Правка → Отменить'.
            on_redo: Callback для 'Правка → Повторить'.
            on_refresh: Callback для 'Вид → Обновить'.
            on_clear_logs: Callback для 'Вид → Очистить логи'.
            on_settings: Callback для 'Сервис → Настройки'.
            on_import: Callback для 'Сервис → Импорт'.
            on_export: Callback для 'Сервис → Экспорт'.
            on_about: Callback для 'Справка → О программе'.
        """
        self._logger = logger
        self._menu = self._build_menu(
            root=root,
            on_exit=on_exit,
            on_undo=on_undo,
            on_redo=on_redo,
            on_refresh=on_refresh,
            on_clear_logs=on_clear_logs,
            on_settings=on_settings,
            on_import=on_import,
            on_export=on_export,
            on_about=on_about,
        )

    @property
    def menu(self) -> tk.Menu:
        """Построенный `tk.Menu` для установки в окно."""
        return self._menu

    # ------------------------------------------------------------------
    # Построение меню
    # ------------------------------------------------------------------
    def _build_menu(
        self,
        root: tk.Misc,
        *,
        on_exit: Callable[[], None],
        on_undo: Callable[[], None],
        on_redo: Callable[[], None],
        on_refresh: Callable[[], None],
        on_clear_logs: Callable[[], None],
        on_settings: Callable[[], None],
        on_import: Callable[[], None],
        on_export: Callable[[], None],
        on_about: Callable[[], None],
    ) -> tk.Menu:
        """Построить иерархию меню.

        Args:
            root: Tk-корень для создания меню.
            on_*: Callback-обработчики для каждого пункта меню.

        Returns:
            Готовый `tk.Menu` со всеми подменю и пунктами.
        """
        menubar = tk.Menu(root)

        menubar.add_cascade(
            label="Файл",
            menu=self._build_file_menu(menubar, on_exit=on_exit),
        )
        menubar.add_cascade(
            label="Правка",
            menu=self._build_edit_menu(menubar, on_undo=on_undo, on_redo=on_redo),
        )
        menubar.add_cascade(
            label="Вид",
            menu=self._build_view_menu(
                menubar,
                on_refresh=on_refresh,
                on_clear_logs=on_clear_logs,
            ),
        )
        menubar.add_cascade(
            label="Сервис",
            menu=self._build_tools_menu(
                menubar,
                on_settings=on_settings,
                on_import=on_import,
                on_export=on_export,
            ),
        )
        menubar.add_cascade(
            label="Справка",
            menu=self._build_help_menu(menubar, on_about=on_about),
        )

        self._logger.debug("MainMenu: меню верхнего уровня построено")
        return menubar

    # ------------------------------------------------------------------
    # Файл
    # ------------------------------------------------------------------
    @staticmethod
    def _build_file_menu(
        parent: tk.Menu,
        *,
        on_exit: Callable[[], None],
    ) -> tk.Menu:
        """Построить подменю 'Файл'."""
        file_menu = tk.Menu(parent, tearoff=0)
        file_menu.add_command(
            label="Выход",
            command=on_exit,
            accelerator="Ctrl+Q",
        )
        return file_menu

    # ------------------------------------------------------------------
    # Правка
    # ------------------------------------------------------------------
    @staticmethod
    def _build_edit_menu(
        parent: tk.Menu,
        *,
        on_undo: Callable[[], None],
        on_redo: Callable[[], None],
    ) -> tk.Menu:
        """Построить подменю 'Правка'."""
        edit_menu = tk.Menu(parent, tearoff=0)
        edit_menu.add_command(
            label="Отменить",
            command=on_undo,
            accelerator="Ctrl+Z",
        )
        edit_menu.add_command(
            label="Повторить",
            command=on_redo,
            accelerator="Ctrl+Y",
        )
        return edit_menu

    # ------------------------------------------------------------------
    # Вид
    # ------------------------------------------------------------------
    @staticmethod
    def _build_view_menu(
        parent: tk.Menu,
        *,
        on_refresh: Callable[[], None],
        on_clear_logs: Callable[[], None],
    ) -> tk.Menu:
        """Построить подменю 'Вид'."""
        view_menu = tk.Menu(parent, tearoff=0)
        view_menu.add_command(
            label="Обновить",
            command=on_refresh,
            accelerator="F5",
        )
        view_menu.add_separator()
        view_menu.add_command(
            label="Очистить логи",
            command=on_clear_logs,
        )
        return view_menu

    # ------------------------------------------------------------------
    # Сервис
    # ------------------------------------------------------------------
    @staticmethod
    def _build_tools_menu(
        parent: tk.Menu,
        *,
        on_settings: Callable[[], None],
        on_import: Callable[[], None],
        on_export: Callable[[], None],
    ) -> tk.Menu:
        """Построить подменю 'Сервис'."""
        tools_menu = tk.Menu(parent, tearoff=0)
        tools_menu.add_command(
            label="Настройки",
            command=on_settings,
        )
        tools_menu.add_separator()
        tools_menu.add_command(label="Импорт", command=on_import)
        tools_menu.add_command(label="Экспорт", command=on_export)
        return tools_menu

    # ------------------------------------------------------------------
    # Справка
    # ------------------------------------------------------------------
    @staticmethod
    def _build_help_menu(
        parent: tk.Menu,
        *,
        on_about: Callable[[], None],
    ) -> tk.Menu:
        """Построить подменю 'Справка'."""
        help_menu = tk.Menu(parent, tearoff=0)
        help_menu.add_command(
            label="О программе",
            command=on_about,
        )
        return help_menu
