# src/presentation/widgets/engagement_type_list_widget.py
"""Виджет списка типов задействований с сортировкой и перестановкой столбцов."""
from __future__ import annotations

import logging
from tkinter import Menu, messagebox, ttk
from typing import List, Optional

import customtkinter as ctk

from src.application.schemas.engagement_schemas import EngagementTypeReadSchema
from src.core.logging_config import log_ui_event, log_user_action, log_user_error
from src.domain.engagements.engagement_type_model import DurationType
from src.presentation.async_bridge import AsyncBridge
from src.presentation.controllers.engagement_type_controller import EngagementTypeController
from src.presentation.widgets.engagement_type_dialog_coordinator import EngagementTypeDialogCoordinator


class EngagementTypeListWidget(ctk.CTkFrame):
    """Таблица типов задействований."""

    _COLUMNS = [
        ("name", "Название", 200),
        ("category", "Группа", 120),
        ("duration_type", "Тип длительности", 130),
        ("default_duration_hours", "Длительность (ч)", 120),
        ("allow_overlap", "Наложения", 90),
        ("color_hex", "Цвет", 70),
    ]

    def __init__(
        self,
        master: ctk.CTk,
        controller: EngagementTypeController,
        bridge: AsyncBridge,
        logger: logging.Logger,
        **kwargs,
    ) -> None:
        super().__init__(master, **kwargs)
        self._controller = controller
        self._bridge = bridge
        self._logger = logger
        self._coordinator = EngagementTypeDialogCoordinator(
            master=master, controller=controller, bridge=bridge,
            logger=logger, on_success=self.refresh,
        )

        self._types: List[EngagementTypeReadSchema] = []
        self._columns = list(self._COLUMNS)
        self._sort_column = "name"
        self._sort_reverse = False

        self._create_widgets()
        self.refresh()

    # ------------------------------------------------------------------
    # UI Setup
    # ------------------------------------------------------------------
    def _create_widgets(self) -> None:
        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", padx=10, pady=(10, 5))
        ctk.CTkButton(toolbar, text="+ Добавить тип", width=140, command=self._on_create_click).pack(side="left")
        ctk.CTkButton(toolbar, text="Обновить", width=100, fg_color="gray", command=self.refresh).pack(side="right")

        tree_frame = ctk.CTkFrame(self, fg_color="transparent")
        tree_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        col_ids = [c[0] for c in self._columns]
        self._tree = ttk.Treeview(tree_frame, columns=col_ids, show="headings", selectmode="browse")
        scrollbar_y = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        scrollbar_x = ttk.Scrollbar(tree_frame, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

        for col_id, heading, width in self._columns:
            self._tree.heading(col_id, text=heading, command=lambda c=col_id: self._on_heading_click(c))
            self._tree.column(col_id, width=width, minwidth=40)

        self._tree.grid(row=0, column=0, sticky="nsew")
        scrollbar_y.grid(row=0, column=1, sticky="ns")
        scrollbar_x.grid(row=1, column=0, sticky="ew")
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        self._header_menu = Menu(self._tree, tearoff=0)
        self._tree.bind("<Button-3>", self._on_tree_right_click)
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
        self._populate_table(self._types)
        log_ui_event(self._logger, "EngagementTypeListWidget", "SORT", f"column={column}, reverse={self._sort_reverse}")

    def _get_sort_key(self, item: EngagementTypeReadSchema) -> tuple:
        key_map = {
            "name": item.name.lower(),
            "category": item.category.lower(),
            "duration_type": item.duration_type.value,
            "default_duration_hours": item.default_duration_hours,
            "allow_overlap": 0 if item.allow_overlap else 1,
            "color_hex": item.color_hex,
        }
        return key_map.get(self._sort_column, "")

    # ------------------------------------------------------------------
    # Column Reordering
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
                move_menu.add_command(label=label, command=lambda t=target_idx: self._move_column(idx, t))
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
            self._tree.heading(col_id, text=heading, command=lambda c=col_id: self._on_heading_click(c))
            self._tree.column(col_id, width=width, minwidth=40)
        self._populate_table(self._types)
        log_ui_event(self._logger, "EngagementTypeListWidget", "COLUMN_REORDERED", f"order={[c[0] for c in self._columns]}")

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        if not self._bridge.is_running():
            return
        self._bridge.run(
            self._controller.get_all(),
            on_success=self._populate_table,
            on_error=self._on_refresh_error,
        )

    def _populate_table(self, types: List[EngagementTypeReadSchema]) -> None:
        if not self.winfo_exists():
            return
        self._types = types
        sorted_types = sorted(types, key=self._get_sort_key, reverse=self._sort_reverse)
        for item in self._tree.get_children():
            self._tree.delete(item)
        for t in sorted_types:
            values_map = {
                "name": t.name,
                "category": t.category,
                "duration_type": t.duration_type.localized,
                "default_duration_hours": f"{t.default_duration_hours:.1f}",
                "allow_overlap": "Да" if t.allow_overlap else "Нет",
                "color_hex": t.color_hex,
            }
            values = tuple(values_map.get(c[0], "") for c in self._columns)
            self._tree.insert("", "end", iid=str(t.id), values=values)

    def _on_refresh_error(self, exc: Exception) -> None:
        log_user_error(self._logger, "refresh_engagement_types", str(exc))
        messagebox.showerror("Ошибка", f"Не удалось загрузить типы: {exc}", parent=self)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _get_selected_type(self) -> Optional[EngagementTypeReadSchema]:
        selection = self._tree.selection()
        if not selection:
            return None
        type_id = selection[0]
        return next((t for t in self._types if str(t.id) == type_id), None)

    def _on_create_click(self) -> None:
        self._coordinator.open_create_dialog()

    def _on_view_click(self) -> None:
        selected = self._get_selected_type()
        if selected:
            self._coordinator.open_edit_dialog(selected)
