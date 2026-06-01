# src/presentation/main_window.py
"""
Главное окно приложения SkedGenie.

Тонкий фасад, ответственный за:
    - Создание Tk-корня и настройку окна (заголовок, размер, позиция).
    - Инициализацию FontManager (требует Tk-корень).
    - Композицию компонентов: MainMenu, NavigationSidebar, PageFactory, LogPanel.
    - Переключение страниц контент-области.
    - Привязку горячих клавиш и обработчиков меню.
    - Применение пользовательских настроек темы (цвета, шрифты).
    - Graceful shutdown при закрытии.
"""
from __future__ import annotations

import logging
import sys
from tkinter import messagebox
from typing import Optional

import customtkinter as ctk

from src.application.services.engagement_color_service import EngagementColorService
from src.core.logging_config import get_ctk_handler, log_ui_event
from src.presentation.async_bridge import AsyncBridge
from src.presentation.controllers.employee_controller import EmployeeController
from src.presentation.controllers.engagement_template_controller import EngagementTemplateController
from src.presentation.controllers.engagement_type_controller import EngagementTypeController
from src.presentation.controllers.task_controller import TaskController
from src.presentation.dialogs.settings_dialog import SettingsDialog
from src.presentation.font_manager import FontManager, FontSize, set_font_manager
from src.presentation.settings import COLOR_PRESETS, Settings
from src.presentation.widgets.log_panel import LogPanel
from src.presentation.widgets.main_menu import MainMenu
from src.presentation.widgets.navigation_sidebar import NavigationSidebar
from src.presentation.widgets.page_factory import PageFactory


