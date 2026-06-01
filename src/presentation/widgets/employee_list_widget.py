# src/presentation/widgets/employee_list_widget.py
"""
Виджет списка сотрудников с таблицей.

Поддерживает:
    - Сортировку по клику на заголовок столбца.
    - Изменение порядка столбцов через контекстное меню заголовка.
    - Столбцы: №, Должность, Звание, ФИО, Статус.
"""
from __future__ import annotations

import logging
from tkinter import Menu, messagebox, ttk
from typing import List, Optional
from uuid import UUID

import customtkinter as ctk

from src.application.schemas.employee_schemas import EmployeeReadSchema
from src.core.logging_config import log_ui_event, log_user_action, log_user_error
from src.presentation.async_bridge import AsyncBridge
from src.presentation.controllers.employee_controller import EmployeeController
from src.presentation.controllers.engagement_template_controller import EngagementTemplateController
from src.presentation.controllers.task_controller import TaskController
from src.presentation.widgets.employee_dialog_coordinator import EmployeeDialogCoordinator


# Порядок столбцов по умолчанию
_DEFAULT_COLUMNS: list[tuple[str, str, int]] = [
    ("num",      "№",         40),
    ("position", "Должность", 140),
    ("rank",     "Звание",    120),
    ("name",     "ФИО",       180),
    ("status",   "Статус",     80),
]


