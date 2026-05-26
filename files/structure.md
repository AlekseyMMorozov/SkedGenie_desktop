# Дерево проекта

SkedGenie_desktop/
  data/
  src/
    application/
      interfaces/
        task_repository_interface.py
      schemas/
        task_schemas.py
    core/
      logging_config.py
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
      dialogs/
        create_task_dialog.py
      widgets/
        log_panel.py
        navigation_sidebar.py
        task_list_widget.py
      async_bridge.py
      font_manager.py
      main_window.py
      settings.py
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
  @abstractmethod async def exists_by_name(self, name: str, exclude_id: UUID | None) -> bool
  @abstractmethod async def create(self, task: PlanningTask) -> PlanningTask
  @abstractmethod async def update(self, task: PlanningTask) -> PlanningTask
  @abstractmethod async def delete(self, task_id: UUID) -> None

# task_schemas.py
## Импорты
- from __future__ import annotations
- from datetime import date, datetime
- from typing import Optional, List
- from uuid import UUID
- from pydantic import BaseModel, ConfigDict, Field
- from src.domain.tasks.planning_task_model import PeriodType
## Классы
class TaskCreateSchema(BaseModel):
class TaskUpdateSchema(BaseModel):
class TaskReadSchema(BaseModel):

# logging_config.py
## Импорты
- from __future__ import annotations
- import logging
- import sys
- from logging.handlers import RotatingFileHandler
- from pathlib import Path
- from typing import Optional
- import customtkinter as ctk
## Классы
class DatabaseLogFilter(logging.Filter):
  def filter(self, record: logging.LogRecord) -> bool
class CTkLogHandler(logging.Handler):
  def __init__(self, root: ctk.CTk) -> None
  def attach_widget(self, widget: ctk.CTkTextbox) -> None
  def detach_widget(self) -> None
  def emit(self, record: logging.LogRecord) -> None
  def _buffer_message(self, msg: str) -> None
  def _flush_buffer(self) -> None
  def _schedule_append(self, msg: str) -> None
  def _append_to_widget(self, msg: str) -> None
## Функции
def get_ctk_handler() -> Optional[CTkLogHandler]
def setup_logging(log_level: int, log_file: Optional[str], console_output: bool, file_output: bool, root: Optional[ctk.CTk]) -> None
def get_logger(name: str) -> logging.Logger
def log_user_action(logger: logging.Logger, action: str, details: str) -> None
def log_user_error(logger: logging.Logger, action: str, error: str) -> None
def log_ui_event(logger: logging.Logger, widget: str, event: str, data: str) -> None
def attach_gui_handler(root: ctk.CTk) -> None

# planning_task_model.py
## Импорты
- from __future__ import annotations
- import calendar
- from datetime import date, datetime, timedelta
- from enum import Enum
- from typing import Optional, List
- from uuid import UUID, uuid4
- from pydantic import BaseModel, Field, model_validator, ConfigDict
- from src.domain.tasks.task_exceptions import EmptyTaskReferenceError, InvalidTaskNameError, InvalidTaskPeriodError
## Классы
class PeriodType(str, Enum):
  @property def localized(self) -> str
class PlanningTask(BaseModel):
  @model_validator(mode='after') def _calculate_period_bounds(self) -> 'PlanningTask'
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
class DuplicateTaskNameError(TaskDomainError):
  def __init__(self, duplicate_name: str) -> None

# task_orm_model.py
## Импорты
- from __future__ import annotations
- from datetime import date, datetime
- from typing import Optional
- from uuid import UUID, uuid4
- from sqlalchemy import DateTime, String, Date
- from sqlalchemy.orm import Mapped, mapped_column
- from src.infrastructure.db.async_database_session import Base
## Классы
class TaskORMModel(Base):
  def __repr__(self) -> str