class MainWindow(ctk.CTk):
    """Главное окно приложения SkedGenie."""

    _WINDOW_TITLE: str = "SkedGenie — Планировщик смен и нарядов"
    _WINDOW_SIZE: str = "1280x800"
    _MIN_SIZE: tuple[int, int] = (900, 600)
    _APP_VERSION: str = "v0.1.0"
    _CARD_CORNER_RADIUS: int = 10

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
        super().__init__(**kwargs)

        self._logger = logger
        self._settings = settings
        self._task_controller = task_controller
        self._employee_controller = employee_controller
        self._engagement_type_controller = engagement_type_controller
        self._engagement_template_controller = engagement_template_controller
        self._color_service = color_service

        # Объекты, требующие Tk-корень
        self._bridge = AsyncBridge(self, logger)
        self._font_manager = self._init_font_manager()

        # Ссылки на виджеты
        self._pages: dict[str, ctk.CTkFrame] = {}
        self._task_list_widget = None
        self._employee_list_widget = None
        self._active_section: str = self._SECTION_TASKS

        # Компоненты верхнего уровня
        self._menu: Optional[MainMenu] = None
        self._sidebar: Optional[NavigationSidebar] = None
        self._content_card: Optional[ctk.CTkFrame] = None
        self._log_panel: Optional[LogPanel] = None

        # Цвета темы (инициализируются дефолтными значениями)
        self._theme_colors: dict[str, str] = {
            "app_bg": "#F3F3F3",
            "dialog_bg": "#FFFFFF",
            "border_color": "#C0C0C0",
        }

        # Сборка окна
        self._setup_window()
        self._create_menu()
        self._create_log_panel()
        self._create_main_layout()
        self._bind_hotkeys()
        self._setup_closing_handler()

        # Применение сохраненной темы
        if self._settings:
            ui = self._settings.get_current().ui
            self._apply_theme(ui.color_preset, ui.font_size)

        self._show_page(self._SECTION_TASKS)
        self._logger.info("MainWindow: главное окно создано (%s)", self._WINDOW_SIZE)

    # ------------------------------------------------------------------
    # Theme & Settings
    # ------------------------------------------------------------------
    def _apply_theme(self, preset_key: str, font_size: FontSize) -> None:
        """Применяет тему ко всем компонентам и сохраняет цвета для диалогов."""
        preset = COLOR_PRESETS.get(preset_key, COLOR_PRESETS["default"])
        app_bg = preset["app"]
        dialog_bg = preset["dialog"]

        # Вычисляем цвет границ (контрастный к dialog_bg)
        border_color = "#C0C0C0" if self._is_light_color(dialog_bg) else "#555555"

        # 1. Сохраняем для использования в диалогах и виджетах
        self._theme_colors = {
            "app_bg": app_bg,
            "dialog_bg": dialog_bg,
            "border_color": border_color,
        }

        # 2. Главное окно и основные контейнеры
        self.configure(fg_color=app_bg)
        if self._content_card:
            self._content_card.configure(fg_color=dialog_bg)
        if self._sidebar:
            self._sidebar.configure(fg_color=app_bg)
        if self._log_panel:
            self._log_panel.configure(fg_color=app_bg)

        # 3. Рекурсивное обновление границ полей ввода и фонов
        self._update_widget_styles(self, dialog_bg, border_color)

        # 4. Шрифты
        if self._font_manager.get_base_size() != font_size:
            self._font_manager.set_size(font_size)
            self._logger.info("MainWindow: размер шрифта изменен на %s", font_size.name)

        self._logger.debug("MainWindow: тема применена (preset=%s, border=%s)", preset_key, border_color)

    @staticmethod
    def _is_light_color(hex_color: str) -> bool:
        """Проверяет, является ли цвет светлым."""
        hex_color = hex_color.lstrip("#")
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        return (r * 299 + g * 587 + b * 114) / 1000 > 140

    def _update_widget_styles(self, widget, bg_color: str, border_color: str) -> None:
        """Рекурсивно обновляет стили виджетов для визуального разделения."""
        try:
            w_class = widget.__class__.__name__

            # Поля ввода: добавляем границу
            if w_class in ("CTkEntry", "CTkTextbox", "CTkComboBox"):
                widget.configure(border_width=1, border_color=border_color)

            # Фреймы внутри контент-карточки: синхронизируем фон
            elif w_class == "CTkFrame" and widget != self._content_card:
                current_fg = getattr(widget, "_fg_color", None)
                if current_fg and current_fg.lower() not in ("transparent", ""):
                    if self._is_light_color(current_fg):
                        widget.configure(fg_color=bg_color)

            for child in widget.winfo_children():
                self._update_widget_styles(child, bg_color, border_color)

        except Exception:
            pass

    def _open_settings_dialog(self) -> None:
        """Открывает диалог настроек с поддержкой live-preview."""
        if not self._settings:
            messagebox.showinfo("Настройки", "Менеджер настроек недоступен.", parent=self)
            return

        SettingsDialog(
            master=self,
            settings=self._settings,
            logger=self._logger,
            on_preview=self._apply_theme,
        )

    # ------------------------------------------------------------------
    # Initialization Helpers
    # ------------------------------------------------------------------
    def _init_font_manager(self) -> FontManager:
        base_size = FontSize.MEDIUM
        if self._settings:
            try:
                base_size = self._settings.get_current().ui.font_size
            except Exception as exc:
                self._logger.warning("MainWindow: ошибка чтения font_size: %s", exc)

        fm = FontManager(base_size=base_size, logger=self._logger)
        set_font_manager(fm)
        return fm

    def _setup_window(self) -> None:
        self.title(self._WINDOW_TITLE)
        self.geometry(self._WINDOW_SIZE)
        self.minsize(*self._MIN_SIZE)

        self.configure(fg_color="#F3F3F3")

        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _create_menu(self) -> None:
        self._menu = MainMenu(
            root=self, logger=self._logger,
            on_exit=self._on_exit,
            on_undo=lambda: messagebox.showinfo("WIP", "Отменить", parent=self),
            on_redo=lambda: messagebox.showinfo("WIP", "Повторить", parent=self),
            on_refresh=self._on_refresh,
            on_clear_logs=lambda: self._log_panel and self._log_panel.clear_logs(),
            on_settings=self._open_settings_dialog,
            on_import=lambda: messagebox.showinfo("WIP", "Импорт", parent=self),
            on_export=lambda: messagebox.showinfo("WIP", "Экспорт", parent=self),
            on_about=self._on_about,
        )
        self.configure(menu=self._menu.menu)

    def _create_main_layout(self) -> None:
        main_container = ctk.CTkFrame(self, fg_color="transparent")
        main_container.pack(fill="both", expand=True)

        self._sidebar = NavigationSidebar(
            master=main_container, logger=self._logger,
            on_select=self._on_section_select, initial_section=self._SECTION_TASKS,
        )
        self._sidebar.pack(side="left", fill="y", padx=(10, 0), pady=10)

        self._content_card = ctk.CTkFrame(
            main_container, fg_color="#FFFFFF", corner_radius=self._CARD_CORNER_RADIUS,
        )
        self._content_card.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        factory = PageFactory(
            content_card=self._content_card,
            task_controller=self._task_controller,
            employee_controller=self._employee_controller,
            engagement_type_controller=self._engagement_type_controller,
            engagement_template_controller=self._engagement_template_controller,
            bridge=self._bridge,
            logger=self._logger,
            color_service=self._color_service,
            settings=self._settings,
            on_theme_changed=self._apply_theme,
        )
        self._pages, self._task_list_widget, self._employee_list_widget = factory.create_all_pages()

    def _create_log_panel(self) -> None:
        self._log_panel = LogPanel(master=self, logger=self._logger)
        self._log_panel.pack(fill="x", side="bottom", padx=10, pady=(0, 10))

    def attach_log_handler(self) -> None:
        handler = get_ctk_handler()
        if handler and self._log_panel:
            self._log_panel.attach_handler()

    def _bind_hotkeys(self) -> None:
        self.bind("<Control-q>", lambda e: self._on_exit())
        self.bind("<F5>", lambda e: self._on_refresh())

    def _setup_closing_handler(self) -> None:
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    # ------------------------------------------------------------------
    # Navigation & Actions
    # ------------------------------------------------------------------
    def _on_section_select(self, section: str) -> None:
        log_ui_event(self._logger, "MainWindow.section_select", "select", section)
        self._show_page(section)

    def _show_page(self, section: str) -> None:
        if section not in self._pages:
            return
        for page in self._pages.values():
            page.pack_forget()
        self._pages[section].pack(in_=self._content_card, fill="both", expand=True)
        self._active_section = section

    def _on_refresh(self) -> None:
        log_ui_event(self._logger, "MainWindow.refresh", "click")
        if self._task_list_widget:
            self._task_list_widget.refresh()
        if self._employee_list_widget:
            self._employee_list_widget.refresh()

        eng_page = self._pages.get(self._SECTION_ENGAGEMENTS)
        if eng_page:
            for child in eng_page.winfo_children():
                if hasattr(child, '_list_widget'):
                    child._list_widget.refresh()
                    break

    def _on_exit(self) -> None:
        self._on_closing()

    def _on_about(self) -> None:
        messagebox.showinfo(
            "О программе",
            f"SkedGenie {self._APP_VERSION}\nПланировщик смен и нарядов",
            parent=self,
        )

    def _on_closing(self) -> None:
        self._logger.info("MainWindow: закрытие")
        if self._bridge:
            self._bridge.shutdown()
        self.destroy()
        if sys.platform == "win32":
            import os
            os._exit(0)

    def run(self) -> None:
        self.after(100, lambda: self._logger.info("MainWindow: интерфейс готов"))
        self.mainloop()
