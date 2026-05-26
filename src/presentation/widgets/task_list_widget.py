# src/presentation/widgets/task_list_widget.py
"""
Виджет вкладки "Задачи" главного окна SkedGenie.

Предоставляет интерфейс для просмотра и управления задачами планирования:
    - Таблица ``ttk.Treeview`` с колонками "№", "Название", "Тип периода".
    - Панель инструментов: "Создать", "Изменить", "Удалить", "Обновить".
    - Модальное создание и редактирование через :class:`TaskDialog`.
    - Обработка :class:`DuplicateTaskNameError` с предложением переименования.
    - Автоматическое обновление таблицы после каждой операции.
"""
from __future__ import annotations

import logging
from tkinter import messagebox, ttk
from typing import Optional, Union
from uuid import UUID

import customtkinter as ctk

from src.application.schemas.task_schemas import (
    TaskCreateSchema,
    TaskReadSchema,
    TaskUpdateSchema,
)
from src.core.logging_config import log_ui_event, log_user_action, log_user_error
from src.domain.tasks.planning_task_model import PERIOD_TYPE_RU
from src.domain.tasks.task_exceptions import DuplicateTaskNameError
from src.presentation.async_bridge import AsyncBridge
from src.presentation.controllers.task_controller import TaskController
from src.presentation.dialogs.task_dialog import TaskDialog


