# src/presentation/font_manager.py
"""
Централизованный менеджер шрифтов для приложения SkedGenie.

Предоставляет единую точку настройки всех шрифтов в приложении с поддержкой:
    - 3 предустановленных размеров (Small/Medium/Large).
    - Типографической иерархии ролей (caption/body/subtitle/title).
    - Горячей перезагрузки шрифтов во всех зарегистрированных виджетах
      без перезапуска приложения.
    - Настройки стандартных Tkinter-виджетов через ``ttk.Style``
      (в частности, ``ttk.Treeview``).

Архитектура:
    - Виджеты регистрируются через :meth:`register_widget` (с ``weakref``).
    - Treeview регистрируется отдельно через :meth:`register_treeview`.
    - При смене размера через :meth:`set_size` все шрифты пересоздаются
      и применяются ко всем зарегистрированным виджетам.
    - Менеджер не занимается чтением/сохранением настроек — это
      ответственность отдельного модуля :mod:`src.presentation.settings`.
"""
from __future__ import annotations

import logging
import weakref
from enum import Enum
from tkinter import ttk
from typing import Optional

import customtkinter as ctk


class FontSize(Enum):
    """Предустановленные размеры шрифта.

    Attributes:
        SMALL: Уменьшенный размер для компактного отображения.
        MEDIUM: Базовый размер (по умолчанию).
        LARGE: Увеличенный размер для лучшей читаемости.
    """

    SMALL = 12
    MEDIUM = 14
    LARGE = 16


