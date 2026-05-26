# src/presentation/widgets/task_list_widget.py
"""
Виджет вкладки "Задачи" главного окна SkedGenie.

Предоставляет интерфейс для просмотра и управления задачами планирования:
    - Таблица :class:`ttk.Treeview` с колонками "№", "Название", "Тип периода".
    - Панель инструментов: "Создать", "Изменить", "Удалить", "Обновить".
    - Модальное создание через :class:`CreateTaskDialog`.
    - Обработка :class:`DuplicateTaskNameError` с предложением переименования.
    - Автоматическое обновление таблицы после каждой операции.

Все асинхронные операции с БД выполняются через :class:`AsyncBridge`,
бизнес-логика — через :class:`TaskController`.
"""
from __future__ import annotations

import logging
from tkinter import messagebox, ttk
from typing import Optional
from uuid import UUID

import customtkinter as ctk

from src.application.schemas.task_schemas import TaskCreateSchema, TaskReadSchema
from src.core.logging_config import log_ui_event, log_user_action, log_user_error
from src.domain.tasks.planning_task_model import PERIOD_TYPE_RU
from src.domain.tasks.task_exceptions import DuplicateTaskNameError
from src.presentation.async_bridge import AsyncBridge
from src.presentation.controllers.task_controller import TaskController
from src.presentation.dialogs.create_task_dialog import CreateTaskDialog


