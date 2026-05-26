# src/presentation/widgets/log_panel.py
"""
Сворачиваемая панель логов для главного окна SkedGenie.

Предоставляет виджет для отображения логов в реальном времени через
:class:`CTkLogHandler` из :mod:`src.core.logging_config`. Поддерживает:
    - Сворачивание/разворачивание для экономии места.
    - Очистку логов пользователем.
    - Автоматическую прокрутку к последним записям.

Интегрируется в главное окно как нижняя панель под вкладками.
"""
from __future__ import annotations

import logging
from typing import Optional

import customtkinter as ctk

from src.core.logging_config import get_ctk_handler, log_ui_event


class LogPanel(ctk.CTkFrame):
    """Сворачиваемая панель логов для главного окна.

    Attributes:
        _logger: Логгер для событий панели.
        _text_box: Текстовое поле для отображения логов.
        _toggle_btn: Кнопка сворачивания/разворачивания.
        _clear_btn: Кнопка очистки логов.
        _is_expanded: Текущее состояние панели (развёрнута/свёрнута).
    """

    _EXPANDED_HEIGHT: int = 150
    _COLLAPSED_HEIGHT: int = 30
    _TOGGLE_ICON_EXPANDED: str = "▼"
    _TOGGLE_ICON_COLLAPSED: str = "▲"

    def __init__(
        self,
        master: ctk.CTk,
        logger: logging.Logger,
        **kwargs,
    ) -> None:
        """Инициализация панели логов.

        Args:
            master: Родительский виджет (главное окно).
            logger: Логгер для событий панели.
            **kwargs: Дополнительные параметры для ``CTkFrame``.
        """
        super().__init__(master, **kwargs)
        self._logger = logger
        self._is_expanded: bool = True

        self._create_widgets()
        self._logger.debug("LogPanel: панель логов создана")

    def _create_widgets(self) -> None:
        """Создание внутренних виджетов панели."""
        # Панель управления (кнопки)
        control_frame = ctk.CTkFrame(self, height=30, fg_color="transparent")
        control_frame.pack(fill="x", padx=5, pady=(5, 0))

        # Заголовок
        title_label = ctk.CTkLabel(
            control_frame,
            text="Логи",
            font=ctk.CTkFont(weight="bold"),
        )
        title_label.pack(side="left", padx=(0, 10))

        # Кнопка сворачивания
        self._toggle_btn = ctk.CTkButton(
            control_frame,
            text=self._TOGGLE_ICON_EXPANDED,
            width=30,
            command=self.toggle_visibility,
        )
        self._toggle_btn.pack(side="right", padx=(5, 0))

        # Кнопка очистки
        self._clear_btn = ctk.CTkButton(
            control_frame,
            text="Очистить",
            width=80,
            command=self.clear_logs,
        )
        self._clear_btn.pack(side="right")

        # Текстовое поле для логов
        self._text_box = ctk.CTkTextbox(
            self,
            height=self._EXPANDED_HEIGHT,
            state="disabled",
            wrap="word",
        )
        self._text_box.pack(fill="both", expand=True, padx=5, pady=5)

    def attach_handler(self) -> None:
        """Подключить панель к ``CTkLogHandler`` из logging_config.

        Вызывается после создания главного окна и инициализации логирования.
        Если handler не найден, логирует предупреждение.
        """
        handler = get_ctk_handler()
        if handler is None:
            self._logger.warning(
                "LogPanel: CTkLogHandler не найден, панель не подключена"
            )
            return

        handler.attach_widget(self._text_box)
        self._logger.info("LogPanel: панель подключена к CTkLogHandler")

    def clear_logs(self) -> None:
        """Очистить содержимое панели логов."""
        log_ui_event(self._logger, "LogPanel.btn_clear", "click")
        self._text_box.configure(state="normal")
        self._text_box.delete("1.0", "end")
        self._text_box.configure(state="disabled")
        self._logger.info("LogPanel: логи очищены пользователем")

    def toggle_visibility(self) -> None:
        """Переключить видимость текстового поля (свернуть/развернуть)."""
        if self._is_expanded:
            # Сворачиваем
            self._text_box.pack_forget()
            self._toggle_btn.configure(text=self._TOGGLE_ICON_COLLAPSED)
            self._is_expanded = False
            log_ui_event(
                self._logger,
                "LogPanel.btn_toggle",
                "click",
                "collapsed",
            )
            self._logger.debug("LogPanel: панель свёрнута")
        else:
            # Разворачиваем
            self._text_box.pack(fill="both", expand=True, padx=5, pady=5)
            self._toggle_btn.configure(text=self._TOGGLE_ICON_EXPANDED)
            self._is_expanded = True
            log_ui_event(
                self._logger,
                "LogPanel.btn_toggle",
                "click",
                "expanded",
            )
            self._logger.debug("LogPanel: панель развёрнута")