class EmployeeListWidget(ctk.CTkFrame):
    """Таблица сотрудников с сортировкой и настройкой столбцов."""

    def __init__(
        self,
        master: ctk.CTk,
        controller: EmployeeController,
        bridge: AsyncBridge,
        logger: logging.Logger,
        task_controller: Optional[TaskController] = None,
        engagement_template_controller: Optional[EngagementTemplateController] = None,
        **kwargs,
    ) -> None:
        super().__init__(master, **kwargs)
        self._controller = controller
        self._bridge = bridge
        self._logger = logger

        self._coordinator = EmployeeDialogCoordinator(
            master=master,
            controller=controller,
            bridge=bridge,
            logger=logger,
            on_success=self.refresh,
            task_controller=task_controller,
            engagement_template_controller=engagement_template_controller,
        )

        # Текущий порядок столбцов (можно сохранять в настройки)
        self._columns: list[tuple[str, str, int]] = list(_DEFAULT_COLUMNS)
        self._sort_column: str = "num"
        self._sort_reverse: bool = False
        self._employees: list[EmployeeReadSchema] = []

        self._create_widgets()
        log_ui_event(self._logger, widget="EmployeeListWidget", event="CREATED")

    # ------------------------------------------------------------------
    # Widgets
    # ------------------------------------------------------------------
    def _create_widgets(self) -> None:
        # Панель кнопок
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=8, pady=(8, 4))

        ctk.CTkButton(btn_frame, text="Создать", width=100, command=self._on_create_click).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="Просмотреть", width=110, command=self._on_view_click).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="Архивировать", width=110, command=self._on_archive_click).pack(side="left", padx=2)
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

        # Контекстное меню заголовка для изменения порядка столбцов
        self._header_menu = Menu(self._tree, tearoff=0)
        self._tree.bind("<Button-3>", self._on_tree_right_click)

        # Двойной клик → просмотр
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
        """Сортировка по столбцу. Повторный клик — обратная сортировка."""
        if self._sort_column == column:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_column = column
            self._sort_reverse = False

        self._populate_table(self._employees)
        log_ui_event(self._logger, widget="EmployeeListWidget", event="SORT",
                     data=f"column={column}, reverse={self._sort_reverse}")

    def _get_sort_key(self, emp: EmployeeReadSchema) -> tuple:
        """Ключ сортировки для сотрудника."""
        key_map = {
            "num":      0,  # Номер вычисляется после сортировки
            "position": (emp.position or "").lower(),
            "rank":     (emp.rank or "").lower(),
            "name":     emp.display_name.lower(),
            "status":   0 if emp.is_active else 1,
        }
        return key_map.get(self._sort_column, "")

    # ------------------------------------------------------------------
    # Column reordering via context menu
    # ------------------------------------------------------------------
    def _on_tree_right_click(self, event) -> None:
        """Контекстное меню для перемещения столбцов."""
        region = self._tree.identify_region(event.x, event.y)
        if region != "heading":
            return

        col_id = self._tree.identify_column(event.x)  # "#1", "#2", ...
        try:
            idx = int(col_id.replace("#", "")) - 1
        except ValueError:
            return

        if idx < 0 or idx >= len(self._columns):
            return

        self._header_menu.delete(0, "end")
        current_name = self._columns[idx][1]

        # Подменю «Переместить»
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
        """Переместить столбец и перерисовать таблицу."""
        col = self._columns.pop(from_idx)
        # Корректируем индекс вставки
        if to_idx > from_idx:
            to_idx -= 1
        self._columns.insert(to_idx, col)

        # Пересоздаём столбцы в Treeview
        col_ids = [c[0] for c in self._columns]
        self._tree["columns"] = col_ids
        for col_id, heading, width in self._columns:
            self._tree.heading(col_id, text=heading,
                               command=lambda c=col_id: self._on_heading_click(c))
            self._tree.column(col_id, width=width, minwidth=40)

        self._populate_table(self._employees)
        log_ui_event(self._logger, widget="EmployeeListWidget", event="COLUMN_REORDERED",
                     data=f"order={[c[0] for c in self._columns]}")

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        if not self._bridge.is_running():
            return
        self._bridge.run(
            self._controller.get_all_employees(),
            on_success=self._populate_table,
            on_error=self._on_refresh_error,
        )

    def _populate_table(self, employees: list[EmployeeReadSchema]) -> None:
        if not self.winfo_exists():
            return
        if not hasattr(self, '_tree') or self._tree is None:
            return

        try:
            self._employees = employees

            # Сортировка
            sorted_emps = sorted(employees, key=self._get_sort_key, reverse=self._sort_reverse)

            # Очистка
            for item in self._tree.get_children():
                self._tree.delete(item)

            # Заполнение
            for idx, emp in enumerate(sorted_emps, start=1):
                status = "Активен" if emp.is_active else "В архиве"
                values_map = {
                    "num":      idx,
                    "position": emp.position or "—",
                    "rank":     emp.rank or "—",
                    "name":     emp.display_name,
                    "status":   status,
                }
                values = tuple(values_map.get(c[0], "") for c in self._columns)
                self._tree.insert("", "end", iid=str(emp.id), values=values)

            log_ui_event(self._logger, widget="EmployeeListWidget",
                         event="TABLE_POPULATED", data=f"count={len(employees)}")
        except Exception as exc:
            self._logger.error("EmployeeListWidget: ошибка заполнения таблицы: %s", exc, exc_info=True)

    def _on_refresh_error(self, exc: Exception) -> None:
        self._logger.error("Failed to load employees: %s", exc, exc_info=True)
        log_user_error(self._logger, action="LOAD_EMPLOYEES", error=str(exc))

    # ------------------------------------------------------------------
    # Selection helpers
    # ------------------------------------------------------------------
    def _get_selected_employee(self) -> Optional[EmployeeReadSchema]:
        selection = self._tree.selection()
        if not selection:
            messagebox.showinfo("Внимание", "Выберите сотрудника в таблице", parent=self)
            return None
        emp_id = UUID(selection[0])
        for emp in self._employees:
            if emp.id == emp_id:
                return emp
        return None

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _on_create_click(self) -> None:
        log_ui_event(self._logger, widget="EmployeeListWidget", event="CREATE_CLICKED")
        self._coordinator.open_create_dialog()

    def _on_view_click(self) -> None:
        emp = self._get_selected_employee()
        if emp is None:
            return
        log_ui_event(self._logger, widget="EmployeeListWidget", event="VIEW_CLICKED",
                     data=f"employee_id={emp.id}")
        self._coordinator.open_card_dialog(emp)

    def _on_archive_click(self) -> None:
        emp = self._get_selected_employee()
        if emp is None:
            return
        self._bridge.run(
            self._controller.toggle_active(emp.id),
            on_success=self._on_archive_success,
            on_error=self._on_archive_error,
        )

    def _on_archive_success(self, updated: EmployeeReadSchema) -> None:
        action = "ARCHIVE" if not updated.is_active else "RESTORE"
        log_user_action(self._logger, action=f"{action}_EMPLOYEE",
                        details=f"'{updated.display_name}' (ID: {updated.id})")
        self.refresh()

    def _on_archive_error(self, exc: Exception) -> None:
        self._logger.error("Archive toggle failed: %s", exc, exc_info=True)
        messagebox.showerror("Ошибка", str(exc), parent=self)

    def _on_delete_click(self) -> None:
        emp = self._get_selected_employee()
        if emp is None:
            return
        self._bridge.run(
            self._controller.get_usage_info(emp.id),
            on_success=lambda info: self._confirm_delete(emp, info.task_count),
            on_error=lambda exc: messagebox.showerror("Ошибка", str(exc), parent=self),
        )

    def _confirm_delete(self, employee: EmployeeReadSchema, task_count: int) -> None:
        msg = f"Удалить сотрудника «{employee.display_name}»?"
        if task_count > 0:
            msg += f"\n\n⚠ Сотрудник используется в {task_count} задач(ах).\nСвязи будут удалены."
        if not messagebox.askyesno("Подтверждение удаления", msg, parent=self):
            return
        self._bridge.run(
            self._controller.delete_employee(employee.id),
            on_success=lambda affected: self._on_delete_success(employee.id, affected),
            on_error=self._on_delete_error,
        )

    def _on_delete_success(self, deleted_id: UUID, affected_tasks: int) -> None:
        log_user_action(self._logger, action="DELETE_EMPLOYEE",
                        details=f"ID: {deleted_id}, detached from {affected_tasks} task(s)")
        self.refresh()

    def _on_delete_error(self, exc: Exception) -> None:
        self._logger.error("Delete failed: %s", exc, exc_info=True)
        messagebox.showerror("Ошибка удаления", str(exc), parent=self)

    def _on_refresh_click(self) -> None:
        log_ui_event(self._logger, widget="EmployeeListWidget", event="REFRESH_CLICKED")
        self.refresh()
