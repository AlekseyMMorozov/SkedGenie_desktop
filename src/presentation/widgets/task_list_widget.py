# src/presentation/widgets/task_list_widget.py
"""
Виджет вкладки "Задачи" главного окна SkedGenie.

Предоставляет интерфейс для просмотра и управления задачами планирования:
    - Таблица ``ttk.Treeview`` с колонками "№", "Название", "Тип периода".
    - Панель инструментов: "Создать", "Просмотреть", "Удалить", "Обновить".
    - Сортировка по клику на заголовок и перестановка столбцов через ПКМ.
    - Делегирует управление диалогами :class:`TaskDialogCoordinator`.
"""
from __future__ import annotations

import logging
from tkinter import Menu, messagebox, ttk
from typing import List, Optional
from uuid import UUID

import customtkinter as ctk

from src.application.schemas.task_schemas import TaskReadSchema
from src.core.logging_config import log_ui_event, log_user_action, log_user_error
from src.domain.tasks.planning_task_model import PERIOD_TYPE_RU
from src.presentation.async_bridge import AsyncBridge
from src.presentation.controllers.employee_controller import EmployeeController
from src.presentation.controllers.engagement_template_controller import (
    EngagementTemplateController,
)
from src.presentation.controllers.task_controller import TaskController
from src.presentation.widgets.task_dialog_coordinator import TaskDialogCoordinator

# Порядок столбцов по умолчанию
_DEFAULT_COLUMNS: list[tuple[str, str, int]] = [
    ("num", "№", 60),
    ("name", "Название", 400),
    ("period_type", "Тип периода", 150),
]


