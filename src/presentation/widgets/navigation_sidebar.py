# src/presentation/widgets/navigation_sidebar.py
"""
Левая навигационная панель главного окна SkedGenie.

Предоставляет вертикальное меню с 5 разделами (Задачи/Графики/Сотрудники/
Задействования/Настройки), иконками-emoji и поддержкой состояний
normal/hover/selected.

Архитектура:
    - Панель уведомляет главное окно о выборе раздела через коллбэк
      ``on_select(section: str)`` — не знает о содержимом контента.
    - Главное окно программно переключает активный раздел через
      :meth:`set_active`.
    - Интегрируется с :class:`FontManager` для единой типографики
      и автоматической горячей перезагрузки шрифтов.
    - Поддерживает светлую и тёмную темы CustomTkinter (цвета
      пересчитываются при каждом применении стилей).

Паттерн использования в :class:`MainWindow`:
    1. Создаётся сайдбар с коллбэком переключения контента.
    2. Упаковывается слева с фиксированной шириной 200px.
    3. При клике на пункт меню сайдбар вызывает коллбэк, главное окно
       показывает соответствующий фрейм в контент-области справа.
"""
from __future__ import annotations

import logging
from typing import Callable

import customtkinter as ctk

from src.core.logging_config import log_ui_event
from src.presentation.font_manager import get_font_manager


