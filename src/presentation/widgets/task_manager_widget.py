# src/presentation/widgets/task_manager_widget.py

"""
Файл: src/presentation/widgets/task_manager_widget.py
Описание: Виджет управления задачами планирования. Содержит таблицу списка,
          диалог создания/редактирования с валидацией и точки интеграции с TaskController.
Архитектура: Presentation слой. Не содержит асинхронного кода или прямых вызовов БД.
"""
from __future__ import annotations

import logging
from datetime import date
from uuid import UUID
from typing import Optional, List

from PySide6.QtCore import Qt, Signal, QDate
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QDialog, QFormLayout, QLineEdit,
    QComboBox, QDateEdit, QMessageBox, QLabel, QAbstractItemView,
)

from src.application.schemas.task_schemas import TaskCreateSchema, TaskUpdateSchema, TaskReadSchema
from src.domain.tasks.planning_task_model import PeriodType


class TaskEditDialog(QDialog):
    """Модальный диалог для создания или редактирования задачи.
    Валидирует ввод через Pydantic перед отправкой сигнала."""

    save_requested = Signal(object)  # TaskCreateSchema | TaskUpdateSchema

    def __init__(self, task: Optional[TaskReadSchema] = None, parent=None):
        super().__init__(parent)
        self._logger = logging.getLogger(__name__)
        self._existing_task = task
        self._setup_ui()
        self._populate_fields()

    def _setup_ui(self) -> None:
        self.setWindowTitle("Редактирование задачи" if self._existing_task else "Новая задача")
        self.setMinimumWidth(400)
        layout = QFormLayout(self)

        self.le_name = QLineEdit()
        layout.addRow("Название:", self.le_name)

        self.cb_period = QComboBox()
        for pt in PeriodType:
            self.cb_period.addItem(pt.value, pt)
        layout.addRow("Тип периода:", self.cb_period)

        self.de_start = QDateEdit()
        self.de_start.setCalendarPopup(True)
        self.de_start.setDate(QDate.currentDate())
        layout.addRow("Дата начала:", self.de_start)

        self.de_end = QDateEdit()
        self.de_end.setCalendarPopup(True)
        self.de_end.setDate(QDate.currentDate().addDays(7))
        layout.addRow("Дата окончания:", self.de_end)

        self.le_ref = QLineEdit()
        layout.addRow("Ссылка/Основание:", self.le_ref)

        btn_layout = QHBoxLayout()
        btn_save = QPushButton("Сохранить")
        btn_cancel = QPushButton("Отмена")
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)
        layout.addRow("", btn_layout)

        btn_save.clicked.connect(self._on_save)
        btn_cancel.clicked.connect(self.reject)

    def _populate_fields(self) -> None:
        if self._existing_task:
            self.le_name.setText(self._existing_task.name)
            self.cb_period.setCurrentText(self._existing_task.period_type)
            self.de_start.setDate(QDate(self._existing_task.period_start.year,
                                        self._existing_task.period_start.month,
                                        self._existing_task.period_start.day))
            self.de_end.setDate(QDate(self._existing_task.period_end.year,
                                      self._existing_task.period_end.month,
                                      self._existing_task.period_end.day))
            self.le_ref.setText(self._existing_task.reference_id or "")

    def _on_save(self) -> None:
        try:
            data = {
                "name": self.le_name.text().strip(),
                "period_type": self.cb_period.currentData().value,
                "period_start": self.de_start.date().toPython(),
                "period_end": self.de_end.date().toPython(),
                "reference_id": self.le_ref.text().strip() or None,
            }
            if self._existing_task:
                schema = TaskUpdateSchema(id=self._existing_task.id, **data)
            else:
                schema = TaskCreateSchema(**data)

            self._logger.debug(f"Dialog validation passed for schema: {schema.__class__.__name__}")
            self.save_requested.emit(schema)
        except Exception as e:
            self._logger.warning(f"Validation failed in dialog: {e}")
            QMessageBox.critical(self, "Ошибка валидации", str(e))


