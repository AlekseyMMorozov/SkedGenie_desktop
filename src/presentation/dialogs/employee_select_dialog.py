# src/presentation/dialogs/employee_select_dialog.py
"""
Модальное окно для выбора сотрудников.

Используется в TaskDialog для привязки сотрудников к задаче.
Реализует мультиселект через имитацию чекбоксов в Treeview.
Поддерживает сортировку и перестановку колонок.
"""
from __future__ import annotations

import logging
from typing import List, Optional
from uuid import UUID

import customtkinter as ctk
from tkinter import Menu, ttk

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

        # Конфигурация колонок: id, заголовок, ширина, можно перемещать, можно сортировать
        self._columns_config = [
            {"id": "status", "heading": "✓", "width": 30, "movable": False, "sortable": False},
            {"id": "name", "heading": "ФИО", "width": 200, "movable": True, "sortable": True},
            {"id": "position", "heading": "Должность", "width": 150, "movable": True, "sortable": True},
            {"id": "rank", "heading": "Звание", "width": 100, "movable": True, "sortable": True},
        ]

        # Состояние сортировки
        self._sort_column: Optional[str] = None
        self._sort_ascending: bool = True

        self._setup_window()
        self._create_widgets()

        # ✅ Применяем тему после создания виджетов
        self._apply_theme_to_self()

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

        self._tree = ttk.Treeview(
            tree_frame,
            show="headings",
            selectmode="none"  # Отключаем стандартное выделение строки
        )

        scrollbar_y = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        scrollbar_x = ttk.Scrollbar(tree_frame, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

        self._tree.grid(row=0, column=0, sticky="nsew")
        scrollbar_y.grid(row=0, column=1, sticky="ns")
        scrollbar_x.grid(row=1, column=0, sticky="ew")

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        # Привязка кликов
        self._tree.bind("<Button-1>", self._on_tree_click)
        self._tree.bind("<Button-3>", self._on_tree_right_click)

        # Построение колонок и данных
        self._rebuild_treeview_columns()
        self._populate_table()

        # Кнопки управления
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", side="bottom", **padding)

        ctk.CTkButton(
            btn_frame,
            text="Отмена",
            fg_color="gray40",
            hover_color="gray30",
            command=self._on_cancel
        ).pack(side="left", expand=True, fill="x", padx=(0, 5))

        ctk.CTkButton(
            btn_frame,
            text="Подтвердить",
            command=self._on_confirm
        ).pack(side="left", expand=True, fill="x", padx=(5, 0))

    def _rebuild_treeview_columns(self) -> None:
        """Перестраивает колонки Treeview на основе текущей конфигурации."""
        # Очищаем старые колонки
        self._tree["columns"] = []

        # Создаем новые колонки
        column_ids = [col["id"] for col in self._columns_config]
        self._tree["columns"] = column_ids

        for col_config in self._columns_config:
            heading_text = col_config["heading"]

            # Добавляем индикатор сортировки
            if self._sort_column == col_config["id"]:
                heading_text += " ▲" if self._sort_ascending else " ▼"

            self._tree.heading(
                col_config["id"],
                text=heading_text,
                command=lambda c=col_config["id"]: self._on_heading_click(c) if col_config["sortable"] else None
            )

            anchor = "center" if col_config["id"] == "status" else "w"
            self._tree.column(col_config["id"], width=col_config["width"], anchor=anchor)

    def _populate_table(self) -> None:
        """Заполняет таблицу данными с учетом текущей сортировки."""
        # Очищаем таблицу
        for item in self._tree.get_children():
            self._tree.delete(item)

        # Сортируем данные если нужно
        employees_to_display = self._all_employees
        if self._sort_column:
            employees_to_display = sorted(
                self._all_employees,
                key=self._get_sort_key,
                reverse=not self._sort_ascending
            )

        # Заполняем таблицу
        for emp in employees_to_display:
            is_selected = emp.id in self._selected_ids
            status_char = "☑" if is_selected else "☐"

            # Собираем значения в порядке колонок
            values = []
            for col_config in self._columns_config:
                if col_config["id"] == "status":
                    values.append(status_char)
                elif col_config["id"] == "name":
                    values.append(emp.display_name)
                elif col_config["id"] == "position":
                    values.append(emp.position or "—")
                elif col_config["id"] == "rank":
                    values.append(emp.rank or "—")

            self._tree.insert(
                "",
                "end",
                iid=str(emp.id),
                values=values,
                tags=("selected",) if is_selected else ()
            )

    def _get_sort_key(self, emp: EmployeeReadSchema) -> tuple:
        """Возвращает ключ сортировки для сотрудника."""
        if self._sort_column == "name":
            return (emp.display_name or "",)
        elif self._sort_column == "position":
            return (emp.position or "яяяяя",)  # None значения в конце
        elif self._sort_column == "rank":
            return (emp.rank or "яяяяя",)  # None значения в конце
        return ("",)

    def _on_heading_click(self, column: str) -> None:
        """Обработчик клика по заголовку колонки (сортировка)."""
        if self._sort_column == column:
            # Переключаем направление сортировки
            self._sort_ascending = not self._sort_ascending
        else:
            # Новая колонка для сортировки
            self._sort_column = column
            self._sort_ascending = True

        # Перестраиваем колонки (обновляем индикаторы) и данные
        self._rebuild_treeview_columns()
        self._populate_table()

        log_ui_event(
            self._logger,
            widget="EmployeeSelectDialog",
            event="SORT",
            data=f"column={column}, ascending={self._sort_ascending}"
        )

    def _on_tree_right_click(self, event) -> None:
        """Обработчик ПКМ по заголовку таблицы (перемещение колонок)."""
        # Определяем, по какой колонке кликнули
        region = self._tree.identify("region", event.x, event.y)
        if region != "heading":
            return

        column = self._tree.identify_column(event.x)
        if not column:
            return

        # column имеет формат "#1", "#2" и т.д.
        try:
            col_index = int(column.replace("#", "")) - 1
        except ValueError:
            return

        if col_index >= len(self._columns_config):
            return

        col_config = self._columns_config[col_index]

        # Если колонку нельзя перемещать, не показываем меню
        if not col_config.get("movable", False):
            return

        # Создаем контекстное меню
        menu = Menu(self, tearoff=0)

        # Определяем, можно ли переместить влево/вправо
        can_move_left = col_index > 0 and self._columns_config[col_index - 1].get("movable", False)
        can_move_right = col_index < len(self._columns_config) - 1 and self._columns_config[col_index + 1].get(
            "movable", False)

        if can_move_left:
            menu.add_command(
                label="← Переместить влево",
                command=lambda: self._move_column(col_index, col_index - 1)
            )

        if can_move_right:
            menu.add_command(
                label="Переместить вправо →",
                command=lambda: self._move_column(col_index, col_index + 1)
            )

        # Показываем меню
        if can_move_left or can_move_right:
            menu.post(event.x_root, event.y_root)

    def _move_column(self, from_idx: int, to_idx: int) -> None:
        """Перемещает колонку с индекса from_idx на to_idx."""
        if from_idx == to_idx:
            return

        # Меняем местами в конфигурации
        col = self._columns_config.pop(from_idx)
        self._columns_config.insert(to_idx, col)

        # Перестраиваем колонки и данные
        self._rebuild_treeview_columns()
        self._populate_table()

        log_ui_event(
            self._logger,
            widget="EmployeeSelectDialog",
            event="MOVE_COLUMN",
            data=f"from={from_idx}, to={to_idx}"
        )

    def _on_tree_click(self, event) -> None:
        """Обработчик ЛКМ по таблице (переключение чекбокса)."""
        # Проверяем, что клик был по строке, а не по заголовку
        region = self._tree.identify("region", event.x, event.y)
        if region != "cell":
            return

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
        current_values = list(self._tree.item(item, "values"))

        # Находим индекс колонки "status"
        status_idx = None
        for idx, col_config in enumerate(self._columns_config):
            if col_config["id"] == "status":
                status_idx = idx
                break

        if status_idx is not None:
            current_values[status_idx] = new_status

        self._tree.item(item, values=current_values, tags=new_tags)

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
