# src/presentation/widgets/employee_list_widget.py
"""
Виджет списка сотрудников с таблицей и CRUD-операциями.

Ответственность:
    - Отображение таблицы сотрудников (№ | ФИО | Должность | Статус).
    - Кнопки: Создать / Просмотреть / Удалить / Обновить / Архивировать.
    - Двойной клик → открытие карточки через координатор (view mode).
    - Обработка CASCADE-удаления с проверкой использования в задачах.
    - Логирование действий пользователя.

Делегирование:
    - Создание → EmployeeDialogCoordinator (диалоги + обработка ошибок).
    - Просмотр/редактирование → EmployeeDialogCoordinator (card dialog).
    - Удаление/архивация → прямые вызовы EmployeeController (требуют выбора строки).

Границы:
    - НЕ обращается к БД напрямую — делегирует EmployeeController.
    - НЕ содержит бизнес-логики — только UI-оркестрация.
    - НЕ управляет жизненным циклом диалогов — делегирует координатору.
"""
from __future__ import annotations

import logging
from tkinter import messagebox, ttk
from typing import Optional
from uuid import UUID

import customtkinter as ctk

from src.application.schemas.employee_schemas import EmployeeReadSchema
from src.core.logging_config import log_ui_event, log_user_action, log_user_error
from src.presentation.async_bridge import AsyncBridge
from src.presentation.controllers.employee_controller import EmployeeController
from src.presentation.widgets.employee_dialog_coordinator import EmployeeDialogCoordinator


