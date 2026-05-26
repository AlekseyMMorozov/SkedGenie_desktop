# src/presentation/async_bridge.py
"""
Мост между синхронным GUI-потоком CustomTkinter и асинхронным ядром приложения.

Запускает единственный daemon-поток с asyncio event loop на всё время жизни
приложения. Все асинхронные операции (БД, сеть, файлы) планируются через
этот мост, что гарантирует:
    - Переиспользование пула соединений SQLAlchemy между запросами.
    - Потокобезопасное обновление UI через root.after(...).
    - Graceful shutdown при закрытии окна.
"""
from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any, Callable, Coroutine

import customtkinter as ctk


class AsyncBridge:
    """Асинхронный мост для планирования корутин из GUI-потока.

    Создаёт один daemon-поток с собственным asyncio event loop. Корутины
    планируются потокобезопасно через ``asyncio.run_coroutine_threadsafe``,
    а коллбэки результата вызываются в GUI-потоке через ``root.after(0, ...)``.

    Attributes:
        _THREAD_NAME: Имя worker-потока для удобства отладки.
        _SHUTDOWN_TIMEOUT: Максимальное время ожидания завершения потока при shutdown.
    """

    _THREAD_NAME: str = "AsyncBridgeWorker"
    _SHUTDOWN_TIMEOUT: float = 2.0

    def __init__(self, root: ctk.CTk, logger: logging.Logger) -> None:
        """Инициализация моста и запуск worker-потока.

        Args:
            root: Главное окно CustomTkinter (источник GUI event loop).
            logger: Логгер для событий моста.

        Raises:
            RuntimeError: Если при создании loop произошла ошибка.
        """
        self._root = root
        self._logger = logger

        self._loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        self._is_running: bool = False
        self._thread: threading.Thread | None = None

        self._start_worker()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def _start_worker(self) -> None:
        """Запуск daemon-потока с event loop."""
        self._thread = threading.Thread(
            target=self._run_loop,
            name=self._THREAD_NAME,
            daemon=True,
        )
        self._is_running = True
        self._thread.start()
        self._logger.debug(
            "AsyncBridge: worker-поток '%s' запущен (daemon=True)",
            self._THREAD_NAME,
        )

    def _run_loop(self) -> None:
        """Точка входа worker-потока: устанавливает loop и запускает его."""
        asyncio.set_event_loop(self._loop)
        self._logger.debug("AsyncBridge: event loop установлен в worker-потоке")
        try:
            self._loop.run_forever()
        except Exception:
            self._logger.exception(
                "AsyncBridge: критическая ошибка в worker-потоке",
            )
        finally:
            self._logger.debug("AsyncBridge: event loop остановлен")

    def is_running(self) -> bool:
        """Возвращает ``True``, если мост активен и принимает корутины."""
        return self._is_running and self._thread is not None and self._thread.is_alive()

    def shutdown(self) -> None:
        """Остановка event loop и worker-потока.

        Корректно завершает все запланированные задачи (с таймаутом).
        Безопасно вызывать несколько раз подряд.
        """
        if not self._is_running:
            self._logger.debug("AsyncBridge: shutdown пропущен (уже остановлен)")
            return

        self._is_running = False
        self._logger.info("AsyncBridge: инициирована остановка")

        if self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)

        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=self._SHUTDOWN_TIMEOUT)
            if self._thread.is_alive():
                self._logger.warning(
                    "AsyncBridge: worker-поток не завершился за %.1f сек",
                    self._SHUTDOWN_TIMEOUT,
                )
            else:
                self._logger.debug("AsyncBridge: worker-поток остановлен корректно")

        # Закрываем loop, освобождая ресурсы (сокеты, соединения).
        try:
            self._loop.close()
        except Exception:
            self._logger.exception("AsyncBridge: ошибка при закрытии event loop")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(
        self,
        coro: Coroutine[Any, Any, Any],
        on_success: Callable[[Any], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        """Запланировать корутину к выполнению в worker-потоке.

        Результат или исключение пробрасываются обратно в GUI-поток
        через ``root.after(0, callback, ...)``.

        Args:
            coro: Корутина для выполнения.
            on_success: Коллбэк при успехе (вызывается в GUI-потоке).
            on_error: Коллбэк при ошибке (вызывается в GUI-потоке).

        Returns:
            None.
        """
        if not self.is_running():
            msg = "AsyncBridge: попытка использования после shutdown"
            self._logger.error(msg)
            if on_error is not None:
                self._safe_gui_call(on_error, RuntimeError(msg))
            return

        self._logger.debug("AsyncBridge: запланирована корутина %s", coro)
        asyncio.run_coroutine_threadsafe(
            self._execute(coro, on_success, on_error),
            self._loop,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    async def _execute(
        self,
        coro: Coroutine[Any, Any, Any],
        on_success: Callable[[Any], None] | None,
        on_error: Callable[[Exception], None] | None,
    ) -> None:
        """Выполнение корутины с логированием и маршрутизацией результата."""
        try:
            result = await coro
            self._logger.debug("AsyncBridge: корутина успешно завершена")
        except asyncio.CancelledError:
            self._logger.warning("AsyncBridge: корутина отменена")
            return
        except Exception as exc:  # noqa: BLE001 — намеренно ловим всё
            self._logger.error(
                "AsyncBridge: ошибка в корутине: %s", exc, exc_info=True,
            )
            if on_error is not None:
                self._safe_gui_call(on_error, exc)
            return

        if on_success is not None:
            self._safe_gui_call(on_success, result)

    def _safe_gui_call(self, callback: Callable[..., None], *args: Any) -> None:
        """Безопасный вызов коллбэка в GUI-потоке через ``root.after``.

        Защищает от исключений в случае, если главное окно уже уничтожено.
        """
        try:
            self._root.after(0, callback, *args)
        except Exception:
            self._logger.exception(
                "AsyncBridge: не удалось запланировать коллбэк в GUI-поток",
            )