class TaskListWidget(ctk.CTkFrame):
    """Виджет вкладки "Задачи" с таблицей и кнопками CRUD."""

    def __init__(
            self,
            master: ctk.CTk,
            controller: TaskController,
            bridge: AsyncBridge,
            logger: logging.Logger,
            employee_controller: Optional[EmployeeController] = None,
            engagement_template_controller: Optional[EngagementTemplateController] = None,
            **kwargs,
    ) -> None:
        super().__init__(master, **kwargs)
        self._master_root = master
        self._controller = controller
        self._bridge = bridge
        self._logger = logger

        if engagement_template_controller is None:
            raise ValueError(
                "TaskListWidget requires engagement_template_controller "
                "for template selection in TaskDialog"
            )

        self._coordinator = TaskDialogCoordinator(
            master=master,
            task_controller=controller,
            employee_controller=employee_controller,
            engagement_template_controller=engagement_template_controller,
            bridge=bridge,
            logger=logger,
            on_success=self.refresh,
        )

        # Текущий порядок столбцов и состояние сортировки
        self._columns: list[tuple[str, str, int]] = list(_DEFAULT_COLUMNS)
        self._sort_column: str = "num"
        self._sort_reverse: bool = False
        self._tasks: list[TaskReadSchema] = []

        self._create_widgets()
        log_ui_event(self._logger, widget="TaskListWidget", event="CREATED")

    # ------------------------------------------------------------------
    # Widgets
    # ------------------------------------------------------------------
    def _create_widgets(self) -> None:
        # Панель кнопок (единый стиль с EmployeeListWidget)
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=8, pady=(8, 4))

        ctk.CTkButton(btn_frame, text="Создать", width=100, command=self._on_create_click).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="Просмотреть", width=110, command=self._on_view_click).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="Удалить", width=90, fg_color="#d9534f", hover_color="#c9302c",
                      command=self._on_delete_click).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="⟳ Обновить", width=100, fg_color="gray40", hover_color="gray30",
                      command=self._on_refresh_click).pack(side="right", padx=2)

        # Таблица
        tree_frame = ctk.CTkFrame(self, fg_color="transparent")
        tree_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        col_ids = [c[0] for c in self._columns]
        self._tree = ttk.Treeview(tree_frame, columns=col_ids, show="headings", selectmode="browse")

        for col_id, heading, width in self._columns:
            self._tree.heading(col_id, text=heading,
                               command=lambda c=col_id: self._on_heading_click(c))
            self._tree.column(col_id, width=width, minwidth=40)

        scrollbar_y = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        scrollbar_x = ttk.Scrollbar(tree_frame, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

        self._tree.grid(row=0, column=0, sticky="nsew")
        scrollbar_y.grid(row=0, column=1, sticky="ns")
        scrollbar_x.grid(row=1, column=0, sticky="ew")
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        # Контекстное меню заголовка
        self._header_menu = Menu(self._tree, tearoff=0)
        self._tree.bind("<Button-3>", self._on_tree_right_click)

        # Двойной клик → просмотр/редактирование
        self._tree.bind("<Double-1>", lambda e: self._on_view_click())

        self._configure_treeview_style()

    def _configure_treeview_style(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", rowheight=28, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))

    # ------------------------------------------------------------------
    # Sorting
    # ------------------------------------------------------------------
    def _on_heading_click(self, column: str) -> None:
        if self._sort_column == column:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_column = column
            self._sort_reverse = False

        self._populate_table(self._tasks)
        log_ui_event(self._logger, widget="TaskListWidget", event="SORT",
                     data=f"column={column}, reverse={self._sort_reverse}")

    def _get_sort_key(self, task: TaskReadSchema) -> tuple:
        key_map = {
            "num": 0,  # Номер вычисляется после сортировки
            "name": task.name.lower(),
            "period_type": PERIOD_TYPE_RU.get(task.period_type, task.period_type).lower(),
        }
        return key_map.get(self._sort_column, "")

    # ------------------------------------------------------------------
    # Column reordering via context menu
    # ------------------------------------------------------------------
    def _on_tree_right_click(self, event) -> None:
        region = self._tree.identify_region(event.x, event.y)
        if region != "heading":
            return

        col_id = self._tree.identify_column(event.x)
        try:
            idx = int(col_id.replace("#", "")) - 1
        except ValueError:
            return

        if idx < 0 or idx >= len(self._columns):
            return

        self._header_menu.delete(0, "end")
        current_name = self._columns[idx][1]

        move_menu = Menu(self._header_menu, tearoff=0)
        for target_idx, (_, target_name, _) in enumerate(self._columns):
            if target_idx != idx:
                label = f"{'↑' if target_idx < idx else '↓'} Перед «{target_name}»"
                move_menu.add_command(
                    label=label,
                    command=lambda t=target_idx: self._move_column(idx, t),
                )
        self._header_menu.add_cascade(label=f"«{current_name}» → Переместить", menu=move_menu)
        self._header_menu.post(event.x_root, event.y_root)

    def _move_column(self, from_idx: int, to_idx: int) -> None:
        col = self._columns.pop(from_idx)
        if to_idx > from_idx:
            to_idx -= 1
        self._columns.insert(to_idx, col)

        col_ids = [c[0] for c in self._columns]
        self._tree["columns"] = col_ids
        for col_id, heading, width in self._columns:
            self._tree.heading(col_id, text=heading,
                               command=lambda c=col_id: self._on_heading_click(c))
            self._tree.column(col_id, width=width, minwidth=40)

        self._populate_table(self._tasks)
        log_ui_event(self._logger, widget="TaskListWidget", event="COLUMN_REORDERED",
                     data=f"order={[c[0] for c in self._columns]}")

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        if not self._bridge.is_running():
            return
        self._bridge.run(
            self._controller.get_all_tasks(),
            on_success=self._populate_table,
            on_error=self._on_refresh_error,
        )

    def _populate_table(self, tasks: list[TaskReadSchema]) -> None:
        if not self.winfo_exists():
            return
        if not hasattr(self, '_tree') or self._tree is None:
            return

        try:
            self._tasks = tasks

            # Сортировка
            sorted_tasks = sorted(tasks, key=self._get_sort_key, reverse=self._sort_reverse)

            # Очистка
            for item in self._tree.get_children():
                self._tree.delete(item)

            # Заполнение
            for idx, task in enumerate(sorted_tasks, start=1):
                period_localized = PERIOD_TYPE_RU.get(task.period_type, task.period_type)
                values_map = {
                    "num": idx,
                    "name": task.name,
                    "period_type": period_localized,
                }
                values = tuple(values_map.get(c[0], "") for c in self._columns)
                self._tree.insert("", "end", iid=str(task.id), values=values)

            log_ui_event(self._logger, widget="TaskListWidget",
                         event="TABLE_POPULATED", data=f"count={len(tasks)}")
        except Exception as exc:
            self._logger.error("TaskListWidget: ошибка заполнения таблицы: %s", exc, exc_info=True)

    def _on_refresh_error(self, exc: Exception) -> None:
        self._logger.error("Failed to load tasks: %s", exc, exc_info=True)
        log_user_error(self._logger, action="LOAD_TASKS", error=str(exc))

    # ------------------------------------------------------------------
    # Selection helpers
    # ------------------------------------------------------------------
    def _get_selected_task(self) -> Optional[TaskReadSchema]:
        selection = self._tree.selection()
        if not selection:
            messagebox.showinfo("Внимание", "Выберите задачу в таблице", parent=self)
            return None
        task_id = UUID(selection[0])
        for task in self._tasks:
            if task.id == task_id:
                return task
        return None

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _on_create_click(self) -> None:
        log_ui_event(self._logger, widget="TaskListWidget", event="CREATE_CLICKED")
        self._coordinator.open_create_dialog()

    def _on_view_click(self) -> None:
        """Открытие диалога редактирования (в текущей логике TaskDialogCoordinator это edit)."""
        task = self._get_selected_task()
        if task is None:
            return
        log_ui_event(self._logger, widget="TaskListWidget", event="VIEW_CLICKED",
                     data=f"task_id={task.id}")
        # В TaskDialogCoordinator пока нет отдельного view-режима, используем edit
        self._coordinator.open_edit_dialog(task)

    def _on_delete_click(self) -> None:
        task = self._get_selected_task()
        if task is None:
            return

        confirmed = messagebox.askyesno(
            "Подтверждение удаления",
            f"Вы действительно хотите удалить задачу '{task.name}'?",
            parent=self,
        )
        if not confirmed:
            return

        log_user_action(self._logger, action="DELETE_TASK_CONFIRMED",
                        details=f"ID: {task.id}, Name: {task.name}")
        self._bridge.run(
            self._controller.delete_task(task.id),
            on_success=lambda _: self._on_delete_success(task.id),
            on_error=self._on_delete_error,
        )

    def _on_delete_success(self, deleted_id: UUID) -> None:
        log_user_action(self._logger, action="DELETE_TASK_SUCCESS",
                        details=f"ID: {deleted_id}")
        self.refresh()

    def _on_delete_error(self, exc: Exception) -> None:
        self._logger.error("Delete failed: %s", exc, exc_info=True)
        messagebox.showerror("Ошибка удаления", str(exc), parent=self)

    def _on_refresh_click(self) -> None:
        log_ui_event(self._logger, widget="TaskListWidget", event="REFRESH_CLICKED")
        self.refresh()