class TaskManagerWidget(QWidget):
    """Виджет-контейнер для списка задач и действий над ними."""

    # Сигналы для отправки запросов в контроллер
    request_load_all = Signal()
    request_create = Signal(object)  # TaskCreateSchema
    request_update = Signal(object)  # TaskUpdateSchema
    request_delete = Signal(UUID)

    def __init__(self, controller=None, parent=None):
        super().__init__(parent)
        self._controller = controller
        self._logger = logging.getLogger(__name__)
        self._setup_ui()
        self._connect_controller()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Панель действий
        btn_layout = QHBoxLayout()
        self.btn_add = QPushButton("+ Создать")
        self.btn_edit = QPushButton("✏ Редактировать")
        self.btn_del = QPushButton("🗑 Удалить")
        self.btn_refresh = QPushButton("↻ Обновить")

        self.btn_edit.setEnabled(False)
        self.btn_del.setEnabled(False)

        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_edit)
        btn_layout.addWidget(self.btn_del)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_refresh)
        layout.addLayout(btn_layout)

        # Таблица
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["ID", "Название", "Период", "Начало", "Окончание", "Ссылка"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.table.setSortingEnabled(True)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.table)

        # Статус-строка виджета
        self.lbl_status = QLabel("Загрузка...")
        self.lbl_status.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self.lbl_status)

        # Привязка кнопок
        self.btn_add.clicked.connect(self._on_add)
        self.btn_edit.clicked.connect(self._on_edit)
        self.btn_del.clicked.connect(self._on_delete)
        self.btn_refresh.clicked.connect(lambda: self.request_load_all.emit())

    def _connect_controller(self) -> None:
        """Связка с контроллером (вызывается из main.py при инициализации DI)."""
        if self._controller is None:
            self._logger.warning("Controller not provided. Widget running in standalone UI mode.")
            return

        # Ожидаемые сигналы от контроллера (будут реализованы в task_controller.py)
        if hasattr(self._controller, "tasks_loaded"):
            self._controller.tasks_loaded.connect(self._populate_table)
        if hasattr(self._controller, "operation_succeeded"):
            self._controller.operation_succeeded.connect(lambda msg: self.lbl_status.setText(msg))
        if hasattr(self._controller, "operation_failed"):
            self._controller.operation_failed.connect(lambda err: self.lbl_status.setText(f"Ошибка: {err}"))

        self.btn_add.clicked.connect(lambda: self.request_create.emit(None))
        self.btn_edit.clicked.connect(self._trigger_edit)
        self.btn_del.clicked.connect(self._trigger_delete)

    def _on_selection_changed(self) -> None:
        has_selection = len(self.table.selectedItems()) > 0
        self.btn_edit.setEnabled(has_selection)
        self.btn_del.setEnabled(has_selection)

    def _populate_table(self, tasks: List[TaskReadSchema]) -> None:
        """Обновление таблицы данными из контроллера."""
        self.table.setRowCount(0)
        for row, task in enumerate(tasks):
            self.table.insertRow(row)
            self._set_item(row, 0, str(task.id)[:8] + "...")
            self._set_item(row, 1, task.name)
            self._set_item(row, 2, task.period_type)
            self._set_item(row, 3, task.period_start.strftime("%d.%m.%Y"))
            self._set_item(row, 4, task.period_end.strftime("%d.%m.%Y"))
            self._set_item(row, 5, task.reference_id or "—")
        self.lbl_status.setText(f"Загружено задач: {len(tasks)}")
        self._logger.info(f"Table populated with {len(tasks)} tasks.")

    def _set_item(self, row: int, col: int, text: str) -> None:
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.setItem(row, col, item)

    # --- Обработчики действий ---
    def _on_add(self) -> None:
        dialog = TaskEditDialog(parent=self)
        dialog.save_requested.connect(self.request_create.emit)
        dialog.exec()

    def _trigger_edit(self) -> None:
        row = self.table.currentRow()
        if row == -1:
            return
        # В реальном DI здесь берем из кэша контроллера, пока заглушка
        self._logger.debug("Edit triggered (requires controller task cache in next iteration)")
        QMessageBox.information(self, "Инфо", "Режим редактирования будет активирован после привязки кэша контроллера.")

    def _trigger_delete(self) -> None:
        row = self.table.currentRow()
        if row == -1:
            return
        # Заглушка: в финале берем UUID из скрытого столбца или кэша
        QMessageBox.information(self, "Инфо", "Удаление требует связи с TaskController (Итерация 1.2)")

    def get_selected_task_index(self) -> int:
        return self.table.currentRow()