class FontManager:
    """Централизованный менеджер шрифтов приложения.

    Типографические роли и их смещения относительно базового размера:
        - ``caption``: ``base - 2`` — для второстепенных подписей, статус-бара.
        - ``body``: ``base`` — основной текст (кнопки, поля ввода, лейблы).
        - ``body_bold``: ``base`` + жирное начертание — для акцентов.
        - ``subtitle``: ``base + 2`` — подзаголовки, заголовки колонок.
        - ``title``: ``base + 6`` — главные заголовки разделов.

    Attributes:
        _ROLE_MODIFIERS: Смещения размера для каждой роли.
        _BOLD_ROLES: Роли с жирным начертанием.
    """

    _ROLE_MODIFIERS: dict[str, int] = {
        "caption": -2,
        "body": 0,
        "body_bold": 0,
        "subtitle": 2,
        "title": 6,
    }
    _BOLD_ROLES: frozenset[str] = frozenset({"body_bold", "subtitle", "title"})

    _DEFAULT_TREEVIEW_STYLE: str = "Custom.Treeview"

    def __init__(
        self,
        base_size: FontSize = FontSize.MEDIUM,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        """Инициализация менеджера шрифтов.

        Args:
            base_size: Базовый размер шрифта (по умолчанию :attr:`FontSize.MEDIUM`).
            logger: Логгер для событий менеджера. Если ``None`` — создаётся
                собственный логгер с именем модуля.
        """
        self._logger = logger or logging.getLogger(__name__)
        self._base_size: FontSize = base_size

        # Кэш шрифтов по ролям.
        self._fonts: dict[str, ctk.CTkFont] = {}

        # Реестры виджетов для горячей перезагрузки.
        # key: id(weakref), value: (weakref_to_widget, role)
        self._widgets: dict[int, tuple[weakref.ref, str]] = {}
        self._treeviews: dict[int, tuple[weakref.ref, str]] = {}

        self._rebuild_fonts()
        self._logger.info(
            "FontManager: инициализирован, base_size=%d (%s)",
            self._base_size.value,
            self._base_size.name,
        )

    # ------------------------------------------------------------------
    # Public API: получение шрифтов
    # ------------------------------------------------------------------
    def get_font(self, role: str = "body") -> ctk.CTkFont:
        """Получить объект шрифта для указанной типографической роли.

        Args:
            role: Типографическая роль (``caption`` / ``body`` / ``body_bold`` /
                ``subtitle`` / ``title``). При передаче неизвестной роли
                возвращается ``body`` с предупреждением в лог.

        Returns:
            Объект :class:`customtkinter.CTkFont`.
        """
        if role not in self._fonts:
            self._logger.warning(
                "FontManager: неизвестная роль '%s', используется 'body'",
                role,
            )
            role = "body"
        return self._fonts[role]

    def get_base_size(self) -> FontSize:
        """Возвращает текущий базовый размер шрифта."""
        return self._base_size

    # ------------------------------------------------------------------
    # Public API: горячая перезагрузка
    # ------------------------------------------------------------------
    def set_size(self, new_size: FontSize) -> None:
        """Изменить базовый размер шрифта и обновить все виджеты.

        Пересоздаёт кэш шрифтов и применяет их ко всем зарегистрированным
        CTk-виджетам и ttk.Treeview.

        Args:
            new_size: Новый базовый размер.
        """
        if new_size is self._base_size:
            self._logger.debug(
                "FontManager: set_size пропущен (размер не изменился: %s)",
                new_size.name,
            )
            return

        old_size = self._base_size
        self._base_size = new_size
        self._rebuild_fonts()
        self._update_registered_widgets()
        self._update_treeview_styles()

        self._logger.info(
            "FontManager: размер изменён %s (%d) → %s (%d)",
            old_size.name,
            old_size.value,
            new_size.name,
            new_size.value,
        )

    # ------------------------------------------------------------------
    # Public API: регистрация виджетов
    # ------------------------------------------------------------------
    def register_widget(
        self,
        widget: ctk.CTkBaseClass,
        role: str = "body",
        apply_immediately: bool = True,
    ) -> None:
        """Зарегистрировать CTk-виджет для горячей перезагрузки.

        Виджет хранится через ``weakref`` — при уничтожении ссылка
        автоматически очищается из реестра.

        Args:
            widget: Виджет CustomTkinter (наследник :class:`CTkBaseClass`).
            role: Типографическая роль для этого виджета.
            apply_immediately: Если ``True`` — сразу применить шрифт
                к виджету. Полезно отключать при пакетной регистрации.
        """
        widget_id = id(widget)
        if widget_id in self._widgets:
            self._logger.debug(
                "FontManager: виджет %s уже зарегистрирован",
                type(widget).__name__,
            )
            return

        self._widgets[widget_id] = (weakref.ref(widget), role)

        if apply_immediately:
            self._apply_font_to_widget(widget, role)

    def register_treeview(
        self,
        treeview: ttk.Treeview,
        style_name: str = _DEFAULT_TREEVIEW_STYLE,
    ) -> None:
        """Зарегистрировать ``ttk.Treeview`` для горячей перезагрузки.

        Args:
            treeview: Виджет ``ttk.Treeview``.
            style_name: Имя стиля ttk (должно совпадать с тем, что
                передано в ``style=...`` при создании виджета).
        """
        treeview_id = id(treeview)
        if treeview_id in self._treeviews:
            self._logger.debug(
                "FontManager: treeview уже зарегистрирован",
            )
            return

        self._treeviews[treeview_id] = (weakref.ref(treeview), style_name)
        self._apply_treeview_style(style_name)

    def apply_treeview_style(
        self,
        style_name: str = _DEFAULT_TREEVIEW_STYLE,
    ) -> None:
        """Применить стиль шрифтов к именованному ``ttk.Style``.

        Вызывается при создании Treeview, который не зарегистрирован
        в менеджере, но должен использовать согласованные размеры шрифтов.

        Args:
            style_name: Имя стиля ttk.
        """
        self._apply_treeview_style(style_name)

    # ------------------------------------------------------------------
    # Internal: построение кэша шрифтов
    # ------------------------------------------------------------------
    def _rebuild_fonts(self) -> None:
        """Пересоздать кэш шрифтов для текущего ``base_size``."""
        self._fonts.clear()
        for role, modifier in self._ROLE_MODIFIERS.items():
            size = max(8, self._base_size.value + modifier)  # защита от отрицательных
            weight = "bold" if role in self._BOLD_ROLES else "normal"
            self._fonts[role] = ctk.CTkFont(
                family="",  # системный шрифт
                size=size,
                weight=weight,
            )
        self._logger.debug(
            "FontManager: кэш шрифтов пересобран для base_size=%d",
            self._base_size.value,
        )

    # ------------------------------------------------------------------
    # Internal: обновление виджетов
    # ------------------------------------------------------------------
    def _update_registered_widgets(self) -> None:
        """Применить новые шрифты ко всем живым зарегистрированным виджетам."""
        dead_ids: list[int] = []

        for widget_id, (widget_ref, role) in self._widgets.items():
            widget = widget_ref()
            if widget is None:
                dead_ids.append(widget_id)
                continue
            self._apply_font_to_widget(widget, role)

        for widget_id in dead_ids:
            del self._widgets[widget_id]

        if dead_ids:
            self._logger.debug(
                "FontManager: очищено %d мёртвых ссылок из реестра виджетов",
                len(dead_ids),
            )

    def _apply_font_to_widget(
        self,
        widget: ctk.CTkBaseClass,
        role: str,
    ) -> None:
        """Применить шрифт роли к конкретному виджету."""
        font = self.get_font(role)
        try:
            widget.configure(font=font)
        except Exception:  # noqa: BLE001
            self._logger.debug(
                "FontManager: не удалось применить шрифт к %s",
                type(widget).__name__,
                exc_info=True,
            )

    def _update_treeview_styles(self) -> None:
        """Обновить стили всех зарегистрированных Treeview."""
        # Обновляем стили для всех уникальных имён.
        unique_styles = {style_name for _, (_, style_name) in self._treeviews.items()}
        for style_name in unique_styles:
            self._apply_treeview_style(style_name)

        # Очищаем мёртвые ссылки.
        dead_ids = [
            tid for tid, (ref, _) in self._treeviews.items() if ref() is None
        ]
        for tid in dead_ids:
            del self._treeviews[tid]

    def _apply_treeview_style(self, style_name: str) -> None:
        """Применить шрифты к ttk-стилю (строки и заголовки Treeview)."""
        style = ttk.Style()
        body_size = self._base_size.value
        subtitle_size = self._base_size.value + self._ROLE_MODIFIERS["subtitle"]

        try:
            style.configure(
                style_name,
                font=("", body_size),
                rowheight=max(24, body_size + 14),
            )
            style.configure(
                f"{style_name}.Heading",
                font=("", subtitle_size, "bold"),
            )
            self._logger.debug(
                "FontManager: ttk-стиль '%s' обновлён (body=%d, heading=%d)",
                style_name,
                body_size,
                subtitle_size,
            )
        except Exception:  # noqa: BLE001
            self._logger.warning(
                "FontManager: не удалось обновить стиль '%s'",
                style_name,
                exc_info=True,
            )


# ---------------------------------------------------------------------------
# Глобальный синглтон (создаётся в main.py и передаётся в виджеты через DI)
# ---------------------------------------------------------------------------
_font_manager_instance: Optional[FontManager] = None


def get_font_manager() -> Optional[FontManager]:
    """Возвращает активный экземпляр :class:`FontManager` (или ``None``)."""
    return _font_manager_instance


def set_font_manager(manager: FontManager) -> None:
    """Устанавливает глобальный экземпляр менеджера шрифтов.

    Вызывается в ``main.py`` после создания экземпляра.
    """
    global _font_manager_instance
    _font_manager_instance = manager
