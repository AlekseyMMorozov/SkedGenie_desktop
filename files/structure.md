# Дерево проекта

SkedGenie_desktop/
  src/
    application/
      interfaces/
        task_repository_interface.py
      schemas/
        task_schemas.py
    domain/
      tasks/
        planning_task_model.py
        task_exceptions.py
    infrastructure/
      db/
        models/
          task_orm_model.py
        async_database_session.py
      repositories/
        task_repository.py
    presentation/
      controllers/
        task_controller.py
      widgets/
        task_manager_widget.py
      main_window.py
  main.py

# Содержание файлов

# task_repository_interface.py
## Импорты
- from __future__ import annotations
- from abc import ABC, abstractmethod
- from uuid import UUID
- from src.domain.tasks.planning_task_model import PlanningTask
## Классы
class ITaskRepository(ABC):
  @abstractmethod async def get_by_id(self, task_id: UUID) -> PlanningTask | None
  @abstractmethod async def get_all(self) -> list[PlanningTask]
  @abstractmethod async def create(self, task: PlanningTask) -> PlanningTask
  @abstractmethod async def update(self, task: PlanningTask) -> PlanningTask
  @abstractmethod async def delete(self, task_id: UUID) -> None

# task_schemas.py
## Импорты
- from __future__ import annotations
- from datetime import date, datetime
- from typing import Optional
- from uuid import UUID
- from pydantic import BaseModel, ConfigDict, Field
- from src.domain.tasks.planning_task_model import PeriodType
## Классы
class TaskCreateSchema(BaseModel):
class TaskUpdateSchema(BaseModel):
class TaskReadSchema(BaseModel):

# planning_task_model.py
## Импорты
- from __future__ import annotations
- import calendar
- from datetime import date, datetime, timedelta
- from enum import Enum
- from typing import Optional
- from uuid import UUID, uuid4
- from pydantic import BaseModel, Field, model_validator
- from src.domain.tasks.task_exceptions import EmptyTaskReferenceError, InvalidTaskNameError, InvalidTaskPeriodError
## Классы
class PeriodType(str, Enum):
class PlanningTask(BaseModel):
  @model_validator(mode='before') @classmethod def _calculate_period_bounds(cls, data: dict) -> dict
  @model_validator(mode='after') def _validate_name_and_references(self) -> 'PlanningTask'
  def clone(self) -> 'PlanningTask'

# task_exceptions.py
## Импорты
- from __future__ import annotations
## Классы
class TaskDomainError(Exception):
class InvalidTaskNameError(TaskDomainError):
class InvalidTaskPeriodError(TaskDomainError):
class EmptyTaskReferenceError(TaskDomainError):

# task_orm_model.py
## Импорты
- from __future__ import annotations
- from datetime import date, datetime
- from typing import Optional
- from sqlalchemy import DateTime, Date, JSON, String
- from sqlalchemy.orm import Mapped, mapped_column
- from src.infrastructure.db.async_database_session import Base
## Классы
class TaskORMModel(Base):
  def __repr__(self) -> str

# async_database_session.py
## Импорты
- from __future__ import annotations
- from pathlib import Path
- from typing import AsyncGenerator
- from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
- from sqlalchemy.orm import DeclarativeBase
## Функции
def get_engine(database_url: str) -> AsyncEngine
def get_session_factory() -> async_sessionmaker[AsyncSession]
async def get_session() -> AsyncGenerator[AsyncSession, None]
async def init_db(dev_reset: bool) -> None

# task_repository.py
## Импорты
- from __future__ import annotations
- from datetime import datetime
- from typing import Optional
- from uuid import UUID
- from sqlalchemy import select, delete
- from src.application.interfaces.task_repository_interface import ITaskRepository
- from src.domain.tasks.planning_task_model import PlanningTask, PeriodType
- from src.infrastructure.db.models.task_orm_model import TaskORMModel
- from src.infrastructure.db.async_database_session import get_session_factory
## Классы
class TaskSQLAlchemyRepository(ITaskRepository):
  @staticmethod def _to_orm(domain: PlanningTask) -> TaskORMModel
  @staticmethod def _to_domain(orm: TaskORMModel) -> PlanningTask
  async def get_by_id(self, task_id: UUID) -> Optional[PlanningTask]
  async def get_all(self) -> list[PlanningTask]
  async def create(self, task: PlanningTask) -> PlanningTask
  async def update(self, task: PlanningTask) -> PlanningTask
  async def delete(self, task_id: UUID) -> None