# async_database_session.py
## Импорты
- from __future__ import annotations
- from typing import AsyncGenerator
- from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
- from sqlalchemy.orm import DeclarativeBase
## Классы
class Base(DeclarativeBase):
## Функции
def get_engine(database_url: str) -> AsyncEngine
def get_session_factory(database_url: str) -> async_sessionmaker[AsyncSession]
async def get_session() -> AsyncGenerator[AsyncSession, None]
async def init_db(dev_reset: bool) -> None

# task_repository.py
## Импорты
- from __future__ import annotations
- import json
- from datetime import datetime
- from typing import Optional, List
- from uuid import UUID
- from sqlalchemy import select, delete, exists
- from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
- from src.application.interfaces.task_repository_interface import ITaskRepository
- from src.domain.tasks.planning_task_model import PlanningTask, PeriodType
- from src.infrastructure.db.models.task_orm_model import TaskORMModel
## Классы
class TaskSQLAlchemyRepository(ITaskRepository):
  def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None
  @staticmethod def _to_orm(domain: PlanningTask) -> TaskORMModel
  @staticmethod def _to_domain(orm: TaskORMModel) -> PlanningTask
  async def get_by_id(self, task_id: UUID) -> Optional[PlanningTask]
  async def get_all(self) -> List[PlanningTask]
  async def exists_by_name(self, name: str, exclude_id: UUID | None) -> bool
  async def create(self, task: PlanningTask) -> PlanningTask
  async def update(self, task: PlanningTask) -> PlanningTask
  async def delete(self, task_id: UUID) -> None

# task_controller.py
## Импорты
- from __future__ import annotations
- import logging
- from typing import Optional
- from uuid import UUID
- from sqlalchemy.exc import SQLAlchemyError
- from src.application.interfaces.task_repository_interface import ITaskRepository
- from src.application.schemas.task_schemas import TaskCreateSchema, TaskReadSchema, TaskUpdateSchema
- from src.core.logging_config import log_user_action, log_user_error
- from src.domain.tasks.planning_task_model import PlanningTask
- from src.domain.tasks.task_exceptions import TaskDomainError, DuplicateTaskNameError
## Классы
class TaskController:
  def __init__(self, repository: ITaskRepository, logger: logging.Logger) -> None
  async def get_all_tasks(self) -> list[TaskReadSchema]
  async def get_task_by_id(self, task_id: UUID) -> Optional[TaskReadSchema]
  async def create_task(self, schema: TaskCreateSchema) -> TaskReadSchema
  async def update_task(self, task_id: UUID, schema: TaskUpdateSchema) -> TaskReadSchema
  async def delete_task(self, task_id: UUID) -> None

# create_task_dialog.py
## Импорты
- from __future__ import annotations
- import logging
- from datetime import date
- from tkinter import messagebox
- from typing import Callable
- import customtkinter as ctk
- from src.application.schemas.task_schemas import TaskCreateSchema
- from src.core.logging_config import log_ui_event, log_user_action
- from src.domain.tasks.planning_task_model import PeriodType
## Классы
class CreateTaskDialog(ctk.CTkToplevel):
  def __init__(self, master: ctk.CTk, logger: logging.Logger, on_save: Callable[[TaskCreateSchema], None], **kwargs) -> None
  def _setup_window(self) -> None
  def _create_widgets(self) -> None
  def _on_add_employees(self) -> None
  def _on_add_engagements(self) -> None
  def _on_cancel(self) -> None
  def _on_save_click(self) -> None

# log_panel.py
## Импорты
- from __future__ import annotations
- import logging
- from typing import Optional
- import customtkinter as ctk
- from src.core.logging_config import get_ctk_handler, log_ui_event
## Классы
class LogPanel(ctk.CTkFrame):
  def __init__(self, master: ctk.CTk, logger: logging.Logger, **kwargs) -> None
  def _create_widgets(self) -> None
  def attach_handler(self) -> None
  def clear_logs(self) -> None
  def toggle_visibility(self) -> None