class NavigationSidebar(ctk.CTkFrame):
    """Левая панель навигации главного окна.

    Attributes:
        _logger: Логгер для событий панели.
        _on_select: Коллбэк, вызываемый при выборе раздела.
        _active_section: Текущий активный раздел.
        _buttons: Словарь ``section → CTkButton`` для управления состояниями.
    """

    _WIDTH: int = 200
    _BUTTON_HEIGHT: int = 42
    _BUTTON_CORNER_RADIUS: int = 8
    _PADDING_X: int = 10
    _PADDING_Y_BETWEEN: int = 4
    _ICON_PAD_RIGHT: int = 10

    # (section_id, emoji_icon, display_label)
    _SECTIONS: list[tuple[str, str, str]] = [
        ("tasks", "📋", "Задачи"),
        ("graphs", "📊", "Графики"),
        ("employees", "👥", "Сотрудники"),
        ("engagements", "📝", "Задействования"),
        ("settings", "⚙", "Настройки"),
    ]

    # Цветовые схемы для разных тем
    _THEME_COLORS: dict[str, dict[str, str]] = {
        "Light": {
            "sidebar_bg": "#EAEAEA",
            "header_fg": "#1E1E1E",
            "btn_normal": "transparent",
            "btn_hover": "#D5D5D5",
            "btn_selected": "#1F6AA5",
            "text_normal": "#1E1E1E",
            "text_selected": "#FFFFFF",
        },
        "Dark": {
            "sidebar_bg": "#252525",
            "header_fg": "#EAEAEA",
            "btn_normal": "transparent",
            "btn_hover": "#3A3A3A",
            "btn_selected": "#60CDFF",
            "text_normal": "#EAEAEA",
            "text_selected": "#1E1E1E",
        },
    }

    def __init__(
        self,
        master,
        logger: logging.Logger,
        on_select: Callable[[str], None],
        initial_section: str = "tasks",
        **kwargs,
    ) -> None:
        """Инициализация навигационной панели.

        Args:
            master: Родительский виджет.
            logger: Логгер для событий панели.
            on_select: Коллбэк, вызываемый при выборе раздела.
                Принимает ``section_id``
                (tasks/graphs/employees/engagements/settings).
            initial_section: ID раздела, который активен при создании.
            **kwargs: Дополнительные параметры для ``CTkFrame``.
        """
        self._logger = logger
        self._on_select = on_select
        self._active_section: str = initial_section
        self._buttons: dict[str, ctk.CTkButton] = {}

        # Применяем фон сайдбара до super().__init__, чтобы избежать мигания
        theme_colors = self._get_theme_colors()
        kwargs.setdefault("fg_color", theme_colors["sidebar_bg"])
        kwargs.setdefault("corner_radius", 0)

        super().__init__(master, **kwargs)

        self._create_widgets()
        # Подсветка начального активного раздела
        self._apply_button_styles()
        self._logger.debug(
            "NavigationSidebar: создана, активный раздел '%s'",
            self._active_section,
        )

    # ------------------------------------------------------------------
    # Создание виджетов
    # ------------------------------------------------------------------
    def _create_widgets(self) -> None:
        """Создание заголовка и кнопок навигации."""
        fm = get_font_manager()

        # ----------------------------------------------------------
        # Заголовок приложения (брендинг)
        # ----------------------------------------------------------
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=self._PADDING_X, pady=(20, 15))

        theme_colors = self._get_theme_colors()
        title_font = fm.get_font("title") if fm else ctk.CTkFont(
            size=20, weight="bold",
        )
        title_label = ctk.CTkLabel(
            header_frame,
            text="SkedGenie",
            font=title_font,
            text_color=theme_colors["header_fg"],
        )
        title_label.pack(anchor="w")
        if fm:
            fm.register_widget(title_label, "title")

        subtitle_font = fm.get_font("caption") if fm else None
        subtitle_kwargs = {"text": "Планировщик смен", "anchor": "w"}
        if subtitle_font:
            subtitle_kwargs["font"] = subtitle_font
            subtitle_kwargs["text_color"] = theme_colors["header_fg"]
        subtitle_label = ctk.CTkLabel(header_frame, **subtitle_kwargs)
        subtitle_label.pack(anchor="w", pady=(2, 0))
        if fm:
            fm.register_widget(subtitle_label, "caption")

        # Разделитель
        separator = ctk.CTkFrame(
            self,
            height=1,
            fg_color=("gray75", "gray30"),
        )
        separator.pack(fill="x", padx=self._PADDING_X, pady=(5, 10))

        # ----------------------------------------------------------
        # Кнопки навигации
        # ----------------------------------------------------------
        body_font = fm.get_font("body") if fm else None

        for section_id, icon, label in self._SECTIONS:
            display_text = f"{icon}  {label}"

            btn_kwargs = {
                "text": display_text,
                "anchor": "w",
                "height": self._BUTTON_HEIGHT,
                "corner_radius": self._BUTTON_CORNER_RADIUS,
                "compound": "left",
                "command": lambda s=section_id: self._on_button_click(s),
            }
            if body_font:
                btn_kwargs["font"] = body_font

            button = ctk.CTkButton(self, **btn_kwargs)
            button.pack(
                fill="x",
                padx=self._PADDING_X,
                pady=self._PADDING_Y_BETWEEN,
            )
            self._buttons[section_id] = button

            if fm:
                fm.register_widget(button, "body")

        # ----------------------------------------------------------
        # Нижняя "пружина" (прижимает кнопки к верху)
        # ----------------------------------------------------------
        spacer = ctk.CTkFrame(self, fg_color="transparent")
        spacer.pack(fill="both", expand=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_active(self, section: str) -> None:
        """Программно переключить активный раздел (без вызова коллбэка).

        Используется главным окном для синхронизации состояния панели
        с отображаемым контентом.

        Args:
            section: ID раздела
                (tasks/graphs/employees/engagements/settings).
        """
        if section not in self._buttons:
            self._logger.warning(
                "NavigationSidebar: попытка активировать неизвестный раздел '%s'",
                section,
            )
            return

        if section == self._active_section:
            return

        self._active_section = section
        self._apply_button_styles()
        self._logger.debug(
            "NavigationSidebar: активный раздел изменён на '%s'",
            section,
        )

    def get_active(self) -> str:
        """Возвращает ID текущего активного раздела."""
        return self._active_section

    def get_width(self) -> int:
        """Возвращает ширину панели (для layout-расчётов главного окна)."""
        return self._WIDTH

    # ------------------------------------------------------------------
    # Internal: обработка кликов и стили
    # ------------------------------------------------------------------
    def _on_button_click(self, section: str) -> None:
        """Обработчик клика по кнопке навигации."""
        log_ui_event(
            self._logger,
            f"NavigationSidebar.btn_{section}",
            "click",
        )

        if section == self._active_section:
            self._logger.debug(
                "NavigationSidebar: клик по активному разделу '%s' — игнорируем",
                section,
            )
            return

        self._active_section = section
        self._apply_button_styles()
        self._on_select(section)

    def _apply_button_styles(self) -> None:
        """Применить стили ко всем кнопкам (с учётом active/hover)."""
        colors = self._get_theme_colors()

        for section_id, button in self._buttons.items():
            if section_id == self._active_section:
                button.configure(
                    fg_color=colors["btn_selected"],
                    hover_color=colors["btn_selected"],
                    text_color=colors["text_selected"],
                )
            else:
                button.configure(
                    fg_color=colors["btn_normal"],
                    hover_color=colors["btn_hover"],
                    text_color=colors["text_normal"],
                )

    def _get_theme_colors(self) -> dict[str, str]:
        """Возвращает цветовую схему для текущей темы CustomTkinter."""
        try:
            appearance = ctk.get_appearance_mode()
        except Exception:
            appearance = "Light"

        return self._THEME_COLORS.get(
            appearance,
            self._THEME_COLORS["Light"],
        )
