# src/presentation/async_bridge.py
"""
Мост между синхронным GUI-потоком CustomTkinter и асинхронным ядром приложения.

Запускает единственный daemon-поток с asyncio event loop на всё время жизни
приложения. Все асинхронные операции (БД, сеть, файлы) планируются через
этот мост, что гарантирует:
    - Переиспользование пула соединений SQLAlchemy между запросами.
    - Потокобезопасное обновление UI через root.after(...).
    - Graceful shutdown при закрытии окна (неблокирующий, через coroutine
      внутри worker-потока).

Публичный API обратно совместим с итерацией №1:
    - ``is_running()`` — проверка активности моста.
    - ``run(coro, on_success, on_error)`` — планирование корутины.
    - ``shutdown()`` — неблокирующая остановка.
"""
from __future__ import annotations

import asyncio
import logging
import threading
import tkinter
from typing import Any, Callable, Coroutine

import customtkinter as ctk


class AsyncBridge:
    """Асинхронный мост для планирования корутин из GUI-потока.

    Создаёт один daemon-поток с собственным asyncio event loop. Корутины
    планируются потокобезопасно через ``asyncio.run_coroutine_threadsafe``,
    а коллбэки результата вызываются в GUI-потоке через ``root.after(0, ...)``.
    """

    _THREAD_NAME: str = "AsyncBridgeWorker"
    _SHUTDOWN_JOIN_TIMEOUT: float = 2.0

    def __init__(self, root: ctk.CTk, logger: logging.Logger) -> None:
        """Инициализация моста и запуск worker-потока.

        Args:
            root: Главное окно CustomTkinter (источник GUI event loop).
            logger: Логгер для событий моста.
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
            self._logger.debug("AsyncBridge: run_forever() завершён")


    def is_running(self) -> bool:
        """Возвращает ``True``, если мост активен и принимает корутины.

        Публичный метод — используется в MainWindow и виджетах для проверки
        состояния моста перед планированием операций.
        """
        return (
            self._is_running
            and self._thread is not None
            and self._thread.is_alive()
        )

    def shutdown(self) -> None:
        """Неблокирующая остановка event loop и worker-потока."""
        if not self._is_running:
            self._logger.debug("AsyncBridge: shutdown пропущен (уже остановлен)")
            return

        self._is_running = False
        self._logger.info("AsyncBridge: инициирована остановка")

        # Планируем shutdown-процедуру ВНУТРИ worker-потока.
        if self._loop.is_running():
            try:
                asyncio.run_coroutine_threadsafe(
                    self._shutdown_procedure(),
                    self._loop,
                )
            except RuntimeError as exc:
                self._logger.warning(
                    "AsyncBridge: не удалось запланировать shutdown-процедуру: %s",
                    exc,
                )

        # Ждём завершения потока с таймаутом.
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=self._SHUTDOWN_JOIN_TIMEOUT)
            if self._thread.is_alive():
                self._logger.warning(
                    "AsyncBridge: worker-поток не завершился за %.1f сек "
                    "(daemon=True, будет завершён ОС при выходе из процесса)",
                    self._SHUTDOWN_JOIN_TIMEOUT,
                )
                # ✅ Fallback для Windows: принудительно закрываем loop из main-потока
                try:
                    if not self._loop.is_closed():
                        self._loop.call_soon_threadsafe(self._loop.stop)
                        # Даём циклу 0.3 сек на реакцию
                        self._thread.join(timeout=0.3)
                except Exception:
                    pass
            else:
                self._logger.debug("AsyncBridge: worker-поток остановлен корректно")

        # ✅ Закрываем loop в main-потоке (освобождает ресурсы)
        try:
            if not self._loop.is_closed():
                self._loop.close()
                self._logger.debug("AsyncBridge: event loop закрыт")
        except Exception:
            self._logger.exception("AsyncBridge: ошибка при закрытии event loop")

        self._logger.info("AsyncBridge: остановка завершена")
        

    async def _shutdown_procedure(self) -> None:
        """Полная процедура graceful shutdown (coroutine внутри worker-потока)."""
        try:
            # 1. Отменяем все pending задачи, кроме текущей.
            current = asyncio.current_task()
            pending = [
                task for task in asyncio.all_tasks(self._loop)
                if task is not current and not task.done()
            ]
            if pending:
                self._logger.debug(
                    "AsyncBridge: отменяется %d pending задач",
                    len(pending),
                )
                for task in pending:
                    task.cancel()
                try:
                    await asyncio.gather(*pending, return_exceptions=True)
                except Exception:
                    self._logger.debug(
                        "AsyncBridge: gather завершился с исключениями (ожидаемо)",
                        exc_info=True,
                    )

            # 2. Закрываем async-генераторы (сессии БД).
            try:
                await self._loop.shutdown_asyncgens()
                self._logger.debug("AsyncBridge: asyncgens закрыты")
            except Exception:
                self._logger.debug(
                    "AsyncBridge: shutdown_asyncgens завершился с ошибкой",
                    exc_info=True,
                )

            # 3. ✅ КРИТИЧНО для Windows/Proactor: НЕ вызываем loop.stop() здесь.
            #    Мы внутри loop, и stop() может не сработать, если loop заблокирован.
            #    Вместо этого просто завершаем корутину — loop остановится сам,
            #    когда не останется задач.
            self._logger.debug("AsyncBridge: _shutdown_procedure завершена")

        except Exception:
            self._logger.exception(
                "AsyncBridge: критическая ошибка в shutdown-процедуре",
            )


    # ------------------------------------------------------------------
    # Public API (обратно совместим с итерацией №1)
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
            coro: Корутина для выполнения (позиционный аргумент).
            on_success: Коллбэк при успехе (вызывается в GUI-потоке).
            on_error: Коллбэк при ошибке (вызывается в GUI-потоке).
        """
        if not self.is_running():
            msg = "AsyncBridge: попытка использования после shutdown"
            self._logger.error(msg)
            if on_error is not None:
                self._safe_gui_call(on_error, RuntimeError(msg))
            return

        self._logger.debug("AsyncBridge: запланирована корутина %s", coro)
        try:
            asyncio.run_coroutine_threadsafe(
                self._execute(coro, on_success, on_error),
                self._loop,
            )
        except RuntimeError as exc:
            # Loop уже закрыт (race condition при закрытии окна).
            self._logger.warning(
                "AsyncBridge: не удалось запланировать корутину (loop закрыт): %s",
                exc,
            )
            if on_error is not None:
                self._safe_gui_call(on_error, exc)

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
            # Нормально при shutdown — не логируем как предупреждение.
            self._logger.debug("AsyncBridge: корутина отменена (shutdown)")
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
        """Безопасный вызов коллбэка в GUI-потоке через ``root.after``."""
        try:
            self._root.after(0, callback, *args)
        except tkinter.TclError as exc:
            # ✅ Ловим специфичную ошибку уничтоженного окна
            self._logger.debug(
                "AsyncBridge: TclError при планировании коллбэка: %s", exc
            )
        except Exception as exc:
            # ✅ Логируем НЕОЖИДАННЫЕ исключения — это важно для отладки
            self._logger.error(
                "AsyncBridge: НЕОЖИДАННОЕ исключение в _safe_gui_call: %s",
                exc, exc_info=True
            )

