# src/presentation/dialogs/engagement_template_select_dialog.py
"""
Диалоговое окно для выбора шаблонов задействований из списка.

Используется внутри TaskDialog для привязки шаблонов к задаче (Вариант A)
и в EmployeeDialogCoordinator для управления задействованиями сотрудника.
Поддерживает сортировку и перестановку колонок.
"""
from __future__ import annotations

import logging
from typing import List, Optional
from uuid import UUID

import customtkinter as ctk
from tkinter import Menu, ttk

from src.application.schemas.engagement_schemas import EngagementTemplateReadSchema
from src.core.logging_config import log_ui_event


class EngagementTemplateSelectDialog(ctk.CTkToplevel):
    """Модальный диалог выбора шаблонов задействований с таблицей."""

    def __init__(
        self,
        master: ctk.CTk,
        logger: logging.Logger,
        templates: List[EngagementTemplateReadSchema],
        selected_ids: Optional[List[UUID]] = None,
        **kwargs,
    ) -> None:
        super().__init__(master, **kwargs)
        self._logger = logger
        self._all_templates = templates
        self._selected_ids: set[UUID] = set(selected_ids or [])
        self._result: Optional[List[UUID]] = None

        # Конфигурация колонок
        self._columns_config = [
            {"id": "status", "heading": "✓", "width": 30, "movable": False, "sortable": False},
            {"id": "name", "heading": "Название", "width": 200, "movable": True, "sortable": True},
            {"id": "short_name", "heading": "Сокращение", "width": 120, "movable": True, "sortable": True},
            {"id": "type_name", "heading": "Тип", "width": 150, "movable": True, "sortable": True},
        ]

        # Состояние сортировки
        self._sort_column: Optional[str] = None
        self._sort_ascending: bool = True

        self._setup_window()
        self._create_widgets()
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
        self.title("Выбор шаблонов задействований")
        self.geometry("600x400")
        self.resizable(True, True)

        self.transient(self.master)
        self.grab_set()
        self.focus_force()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

    def _create_widgets(self) -> None:
        padding = {"padx": 10, "pady": 10}

        label = ctk.CTkLabel(
            self,
            text="Отметьте шаблоны, которые будут доступны:",
            font=ctk.CTkFont(weight="bold")
        )
        label.pack(fill="x", **padding)

        tree_frame = ctk.CTkFrame(self, fg_color="transparent")
        tree_frame.pack(fill="both", expand=True, **padding)

        self._tree = ttk.Treeview(
            tree_frame,
            show="headings",
            selectmode="none"
        )

        scrollbar_y = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        scrollbar_x = ttk.Scrollbar(tree_frame, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

        self._tree.grid(row=0, column=0, sticky="nsew")
        scrollbar_y.grid(row=0, column=1, sticky="ns")
        scrollbar_x.grid(row=1, column=0, sticky="ew")

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        self._tree.bind("<Button-1>", self._on_tree_click)
        self._tree.bind("<Button-3>", self._on_tree_right_click)

        self._rebuild_treeview_columns()
        self._populate_table()

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
            text="Применить",
            command=self._on_apply
        ).pack(side="left", expand=True, fill="x", padx=(5, 0))

    def _rebuild_treeview_columns(self) -> None:
        """Перестраивает колонки Treeview на основе текущей конфигурации."""
        self._tree["columns"] = []

        column_ids = [col["id"] for col in self._columns_config]
        self._tree["columns"] = column_ids

        for col_config in self._columns_config:
            heading_text = col_config["heading"]

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
        for item in self._tree.get_children():
            self._tree.delete(item)

        templates_to_display = self._all_templates
        if self._sort_column:
            templates_to_display = sorted(
                self._all_templates,
                key=self._get_sort_key,
                reverse=not self._sort_ascending
            )

        for tpl in templates_to_display:
            is_selected = tpl.id in self._selected_ids
            status_char = "☑" if is_selected else "☐"

            values = []
            for col_config in self._columns_config:
                if col_config["id"] == "status":
                    values.append(status_char)
                elif col_config["id"] == "name":
                    values.append(tpl.name)
                elif col_config["id"] == "short_name":
                    values.append(tpl.short_name or "—")
                elif col_config["id"] == "type_name":
                    type_name = getattr(tpl, "type_name", None) or getattr(tpl, "category", "—")
                    values.append(type_name)

            self._tree.insert(
                "",
                "end",
                iid=str(tpl.id),
                values=values,
                tags=("selected",) if is_selected else ()
            )

    def _get_sort_key(self, tpl: EngagementTemplateReadSchema) -> tuple:
        """Возвращает ключ сортировки для шаблона."""
        if self._sort_column == "name":
            return (tpl.name or "",)
        elif self._sort_column == "short_name":
            return (tpl.short_name or "яяяяя",)
        elif self._sort_column == "type_name":
            type_name = getattr(tpl, "type_name", None) or getattr(tpl, "category", "яяяяя")
            return (type_name or "яяяяя",)
        return ("",)

    def _on_heading_click(self, column: str) -> None:
        """Обработчик клика по заголовку колонки (сортировка)."""
        if self._sort_column == column:
            self._sort_ascending = not self._sort_ascending
        else:
            self._sort_column = column
            self._sort_ascending = True

        self._rebuild_treeview_columns()
        self._populate_table()

        log_ui_event(
            self._logger,
            widget="EngagementTemplateSelectDialog",
            event="SORT",
            data=f"column={column}, ascending={self._sort_ascending}"
        )

    def _on_tree_right_click(self, event) -> None:
        """Обработчик ПКМ по заголовку таблицы (перемещение колонок)."""
        region = self._tree.identify("region", event.x, event.y)
        if region != "heading":
            return

        column = self._tree.identify_column(event.x)
        if not column:
            return

        try:
            col_index = int(column.replace("#", "")) - 1
        except ValueError:
            return

        if col_index >= len(self._columns_config):
            return

        col_config = self._columns_config[col_index]

        if not col_config.get("movable", False):
            return

        menu = Menu(self, tearoff=0)

        can_move_left = col_index > 0 and self._columns_config[col_index - 1].get("movable", False)
        can_move_right = col_index < len(self._columns_config) - 1 and self._columns_config[col_index + 1].get("movable", False)

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

        if can_move_left or can_move_right:
            menu.post(event.x_root, event.y_root)

    def _move_column(self, from_idx: int, to_idx: int) -> None:
        """Перемещает колонку с индекса from_idx на to_idx."""
        if from_idx == to_idx:
            return

        col = self._columns_config.pop(from_idx)
        self._columns_config.insert(to_idx, col)

        self._rebuild_treeview_columns()
        self._populate_table()

        log_ui_event(
            self._logger,
            widget="EngagementTemplateSelectDialog",
            event="MOVE_COLUMN",
            data=f"from={from_idx}, to={to_idx}"
        )

    def _on_tree_click(self, event) -> None:
        """Обработчик ЛКМ по таблице (переключение чекбокса)."""
        region = self._tree.identify("region", event.x, event.y)
        if region != "cell":
            return

        item = self._tree.identify_row(event.y)
        if not item:
            return

        tpl_id = UUID(item)

        if tpl_id in self._selected_ids:
            self._selected_ids.remove(tpl_id)
            new_status = "☐"
            new_tags = ()
        else:
            self._selected_ids.add(tpl_id)
            new_status = "☑"
            new_tags = ("selected",)

        current_values = list(self._tree.item(item, "values"))

        status_idx = None
        for idx, col_config in enumerate(self._columns_config):
            if col_config["id"] == "status":
                status_idx = idx
                break

        if status_idx is not None:
            current_values[status_idx] = new_status

        self._tree.item(item, values=current_values, tags=new_tags)

        log_ui_event(self._logger, widget="EngagementTemplateSelectDialog", event="TOGGLE_TEMPLATE", data=str(tpl_id))

    def _on_apply(self) -> None:
        log_ui_event(self._logger, "EngagementTemplateSelectDialog.btn_apply", "click")
        self._result = list(self._selected_ids)
        self.destroy()

    def _on_cancel(self) -> None:
        log_ui_event(self._logger, "EngagementTemplateSelectDialog.btn_cancel", "click")
        self._result = None
        self.destroy()

    def get_result(self) -> Optional[List[UUID]]:
        """Возвращает список выбранных ID или None при отмене."""
        return self._result