class EmployeeListWidget(ctk.CTkFrame):
    """Виджет списка сотрудников с таблицей и кнопками управления."""

    def __init__(
        self,
        master: ctk.CTk,
        controller: EmployeeController,
        bridge: AsyncBridge,
        logger: logging.Logger,
        **kwargs,
    ) -> None:
        """Инициализация виджета.

        Args:
            master: родительское окно (MainWindow).
            controller: EmployeeController для CRUD-операций.
            bridge: AsyncBridge для выполнения async-операций.
            logger: логгер для записи событий.
            **kwargs: дополнительные параметры для CTkFrame.
        """
        super().__init__(master, **kwargs)
        self._controller = controller
        self._bridge = bridge
        self._logger = logger
        self._employees: list[EmployeeReadSchema] = []

        # Координатор диалогов (создание + карточка)
        self._coordinator = EmployeeDialogCoordinator(
            master=self.winfo_toplevel(),
            controller=controller,
            bridge=bridge,
            logger=logger,
            on_success=self.refresh,
        )

        self._create_widgets()
        self._configure_treeview_style()

    # ------------------------------------------------------------------
    # Создание виджетов
    # ------------------------------------------------------------------
    def _create_widgets(self) -> None:
        """Создать все UI-компоненты виджета."""
        # Заголовок
        title_label = ctk.CTkLabel(
            self,
            text="Сотрудники",
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        title_label.pack(anchor="w", pady=(0, 15))

        # Панель кнопок
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.pack(fill="x", pady=(0, 15))

        create_button = ctk.CTkButton(
            button_frame,
            text="Создать",
            command=self._on_create_click,
            width=100,
        )
        create_button.pack(side="left", padx=(0, 10))

        view_button = ctk.CTkButton(
            button_frame,
            text="Просмотреть",
            command=self._on_view_click,
            width=120,
        )
        view_button.pack(side="left", padx=(0, 10))

        delete_button = ctk.CTkButton(
            button_frame,
            text="Удалить",
            command=self._on_delete_click,
            width=100,
            fg_color="red",
            hover_color="darkred",
        )
        delete_button.pack(side="left", padx=(0, 10))

        archive_button = ctk.CTkButton(
            button_frame,
            text="Архивировать",
            command=self._on_archive_click,
            width=120,
        )
        archive_button.pack(side="left", padx=(0, 10))

        refresh_button = ctk.CTkButton(
            button_frame,
            text="Обновить",
            command=self._on_refresh_click,
            width=100,
        )
        refresh_button.pack(side="right")

        # Таблица сотрудников
        tree_frame = ctk.CTkFrame(self, fg_color="transparent")
        tree_frame.pack(fill="both", expand=True)

        columns = ("num", "display_name", "position", "status")
        self._tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
        )

        self._tree.heading("num", text="№")
        self._tree.heading("display_name", text="ФИО")
        self._tree.heading("position", text="Должность")
        self._tree.heading("status", text="Статус")

        self._tree.column("num", width=50, anchor="center")
        self._tree.column("display_name", width=250, anchor="w")
        self._tree.column("position", width=200, anchor="w")
        self._tree.column("status", width=100, anchor="center")

        # Прокрутка
        scrollbar = ttk.Scrollbar(
            tree_frame, orient="vertical", command=self._tree.yview
        )
        self._tree.configure(yscrollcommand=scrollbar.set)

        self._tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Двойной клик → просмотр карточки (через координатор)
        self._tree.bind("<Double-1>", lambda e: self._on_view_click())

    def _configure_treeview_style(self) -> None:
        """Настроить стили для Treeview (светлая/тёмная тема)."""
        style = ttk.Style()
        style.theme_use("clam")

        appearance = ctk.get_appearance_mode()

        if appearance == "Dark":
            bg_color = "#2b2b2b"
            fg_color = "#ffffff"
            field_bg = "#1e1e1e"
            select_bg = "#1f538d"
            select_fg = "#ffffff"
        else:
            bg_color = "#ffffff"
            fg_color = "#000000"
            field_bg = "#f0f0f0"
            select_bg = "#0078d7"
            select_fg = "#ffffff"

        style.configure(
            "Treeview",
            background=bg_color,
            foreground=fg_color,
            fieldbackground=field_bg,
            rowheight=25,
        )
        style.map(
            "Treeview",
            background=[("selected", select_bg)],
            foreground=[("selected", select_fg)],
        )

    # ------------------------------------------------------------------
    # Обновление данных
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        """Обновить список сотрудников из контроллера."""
        log_ui_event(
            self._logger,
            widget="EmployeeListWidget",
            event="REFRESH_REQUESTED",
            data="",
        )

        self._bridge.run(
            self._controller.get_all_employees(),
            on_success=self._populate_table,
            on_error=self._on_refresh_error,
        )


    def _populate_table(self, employees: list[EmployeeReadSchema]) -> None:
        """Заполнить таблицу данными сотрудников с защитой от гонок инициализации."""
        # ✅ Защита 1: Виджет уже уничтожен (например, при быстром закрытии окна)
        if not self.winfo_exists():
            self._logger.debug("EmployeeListWidget: виджет уничтожён, пропуск обновления")
            return

        # ✅ Защита 2: Treeview ещё не создан или удалён
        if not hasattr(self, '_tree') or self._tree is None:
            self._logger.debug("EmployeeListWidget: Treeview не инициализирован, пропуск")
            return

        try:
            # Очистка текущих данных
            for item in self._tree.get_children():
                self._tree.delete(item)

            # Сохраняем ссылку на новые данные
            self._employees = employees

            # Вставка новых записей
            for idx, emp in enumerate(employees, start=1):
                status = "Активен" if emp.is_active else "В архиве"
                self._tree.insert(
                    "",
                    "end",
                    iid=str(emp.id),
                    values=(
                        idx,
                        emp.display_name,
                        emp.position or "",
                        status,
                    ),
                )

            self._logger.debug(
                "EmployeeListWidget: таблица обновлена, сотрудников: %d",
                len(employees),
            )
            log_ui_event(
                self._logger,
                widget="EmployeeListWidget",
                event="TABLE_POPULATED",
                data=f"count={len(employees)}",
            )
        except Exception as exc:
            self._logger.error(
                "EmployeeListWidget: критическая ошибка при заполнении таблицы: %s",
                exc,
                exc_info=True,
            )


    def _on_refresh_error(self, exc: Exception) -> None:
        """Обработать ошибку обновления списка."""
        self._logger.exception("Failed to refresh employee list")
        log_user_error(
            self._logger,
            action="REFRESH_EMPLOYEES",
            error=f"Failed to refresh employee list: {exc}",
        )
        messagebox.showerror(
            "Ошибка обновления",
            f"Не удалось обновить список сотрудников:\n{exc}",
            parent=self,
        )

    # ------------------------------------------------------------------
    # Получение выбранного сотрудника
    # ------------------------------------------------------------------
    def _get_selected_employee(self) -> Optional[EmployeeReadSchema]:
        """Получить выбранного в таблице сотрудника."""
        selection = self._tree.selection()
        if not selection:
            messagebox.showwarning(
                "Не выбран сотрудник",
                "Пожалуйста, выберите сотрудника из списка.",
                parent=self,
            )
            return None

        employee_id = UUID(selection[0])
        for emp in self._employees:
            if emp.id == employee_id:
                return emp

        return None

    # ------------------------------------------------------------------
    # Создание сотрудника (делегирование координатору)
    # ------------------------------------------------------------------
    def _on_create_click(self) -> None:
        """Обработать нажатие кнопки 'Создать'."""
        log_ui_event(
            self._logger,
            widget="EmployeeListWidget",
            event="CREATE_CLICKED",
            data="",
        )
        self._coordinator.open_create_dialog()

    # ------------------------------------------------------------------
    # Просмотр карточки (делегирование координатору)
    # ------------------------------------------------------------------
    def _on_view_click(self) -> None:
        """Обработать нажатие кнопки 'Просмотреть' или двойной клик."""
        employee = self._get_selected_employee()
        if not employee:
            return

        log_ui_event(
            self._logger,
            widget="EmployeeListWidget",
            event="VIEW_CLICKED",
            data=f"employee_id={employee.id}",
        )
        self._coordinator.open_card_dialog(employee)

    # ------------------------------------------------------------------
    # Удаление сотрудника (прямой вызов контроллера)
    # ------------------------------------------------------------------
    def _on_delete_click(self) -> None:
        """Обработать нажатие кнопки 'Удалить'."""
        employee = self._get_selected_employee()
        if not employee:
            return

        log_ui_event(
            self._logger,
            widget="EmployeeListWidget",
            event="DELETE_CLICKED",
            data=f"employee_id={employee.id}",
        )

        self._bridge.run(
            self._controller.get_usage_info(employee.id),
            on_success=lambda info: self._confirm_delete(employee, info.task_count),
            on_error=self._on_delete_error,
        )

    def _confirm_delete(self, employee: EmployeeReadSchema, task_count: int) -> None:
        """Показать диалог подтверждения удаления."""
        if task_count > 0:
            message = (
                f"Сотрудник '{employee.display_name}' используется в {task_count} задач(ах).\n\n"
                f"При удалении он будет исключён из всех задач (CASCADE).\n\n"
                f"Вы уверены, что хотите удалить сотрудника?"
            )
        else:
            message = (
                f"Вы уверены, что хотите удалить сотрудника '{employee.display_name}'?\n\n"
                f"Это действие необратимо."
            )

        confirmed = messagebox.askyesno(
            "Подтверждение удаления",
            message,
            parent=self,
        )

        if confirmed:
            self._bridge.run(
                self._controller.delete_employee(employee.id),
                on_success=lambda affected: self._on_delete_success(employee.id, affected),
                on_error=self._on_delete_error,
            )

    def _on_delete_success(self, deleted_id: UUID, affected_tasks: int) -> None:
        """Обработать успешное удаление сотрудника."""
        log_user_action(
            self._logger,
            action="DELETE_EMPLOYEE",
            details=f"Deleted employee {deleted_id}, detached from {affected_tasks} task(s)",
        )
        messagebox.showinfo(
            "Успех",
            f"Сотрудник успешно удалён.\nИсключён из {affected_tasks} задач(и).",
            parent=self,
        )
        self.refresh()

    def _on_delete_error(self, exc: Exception) -> None:
        """Обработать ошибку удаления."""
        self._logger.exception("Failed to delete employee")
        log_user_error(
            self._logger,
            action="DELETE_EMPLOYEE",
            error=f"Failed to delete employee: {exc}",
        )
        messagebox.showerror(
            "Ошибка удаления",
            f"Не удалось удалить сотрудника:\n{exc}",
            parent=self,
        )

    # ------------------------------------------------------------------
    # Архивация / Восстановление (прямой вызов контроллера)
    # ------------------------------------------------------------------
    def _on_archive_click(self) -> None:
        """Обработать нажатие кнопки 'Архивировать'."""
        employee = self._get_selected_employee()
        if not employee:
            return

        action = "восстановить" if not employee.is_active else "архивировать"
        confirmed = messagebox.askyesno(
            "Подтверждение",
            f"Вы уверены, что хотите {action} сотрудника '{employee.display_name}'?",
            parent=self,
        )

        if not confirmed:
            return

        log_ui_event(
            self._logger,
            widget="EmployeeListWidget",
            event="ARCHIVE_CLICKED",
            data=f"employee_id={employee.id}, current_status={employee.is_active}",
        )

        self._bridge.run(
            self._controller.toggle_active(employee.id),
            on_success=self._on_archive_success,
            on_error=self._on_archive_error,
        )

    def _on_archive_success(self, updated: EmployeeReadSchema) -> None:
        """Обработать успешное переключение статуса."""
        status = "активирован" if updated.is_active else "архивирован"
        log_user_action(
            self._logger,
            action="TOGGLE_ACTIVE",
            details=f"Employee {updated.id} {status}",
        )
        messagebox.showinfo(
            "Успех",
            f"Сотрудник '{updated.display_name}' {status}.",
            parent=self,
        )
        self.refresh()

    def _on_archive_error(self, exc: Exception) -> None:
        """Обработать ошибку переключения статуса."""
        self._logger.exception("Failed to toggle active status")
        log_user_error(
            self._logger,
            action="TOGGLE_ACTIVE",
            error=f"Failed to toggle active status: {exc}",
        )
        messagebox.showerror(
            "Ошибка",
            f"Не удалось изменить статус сотрудника:\n{exc}",
            parent=self,
        )

    # ------------------------------------------------------------------
    # Обновление списка
    # ------------------------------------------------------------------
    def _on_refresh_click(self) -> None:
        """Обработать нажатие кнопки 'Обновить'."""
        log_ui_event(
            self._logger,
            widget="EmployeeListWidget",
            event="REFRESH_CLICKED",
            data="",
        )
        self.refresh()
