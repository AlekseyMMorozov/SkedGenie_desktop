# src/presentation/main_window.py
"""
Главное окно приложения SkedGenie.

Тонкий фасад, ответственный за:
    - Создание Tk-корня и настройку окна (заголовок, размер, позиция).
    - Инициализацию FontManager (требует Tk-корень).
    - Композицию компонентов: MainMenu, NavigationSidebar, PageFactory, LogPanel.
    - Переключение страниц контент-области.
    - Привязку горячих клавиш и обработчиков меню.
    - Graceful shutdown при закрытии.

Делегирование:
    - Построение структуры меню → :class:`MainMenu`.
    - Создание страниц контента → :class:`PageFactory`.
    - Асинхронные операции → :class:`AsyncBridge`.
    - Бизнес-логика → Контроллеры (Task, Employee, EngagementType, EngagementTemplate).

Цветовая схема (Material Design 3 / Fluent Light):
    - Фон окна: ``#F3F3F3`` (светло-серый).
    - Фон контент-области: ``#FFFFFF`` (белая карточка с закруглёнными углами).
"""
from __future__ import annotations

import logging
import sys
from tkinter import messagebox
from typing import Optional

import customtkinter as ctk

from src.application.services.engagement_color_service import EngagementColorService
from src.core.logging_config import (
    get_ctk_handler,
    log_ui_event,
    log_user_action,
)
from src.presentation.async_bridge import AsyncBridge
from src.presentation.controllers.employee_controller import EmployeeController
from src.presentation.controllers.engagement_template_controller import EngagementTemplateController
from src.presentation.controllers.engagement_type_controller import EngagementTypeController
from src.presentation.controllers.task_controller import TaskController
from src.presentation.font_manager import (
    FontManager,
    FontSize,
    get_font_manager,
    set_font_manager,
)
from src.presentation.settings import Settings
from src.presentation.widgets.employee_list_widget import EmployeeListWidget
from src.presentation.widgets.log_panel import LogPanel
from src.presentation.widgets.main_menu import MainMenu
from src.presentation.widgets.navigation_sidebar import NavigationSidebar
from src.presentation.widgets.page_factory import PageFactory
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

    Тонкий фасад, координирующий работу компонентов UI.
    Не содержит бизнес-логики и не создаёт сложных структур —
    делегирует эти задачи MainMenu, PageFactory и контроллерам.
    """

    _WINDOW_TITLE: str = "SkedGenie — Планировщик смен и нарядов"
    _WINDOW_SIZE: str = "1280x800"
    _MIN_SIZE: tuple[int, int] = (900, 600)
    _APP_VERSION: str = "v0.1.0"

    _CARD_CORNER_RADIUS: int = 10

    # ID разделов — должны совпадать с PageFactory.SECTION_* и NavigationSidebar._SECTIONS.
    _SECTION_TASKS: str = PageFactory.SECTION_TASKS
    _SECTION_GRAPHS: str = PageFactory.SECTION_GRAPHS
    _SECTION_EMPLOYEES: str = PageFactory.SECTION_EMPLOYEES
    _SECTION_ENGAGEMENTS: str = PageFactory.SECTION_ENGAGEMENTS
    _SECTION_SETTINGS: str = PageFactory.SECTION_SETTINGS

    def __init__(
        self,
        task_controller: TaskController,
        logger: logging.Logger,
        settings: Optional[Settings] = None,
        employee_controller: Optional[EmployeeController] = None,
        engagement_type_controller: Optional[EngagementTypeController] = None,
        engagement_template_controller: Optional[EngagementTemplateController] = None,
        color_service: Optional[EngagementColorService] = None,
        **kwargs,
    ) -> None:
        """Инициализация главного окна.

        Args:
            task_controller: Контроллер задач.
            logger: Логгер для событий окна.
            settings: Менеджер настроек (для будущего диалога настроек).
            employee_controller: Контроллер сотрудников.
            engagement_type_controller: Контроллер типов задействований.
            engagement_template_controller: Контроллер шаблонов задействований.
            color_service: Сервис генерации уникальных цветов.
            **kwargs: Дополнительные параметры для ``CTk``.
        """
        # super().__init__() создаёт Tk-корень — это ОБЯЗАТЕЛЬНО должно
        # произойти ДО создания AsyncBridge и FontManager.
        super().__init__(**kwargs)

        self._logger = logger
        self._settings = settings
        self._task_controller = task_controller
        self._employee_controller = employee_controller
        self._engagement_type_controller = engagement_type_controller
        self._engagement_template_controller = engagement_template_controller
        self._color_service = color_service

        # Объекты, требующие Tk-корень.
        self._bridge = AsyncBridge(self, logger)
        self._font_manager = self._init_font_manager()

        # Ссылки на виджеты (заполняются PageFactory).
        self._pages: dict[str, ctk.CTkFrame] = {}
        self._task_list_widget: Optional[TaskListWidget] = None
        self._employee_list_widget: Optional[EmployeeListWidget] = None
        self._active_section: str = self._SECTION_TASKS

        # Компоненты верхнего уровня.
        self._menu: Optional[MainMenu] = None
        self._sidebar: Optional[NavigationSidebar] = None
        self._content_card: Optional[ctk.CTkFrame] = None
        self._log_panel: Optional[LogPanel] = None

        # Сборка окна.
        self._setup_window()
        self._create_menu()
        self._create_log_panel()
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
        """Создать и зарегистрировать FontManager."""
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

        window_bg = self._get_theme_color(_WINDOW_BG_COLORS, default="#F3F3F3")
        self.configure(fg_color=window_bg)

        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _create_menu(self) -> None:
        """Создать главное меню через MainMenu (делегирование)."""
        self._menu = MainMenu(
            root=self,
            logger=self._logger,
            on_exit=self._on_exit,
            on_undo=self._on_undo_stub,
            on_redo=self._on_redo_stub,
            on_refresh=self._on_refresh,
            on_clear_logs=self._on_clear_logs,
            on_settings=self._on_settings_stub,
            on_import=self._on_import_stub,
            on_export=self._on_export_stub,
            on_about=self._on_about,
        )
        self.configure(menu=self._menu.menu)
        self._logger.debug("MainWindow: меню создано через MainMenu")

    def _create_main_layout(self) -> None:
        """Создание основной раскладки: сайдбар + контент-область."""
        main_container = ctk.CTkFrame(self, fg_color="transparent")
        main_container.pack(fill="both", expand=True)

        self._sidebar = NavigationSidebar(
            master=main_container,
            logger=self._logger,
            on_select=self._on_section_select,
            initial_section=self._SECTION_TASKS,
        )
        self._sidebar.pack(
            side="left",
            fill="y",
            padx=(10, 0),
            pady=10,
        )

        card_color = self._get_theme_color(
            _CONTENT_CARD_COLORS, default="#FFFFFF",
        )
        self._content_card = ctk.CTkFrame(
            main_container,
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

        # Делегирование создания страниц фабрике.
        page_factory = PageFactory(
            content_card=self._content_card,
            task_controller=self._task_controller,
            employee_controller=self._employee_controller,
            engagement_type_controller=self._engagement_type_controller,
            engagement_template_controller=self._engagement_template_controller,
            bridge=self._bridge,
            logger=self._logger,
            color_service=self._color_service,
        )
        self._pages, self._task_list_widget, self._employee_list_widget = (
            page_factory.create_all_pages()
        )

        self._logger.debug("MainWindow: сайдбар + контент-область + страницы созданы")

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
            pady=(0, 10),
        )
        self._logger.debug(
            "MainWindow: панель логов создана (handler будет прикреплён позже)",
        )

    def attach_log_handler(self) -> None:
        """Прикрепить ``CTkLogHandler`` к панели логов."""
        handler = get_ctk_handler()
        if handler is None:
            self._logger.warning(
                "MainWindow: CTkLogHandler не найден при attach_log_handler(), "
                "панель логов останется пустой",
            )
            return

        if self._log_panel is not None:
            self._log_panel.attach_handler()
        self._logger.info(
            "MainWindow: CTkLogHandler успешно прикреплён к панели логов",
        )

    def _bind_hotkeys(self) -> None:
        """Привязка горячих клавиш."""
        self.bind("<Control-q>", lambda e: self._on_exit())
        self.bind("<F5>", lambda e: self._on_refresh())
        self._logger.debug(
            "MainWindow: горячие клавиши привязаны (Ctrl+Q, F5)",
        )

    def _setup_closing_handler(self) -> None:
        """Привязка обработчика закрытия окна (WM_DELETE_WINDOW)."""
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        self._logger.debug("MainWindow: обработчик закрытия окна привязан")

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
        """Обработчик 'Файл → Выход'."""
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
        """Обработчик 'Вид → Обновить'.

        Обновляет данные во всех существующих list-виджетах.
        """
        log_ui_event(self._logger, "MainWindow.menu_view_refresh", "click")

        if self._task_list_widget is not None:
            self._task_list_widget.refresh()

        if self._employee_list_widget is not None:
            self._employee_list_widget.refresh()

        # Обновление страницы задействований, если она активна или существует
        engagements_page = self._pages.get(self._SECTION_ENGAGEMENTS)
        if engagements_page:
            # Находим EngagementManagementWidget внутри страницы
            for child in engagements_page.winfo_children():
                if hasattr(child, '_list_widget'):
                    child._list_widget.refresh()
                    break

    def _on_clear_logs(self) -> None:
        """Обработчик 'Вид → Очистить логи'."""
        log_ui_event(self._logger, "MainWindow.menu_view_clear_logs", "click")
        if self._log_panel is not None:
            self._log_panel.clear_logs()

    def _on_settings_stub(self) -> None:
        """'Сервис → Настройки' — переключение на страницу настроек."""
        log_ui_event(self._logger, "MainWindow.menu_tools_settings", "click")
        if self._sidebar is not None:
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
        """Обработчик 'Справка → О программе'."""
        log_ui_event(self._logger, "MainWindow.menu_help_about", "click")
        messagebox.showinfo(
            "О программе",
            f"SkedGenie — Планировщик смен и нарядов\n\n"
            f"Версия: {self._APP_VERSION}\n"
            f"Дата: 2026-05-30\n\n"
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
        """Обработчик закрытия окна."""
        self._logger.info("MainWindow: инициировано закрытие окна")

        try:
            if hasattr(self, '_bridge') and self._bridge:
                self._logger.debug("MainWindow: вызов bridge.shutdown()")
                self._bridge.shutdown()
                self._logger.debug("MainWindow: bridge.shutdown() завершён")
        except Exception as exc:
            self._logger.error("MainWindow: ошибка при shutdown bridge: %s", exc, exc_info=True)

        try:
            self._logger.debug("MainWindow: вызов destroy()")
            self.destroy()
            self._logger.debug("MainWindow: destroy() завершён")
        except Exception as exc:
            self._logger.error("MainWindow: ошибка при destroy: %s", exc, exc_info=True)

        # ✅ Fallback для Windows: если процесс всё ещё висит — завершаем
        if sys.platform == "win32":
            import os
            os._exit(0)


    def run(self) -> None:
        """Запуск главного цикла событий."""
        self.after(100, self._initial_load)
        self._logger.info("MainWindow: запуск mainloop")
        self.mainloop()


    def _initial_load(self) -> None:
        """Первичная загрузка данных с отложенным стартом для стабильности на Windows."""
        self._logger.info("MainWindow: первичная загрузка данных из БД")
        self.after(300, self._do_initial_load)


    def _do_initial_load(self) -> None:
        """
        Отложенная инициализация.
        Убраны все запросы к БД и обновления виджетов.
        Загрузка происходит только по явному действию пользователя (клик по кнопке/вкладке),
        когда event loop Tkinter полностью стабилен.
        """
        if not self.winfo_exists():
            return

        # Просто логируем готовность. Никаких bridge.run() здесь!
        self._logger.info("MainWindow: интерфейс готов к работе")

    def _safe_schedule_refresh(self, widget) -> None:
        """
        Безопасно планирует обновление виджета в главном потоке.
        Использует after(0) для гарантии выполнения в event loop Tkinter.
        """
        try:
            if widget and widget.winfo_exists():
                # ✅ КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ: используем after(0) вместо прямого вызова
                # Это предотвращает Race Condition и Access Violation
                widget.after(0, widget.refresh)
        except Exception as exc:
            self._logger.warning("Ошибка при планировании обновления виджета: %s", exc)