class TaskListWidget(ctk.CTkFrame):
    """Виджет вкладки "Задачи" с таблицей и кнопками CRUD.

    Attributes:
        _controller: Контроллер задач (фасад над репозиторием).
        _bridge: Мост для вызова async-методов из GUI-потока.
        _logger: Логгер для событий виджета.
        _treeview: ``ttk.Treeview`` с данными задач.
        _tasks_by_id: Маппинг ``item_id → TaskReadSchema``.
        _task_counter: Счётчик строк для отображения "№".
    """

    _MAX_RENAME_ATTEMPTS: int = 10

    def __init__(
        self,
        master: ctk.CTk,
        controller: TaskController,
        bridge: AsyncBridge,
        logger: logging.Logger,
        **kwargs,
    ) -> None:
        """Инициализация виджета вкладки задач."""
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
        # Панель инструментов
        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", padx=10, pady=(10, 5))

        self._btn_create = ctk.CTkButton(
            toolbar, text="Создать", width=100,
            command=self._on_create_click,
        )
        self._btn_create.pack(side="left", padx=(0, 5))

        self._btn_update = ctk.CTkButton(
            toolbar, text="Изменить", width=100,
            command=self._on_update_click,
        )
        self._btn_update.pack(side="left", padx=(0, 5))

        self._btn_delete = ctk.CTkButton(
            toolbar, text="Удалить", width=100,
            fg_color="#c0392b", hover_color="#a93226",
            command=self._on_delete_click,
        )
        self._btn_delete.pack(side="left", padx=(0, 5))

        self._btn_refresh = ctk.CTkButton(
            toolbar, text="Обновить", width=100,
            fg_color="gray", hover_color="darkgray",
            command=self._on_refresh_click,
        )
        self._btn_refresh.pack(side="right")

        # Контейнер для таблицы
        tree_container = ctk.CTkFrame(self, fg_color="transparent")
        tree_container.pack(fill="both", expand=True, padx=10, pady=5)

        self._configure_treeview_style()

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

        scrollbar = ttk.Scrollbar(
            tree_container, orient="vertical", command=self._treeview.yview,
        )
        self._treeview.configure(yscrollcommand=scrollbar.set)

        self._treeview.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Двойной клик — тоже редактирование
        self._treeview.bind("<Double-1>", lambda e: self._on_update_click())

    def _configure_treeview_style(self) -> None:
        """Настройка стиля ``ttk.Treeview`` под тему CustomTkinter."""
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            self._logger.debug("TaskListWidget: тема 'clam' недоступна")

        appearance = ctk.get_appearance_mode()
        if appearance == "Dark":
            bg, fg = "#2b2b2b", "#dcdcdc"
            selected_bg, selected_fg = "#1f538d", "#ffffff"
            heading_bg = "#1f1f1f"
        else:
            bg, fg = "#ffffff", "#000000"
            selected_bg, selected_fg = "#1f538d", "#ffffff"
            heading_bg = "#e0e0e0"

        style.configure(
            "Treeview",
            background=bg, foreground=fg, fieldbackground=bg, rowheight=28,
        )
        style.configure(
            "Treeview.Heading",
            background=heading_bg, foreground=fg,
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
    # Обработчики кнопок
    # ------------------------------------------------------------------
    def _on_create_click(self) -> None:
        """Открытие диалога создания новой задачи."""
        log_ui_event(self._logger, "TaskListWidget.btn_create", "click")
        self._logger.debug("TaskListWidget: открытие диалога создания задачи")

        TaskDialog(
            master=self._master_root,
            logger=self._logger,
            on_save=self._dispatch_save,
            task=None,
        )

    def _on_update_click(self) -> None:
        """Открытие диалога редактирования выбранной задачи."""
        log_ui_event(self._logger, "TaskListWidget.btn_update", "click")

        selected = self._get_selected_task()
        if selected is None:
            messagebox.showinfo(
                "Нет выбора",
                "Выберите задачу в таблице для изменения.",
                parent=self._master_root,
            )
            return

        self._logger.debug(
            "TaskListWidget: открытие диалога редактирования задачи ID=%s",
            selected.id,
        )

        TaskDialog(
            master=self._master_root,
            logger=self._logger,
            on_save=self._dispatch_save,
            task=selected,
        )

    def _on_delete_click(self) -> None:
        """Обработчик кнопки 'Удалить'."""
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
        """Обработчик кнопки 'Обновить'."""
        log_ui_event(self._logger, "TaskListWidget.btn_refresh", "click")
        self._logger.debug("TaskListWidget: обновление списка задач из БД")
        self._bridge.run(
            coro=self._controller.get_all_tasks(),
            on_success=self._populate_table,
            on_error=self._on_refresh_error,
        )

    # ------------------------------------------------------------------
    # Диспетчер сохранения (создание / редактирование)
    # ------------------------------------------------------------------
    def _dispatch_save(
        self,
        task_id: Optional[UUID],
        schema: Union[TaskCreateSchema, TaskUpdateSchema],
    ) -> None:
        """Маршрутизирует коллбэк из диалога к нужному методу.

        Args:
            task_id: ID задачи для редактирования или ``None`` для создания.
            schema: Схема данных (:class:`TaskCreateSchema` или
                :class:`TaskUpdateSchema`).
        """
        if task_id is None:
            # Режим создания
            if not isinstance(schema, TaskCreateSchema):
                self._logger.error(
                    "TaskListWidget: _dispatch_save получил task_id=None, "
                    "но schema не TaskCreateSchema",
                )
                return
            self._execute_create(schema)
        else:
            # Режим редактирования
            if not isinstance(schema, TaskUpdateSchema):
                self._logger.error(
                    "TaskListWidget: _dispatch_save получил task_id=%s, "
                    "но schema не TaskUpdateSchema",
                    task_id,
                )
                return
            self._execute_update(task_id, schema)

    # ------------------------------------------------------------------
    # Создание задачи
    # ------------------------------------------------------------------
    def _execute_create(
        self,
        schema: TaskCreateSchema,
        attempt: int = 1,
    ) -> None:
        """Запуск async-создания задачи через bridge."""
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
        self._on_refresh_click()

    def _on_create_error(
        self,
        exc: Exception,
        schema: TaskCreateSchema,
        attempt: int,
    ) -> None:
        """Обработчик ошибки создания задачи."""
        if isinstance(exc, DuplicateTaskNameError):
            if attempt >= self._MAX_RENAME_ATTEMPTS:
                log_user_error(
                    self._logger,
                    "Создание задачи",
                    f"Превышен лимит попыток ({self._MAX_RENAME_ATTEMPTS})",
                )
                messagebox.showerror(
                    "Ошибка",
                    "Не удалось подобрать уникальное имя. Введите название вручную.",
                    parent=self._master_root,
                )
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
                new_schema = schema.model_copy(update={"name": suggested_name})
                self._execute_create(new_schema, attempt=attempt + 1)
            else:
                log_user_action(
                    self._logger,
                    "Отмена переименования",
                    f"Пользователь отказался от '{suggested_name}'",
                )
                self._on_create_click()
            return

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
    # Редактирование задачи
    # ------------------------------------------------------------------
    def _execute_update(
        self,
        task_id: UUID,
        schema: TaskUpdateSchema,
    ) -> None:
        """Запуск async-обновления задачи через bridge."""
        if not self._bridge.is_running():
            self._logger.error(
                "TaskListWidget: AsyncBridge недоступен, обновление отменено",
            )
            return

        self._bridge.run(
            coro=self._controller.update_task(task_id, schema),
            on_success=self._on_update_success,
            on_error=lambda exc, tid=task_id: self._on_update_error(exc, tid),
        )

    def _on_update_success(self, task: TaskReadSchema) -> None:
        """Обработчик успешного обновления задачи."""
        log_user_action(
            self._logger,
            "Задача обновлена в таблице",
            f"ID: {task.id}, Имя: {task.name}",
        )
        self._on_refresh_click()

    def _on_update_error(self, exc: Exception, task_id: UUID) -> None:
        """Обработчик ошибки обновления задачи."""
        if isinstance(exc, DuplicateTaskNameError):
            log_user_error(
                self._logger,
                "Обновление задачи",
                f"ID={task_id}, Дубликат: '{exc.duplicate_name}'",
            )
            messagebox.showerror(
                "Дубликат названия",
                f"Задача с названием '{exc.duplicate_name}' уже существует.\n\n"
                "Пожалуйста, выберите другое название.",
                parent=self._master_root,
            )
            # Повторно открываем диалог редактирования (свежая копия задачи)
            self._bridge.run(
                coro=self._controller.get_task_by_id(task_id),
                on_success=self._reopen_edit_dialog,
                on_error=lambda e: self._logger.error(
                    "Не удалось перезагрузить задачу для редактирования: %s", e,
                ),
            )
            return

        log_user_error(
            self._logger,
            "Обновление задачи",
            f"ID={task_id}, {type(exc).__name__}: {exc}",
        )
        messagebox.showerror(
            "Ошибка обновления задачи",
            f"Не удалось обновить задачу:\n{exc}",
            parent=self._master_root,
        )

    def _reopen_edit_dialog(self, task: Optional[TaskReadSchema]) -> None:
        """Повторно открывает диалог редактирования (после ошибки дубликата).

        Args:
            task: Актуальные данные задачи (или ``None``, если удалена).
        """
        if task is None:
            self._logger.warning(
                "TaskListWidget: задача не найдена для повторного редактирования",
            )
            messagebox.showinfo(
                "Задача не найдена",
                "Задача была удалена другим пользователем.",
                parent=self._master_root,
            )
            self._on_refresh_click()
            return

        TaskDialog(
            master=self._master_root,
            logger=self._logger,
            on_save=self._dispatch_save,
            task=task,
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
        """Заполнить таблицу задачами (полная перезапись)."""
        for item_id in self._treeview.get_children():
            self._treeview.delete(item_id)
        self._tasks_by_id.clear()
        self._task_counter = 0

        for task in tasks:
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
        """Получить выбранную в таблице задачу."""
        selection = self._treeview.selection()
        if not selection:
            return None
        item_id = selection[0]
        return self._tasks_by_id.get(item_id)