# navigation_sidebar.py
## Импорты
- from __future__ import annotations
- import logging
- from typing import Callable
- import customtkinter as ctk
- from src.core.logging_config import log_ui_event
- from src.presentation.font_manager import get_font_manager
## Классы
class NavigationSidebar(ctk.CTkFrame):
  def __init__(self, master, logger: logging.Logger, on_select: Callable[[str], None], initial_section: str, **kwargs) -> None
  def _create_widgets(self) -> None
  def set_active(self, section: str) -> None
  def get_active(self) -> str
  def get_width(self) -> int
  def _on_button_click(self, section: str) -> None
  def _apply_button_styles(self) -> None
  def _get_theme_colors(self) -> dict[str, str]

# task_list_widget.py
## Импорты
- from __future__ import annotations
- import logging
- from tkinter import messagebox, ttk
- from typing import Optional
- from uuid import UUID
- import customtkinter as ctk
- from src.application.schemas.task_schemas import TaskCreateSchema, TaskReadSchema
- from src.core.logging_config import log_ui_event, log_user_action, log_user_error
- from src.domain.tasks.planning_task_model import PERIOD_TYPE_RU
- from src.domain.tasks.task_exceptions import DuplicateTaskNameError
- from src.presentation.async_bridge import AsyncBridge
- from src.presentation.controllers.task_controller import TaskController
- from src.presentation.dialogs.create_task_dialog import CreateTaskDialog
## Классы
class TaskListWidget(ctk.CTkFrame):
  def __init__(self, master: ctk.CTk, controller: TaskController, bridge: AsyncBridge, logger: logging.Logger, **kwargs) -> None
  def _create_widgets(self) -> None
  def _configure_treeview_style(self) -> None
  def refresh(self) -> None
  def _on_create_click(self) -> None
  def _on_update_click(self) -> None
  def _on_delete_click(self) -> None
  def _on_refresh_click(self) -> None
  def _execute_create(self, schema: TaskCreateSchema, attempt: int) -> None
  def _on_create_success(self, task: TaskReadSchema) -> None
  def _on_create_error(self, exc: Exception, schema: TaskCreateSchema, attempt: int) -> None
  def _on_delete_success(self, deleted_id: UUID) -> None
  def _on_delete_error(self, exc: Exception) -> None
  def _on_refresh_error(self, exc: Exception) -> None
  def _populate_table(self, tasks: list[TaskReadSchema]) -> None
  def _get_selected_task(self) -> Optional[TaskReadSchema]

# async_bridge.py
## Импорты
- from __future__ import annotations
- import asyncio
- import logging
- import threading
- from typing import Any, Callable, Coroutine
- import customtkinter as ctk
## Классы
class AsyncBridge:
  def __init__(self, root: ctk.CTk, logger: logging.Logger) -> None
  def _start_worker(self) -> None
  def _run_loop(self) -> None
  def is_running(self) -> bool
  def shutdown(self) -> None
  def run(self, coro: Coroutine[Any, Any, Any], on_success: Callable[[Any], None] | None, on_error: Callable[[Exception], None] | None) -> None
  async def _execute(self, coro: Coroutine[Any, Any, Any], on_success: Callable[[Any], None] | None, on_error: Callable[[Exception], None] | None) -> None
  def _safe_gui_call(self, callback: Callable[..., None], *args: Any) -> None

# font_manager.py
## Импорты
- from __future__ import annotations
- import logging
- import weakref
- from enum import Enum
- from tkinter import ttk
- from typing import Optional
- import customtkinter as ctk
## Классы
class FontSize(Enum):
class FontManager:
  def __init__(self, base_size: FontSize, logger: Optional[logging.Logger]) -> None
  def get_font(self, role: str) -> ctk.CTkFont
  def get_base_size(self) -> FontSize
  def set_size(self, new_size: FontSize) -> None
  def register_widget(self, widget: ctk.CTkBaseClass, role: str, apply_immediately: bool) -> None
  def register_treeview(self, treeview: ttk.Treeview, style_name: str) -> None
  def apply_treeview_style(self, style_name: str) -> None
  def _rebuild_fonts(self) -> None
  def _update_registered_widgets(self) -> None
  def _apply_font_to_widget(self, widget: ctk.CTkBaseClass, role: str) -> None
  def _update_treeview_styles(self) -> None
  def _apply_treeview_style(self, style_name: str) -> None