# task_controller.py
## Импорты
- from __future__ import annotations
- import asyncio
- import logging
- import threading
- from typing import List, Optional
- from uuid import UUID
- from PySide6.QtCore import QObject, Signal
- from src.application.interfaces.task_repository_interface import ITaskRepository
- from src.application.schemas.task_schemas import TaskCreateSchema, TaskUpdateSchema, TaskReadSchema
- from src.domain.tasks.planning_task_model import PlanningTask
- from src.domain.tasks.task_exceptions import TaskDomainError
## Классы
class TaskController(QObject):
  def __init__(self, repository: ITaskRepository, parent)
  def load_tasks(self) -> None
  def create_task(self, schema: TaskCreateSchema) -> None
  def update_task(self, schema: TaskUpdateSchema) -> None
  def delete_task(self, task_id: UUID) -> None
  def get_cached_task(self, task_id: UUID) -> Optional[TaskReadSchema]
  def _update_cache(self, tasks: List[PlanningTask]) -> None
  @staticmethod def _map_to_schema(domain: PlanningTask) -> TaskReadSchema
  async def _execute_load_all(self) -> List[PlanningTask]
  async def _execute_create(self, schema: TaskCreateSchema) -> None
  async def _execute_update(self, schema: TaskUpdateSchema) -> None
  async def _execute_delete(self, task_id: UUID) -> None
  def _dispatch_async(self, coro_func, *args, success_msg: str = 'Готово') -> None

# task_manager_widget.py
## Импорты
- from __future__ import annotations
- import logging
- from datetime import date
- from uuid import UUID
- from typing import Optional, List
- from PySide6.QtCore import Qt, Signal, QDate
- from PySide6.QtGui import QAction, QKeySequence
- from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QDialog, QFormLayout, QLineEdit, QComboBox, QDateEdit, QMessageBox, QLabel, QAbstractItemView
- from src.application.schemas.task_schemas import TaskCreateSchema, TaskUpdateSchema, TaskReadSchema
- from src.domain.tasks.planning_task_model import PeriodType
## Классы
class TaskEditDialog(QDialog):
  def __init__(self, task: Optional[TaskReadSchema], parent)
  def _setup_ui(self) -> None
  def _populate_fields(self) -> None
  def _on_save(self) -> None
class TaskManagerWidget(QWidget):
  def __init__(self, controller, parent)
  def _setup_ui(self) -> None
  def _connect_controller(self) -> None
  def _on_selection_changed(self) -> None
  def _populate_table(self, tasks: List[TaskReadSchema]) -> None
  def _set_item(self, row: int, col: int, text: str) -> None
  def _on_add(self) -> None
  def _trigger_edit(self) -> None
  def _trigger_delete(self) -> None
  def get_selected_task_index(self) -> int

# main_window.py
## Импорты
- from __future__ import annotations
- import logging
- from typing import Optional
- from PySide6.QtCore import Qt, Signal
- from PySide6.QtGui import QAction
- from PySide6.QtWidgets import QMainWindow, QMenuBar, QMenu, QStatusBar, QTabWidget, QDockWidget, QPlainTextEdit, QMessageBox, QWidget
- from src.presentation.controllers.task_controller import TaskController
## Классы
class MainWindow(QMainWindow):
  def __init__(self, task_controller: Optional[TaskController], parent)
  def _setup_window_properties(self) -> None
  def _setup_central_widget(self) -> None
  def _setup_menu_bar(self) -> None
  def _setup_status_bar(self) -> None
  def _setup_log_dock(self) -> None
  def _connect_signals(self) -> None
  def _toggle_log_visibility(self, visible: bool) -> None
  def update_undo_redo_state(self, can_undo: bool, can_redo: bool) -> None
  def log_message(self, message: str, level: str) -> None
  def _on_settings_requested(self) -> None
  def _on_about_requested(self) -> None
  def close_event(self, event) -> None

# main.py
## Импорты
- from __future__ import annotations
- import asyncio
- import logging
- import sys
- from pathlib import Path
- from PySide6.QtWidgets import QApplication
- from src.infrastructure.db.async_database_session import init_db, get_session_factory
- from src.infrastructure.repositories.task_repository import TaskSQLAlchemyRepository
- from src.presentation.main_window import MainWindow
- from src.presentation.controllers.task_controller import TaskController
- from src.presentation.widgets.task_manager_widget import TaskManagerWidget
## Функции
def setup_logging() -> None
async def bootstrap(app: QApplication) -> None
def main() -> None
