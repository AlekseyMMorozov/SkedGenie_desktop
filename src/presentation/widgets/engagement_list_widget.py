# src/presentation/widgets/engagement_list_widget.py
"""Виджет единого списка задействований (Тип + Шаблон)."""
from __future__ import annotations

import logging
from tkinter import Menu, messagebox, ttk
from typing import Dict, List, Optional

import customtkinter as ctk

from src.application.schemas.engagement_schemas import EngagementTemplateReadSchema, EngagementTypeReadSchema
from src.application.services.engagement_color_service import EngagementColorService
from src.core.logging_config import log_ui_event, log_user_error
from src.presentation.async_bridge import AsyncBridge
from src.presentation.controllers.engagement_template_controller import EngagementTemplateController
from src.presentation.controllers.engagement_type_controller import EngagementTypeController
from src.presentation.dialogs.engagement_dialog import EngagementDialog

# Порядок столбцов по умолчанию
_DEFAULT_COLUMNS: list[tuple[str, str, int]] = [
    ("name", "Название", 200),
    ("short_name", "Краткое имя", 100),
    ("category", "Группа", 120),
    ("duration", "Длительность", 100),
    ("overlap", "Наложения", 80),
]


class EngagementListWidget(ctk.CTkFrame):
    """Таблица задействований с объединенными данными."""

    def __init__(
            self,
            master: ctk.CTk,
            template_controller: EngagementTemplateController,
            type_controller: EngagementTypeController,
            bridge: AsyncBridge,
            logger: logging.Logger,
            color_service: EngagementColorService,
            **kwargs,
    ) -> None:
        super().__init__(master, **kwargs)
        self._template_controller = template_controller
        self._type_controller = type_controller
        self._bridge = bridge
        self._logger = logger
        self._color_service = color_service

        self._templates: List[EngagementTemplateReadSchema] = []
        self._types_map: Dict[str, EngagementTypeReadSchema] = {}

        # Текущий порядок столбцов и состояние сортировки
        self._columns: list[tuple[str, str, int]] = list(_DEFAULT_COLUMNS)
        self._sort_column: str = "name"
        self._sort_reverse: bool = False

        self._create_widgets()
        log_ui_event(self._logger, widget="EngagementListWidget", event="CREATED")

    # ------------------------------------------------------------------
    # UI Setup
    # ------------------------------------------------------------------
    def _create_widgets(self) -> None:
        # Панель кнопок (единый стиль)
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
    # Sorting & Reordering
    # ------------------------------------------------------------------
    def _on_heading_click(self, column: str) -> None:
        if self._sort_column == column:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_column = column
            self._sort_reverse = False

        self._populate_table(self._templates)
        log_ui_event(self._logger, widget="EngagementListWidget", event="SORT",
                     data=f"column={column}, reverse={self._sort_reverse}")

    def _get_sort_key(self, item: EngagementTemplateReadSchema) -> tuple:
        type_info = self._types_map.get(str(item.type_id))
        category = type_info.category if type_info else ""
        duration = type_info.default_duration_hours if type_info else 0.0
        overlap = 0 if (type_info and type_info.allow_overlap) else 1

        key_map = {
            "name": item.name.lower(),
            "short_name": item.short_name.lower(),
            "category": category.lower(),
            "duration": duration,
            "overlap": overlap,
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
                    command=lambda t=target_idx: self._move_column(idx, t)
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

        self._populate_table(self._templates)
        log_ui_event(self._logger, widget="EngagementListWidget", event="COLUMN_REORDERED",
                     data=f"order={[c[0] for c in self._columns]}")

    # ------------------------------------------------------------------
    # Data Loading
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        if not self._bridge.is_running():
            return
        self._bridge.run(
            self._load_data(),
            on_success=self._on_data_loaded,
            on_error=self._on_refresh_error,
        )

    async def _load_data(self) -> tuple[List[EngagementTemplateReadSchema], List[EngagementTypeReadSchema]]:
        templates = await self._template_controller.get_all()
        types = await self._type_controller.get_all()
        return templates, types

    def _on_data_loaded(self, data: tuple[List[EngagementTemplateReadSchema], List[EngagementTypeReadSchema]]) -> None:
        templates, types = data
        self._types_map = {str(t.id): t for t in types}
        self._populate_table(templates)
        log_ui_event(self._logger, widget="EngagementListWidget",
                     event="DATA_LOADED", data=f"templates={len(templates)}, types={len(types)}")

    @staticmethod
    def _contrast_text_color(hex_color: str) -> str:
        hex_color = hex_color.lstrip("#")
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        brightness = (r * 299 + g * 587 + b * 114) / 1000
        return "#000000" if brightness > 140 else "#FFFFFF"

    def _populate_table(self, templates: List[EngagementTemplateReadSchema]) -> None:
        if not self.winfo_exists():
            return
        if not hasattr(self, '_tree') or self._tree is None:
            return

        try:
            self._templates = templates
            sorted_templates = sorted(templates, key=self._get_sort_key, reverse=self._sort_reverse)

            for item in self._tree.get_children():
                self._tree.delete(item)

            for t in sorted_templates:
                type_info = self._types_map.get(str(t.type_id))
                category = type_info.category if type_info else "—"
                duration_str = f"{type_info.default_duration_hours:.1f}ч" if type_info else "—"
                overlap_str = "Да" if (type_info and type_info.allow_overlap) else "Нет"

                bg_color = t.custom_color_hex or (type_info.color_hex if type_info else "#CCCCCC")
                fg_color = self._contrast_text_color(bg_color)

                tag_name = f"color_{t.id}"
                self._tree.tag_configure(tag_name, background=bg_color, foreground=fg_color)

                values_map = {
                    "name": t.name,
                    "short_name": t.short_name,
                    "category": category,
                    "duration": duration_str,
                    "overlap": overlap_str,
                }
                values = tuple(values_map.get(c[0], "") for c in self._columns)
                self._tree.insert("", "end", iid=str(t.id), values=values, tags=(tag_name,))

        except Exception as exc:
            self._logger.error("EngagementListWidget: ошибка заполнения таблицы: %s", exc, exc_info=True)

    def _on_refresh_error(self, exc: Exception) -> None:
        self._logger.error("Failed to load engagements: %s", exc, exc_info=True)
        log_user_error(self._logger, action="LOAD_ENGAGEMENTS", error=str(exc))
        messagebox.showerror("Ошибка", f"Не удалось загрузить задействования: {exc}", parent=self)

    # ------------------------------------------------------------------
    # Selection helpers
    # ------------------------------------------------------------------
    def _get_selected_template(self) -> Optional[EngagementTemplateReadSchema]:
        selection = self._tree.selection()
        if not selection:
            return None
        template_id = selection[0]
        return next((t for t in self._templates if str(t.id) == template_id), None)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _on_create_click(self) -> None:
        log_ui_event(self._logger, widget="EngagementListWidget", event="CREATE_CLICKED")
        self._bridge.run(
            self._type_controller.get_all(),
            on_success=lambda types: EngagementDialog(
                master=self.winfo_toplevel(),
                logger=self._logger,
                mode="create",
                type_controller=self._type_controller,
                template_controller=self._template_controller,
                bridge=self._bridge,
                on_success=lambda: self.after(0, self.refresh),
                color_service=self._color_service,
                available_types=types,
            ),
            on_error=lambda e: messagebox.showerror("Ошибка", f"Не удалось загрузить типы: {e}", parent=self)
        )

    def _on_view_click(self) -> None:
        """Открытие диалога редактирования (просмотр через edit)."""
        selected = self._get_selected_template()
        if selected is None:
            messagebox.showinfo("Внимание", "Выберите задействование в таблице", parent=self)
            return

        log_ui_event(self._logger, widget="EngagementListWidget", event="VIEW_CLICKED",
                     data=f"template_id={selected.id}")

        type_info = self._types_map.get(str(selected.type_id))
        self._bridge.run(
            self._type_controller.get_all(),
            on_success=lambda types: EngagementDialog(
                master=self.winfo_toplevel(),
                logger=self._logger,
                mode="edit",
                type_controller=self._type_controller,
                template_controller=self._template_controller,
                bridge=self._bridge,
                on_success=lambda: self.after(0, self.refresh),
                color_service=self._color_service,
                template=selected,
                engagement_type=type_info,
                available_types=types,
            ),
            on_error=lambda e: messagebox.showerror("Ошибка", f"Не удалось загрузить типы: {e}", parent=self)
        )

    def _on_delete_click(self) -> None:
        selected = self._get_selected_template()
        if selected is None:
            messagebox.showinfo("Внимание", "Выберите задействование в таблице", parent=self)
            return

        if messagebox.askyesno("Подтверждение удаления", f"Удалить задействование '{selected.name}'?", parent=self):
            self._bridge.run(
                self._template_controller.delete(selected.id),
                on_success=lambda _: self.after(0, self.refresh),
                on_error=lambda e: messagebox.showerror("Ошибка", f"Не удалось удалить: {e}", parent=self)
            )

    def _on_refresh_click(self) -> None:
        log_ui_event(self._logger, widget="EngagementListWidget", event="REFRESH_CLICKED")
        self.refresh()
