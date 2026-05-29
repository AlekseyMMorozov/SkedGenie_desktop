# src/presentation/dialogs/employee_select_dialog.py
"""
Модальное окно для выбора сотрудников.

Используется в TaskDialog для привязки сотрудников к задаче.
Реализует мультиселект через имитацию чекбоксов в Treeview.
"""
from __future__ import annotations

import logging
from typing import List, Optional
from uuid import UUID

import customtkinter as ctk
from tkinter import ttk

from src.application.schemas.employee_schemas import EmployeeReadSchema
from src.core.logging_config import log_ui_event


class EmployeeSelectDialog(ctk.CTkToplevel):
    """Диалог выбора сотрудников (мультиселект)."""

    def __init__(
            self,
            master: ctk.CTk,
            logger: logging.Logger,
            employees: List[EmployeeReadSchema],
            selected_ids: Optional[List[UUID]] = None,
            **kwargs,
    ) -> None:
        super().__init__(master, **kwargs)
        self._logger = logger
        self._all_employees = employees
        # Используем set для быстрого поиска
        self._selected_ids: set[UUID] = set(selected_ids or [])

        self._result: Optional[List[UUID]] = None

        self._setup_window()
        self._create_widgets()

    def _setup_window(self) -> None:
        self.title("Выбор сотрудников")
        self.geometry("600x400")
        self.resizable(True, True)

        self.transient(self.master)
        self.grab_set()
        self.focus_force()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

    def _create_widgets(self) -> None:
        padding = {"padx": 10, "pady": 10}

        # Инструкция
        label = ctk.CTkLabel(
            self,
            text="Отметьте сотрудников для добавления в задачу:",
            font=ctk.CTkFont(weight="bold")
        )
        label.pack(fill="x", **padding)

        # Frame для Treeview
        tree_frame = ctk.CTkFrame(self, fg_color="transparent")
        tree_frame.pack(fill="both", expand=True, **padding)

        columns = ("status", "name", "position", "rank")
        self._tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            selectmode="none"  # Отключаем стандартное выделение строки
        )

        self._tree.heading("status", text="✓")
        self._tree.column("status", width=30, anchor="center")

        self._tree.heading("name", text="ФИО")
        self._tree.column("name", width=200)

        self._tree.heading("position", text="Должность")
        self._tree.column("position", width=150)

        self._tree.heading("rank", text="Звание")
        self._tree.column("rank", width=100)

        scrollbar_y = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        scrollbar_x = ttk.Scrollbar(tree_frame, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

        self._tree.grid(row=0, column=0, sticky="nsew")
        scrollbar_y.grid(row=0, column=1, sticky="ns")
        scrollbar_x.grid(row=1, column=0, sticky="ew")

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        # Заполнение данными
        for emp in self._all_employees:
            is_selected = emp.id in self._selected_ids
            status_char = "☑" if is_selected else "☐"

            self._tree.insert(
                "",
                "end",
                iid=str(emp.id),
                values=(status_char, emp.display_name, emp.position or "—", emp.rank or "—"),
                tags=("selected",) if is_selected else ()
            )

        # Привязка клика для переключения состояния
        self._tree.bind("<Button-1>", self._on_tree_click)

        # Кнопки управления
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", side="bottom", **padding)

        ctk.CTkButton(
            btn_frame,
            text="Отмена",
            fg_color="gray",
            hover_color="darkgray",
            command=self._on_cancel
        ).pack(side="left", expand=True, fill="x", padx=(0, 5))

        ctk.CTkButton(
            btn_frame,
            text="Подтвердить",
            command=self._on_confirm
        ).pack(side="left", expand=True, fill="x", padx=(5, 0))

    def _on_tree_click(self, event) -> None:
        item = self._tree.identify_row(event.y)
        if not item:
            return

        emp_id = UUID(item)

        # Переключение состояния
        if emp_id in self._selected_ids:
            self._selected_ids.remove(emp_id)
            new_status = "☐"
            new_tags = ()
        else:
            self._selected_ids.add(emp_id)
            new_status = "☑"
            new_tags = ("selected",)

        # Обновление значения в дереве
        current_values = self._tree.item(item, "values")
        # current_values: (status, name, position, rank)
        new_values = (new_status, current_values[1], current_values[2], current_values[3])
        self._tree.item(item, values=new_values, tags=new_tags)

        log_ui_event(self._logger, widget="EmployeeSelectDialog", event="TOGGLE_EMPLOYEE", data=str(emp_id))

    def _on_confirm(self) -> None:
        self._result = list(self._selected_ids)
        log_ui_event(self._logger, widget="EmployeeSelectDialog", event="CONFIRM", data=f"count={len(self._result)}")
        self.destroy()

    def _on_cancel(self) -> None:
        self._result = None
        log_ui_event(self._logger, widget="EmployeeSelectDialog", event="CANCEL")
        self.destroy()

    def get_result(self) -> Optional[List[UUID]]:
        """Возвращает список выбранных ID или None, если отменено."""
        return self._result
