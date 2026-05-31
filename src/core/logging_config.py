# src/core/logging_config.py
"""
Конфигурация системы логирования приложения SkedGenie.

Предоставляет:
    - Настраиваемые консольный и файловый хэндлеры (с ротацией).
    - Потокобезопасный CustomTkinter-хэндлер ``CTkLogHandler`` для отображения
      логов в GUI (с внутренним буфером и фильтрацией БД-событий).
    - Вспомогательные функции для единообразного логирования пользовательских
      действий, ошибок и UI-событий.

Требование: **"БД в интерфейс не логируется"** — сообщения логгеров
``sqlalchemy.*`` пропускаются в файл и консоль, но не попадают в GUI-панель.
"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

import customtkinter as ctk


# ---------------------------------------------------------------------------
# Константы
# ---------------------------------------------------------------------------
LOG_FORMAT_FILE: str = (
    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
)
LOG_FORMAT_CONSOLE: str = "%(asctime)s | %(levelname)-8s | %(message)s"
LOG_FORMAT_GUI: str = "%(asctime)s | %(levelname)-8s | %(message)s"
LOG_DATEFMT: str = "%Y-%m-%d %H:%M:%S"

# Имена логгеров инфраструктуры БД, которые не должны попадать в GUI.
_DB_LOGGER_NAMES: tuple[str, ...] = (
    "sqlalchemy",
    "sqlalchemy.engine",
    "sqlalchemy.pool",
    "aiosqlite",
)

# Ограничение буфера CTkLogHandler, чтобы не допустить утечки памяти
# при длительной работе без подключённого виджета.
_MAX_BUFFER_SIZE: int = 1000

# Параметры ротации файла логов.
_LOG_MAX_BYTES: int = 5 * 1024 * 1024  # 5 МБ
_LOG_BACKUP_COUNT: int = 3


# ---------------------------------------------------------------------------
# Фильтр БД-логов для GUI
# ---------------------------------------------------------------------------
class DatabaseLogFilter(logging.Filter):
    """Фильтр, блокирующий сообщения от логгеров SQLAlchemy/aiosqlite.

    Применяется к ``CTkLogHandler`` для соблюдения требования
    "БД в интерфейс не логируется". Файловый и консольный хэндлеры
    этот фильтр не используют.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Возвращает ``True``, если запись НЕ относится к инфраструктуре БД."""
        return not record.name.startswith(_DB_LOGGER_NAMES)


# ---------------------------------------------------------------------------
# CustomTkinter log handler
# ---------------------------------------------------------------------------
class CTkLogHandler(logging.Handler):
    """Потокобезопасный ``logging.Handler`` для CustomTkinter-виджета.

    Особенности:
        - Доставляет сообщения в GUI-поток через ``root.after(0, ...)``.
        - До вызова :meth:`attach_widget` накапливает записи во внутреннем
          буфере (FIFO, ограниченном ``_MAX_BUFFER_SIZE``).
        - Прикрепляется к виджету с методом ``insert`` (например,
          ``ctk.CTkTextbox``) — прикреплённый виджет получает буфер и
          все последующие сообщения.

    Attributes:
        _root: Главное окно CustomTkinter (источник GUI event loop).
        _widget: Прикреплённый виджет для отображения логов (или ``None``).
        _buffer: Очередь отформатированных строк до прикрепления виджета.
    """

    def __init__(self, root: ctk.CTk) -> None:
        super().__init__()
        self._root = root
        self._widget: Optional[ctk.CTkTextbox] = None
        self._buffer: list[str] = []
        self.setFormatter(logging.Formatter(LOG_FORMAT_GUI, datefmt=LOG_DATEFMT))
        self.addFilter(DatabaseLogFilter())

    def attach_widget(self, widget: ctk.CTkTextbox) -> None:
        """Прикрепить виджет для отображения логов и сбросить буфер.

        Args:
            widget: ``CTkTextbox`` (или совместимый виджет) с методом
                ``insert(index, text)`` и ``see(index)``.
        """
        self._widget = widget
        self._flush_buffer()

    def detach_widget(self) -> None:
        """Открепить виджет. Последующие сообщения снова идут в буфер."""
        self._widget = None

    def emit(self, record: logging.LogRecord) -> None:
        """Обработать запись логгера (потокобезопасно)."""
        try:
            msg = self.format(record)
            if self._widget is None:
                self._buffer_message(msg)
            else:
                self._schedule_append(msg)
        except Exception:  # noqa: BLE001
            self.handleError(record)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _buffer_message(self, msg: str) -> None:
        if len(self._buffer) >= _MAX_BUFFER_SIZE:
            self._buffer.pop(0)  # FIFO: удаляем самое старое
        self._buffer.append(msg + "\n")

    def _flush_buffer(self) -> None:
        if self._widget is None or not self._buffer:
            return
        pending = self._buffer
        self._buffer = []
        for msg in pending:
            self._schedule_append(msg.rstrip("\n"))

    def _schedule_append(self, msg: str) -> None:
        """Запланировать добавление текста в виджет через GUI-поток."""
        try:
            self._root.after(0, self._append_to_widget, msg)
        except Exception:  # noqa: BLE001
            # Окно уже уничтожено — тихо игнорируем, чтобы не уронить worker.
            pass

    def _append_to_widget(self, msg: str) -> None:
        if self._widget is None:
            return
        try:
            self._widget.configure(state="normal")
            self._widget.insert("end", msg + "\n")
            self._widget.see("end")
            self._widget.configure(state="disabled")
        except Exception:  # noqa: BLE001
            # Виджет уничтожен или недоступен — открепляем, чтобы не спамить.
            self._widget = None


# ---------------------------------------------------------------------------
# Глобальный реестр хэндлера GUI (для доступа из main_window.py)
# ---------------------------------------------------------------------------
_ctk_handler: Optional[CTkLogHandler] = None


def get_ctk_handler() -> Optional[CTkLogHandler]:
    """Возвращает активный ``CTkLogHandler`` (или ``None``, если не создан)."""
    return _ctk_handler


# ---------------------------------------------------------------------------
# Инициализация
# ---------------------------------------------------------------------------
def setup_logging(
    log_level: int = logging.INFO,
    log_file: Optional[str] = None,
    console_output: bool = True,
    file_output: bool = True,
    root: Optional[ctk.CTk] = None,
) -> None:
    """Настроить корневой логгер приложения.

    Args:
        log_level: Уровень логирования (например, ``logging.DEBUG``).
        log_file: Путь к файлу логов. Если ``None`` и ``file_output=True``,
            используется ``logs/app.log`` в корне проекта.
        console_output: Включить ли вывод в ``stdout``.
        file_output: Включить ли вывод в файл (с ротацией).
        root: Главное окно CustomTkinter. Если передано — создаётся
            ``CTkLogHandler`` для доставки логов в GUI.
    """
    global _ctk_handler

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # ✅ Отключаем шумное логирование SQLAlchemy (оставляем только WARNING и выше)
    # Это убирает DEBUG-логи запросов из консоли и файла, но оставляет ошибки.
    for db_logger_name in _DB_LOGGER_NAMES:
        logging.getLogger(db_logger_name).setLevel(logging.WARNING)

    # Избегаем дублирования хэндлеров при повторных вызовах setup_logging.
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(
            logging.Formatter(LOG_FORMAT_CONSOLE, datefmt=LOG_DATEFMT)
        )
        root_logger.addHandler(console_handler)

    if file_output:
        if log_file is None:
            log_path = Path("logs") / "app.log"
        else:
            log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            filename=str(log_path),
            maxBytes=_LOG_MAX_BYTES,
            backupCount=_LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(
            logging.Formatter(LOG_FORMAT_FILE, datefmt=LOG_DATEFMT)
        )
        root_logger.addHandler(file_handler)

    if root is not None:
        _ctk_handler = CTkLogHandler(root)
        root_logger.addHandler(_ctk_handler)


def get_logger(name: str) -> logging.Logger:
    """Получить именованный логгер (стандартный wrapper над ``logging.getLogger``)."""
    return logging.getLogger(name)


# ---------------------------------------------------------------------------
# Вспомогательные функции единообразного логирования
# ---------------------------------------------------------------------------
def log_user_action(logger: logging.Logger, action: str, details: str) -> None:
    """Зафиксировать осмысленное действие пользователя.

    Args:
        logger: Логгер источника события.
        action: Краткое название действия (например, "Создание задачи").
        details: Детали (введённые данные, результат операции).
    """
    logger.info("[USER] %s | %s", action, details)


def log_user_error(logger: logging.Logger, action: str, error: str) -> None:
    """Зафиксировать ошибку, возникшую при действии пользователя.

    Args:
        logger: Логгер источника события.
        action: Действие, при котором произошла ошибка.
        error: Текст или описание ошибки.
    """
    logger.error("[USER_ERROR] %s | %s", action, error)


def log_ui_event(
    logger: logging.Logger,
    widget: str,
    event: str,
    data: str = "",
) -> None:
    """Зафиксировать низкоуровневое UI-событие (клик, ввод).

    Args:
        logger: Логгер источника события.
        widget: Идентификатор виджета (например, "TaskListWidget.btn_refresh").
        event: Тип события ("click", "input", "select").
        data: Дополнительные данные (введённый текст, выбранное значение).
    """
    if data:
        logger.debug("[UI] %s.%s | data=%s", widget, event, data)
    else:
        logger.debug("[UI] %s.%s", widget, event)

def attach_gui_handler(root: ctk.CTk) -> None:
    """Прикрепить GUI-хэндлер к уже настроенному логгеру.

    Вызывается после создания главного окна для подключения
    :class:`CTkLogHandler` к корневому логгеру.

    Args:
        root: Главное окно CustomTkinter.
    """
    global _ctk_handler
    if _ctk_handler is not None:
        logging.getLogger().debug(
            "attach_gui_handler: CTkLogHandler уже прикреплён, пропускаем"
        )
        return

    _ctk_handler = CTkLogHandler(root)
    logging.getLogger().addHandler(_ctk_handler)
    logging.getLogger().info(
        "attach_gui_handler: CTkLogHandler успешно прикреплён к GUI"
    )
