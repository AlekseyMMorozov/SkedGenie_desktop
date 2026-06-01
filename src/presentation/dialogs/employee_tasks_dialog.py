# src/presentation/dialogs/employee_tasks_dialog.py
"""
Модальное окно для просмотра и управления задачами сотрудника.

Отображает список задач, в которых участвует сотрудник, и позволяет
добавлять/исключать сотрудника из задач.
Поддерживает сортировку и перестановку столбцов.
"""
from __future__ import annotations

import logging
from tkinter import Menu, messagebox, ttk
from typing import Callable, List, Optional
from uuid import UUID

import customtkinter as ctk

from src.application.schemas.task_schemas import TaskReadSchema
from src.core.logging_config import log_ui_event, log_user_action
from src.domain.tasks.planning_task_model import PERIOD_TYPE_RU

# Порядок столбцов по умолчанию
_DEFAULT_COLUMNS: list[tuple[str, str, int]] = [
    ("name", "Название задачи", 300),
    ("period", "Тип периода", 150),
    ("status", "Статус", 100),
]


class EmployeeTasksDialog(ctk.CTkToplevel):
    """Диалог управления задачами сотрудника."""

    def __init__(
            self,
            master: ctk.CTk,
            logger: logging.Logger,
            employee_id: UUID,
            employee_name: str,
            tasks: List[TaskReadSchema],
            on_remove_from_task: Callable[[UUID, UUID], None],
            on_add_to_task: Optional[Callable[[UUID], None]] = None,
            **kwargs,
    ) -> None:
        super().__init__(master, **kwargs)
        self._logger = logger
        self._employee_id = employee_id
        self._employee_name = employee_name
        self._tasks = tasks
        self._on_remove_from_task = on_remove_from_task
        self._on_add_to_task = on_add_to_task

        # Сортировка и столбцы
        self._columns: list[tuple[str, str, int]] = list(_DEFAULT_COLUMNS)
        self._sort_column: str = "name"
        self._sort_reverse: bool = False

        self._setup_window()
        self._create_widgets()

        # ✅ Применяем тему после создания виджетов
        self._apply_theme_to_self()

        self._populate_table()

    # ------------------------------------------------------------------
    # Theme & Window Setup
    # ------------------------------------------------------------------
    def _apply_theme_to_self(self) -> None:
        """Применяет цвета темы к диалогу и таблице."""
        root = self.winfo_toplevel()
        if hasattr(root, '_theme_colors'):
            colors = root._theme_colors
            dialog_bg = colors.get("dialog_bg", "#FFFFFF")
            border_color = colors.get("border_color", "#C0C0C0")

            self.configure(fg_color=dialog_bg)
            self._configure_treeview_style(dialog_bg, border_color)
        else:
            self.configure(fg_color="#FFFFFF")
            self._configure_treeview_style("#FFFFFF", "#C0C0C0")

    def _configure_treeview_style(self, bg_color: str, border_color: str) -> None:
        """Настраивает стиль Treeview под текущую тему."""
        style = ttk.Style()
        style.theme_use("clam")

        # Определяем цвет текста в зависимости от яркости фона
        text_color = "#000000" if self._is_light_color(bg_color) else "#FFFFFF"
        heading_bg = "#E0E0E0" if self._is_light_color(bg_color) else "#3A3A3A"

        style.configure(
            "Treeview",
            background=bg_color,
            foreground=text_color,
            fieldbackground=bg_color,
            rowheight=28,
            font=("Segoe UI", 10),
            borderwidth=0,
        )
        style.configure(
            "Treeview.Heading",
            background=heading_bg,
            foreground=text_color,
            font=("Segoe UI", 10, "bold"),
            relief="flat",
        )
        style.map(
            "Treeview",
            background=[("selected", "#1F6AA5")],
            foreground=[("selected", "#FFFFFF")],
        )

    @staticmethod
    def _is_light_color(hex_color: str) -> bool:
        hex_color = hex_color.lstrip("#")
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        return (r * 299 + g * 587 + b * 114) / 1000 > 140

    def _setup_window(self) -> None:
        self.title(f"Задачи: {self._employee_name}")
        self.geometry("700x500")
        self.resizable(True, True)

        self.transient(self.master)
        self.grab_set()
        self.focus_force()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _create_widgets(self) -> None:
        padding = {"padx": 10, "pady": 10}

        # Заголовок
        self._header_label = ctk.CTkLabel(
            self,
            text=f"Сотрудник участвует в {len(self._tasks)} задачах:",
            font=ctk.CTkFont(weight="bold", size=14)
        )
        self._header_label.pack(fill="x", **padding)

        # Таблица задач
        tree_frame = ctk.CTkFrame(self, fg_color="transparent")
        tree_frame.pack(fill="both", expand=True, **padding)

        col_ids = [c[0] for c in self._columns]
        self._tree = ttk.Treeview(
            tree_frame,
            columns=col_ids,
            show="headings",
            selectmode="browse"
        )

        for col_id, heading, width in self._columns:
            self._tree.heading(col_id, text=heading,
                               command=lambda c=col_id: self._on_heading_click(c))
            self._tree.column(col_id, width=width, minwidth=60)

        scrollbar_y = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=scrollbar_y.set)

        self._tree.grid(row=0, column=0, sticky="nsew")
        scrollbar_y.grid(row=0, column=1, sticky="ns")
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        # Контекстное меню заголовка
        self._header_menu = Menu(self._tree, tearoff=0)
        self._tree.bind("<Button-3>", self._on_tree_right_click)

        # Кнопки управления
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", side="bottom", **padding)

        ctk.CTkButton(
            btn_frame,
            text="Закрыть",
            fg_color="gray40",
            hover_color="gray30",
            command=self.destroy
        ).pack(side="left", expand=True, fill="x", padx=(0, 5))

        if self._on_add_to_task:
            ctk.CTkButton(
                btn_frame,
                text="Добавить в задачу",
                command=self._on_add_click
            ).pack(side="left", expand=True, fill="x", padx=(5, 5))

        ctk.CTkButton(
            btn_frame,
            text="Удалить из задачи",
            fg_color="#d9534f",
            hover_color="#c9302c",
            command=self._on_remove_click
        ).pack(side="left", expand=True, fill="x", padx=(5, 0))

    # ------------------------------------------------------------------
    # Sorting & Column Reordering
    # ------------------------------------------------------------------
    def _on_heading_click(self, column: str) -> None:
        if self._sort_column == column:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_column = column
            self._sort_reverse = False
        self._populate_table()
        log_ui_event(self._logger, widget="EmployeeTasksDialog", event="SORT",
                     data=f"column={column}, reverse={self._sort_reverse}")

    def _get_sort_key(self, task: TaskReadSchema) -> tuple:
        key_map = {
            "name": task.name.lower(),
            "period": task.period_type,
            "status": "active",
        }
        return key_map.get(self._sort_column, "")

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
            self._tree.column(col_id, width=width, minwidth=60)

        self._populate_table()
        log_ui_event(self._logger, widget="EmployeeTasksDialog", event="COLUMN_REORDERED",
                     data=f"order={[c[0] for c in self._columns]}")

    # ------------------------------------------------------------------
    # Data Population
    # ------------------------------------------------------------------
    def _populate_table(self) -> None:
        sorted_tasks = sorted(self._tasks, key=self._get_sort_key, reverse=self._sort_reverse)

        for item in self._tree.get_children():
            self._tree.delete(item)

        for task in sorted_tasks:
            period_localized = PERIOD_TYPE_RU.get(task.period_type, task.period_type)
            values_map = {
                "name": task.name,
                "period": period_localized,
                "status": "Активна",
            }
            values = tuple(values_map.get(c[0], "") for c in self._columns)
            self._tree.insert("", "end", iid=str(task.id), values=values)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _on_add_click(self) -> None:
        if self._on_add_to_task:
            log_ui_event(self._logger, widget="EmployeeTasksDialog", event="ADD_CLICKED")
            self._on_add_to_task(self._employee_id)

    def _on_remove_click(self) -> None:
        selection = self._tree.selection()
        if not selection:
            messagebox.showinfo("Внимание", "Выберите задачу для удаления сотрудника.", parent=self)
            return

        task_id = UUID(selection[0])
        task_name = self._tree.item(selection[0], "values")[0]

        confirmed = messagebox.askyesno(
            "Подтверждение",
            f"Удалить сотрудника «{self._employee_name}» из задачи «{task_name}»?\n\n"
            f"Сотрудник не будет удален из базы данных, но исключается из будущих графиков этой задачи.",
            parent=self
        )

        if confirmed:
            log_user_action(
                self._logger,
                "Удаление сотрудника из задачи (диалог)",
                f"Employee: {self._employee_name}, Task: {task_name}"
            )
            try:
                self._on_remove_from_task(self._employee_id, task_id)
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось удалить сотрудника из задачи: {e}", parent=self)
                self._logger.error("Error removing employee from task: %s", e, exc_info=True)

    def remove_task_from_list(self, task_id: UUID) -> None:
        """Удалить задачу из списка локально."""
        if self._tree.exists(str(task_id)):
            self._tree.delete(str(task_id))
        self._tasks = [t for t in self._tasks if t.id != task_id]
        count = len(self._tasks)
        self._header_label.configure(text=f"Сотрудник участвует в {count} задачах:")

    def add_task_to_list(self, task: TaskReadSchema) -> None:
        """Добавить задачу в список локально."""
        if any(t.id == task.id for t in self._tasks):
            return

        self._tasks.append(task)
        self._populate_table()
        count = len(self._tasks)
        self._header_label.configure(text=f"Сотрудник участвует в {count} задачах:")
