# src/presentation/async_bridge.py
"""
Мост между синхронным GUI-потоком CustomTkinter и асинхронным ядром приложения.

Обеспечивает:
    - Потокобезопасное выполнение корутин в единственном worker-потоке.
    - Автоматическую блокировку UI во время выполнения операций.
    - Визуальную индикацию загрузки (курсор, отключение кнопок).
    - Graceful shutdown при закрытии окна.
"""
from __future__ import annotations

import asyncio
import logging
import threading
import tkinter as tk
from typing import Any, Callable, Coroutine

import customtkinter as ctk


class AsyncBridge:
    """Асинхронный мост для планирования корутин из GUI-потока."""

    _THREAD_NAME: str = "AsyncBridgeWorker"
    _SHUTDOWN_JOIN_TIMEOUT: float = 2.0

    def __init__(self, root: ctk.CTk, logger: logging.Logger) -> None:
        self._root = root
        self._logger = logger
        self._loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        self._is_running: bool = False
        self._thread: threading.Thread | None = None
        self._ui_locked: bool = False

        self._start_worker()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def _start_worker(self) -> None:
        self._thread = threading.Thread(
            target=self._run_loop, name=self._THREAD_NAME, daemon=True,
        )
        self._is_running = True
        self._thread.start()
        self._logger.debug("AsyncBridge: worker-поток '%s' запущен", self._THREAD_NAME)

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_forever()
        except Exception:
            self._logger.exception("AsyncBridge: критическая ошибка в worker-потоке")

    def is_running(self) -> bool:
        return self._is_running and self._thread is not None and self._thread.is_alive()

    def shutdown(self) -> None:
        if not self._is_running:
            return
        self._is_running = False
        self._logger.info("AsyncBridge: инициирована остановка")

        if self._loop.is_running():
            try:
                asyncio.run_coroutine_threadsafe(self._shutdown_procedure(), self._loop)
            except RuntimeError as exc:
                self._logger.warning("AsyncBridge: не удалось запланировать shutdown: %s", exc)

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=self._SHUTDOWN_JOIN_TIMEOUT)
            if self._thread.is_alive():
                self._logger.warning("AsyncBridge: worker-поток не завершился за %.1f сек", self._SHUTDOWN_JOIN_TIMEOUT)
                try:
                    if not self._loop.is_closed():
                        self._loop.call_soon_threadsafe(self._loop.stop)
                        self._thread.join(timeout=0.3)
                except Exception:
                    pass

        try:
            if not self._loop.is_closed():
                self._loop.close()
        except Exception:
            self._logger.exception("AsyncBridge: ошибка при закрытии event loop")

    async def _shutdown_procedure(self) -> None:
        try:
            current = asyncio.current_task()
            pending = [t for t in asyncio.all_tasks(self._loop) if t is not current and not t.done()]
            if pending:
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
            await self._loop.shutdown_asyncgens()
        except Exception:
            self._logger.exception("AsyncBridge: ошибка в shutdown-процедуре")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(
            self,
            coro: Coroutine[Any, Any, Any],
            on_success: Callable[[Any], None] | None = None,
            on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        """Запланировать корутину с автоматической блокировкой UI."""
        if not self.is_running():
            self._logger.error("AsyncBridge: попытка использования после shutdown")
            if on_error:
                self._safe_gui_call(on_error, RuntimeError("Bridge stopped"))
            return

        # ✅ Блокировка от повторных кликов
        if self._ui_locked:
            self._logger.warning("AsyncBridge: операция проигнорирована (UI заблокирован)")
            return

        # ✅ Блокируем UI ПЕРЕД отправкой задачи
        self._safe_gui_call(self._set_ui_state, True)

        try:
            asyncio.run_coroutine_threadsafe(
                self._execute(coro, on_success, on_error), self._loop,
            )
        except RuntimeError as exc:
            self._safe_gui_call(self._set_ui_state, False)
            if on_error:
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
        """Выполнение корутины с гарантированной разблокировкой UI."""
        try:
            result = await coro
            if on_success is not None:
                self._safe_gui_call(on_success, result)
        except asyncio.CancelledError:
            self._logger.debug("AsyncBridge: корутина отменена")
        except Exception as exc:
            self._logger.error("AsyncBridge: ошибка в корутине: %s", exc, exc_info=True)
            if on_error is not None:
                self._safe_gui_call(on_error, exc)
        finally:
            # ✅ ГАРАНТИРОВАННАЯ РАЗБЛОКИРОВКА даже при ошибке
            self._safe_gui_call(self._set_ui_state, False)

    def _set_ui_state(self, locked: bool) -> None:
        """Блокирует/разблокирует контент-область и меняет курсор."""
        try:
            if not self._root.winfo_exists():
                return

            self._ui_locked = locked
            state = "disabled" if locked else "normal"
            cursor = "watch" if locked else ""

            # Находим content_card (обычно второй ребенок main_container)
            for child in self._root.winfo_children():
                if hasattr(child, 'winfo_children'):
                    for sub_child in child.winfo_children():
                        # Ищем карточку с corner_radius > 0 (белая область контента)
                        if getattr(sub_child, '_corner_radius', 0) > 0:
                            sub_child.configure(cursor=cursor)
                            self._toggle_widgets_state(sub_child, state)
                            break
        except Exception as exc:
            self._logger.debug("AsyncBridge: ошибка при изменении состояния UI: %s", exc)

    def _toggle_widgets_state(self, widget: tk.Widget, state: str) -> None:
        """Рекурсивное переключение состояния виджетов."""
        try:
            w_class = widget.__class__.__name__
            # Не отключаем контейнеры и скроллбары, только интерактивные элементы
            if w_class not in ('CTkFrame', 'Frame', 'Scrollbar', 'Canvas'):
                if hasattr(widget, 'configure'):
                    widget.configure(state=state)

            for child in widget.winfo_children():
                self._toggle_widgets_state(child, state)
        except Exception:
            pass

    def _safe_gui_call(self, callback: Callable[..., None], *args: Any) -> None:
        try:
            self._root.after(0, callback, *args)
        except tk.TclError as exc:
            self._logger.debug("AsyncBridge: TclError в _safe_gui_call: %s", exc)
        except Exception as exc:
            self._logger.error("AsyncBridge: неожиданная ошибка в _safe_gui_call: %s", exc, exc_info=True)