class TaskListWidget(ctk.CTkFrame):
    """Виджет вкладки "Задачи" с таблицей и кнопками CRUD.

    Attributes:
        _controller: Контроллер задач (фасад над репозиторием).
        _bridge: Мост для вызова async-методов из GUI-потока.
        _logger: Логгер для событий виджета.
        _treeview: ``ttk.Treeview`` с данными задач.
        _tasks_by_id: Маппинг ``item_id → TaskReadSchema`` для быстрого доступа.
        _task_counter: Счётчик строк для отображения "№".
    """

    _MAX_RENAME_ATTEMPTS: int = 10  # Защита от бесконечной рекурсии

    def __init__(
        self,
        master: ctk.CTk,
        controller: TaskController,
        bridge: AsyncBridge,
        logger: logging.Logger,
        **kwargs,
    ) -> None:
        """Инициализация виджета вкладки задач.

        Args:
            master: Родительский виджет (главное окно или контейнер вкладки).
            controller: Контроллер задач.
            bridge: Мост async-операций.
            logger: Логгер для событий виджета.
            **kwargs: Дополнительные параметры для ``CTkFrame``.
        """
        super().__init__(master, **kwargs)
        self._master_root = master
        self._controller = controller
        self._bridge = bridge
        self._logger = logger

        self._tasks_by_id: dict[str, TaskReadSchema] = {}
        self._task_counter: int = 0

        self._create_widgets()
        self._logger.debug("TaskListWidget: виджет вкладки 'Задачи' создан")

    # ------------------------------------------------------------------
    # Создание UI
    # ------------------------------------------------------------------
    def _create_widgets(self) -> None:
        """Создание панели инструментов и таблицы."""
        # Панель инструментов (сверху)
        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", padx=10, pady=(10, 5))

        self._btn_create = ctk.CTkButton(
            toolbar,
            text="Создать",
            width=100,
            command=self._on_create_click,
        )
        self._btn_create.pack(side="left", padx=(0, 5))

        self._btn_update = ctk.CTkButton(
            toolbar,
            text="Изменить",
            width=100,
            command=self._on_update_click,
        )
        self._btn_update.pack(side="left", padx=(0, 5))

        self._btn_delete = ctk.CTkButton(
            toolbar,
            text="Удалить",
            width=100,
            fg_color="#c0392b",
            hover_color="#a93226",
            command=self._on_delete_click,
        )
        self._btn_delete.pack(side="left", padx=(0, 5))

        self._btn_refresh = ctk.CTkButton(
            toolbar,
            text="Обновить",
            width=100,
            fg_color="gray",
            hover_color="darkgray",
            command=self._on_refresh_click,
        )
        self._btn_refresh.pack(side="right")

        # Контейнер для таблицы (с прокруткой)
        tree_container = ctk.CTkFrame(self, fg_color="transparent")
        tree_container.pack(fill="both", expand=True, padx=10, pady=5)

        # Настройка стиля Treeview под тему CustomTkinter
        self._configure_treeview_style()

        # Таблица
        columns = ("num", "name", "period_type")
        self._treeview = ttk.Treeview(
            tree_container,
            columns=columns,
            show="headings",
            selectmode="browse",
        )

        self._treeview.heading("num", text="№", anchor="center")
        self._treeview.heading("name", text="Название", anchor="w")
        self._treeview.heading("period_type", text="Тип периода", anchor="w")

        self._treeview.column("num", width=60, anchor="center", stretch=False)
        self._treeview.column("name", width=400, anchor="w")
        self._treeview.column("period_type", width=150, anchor="w")

        # Прокрутка
        scrollbar = ttk.Scrollbar(
            tree_container,
            orient="vertical",
            command=self._treeview.yview,
        )
        self._treeview.configure(yscrollcommand=scrollbar.set)

        self._treeview.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _configure_treeview_style(self) -> None:
        """Настройка стиля ``ttk.Treeview`` под текущую тему CustomTkinter.

        Обеспечивает визуальную согласованность стандартного Tkinter-виджета
        с CustomTkinter-оформлением.
        """
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            self._logger.debug("TaskListWidget: тема 'clam' недоступна")

        appearance = ctk.get_appearance_mode()
        if appearance == "Dark":
            bg = "#2b2b2b"
            fg = "#dcdcdc"
            selected_bg = "#1f538d"
            selected_fg = "#ffffff"
            heading_bg = "#1f1f1f"
        else:
            bg = "#ffffff"
            fg = "#000000"
            selected_bg = "#1f538d"
            selected_fg = "#ffffff"
            heading_bg = "#e0e0e0"

        style.configure(
            "Treeview",
            background=bg,
            foreground=fg,
            fieldbackground=bg,
            rowheight=28,
        )
        style.configure(
            "Treeview.Heading",
            background=heading_bg,
            foreground=fg,
            font=("Segoe UI", 10, "bold"),
        )
        style.map(
            "Treeview",
            background=[("selected", selected_bg)],
            foreground=[("selected", selected_fg)],
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        """Публичный метод для внешнего запуска обновления таблицы."""
        self._on_refresh_click()

    # ------------------------------------------------------------------
    # Event handlers (кнопки)
    # ------------------------------------------------------------------
    def _on_create_click(self) -> None:
        """Обработчик кнопки 'Создать': открытие модального диалога."""
        log_ui_event(self._logger, "TaskListWidget.btn_create", "click")
        self._logger.debug("TaskListWidget: открытие диалога создания задачи")

        CreateTaskDialog(
            master=self._master_root,
            logger=self._logger,
            on_save=self._execute_create,
        )

    def _on_update_click(self) -> None:
        """Обработчик кнопки 'Изменить' (заглушка)."""
        log_ui_event(self._logger, "TaskListWidget.btn_update", "click")

        selected = self._get_selected_task()
        if selected is None:
            messagebox.showinfo(
                "Нет выбора",
                "Выберите задачу в таблице для изменения.",
                parent=self._master_root,
            )
            return

        log_user_action(
            self._logger,
            "Изменение задачи (заглушка)",
            f"ID: {selected.id}, Имя: {selected.name}",
        )
        messagebox.showinfo(
            "В разработке",
            f"Диалог изменения задачи '{selected.name}' будет реализован позже.",
            parent=self._master_root,
        )

    def _on_delete_click(self) -> None:
        """Обработчик кнопки 'Удалить': подтверждение и async-удаление."""
        log_ui_event(self._logger, "TaskListWidget.btn_delete", "click")

        selected = self._get_selected_task()
        if selected is None:
            messagebox.showinfo(
                "Нет выбора",
                "Выберите задачу в таблице для удаления.",
                parent=self._master_root,
            )
            return

        confirmed = messagebox.askyesno(
            "Подтверждение удаления",
            f"Вы действительно хотите удалить задачу '{selected.name}'?",
            parent=self._master_root,
        )
        if not confirmed:
            self._logger.debug(
                "TaskListWidget: пользователь отменил удаление задачи ID=%s",
                selected.id,
            )
            return

        log_user_action(
            self._logger,
            "Удаление задачи (подтверждено)",
            f"ID: {selected.id}, Имя: {selected.name}",
        )
        self._bridge.run(
            coro=self._controller.delete_task(selected.id),
            on_success=lambda _: self._on_delete_success(selected.id),
            on_error=self._on_delete_error,
        )

    def _on_refresh_click(self) -> None:
        """Обработчик кнопки 'Обновить': полная перезагрузка таблицы."""
        log_ui_event(self._logger, "TaskListWidget.btn_refresh", "click")
        self._logger.debug("TaskListWidget: обновление списка задач из БД")
        self._bridge.run(
            coro=self._controller.get_all_tasks(),
            on_success=self._populate_table,
            on_error=self._on_refresh_error,
        )

    # ------------------------------------------------------------------
    # Создание задачи: цепочка вызовов
    # ------------------------------------------------------------------
    def _execute_create(
        self,
        schema: TaskCreateSchema,
        attempt: int = 1,
    ) -> None:
        """Запуск async-создания задачи через bridge.

        Args:
            schema: Схема создания задачи.
            attempt: Номер попытки (для защиты от бесконечной рекурсии).
        """
        if not self._bridge.is_running():
            self._logger.error(
                "TaskListWidget: AsyncBridge недоступен, создание отменено",
            )
            return

        self._bridge.run(
            coro=self._controller.create_task(schema),
            on_success=self._on_create_success,
            on_error=lambda exc, s=schema, a=attempt: self._on_create_error(
                exc, s, a,
            ),
        )


    def _on_create_success(self, task: TaskReadSchema) -> None:
        """Обработчик успешного создания задачи."""
        log_user_action(
            self._logger,
            "Задача отображена в таблице",
            f"ID: {task.id}, Имя: {task.name}",
        )
        # Локализация типа периода (строка → русский)
        period_localized = PERIOD_TYPE_RU.get(task.period_type, task.period_type)

        # Добавляем в таблицу и хранилище
        self._task_counter += 1
        item_id = self._treeview.insert(
            parent="",
            index="end",
            values=(self._task_counter, task.name, period_localized),
        )
        self._tasks_by_id[item_id] = task

        # Автообновление таблицы (полное) для согласованности с БД
        self._on_refresh_click()


    def _on_create_error(
        self,
        exc: Exception,
        schema: TaskCreateSchema,
        attempt: int,
    ) -> None:
        """Обработчик ошибки создания задачи.

        При :class:`DuplicateTaskNameError` предлагает пользователю
        переименовать задачу, добавив суффикс ``(2)``, ``(3)`` и т.д.
        """
        if isinstance(exc, DuplicateTaskNameError):
            if attempt >= self._MAX_RENAME_ATTEMPTS:
                log_user_error(
                    self._logger,
                    "Создание задачи",
                    f"Превышен лимит попыток переименования ({self._MAX_RENAME_ATTEMPTS})",
                )
                messagebox.showerror(
                    "Ошибка",
                    "Не удалось подобрать уникальное имя. "
                    "Введите название вручную.",
                    parent=self._master_root,
                )
                # Повторно открываем диалог для ручного ввода
                self._on_create_click()
                return

            suggested_name = f"{exc.duplicate_name} ({attempt + 1})"
            rename = messagebox.askyesno(
                "Дубликат названия",
                f"Задача с названием '{exc.duplicate_name}' уже существует.\n\n"
                f"Переименовать и создать под именем '{suggested_name}'?",
                parent=self._master_root,
            )

            if rename:
                log_user_action(
                    self._logger,
                    "Переименование дубликата",
                    f"'{exc.duplicate_name}' → '{suggested_name}' (попытка {attempt + 1})",
                )
                # Формируем новую схему с переименованным названием
                new_schema = schema.model_copy(update={"name": suggested_name})
                self._execute_create(new_schema, attempt=attempt + 1)
            else:
                log_user_action(
                    self._logger,
                    "Отмена переименования",
                    f"Пользователь отказался от '{suggested_name}'",
                )
                # Повторно открываем диалог для ручного ввода
                self._on_create_click()
            return

        # Все остальные ошибки
        log_user_error(
            self._logger,
            "Создание задачи",
            f"{type(exc).__name__}: {exc}",
        )
        messagebox.showerror(
            "Ошибка создания задачи",
            f"Не удалось создать задачу:\n{exc}",
            parent=self._master_root,
        )

    # ------------------------------------------------------------------
    # Обработчики остальных операций
    # ------------------------------------------------------------------
    def _on_delete_success(self, deleted_id: UUID) -> None:
        """Обработчик успешного удаления задачи."""
        log_user_action(
            self._logger,
            "Задача удалена из таблицы",
            f"ID: {deleted_id}",
        )
        # Полное обновление таблицы для согласованности нумерации
        self._on_refresh_click()

    def _on_delete_error(self, exc: Exception) -> None:
        """Обработчик ошибки удаления."""
        log_user_error(
            self._logger,
            "Удаление задачи",
            f"{type(exc).__name__}: {exc}",
        )
        messagebox.showerror(
            "Ошибка удаления",
            f"Не удалось удалить задачу:\n{exc}",
            parent=self._master_root,
        )

    def _on_refresh_error(self, exc: Exception) -> None:
        """Обработчик ошибки обновления списка."""
        log_user_error(
            self._logger,
            "Обновление списка задач",
            f"{type(exc).__name__}: {exc}",
        )
        messagebox.showerror(
            "Ошибка обновления",
            f"Не удалось загрузить список задач:\n{exc}",
            parent=self._master_root,
        )

    # ------------------------------------------------------------------
    # Вспомогательные методы
    # ------------------------------------------------------------------

    def _populate_table(self, tasks: list[TaskReadSchema]) -> None:
        """Заполнить таблицу задачами (полная перезапись).

        Args:
            tasks: Список задач для отображения.
        """
        # Очистка
        for item_id in self._treeview.get_children():
            self._treeview.delete(item_id)
        self._tasks_by_id.clear()
        self._task_counter = 0

        # Заполнение
        for task in tasks:
            # Локализация типа периода (строка → русский)
            period_localized = PERIOD_TYPE_RU.get(task.period_type, task.period_type)

            self._task_counter += 1
            item_id = self._treeview.insert(
                parent="",
                index="end",
                values=(self._task_counter, task.name, period_localized),
            )
            self._tasks_by_id[item_id] = task

        self._logger.debug(
            "TaskListWidget: таблица обновлена, задач: %d",
            len(tasks),
        )


    def _get_selected_task(self) -> Optional[TaskReadSchema]:
        """Получить выбранную в таблице задачу.

        Returns:
            :class:`TaskReadSchema` или ``None``, если ничего не выбрано.
        """
        selection = self._treeview.selection()
        if not selection:
            return None
        item_id = selection[0]
        return self._tasks_by_id.get(item_id)