## Функции
def get_font_manager() -> Optional[FontManager]
def set_font_manager(manager: FontManager) -> None

# main_window.py
## Импорты
- from __future__ import annotations
- import logging
- from tkinter import messagebox
- from typing import Optional
- import customtkinter as ctk
- import tkinter as tk
- from src.core.logging_config import log_ui_event, log_user_action
- from src.presentation.async_bridge import AsyncBridge
- from src.presentation.controllers.task_controller import TaskController
- from src.presentation.font_manager import FontManager, FontSize, get_font_manager, set_font_manager
- from src.presentation.settings import Settings
- from src.presentation.widgets.log_panel import LogPanel
- from src.presentation.widgets.navigation_sidebar import NavigationSidebar
- from src.presentation.widgets.task_list_widget import TaskListWidget
## Классы
class MainWindow(ctk.CTk):
  def __init__(self, task_controller: TaskController, logger: logging.Logger, settings: Optional[Settings], **kwargs) -> None
  def _init_font_manager(self) -> FontManager
  def _setup_window(self) -> None
  def _create_menu(self) -> None
  def _create_main_layout(self) -> None
  def _create_pages(self) -> None
  def _create_stub_page(self, title: str, message: str, title_font: ctk.CTkFont, subtitle_font: ctk.CTkFont, fm) -> ctk.CTkFrame
  def _create_log_panel(self) -> None
  def _create_status_bar(self) -> None
  def _bind_hotkeys(self) -> None
  def _setup_closing_handler(self) -> None
  def _on_section_select(self, section: str) -> None
  def _show_page(self, section: str) -> None
  def _on_exit(self) -> None
  def _on_undo_stub(self) -> None
  def _on_redo_stub(self) -> None
  def _on_refresh(self) -> None
  def _on_clear_logs(self) -> None
  def _on_settings_stub(self) -> None
  def _on_import_stub(self) -> None
  def _on_export_stub(self) -> None
  def _on_about(self) -> None
  @staticmethod def _get_theme_color(colors_map: dict[str, str], default: str) -> str
  def _on_closing(self) -> None
  def run(self) -> None
  def _initial_load_tasks(self) -> None

# settings.py
## Импорты
- from __future__ import annotations
- import json
- import logging
- import tempfile
- from pathlib import Path
- from typing import Optional
- from pydantic import BaseModel, ValidationError
- from src.presentation.font_manager import FontSize
## Классы
class AppSettings(BaseModel):
class Settings:
  def __init__(self, settings_path: Path, logger: Optional[logging.Logger]) -> None
  def load(self) -> AppSettings
  def save(self, settings: Optional[AppSettings]) -> None
  def get_current(self) -> AppSettings
  def update_font_size(self, new_size: FontSize) -> None
  def update_appearance_mode(self, mode: str) -> None
  def update_color_theme(self, theme: str) -> None

# main.py
## Импорты
- from __future__ import annotations
- import asyncio
- import logging
- import sys
- from pathlib import Path
- import customtkinter as ctk
- from src.core.logging_config import setup_logging, get_logger, attach_gui_handler
- from src.infrastructure.db.async_database_session import init_db, get_session_factory
- from src.infrastructure.repositories.task_repository import TaskSQLAlchemyRepository
- from src.presentation.controllers.task_controller import TaskController
- from src.presentation.main_window import MainWindow
- from src.presentation.settings import Settings
- from src.presentation.settings import AppSettings
## Функции
def main() -> None
