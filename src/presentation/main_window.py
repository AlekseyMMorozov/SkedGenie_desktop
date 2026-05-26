# src/presentation/main_window.py
"""
Главное окно приложения SkedGenie.

Предоставляет основной интерфейс пользователя с:
    - Меню верхнего уровня (Файл/Правка/Вид/Сервис/Справка) — нативный tk.Menu.
    - Левой навигационной панелью :class:`NavigationSidebar` с 5 разделами
      (Задачи / Графики / Сотрудники / Задействования / Настройки).
    - Контент-областью справа с переключаемыми страницами (white-card layout).
    - Сворачиваемой панелью логов :class:`LogPanel`.
    - Статус-баром с текущим состоянием и версией.
    - Горячими клавишами (Ctrl+Q для выхода, F5 для обновления).
    - Graceful shutdown через ``protocol("WM_DELETE_WINDOW")``.
    - Централизованным управлением шрифтами через :class:`FontManager`.

Цветовая схема (Material Design 3 / Fluent Light):
    - Фон окна: ``#F3F3F3`` (светло-серый).
    - Фон контент-области: ``#FFFFFF`` (белая карточка с закруглёнными углами).
    - Фон сайдбара: определяется автоматически по теме CustomTkinter.

Все асинхронные операции выполняются через :class:`AsyncBridge`,
бизнес-логика — через :class:`TaskController`.
"""
from __future__ import annotations

import logging
from tkinter import messagebox
from typing import Optional

import customtkinter as ctk
import tkinter as tk

from src.core.logging_config import log_ui_event, log_user_action
from src.presentation.async_bridge import AsyncBridge
from src.presentation.controllers.task_controller import TaskController
from src.presentation.font_manager import (
    FontManager,
    FontSize,
    get_font_manager,
    set_font_manager,
)
from src.presentation.settings import Settings
from src.presentation.widgets.log_panel import LogPanel
from src.presentation.widgets.navigation_sidebar import NavigationSidebar
from src.presentation.widgets.task_list_widget import TaskListWidget


# Цвета фона для light/dark темы.
_WINDOW_BG_COLORS: dict[str, str] = {
    "Light": "#F3F3F3",
    "Dark": "#1E1E1E",
}
_CONTENT_CARD_COLORS: dict[str, str] = {
    "Light": "#FFFFFF",
    "Dark": "#2D2D2D",
}


class MainWindow(ctk.CTk):
    """Главное окно приложения SkedGenie.

    Attributes:
        _task_controller: Контроллер задач (фасад над репозиторием).
        _bridge: Мост для вызова async-методов (создаётся внутри окна).
        _font_manager: Менеджер шрифтов (создаётся внутри окна).
        _logger: Логгер для событий окна.
        _settings: Менеджер настроек (для будущего диалога настроек).
        _sidebar: Навигационная панель слева.
        _pages: Словарь ``section_id → CTkFrame`` для переключения контента.
        _active_section: ID текущего активного раздела.
        _content_card: Белая карточка-контейнер для страниц.
        _task_list_widget: Виджет задач (живёт внутри страницы tasks).
    """

    _WINDOW_TITLE: str = "SkedGenie — Планировщик смен и нарядов"
    _WINDOW_SIZE: str = "1280x800"
    _MIN_SIZE: tuple[int, int] = (900, 600)
    _APP_VERSION: str = "v0.1.0"

    _CONTENT_PADDING: int = 15
    _CARD_CORNER_RADIUS: int = 10

    # ID разделов должны совпадать с NavigationSidebar._SECTIONS.
    _SECTION_TASKS: str = "tasks"
    _SECTION_GRAPHS: str = "graphs"
    _SECTION_EMPLOYEES: str = "employees"
    _SECTION_ENGAGEMENTS: str = "engagements"
    _SECTION_SETTINGS: str = "settings"

    def __init__(
        self,
        task_controller: TaskController,
        logger: logging.Logger,
        settings: Optional[Settings] = None,
        **kwargs,
    ) -> None:
        """Инициализация главного окна.

        Args:
            task_controller: Контроллер задач.
            logger: Логгер для событий окна.
            settings: Менеджер настроек (для будущего диалога настроек).
            **kwargs: Дополнительные параметры для ``CTk``.
        """
        # super().__init__() создаёт Tk-корень — это ОБЯЗАТЕЛЬНО должно
        # произойти ДО создания AsyncBridge и FontManager.
        super().__init__(**kwargs)

        self._logger = logger
        self._settings = settings
        self._task_controller = task_controller

        # Создание объектов, требующих Tk-корень.
        self._bridge = AsyncBridge(self, logger)
        self._font_manager = self._init_font_manager()

        self._pages: dict[str, ctk.CTkFrame] = {}
        self._active_section: str = self._SECTION_TASKS

        self._setup_window()
        self._create_menu()
        self._create_log_panel()
        self._create_status_bar()
        self._create_main_layout()
        self._bind_hotkeys()
        self._setup_closing_handler()

        # Первичное отображение страницы "Задачи".
        self._show_page(self._SECTION_TASKS)

        self._logger.info(
            "MainWindow: главное окно создано (%s)",
            self._WINDOW_SIZE,
        )

    # ------------------------------------------------------------------
    # Инициализация FontManager (требует Tk-корень)
    # ------------------------------------------------------------------
    def _init_font_manager(self) -> FontManager:
        """Создать и зарегистрировать FontManager.

        Читает размер шрифта из settings (если передан), иначе использует
        ``FontSize.MEDIUM``. Регистрирует экземпляр как глобальный синглтон
        через :func:`set_font_manager`.

        Returns:
            Созданный экземпляр :class:`FontManager`.
        """
        # Определяем базовый размер из настроек.
        if self._settings is not None:
            try:
                base_size = self._settings.get_current().font_size
            except Exception as exc:  # noqa: BLE001
                self._logger.warning(
                    "MainWindow: не удалось получить font_size из настроек: %s. "
                    "Используется MEDIUM.",
                    exc,
                )
                base_size = FontSize.MEDIUM
        else:
            base_size = FontSize.MEDIUM

        font_manager = FontManager(base_size=base_size, logger=self._logger)
        set_font_manager(font_manager)

        self._logger.info(
            "MainWindow: FontManager создан (base_size=%s, %dpx)",
            base_size.name,
            base_size.value,
        )
        return font_manager

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------
    def _setup_window(self) -> None:
        """Настройка параметров окна (заголовок, размер, позиция, фон)."""
        self.title(self._WINDOW_TITLE)
        self.geometry(self._WINDOW_SIZE)
        self.minsize(*self._MIN_SIZE)

        # Фон окна в зависимости от текущей темы.
        window_bg = self._get_theme_color(_WINDOW_BG_COLORS, default="#F3F3F3")
        self.configure(fg_color=window_bg)

        # Центрирование на экране.
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _create_menu(self) -> None:
        """Создание меню верхнего уровня (стандартный tkinter.Menu)."""
        menubar = tk.Menu(self)
        self.configure(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Файл", menu=file_menu)
        file_menu.add_command(
            label="Выход", command=self._on_exit, accelerator="Ctrl+Q",
        )

        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Правка", menu=edit_menu)
        edit_menu.add_command(
            label="Отменить", command=self._on_undo_stub, accelerator="Ctrl+Z",
        )
        edit_menu.add_command(
            label="Повторить", command=self._on_redo_stub, accelerator="Ctrl+Y",
        )

        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Вид", menu=view_menu)
        view_menu.add_command(
            label="Обновить", command=self._on_refresh, accelerator="F5",
        )
        view_menu.add_separator()
        view_menu.add_command(
            label="Очистить логи", command=self._on_clear_logs,
        )

        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Сервис", menu=tools_menu)
        tools_menu.add_command(
            label="Настройки", command=self._on_settings_stub,
        )
        tools_menu.add_separator()
        tools_menu.add_command(label="Импорт", command=self._on_import_stub)
        tools_menu.add_command(label="Экспорт", command=self._on_export_stub)

        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Справка", menu=help_menu)
        help_menu.add_command(label="О программе", command=self._on_about)

        self._logger.debug("MainWindow: меню верхнего уровня создано")

    def _create_main_layout(self) -> None:
        """Создание основной раскладки: сайдбар + контент-область."""
        self._main_container = ctk.CTkFrame(self, fg_color="transparent")
        self._main_container.pack(fill="both", expand=True)

        self._sidebar = NavigationSidebar(
            master=self._main_container,
            logger=self._logger,
            on_select=self._on_section_select,
            initial_section=self._SECTION_TASKS,
        )
        self._sidebar.pack(
            side="left",
            fill="y",
            padx=(10, 0),
            pady=(10, 10),
        )

        card_color = self._get_theme_color(
            _CONTENT_CARD_COLORS, default="#FFFFFF",
        )
        self._content_card = ctk.CTkFrame(
            self._main_container,
            fg_color=card_color,
            corner_radius=self._CARD_CORNER_RADIUS,
        )
        self._content_card.pack(
            side="right",
            fill="both",
            expand=True,
            padx=10,
            pady=10,
        )

        self._create_pages()

        self._logger.debug("MainWindow: сайдбар + контент-область созданы")

    def _create_pages(self) -> None:
        """Создание фреймов-страниц для каждого раздела."""
        fm = get_font_manager()
        title_font = fm.get_font("title") if fm else ctk.CTkFont(
            size=20, weight="bold",
        )
        subtitle_font = fm.get_font("subtitle") if fm else ctk.CTkFont(size=16)

        # --- Страница "Задачи" ---
        tasks_page = ctk.CTkFrame(self._content_card, fg_color="transparent")
        tasks_page.pack_propagate(False)

        tasks_header = ctk.CTkLabel(
            tasks_page,
            text="Задачи планирования",
            font=title_font,
            anchor="w",
        )
        tasks_header.pack(
            fill="x",
            padx=self._CONTENT_PADDING,
            pady=(self._CONTENT_PADDING, 5),
        )
        if fm:
            fm.register_widget(tasks_header, "title")

        self._task_list_widget = TaskListWidget(
            master=tasks_page,
            controller=self._task_controller,
            bridge=self._bridge,
            logger=self._logger,
        )
        self._task_list_widget.pack(
            fill="both",
            expand=True,
            padx=self._CONTENT_PADDING,
            pady=(0, self._CONTENT_PADDING),
        )
        self._pages[self._SECTION_TASKS] = tasks_page

        # --- Страница "Графики" (заглушка) ---
        graphs_page = self._create_stub_page(
            title="Графики",
            message="Модуль 'Графики' находится в разработке",
            title_font=title_font,
            subtitle_font=subtitle_font,
            fm=fm,
        )
        self._pages[self._SECTION_GRAPHS] = graphs_page

        # --- Страница "Сотрудники" (заглушка) ---
        employees_page = self._create_stub_page(
            title="Сотрудники",
            message="Модуль 'Сотрудники' находится в разработке",
            title_font=title_font,
            subtitle_font=subtitle_font,
            fm=fm,
        )
        self._pages[self._SECTION_EMPLOYEES] = employees_page

        # --- Страница "Задействования" (заглушка) ---
        engagements_page = self._create_stub_page(
            title="Задействования",
            message="Модуль 'Задействования' находится в разработке",
            title_font=title_font,
            subtitle_font=subtitle_font,
            fm=fm,
        )
        self._pages[self._SECTION_ENGAGEMENTS] = engagements_page

        # --- Страница "Настройки" (заглушка) ---
        settings_page = self._create_stub_page(
            title="Настройки",
            message="Модуль 'Настройки' находится в разработке",
            title_font=title_font,
            subtitle_font=subtitle_font,
            fm=fm,
        )
        self._pages[self._SECTION_SETTINGS] = settings_page

        self._logger.debug(
            "MainWindow: создано %d страниц контента",
            len(self._pages),
        )

    def _create_stub_page(
        self,
        title: str,
        message: str,
        title_font: ctk.CTkFont,
        subtitle_font: ctk.CTkFont,
        fm,
    ) -> ctk.CTkFrame:
        """Создать страницу-заглушку с заголовком и сообщением."""
        page = ctk.CTkFrame(self._content_card, fg_color="transparent")

        header = ctk.CTkLabel(
            page,
            text=title,
            font=title_font,
            anchor="w",
        )
        header.pack(
            fill="x",
            padx=self._CONTENT_PADDING,
            pady=(self._CONTENT_PADDING, 5),
        )
        if fm:
            fm.register_widget(header, "title")

        stub_label = ctk.CTkLabel(
            page,
            text=message,
            font=subtitle_font,
        )
        stub_label.pack(expand=True)
        if fm:
            fm.register_widget(stub_label, "subtitle")

        return page

    def _create_log_panel(self) -> None:
        """Создание сворачиваемой панели логов."""
        self._log_panel = LogPanel(
            master=self,
            logger=self._logger,
        )
        self._log_panel.pack(
            fill="x",
            side="bottom",
            padx=10,
            pady=(0, 5),
        )
        self._log_panel.attach_handler()
        self._logger.debug("MainWindow: панель логов создана и подключена")

    def _create_status_bar(self) -> None:
        """Создание статус-бара внизу окна с типографической ролью 'caption'."""
        fm = get_font_manager()
        caption_font = fm.get_font("caption") if fm else None

        status_frame = ctk.CTkFrame(self, height=25, fg_color="transparent")
        status_frame.pack(fill="x", side="bottom", padx=10, pady=(0, 5))

        status_kwargs = {"text": "Готов", "anchor": "w"}
        if caption_font:
            status_kwargs["font"] = caption_font
        self._status_label = ctk.CTkLabel(status_frame, **status_kwargs)
        self._status_label.pack(side="left", padx=(5, 0))
        if fm:
            fm.register_widget(self._status_label, "caption")

        version_kwargs = {"text": self._APP_VERSION, "anchor": "e"}
        if caption_font:
            version_kwargs["font"] = caption_font
        version_label = ctk.CTkLabel(status_frame, **version_kwargs)
        version_label.pack(side="right", padx=(0, 5))
        if fm:
            fm.register_widget(version_label, "caption")

        self._logger.debug("MainWindow: статус-бар создан")

    def _bind_hotkeys(self) -> None:
        """Привязка горячих клавиш."""
        self.bind("<Control-q>", lambda e: self._on_exit())
        self.bind("<F5>", lambda e: self._on_refresh())
        self._logger.debug(
            "MainWindow: горячие клавиши привязаны (Ctrl+Q, F5)",
        )

    def _setup_closing_handler(self) -> None:
        """Настройка обработчика закрытия окна."""
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    # ------------------------------------------------------------------
    # Переключение страниц
    # ------------------------------------------------------------------
    def _on_section_select(self, section: str) -> None:
        """Обработчик выбора раздела в сайдбаре."""
        log_ui_event(
            self._logger,
            "MainWindow.section_select",
            "select",
            section,
        )
        self._show_page(section)

    def _show_page(self, section: str) -> None:
        """Показать страницу выбранного раздела, скрыв остальные."""
        if section not in self._pages:
            self._logger.warning(
                "MainWindow: попытка показать неизвестный раздел '%s'",
                section,
            )
            return

        for page in self._pages.values():
            try:
                page.pack_forget()
            except Exception:  # noqa: BLE001
                pass

        active_page = self._pages[section]
        active_page.pack(
            in_=self._content_card,
            fill="both",
            expand=True,
        )

        self._active_section = section
        self._logger.debug(
            "MainWindow: показана страница '%s'",
            section,
        )

    # ------------------------------------------------------------------
    # Menu handlers
    # ------------------------------------------------------------------
    def _on_exit(self) -> None:
        """Обработчик меню 'Файл → Выход'."""
        log_ui_event(self._logger, "MainWindow.menu_file_exit", "click")
        self._on_closing()

    def _on_undo_stub(self) -> None:
        """Заглушка: 'Правка → Отменить'."""
        log_ui_event(self._logger, "MainWindow.menu_edit_undo", "click")
        messagebox.showinfo(
            "В разработке",
            "Функция 'Отменить' будет реализована позже.",
            parent=self,
        )

    def _on_redo_stub(self) -> None:
        """Заглушка: 'Правка → Повторить'."""
        log_ui_event(self._logger, "MainWindow.menu_edit_redo", "click")
        messagebox.showinfo(
            "В разработке",
            "Функция 'Повторить' будет реализована позже.",
            parent=self,
        )

    def _on_refresh(self) -> None:
        """Обработчик меню 'Вид → Обновить'."""
        log_ui_event(self._logger, "MainWindow.menu_view_refresh", "click")
        self._task_list_widget.refresh()

    def _on_clear_logs(self) -> None:
        """Обработчик меню 'Вид → Очистить логи'."""
        log_ui_event(self._logger, "MainWindow.menu_view_clear_logs", "click")
        self._log_panel.clear_logs()

    def _on_settings_stub(self) -> None:
        """Заглушка: 'Сервис → Настройки' — переключение на страницу настроек."""
        log_ui_event(self._logger, "MainWindow.menu_tools_settings", "click")
        self._sidebar.set_active(self._SECTION_SETTINGS)
        self._show_page(self._SECTION_SETTINGS)

    def _on_import_stub(self) -> None:
        """Заглушка: 'Сервис → Импорт'."""
        log_ui_event(self._logger, "MainWindow.menu_tools_import", "click")
        messagebox.showinfo(
            "В разработке",
            "Функция импорта будет реализована позже.",
            parent=self,
        )

    def _on_export_stub(self) -> None:
        """Заглушка: 'Сервис → Экспорт'."""
        log_ui_event(self._logger, "MainWindow.menu_tools_export", "click")
        messagebox.showinfo(
            "В разработке",
            "Функция экспорта будет реализована позже.",
            parent=self,
        )

    def _on_about(self) -> None:
        """Обработчик меню 'Справка → О программе'."""
        log_ui_event(self._logger, "MainWindow.menu_help_about", "click")
        messagebox.showinfo(
            "О программе",
            f"SkedGenie — Планировщик смен и нарядов\n\n"
            f"Версия: {self._APP_VERSION}\n"
            f"Дата: 2026-05-26\n\n"
            f"Десктопное приложение для автоматического планирования\n"
            f"смен, нарядов и дежурств с проверкой жёстких правил.",
            parent=self,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _get_theme_color(
        colors_map: dict[str, str],
        default: str,
    ) -> str:
        """Получить цвет для текущей темы CustomTkinter."""
        try:
            appearance = ctk.get_appearance_mode()
        except Exception:
            appearance = "Light"
        return colors_map.get(appearance, default)

    # ------------------------------------------------------------------
    # Window lifecycle
    # ------------------------------------------------------------------
    def _on_closing(self) -> None:
        """Обработчик закрытия окна: graceful shutdown."""
        log_user_action(
            self._logger,
            "Закрытие приложения",
            "Пользователь закрыл окно",
        )
        self._logger.info("MainWindow: инициировано закрытие окна")

        if self._bridge.is_running():
            self._logger.debug("MainWindow: остановка AsyncBridge")
            self._bridge.shutdown()

        self.destroy()
        self._logger.info("MainWindow: окно закрыто")

    def run(self) -> None:
        """Запуск главного цикла событий."""
        self.after(100, self._initial_load_tasks)
        self._logger.info("MainWindow: запуск mainloop")
        self.mainloop()

    def _initial_load_tasks(self) -> None:
        """Первичная загрузка задач из БД при старте приложения."""
        self._logger.info("MainWindow: первичная загрузка задач из БД")
        self._task_list_widget.refresh()
