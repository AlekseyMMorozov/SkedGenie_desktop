# Дерево проекта

SkedGenie_desktop/
  data/
  src/
    application/
      interfaces/
        employee_repository_interface.py
        task_repository_interface.py
      schemas/
        employee_schemas.py
        task_schemas.py
      services/
        employee_link_service.py
    core/
      logging_config.py
    domain/
      employees/
        employee_exceptions.py
        employee_model.py
      tasks/
        planning_task_model.py
        task_exceptions.py
    infrastructure/
      db/
        models/
          employee_orm_model.py
          task_orm_model.py
        async_database_session.py
      repositories/
        employee_repository.py
        task_repository.py
    presentation/
      controllers/
        display_name_resolver.py
        employee_controller.py
        task_controller.py
      dialogs/
        employee_dialog.py
        task_dialog.py
      widgets/
        employee_card_sections.py
        employee_dialog_coordinator.py
        employee_list_widget.py
        log_panel.py
        main_menu.py
        navigation_sidebar.py
        page_factory.py
        task_list_widget.py
      async_bridge.py
      font_manager.py
      main_window.py
      settings.py
  __init__.py
  main.py

# Содержание файлов

# employee_repository_interface.py
## Импорты
- from __future__ import annotations
- from abc import ABC, abstractmethod
- from typing import List, Optional
- from uuid import UUID
- from src.domain.employees.employee_model import Employee
## Классы
class IEmployeeRepository(ABC):
  @abstractmethod async def get_by_id(self, employee_id: UUID) -> Optional[Employee]
  @abstractmethod async def get_all(self) -> List[Employee]
  @abstractmethod async def get_active_only(self) -> List[Employee]
  @abstractmethod async def exists_by_email(self, email: str, exclude_id: Optional[UUID]) -> bool
  @abstractmethod async def exists_by_tab_number(self, tab_number: str, exclude_id: Optional[UUID]) -> bool
  @abstractmethod async def create(self, employee: Employee) -> Employee
  @abstractmethod async def update(self, employee: Employee) -> Employee
  @abstractmethod async def delete(self, employee_id: UUID) -> None

# task_repository_interface.py
## Импорты
- from __future__ import annotations
- from abc import ABC, abstractmethod
- from typing import List
- from uuid import UUID
- from src.domain.tasks.planning_task_model import PlanningTask
## Классы
class ITaskRepository(ABC):
  @abstractmethod async def get_by_id(self, task_id: UUID) -> PlanningTask | None
  @abstractmethod async def get_all(self) -> List[PlanningTask]
  @abstractmethod async def exists_by_name(self, name: str, exclude_id: UUID | None) -> bool
  @abstractmethod async def create(self, task: PlanningTask) -> PlanningTask
  @abstractmethod async def update(self, task: PlanningTask) -> PlanningTask
  @abstractmethod async def delete(self, task_id: UUID) -> None
  @abstractmethod async def count_tasks_using_employee(self, employee_id: UUID) -> int
  @abstractmethod async def remove_employee_from_all_tasks(self, employee_id: UUID) -> int
  @abstractmethod async def remove_employee_from_task(self, employee_id: UUID, task_id: UUID) -> bool

# employee_schemas.py
## Импорты
- from __future__ import annotations
- import re
- from datetime import date, datetime
- from typing import List, Optional
- from uuid import UUID
- from pydantic import BaseModel, ConfigDict, Field, field_validator
- from src.domain.employees.employee_exceptions import InvalidEmployeeNameError
## Классы
class EmployeeCreateSchema(BaseModel):
  @field_validator('last_name', 'first_name', 'middle_name') @classmethod def _strip_and_validate_name(cls, value: Optional[str], info) -> Optional[str]
  @field_validator('tab_number') @classmethod def _normalize_tab_number(cls, value: Optional[str]) -> Optional[str]
  @field_validator('email') @classmethod def _validate_email(cls, value: Optional[str]) -> Optional[str]
  @field_validator('phone') @classmethod def _normalize_phone(cls, value: Optional[str]) -> Optional[str]
  @field_validator('birth_date') @classmethod def _validate_birth_date(cls, value: Optional[date]) -> Optional[date]
class EmployeeUpdateSchema(BaseModel):
  @field_validator('last_name', 'first_name', 'middle_name') @classmethod def _strip_and_validate_name(cls, value: Optional[str], info) -> Optional[str]
  @field_validator('tab_number') @classmethod def _normalize_tab_number(cls, value: Optional[str]) -> Optional[str]
  @field_validator('email') @classmethod def _validate_email(cls, value: Optional[str]) -> Optional[str]
  @field_validator('phone') @classmethod def _normalize_phone(cls, value: Optional[str]) -> Optional[str]
  @field_validator('birth_date') @classmethod def _validate_birth_date(cls, value: Optional[date]) -> Optional[date]
class EmployeeReadSchema(BaseModel):

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

# employee_link_service.py
## Импорты
- from __future__ import annotations
- import logging
- from dataclasses import dataclass
- from uuid import UUID
- from src.application.interfaces.employee_repository_interface import IEmployeeRepository
- from src.application.interfaces.task_repository_interface import ITaskRepository
## Классы
class EmployeeUsageInfo:
class EmployeeLinkService:
  def __init__(self, employee_repository: IEmployeeRepository, task_repository: ITaskRepository, logger: logging.Logger) -> None
  async def get_usage_info(self, employee_id: UUID) -> EmployeeUsageInfo
  async def get_task_count(self, employee_id: UUID) -> int
  async def remove_from_task(self, employee_id: UUID, task_id: UUID) -> bool
  async def cascade_remove_from_tasks(self, employee_id: UUID) -> int

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

# employee_exceptions.py
## Импорты
- from __future__ import annotations
- from uuid import UUID
## Классы
class EmployeeDomainError(Exception):
class InvalidEmployeeNameError(EmployeeDomainError):
class DuplicateEmployeeError(EmployeeDomainError):
  def __init__(self, duplicate_field: str, duplicate_value: str) -> None
class EmployeeInUseError(EmployeeDomainError):
  def __init__(self, employee_id: UUID, employee_name: str, task_count: int) -> None

# employee_model.py
## Импорты
- from __future__ import annotations
- from datetime import date, datetime
- from typing import List, Optional
- from uuid import UUID, uuid4
- from pydantic import BaseModel, ConfigDict, Field, model_validator
- from src.domain.employees.employee_exceptions import EmployeeDomainError, InvalidEmployeeNameError
## Классы
class Employee(BaseModel):
  @model_validator(mode='after') def _validate_and_build(self) -> 'Employee'
  @staticmethod def _build_basic_display_name(last_name: str, first_name: str, middle_name: Optional[str]) -> str
  def get_full_name(self) -> str
  def toggle_active(self) -> None
  def with_updated_display_name(self, new_display_name: str) -> 'Employee'
  def clone(self) -> 'Employee'

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

# employee_orm_model.py
## Импорты
- from __future__ import annotations
- from datetime import date, datetime
- from typing import Optional
- from uuid import UUID, uuid4
- from sqlalchemy import Boolean, Date, DateTime, Index, String, Text, text
- from sqlalchemy.orm import Mapped, mapped_column
- from src.infrastructure.db.async_database_session import Base
## Классы
class EmployeeORMModel(Base):
  def __repr__(self) -> str

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

# employee_repository.py
## Импорты
- from __future__ import annotations
- import json
- from datetime import datetime
- from typing import List, Optional
- from uuid import UUID
- from sqlalchemy import delete, exists, select
- from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
- from src.application.interfaces.employee_repository_interface import IEmployeeRepository
- from src.domain.employees.employee_model import Employee
- from src.infrastructure.db.models.employee_orm_model import EmployeeORMModel
## Классы
class EmployeeSQLAlchemyRepository(IEmployeeRepository):
  def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None
  @staticmethod def _to_orm(domain: Employee) -> EmployeeORMModel
  @staticmethod def _to_domain(orm: EmployeeORMModel) -> Employee
  async def get_by_id(self, employee_id: UUID) -> Optional[Employee]
  async def get_all(self) -> List[Employee]
  async def get_active_only(self) -> List[Employee]
  async def exists_by_email(self, email: str, exclude_id: Optional[UUID]) -> bool
  async def exists_by_tab_number(self, tab_number: str, exclude_id: Optional[UUID]) -> bool
  async def create(self, employee: Employee) -> Employee
  async def update(self, employee: Employee) -> Employee
  async def delete(self, employee_id: UUID) -> None

# task_repository.py
## Импорты
- from __future__ import annotations
- import json
- from datetime import datetime
- from typing import List, Optional
- from uuid import UUID
- from sqlalchemy import delete, exists, select
- from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
- from src.application.interfaces.task_repository_interface import ITaskRepository
- from src.domain.tasks.planning_task_model import PlanningTask, PeriodType
- from src.infrastructure.db.models.task_orm_model import TaskORMModel
## Классы
class TaskSQLAlchemyRepository(ITaskRepository):
  def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None
  @staticmethod def _to_orm(domain: PlanningTask) -> TaskORMModel
  @staticmethod def _to_domain(orm: TaskORMModel) -> PlanningTask
  @staticmethod def _orm_contains_employee(orm: TaskORMModel, employee_id: UUID) -> bool
  @staticmethod def _remove_employee_from_orm(orm: TaskORMModel, employee_id: UUID) -> bool
  async def get_by_id(self, task_id: UUID) -> Optional[PlanningTask]
  async def get_all(self) -> List[PlanningTask]
  async def exists_by_name(self, name: str, exclude_id: UUID | None) -> bool
  async def create(self, task: PlanningTask) -> PlanningTask
  async def update(self, task: PlanningTask) -> PlanningTask
  async def delete(self, task_id: UUID) -> None
  async def count_tasks_using_employee(self, employee_id: UUID) -> int
  async def remove_employee_from_all_tasks(self, employee_id: UUID) -> int
  async def remove_employee_from_task(self, employee_id: UUID, task_id: UUID) -> bool

# display_name_resolver.py
## Импорты
- from __future__ import annotations
- from collections import Counter, defaultdict
- from dataclasses import dataclass, field
- from typing import Iterable, List
- from src.domain.employees.employee_model import Employee
## Классы
class _ExpansionState:
  def build_name(self) -> str
  def can_expand_first(self) -> bool
  def can_expand_middle(self) -> bool
  def expand(self) -> bool
## Функции
def resolve_display_names(employees: Iterable[Employee]) -> List[Employee]
def _group_by_surname(employees: Iterable[Employee]) -> dict[str, list[Employee]]
def _format_initial(value: str, length: int) -> str
def _expand_conflicts(group: List[Employee]) -> List[Employee]

# employee_controller.py
## Импорты
- from __future__ import annotations
- import logging
- from typing import List, Optional
- from uuid import UUID
- from sqlalchemy.exc import IntegrityError
- from src.application.interfaces.employee_repository_interface import IEmployeeRepository
- from src.application.schemas.employee_schemas import EmployeeCreateSchema, EmployeeReadSchema, EmployeeUpdateSchema
- from src.application.services.employee_link_service import EmployeeLinkService, EmployeeUsageInfo
- from src.core.logging_config import log_user_action, log_user_error
- from src.domain.employees.employee_exceptions import DuplicateEmployeeError, EmployeeDomainError
- from src.domain.employees.employee_model import Employee
- from src.presentation.controllers.display_name_resolver import resolve_display_names
## Классы
class EmployeeController:
  def __init__(self, employee_repository: IEmployeeRepository, link_service: EmployeeLinkService, logger: logging.Logger) -> None
  async def get_all_employees(self) -> List[EmployeeReadSchema]
  async def get_active_employees(self) -> List[EmployeeReadSchema]
  async def get_employee_by_id(self, employee_id: UUID) -> Optional[EmployeeReadSchema]
  async def create_employee(self, schema: EmployeeCreateSchema) -> EmployeeReadSchema
  async def update_employee(self, employee_id: UUID, schema: EmployeeUpdateSchema) -> EmployeeReadSchema
  async def toggle_active(self, employee_id: UUID) -> EmployeeReadSchema
  async def get_usage_info(self, employee_id: UUID) -> EmployeeUsageInfo
  async def delete_employee(self, employee_id: UUID) -> int
  async def remove_from_task(self, employee_id: UUID, task_id: UUID) -> bool
  def _to_read_schema(self, employee: Employee) -> EmployeeReadSchema

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

# employee_dialog.py
## Импорты
- from __future__ import annotations
- import logging
- import re
- from datetime import date
- from tkinter import messagebox
- from typing import Callable, Optional, Union
- from uuid import UUID
- import customtkinter as ctk
- from pydantic import ValidationError
- from src.application.schemas.employee_schemas import EmployeeCreateSchema, EmployeeReadSchema, EmployeeUpdateSchema
- from src.core.logging_config import log_ui_event
## Классы
class EmployeeDialog(ctk.CTkToplevel):
  def __init__(self, master: ctk.CTk, logger: logging.Logger, on_save: Callable[[Optional[UUID], Union[EmployeeCreateSchema, EmployeeUpdateSchema]], None], mode: str, employee: Optional[EmployeeReadSchema], prefill_data: Optional[dict], **kwargs) -> None
  def _setup_window(self) -> None
  def _create_widgets(self) -> None
  def _add_field(self, parent: ctk.CTkFrame, label: str, placeholder: str) -> ctk.CTkEntry
  @staticmethod def _auto_tab(event, current_entry: ctk.CTkEntry, next_entry: ctk.CTkEntry, max_len: int) -> None
  @staticmethod def _pad_date_field(entry: ctk.CTkEntry, expected_len: int) -> None
  def _parse_birth_date(self) -> Optional[date]
  def _apply_mode(self) -> None
  def _on_edit_click(self) -> None
  def _on_primary_click(self) -> None
  def _populate_fields(self) -> None
  def _populate_from_employee(self) -> None
  def _populate_from_prefill(self) -> None
  def _on_save_click(self) -> None
  def _on_cancel(self) -> None

# task_dialog.py
## Импорты
- from __future__ import annotations
- import logging
- from datetime import date
- from tkinter import messagebox
- from typing import Callable, Optional, Union
- import customtkinter as ctk
- from src.application.schemas.task_schemas import TaskCreateSchema, TaskReadSchema, TaskUpdateSchema
- from src.core.logging_config import log_ui_event, log_user_action
- from src.domain.tasks.planning_task_model import PeriodType
## Классы
class TaskDialog(ctk.CTkToplevel):
  def __init__(self, master: ctk.CTk, logger: logging.Logger, on_save: Callable[[Optional, Union[TaskCreateSchema, TaskUpdateSchema]], None], task: Optional[TaskReadSchema], **kwargs) -> None
  def _setup_window(self) -> None
  def _create_widgets(self) -> None
  def _on_add_employees(self) -> None
  def _on_add_engagements(self) -> None
  def _on_cancel(self) -> None
  def _on_save_click(self) -> None

# employee_card_sections.py
## Импорты
- from __future__ import annotations
- from datetime import date
- from typing import Optional, Union
- from uuid import UUID
- import customtkinter as ctk
- from src.application.schemas.employee_schemas import EmployeeReadSchema
- from src.presentation.font_manager import FontManager
## Функции
def _field_row(parent: ctk.CTkFrame, label: str, value: str, editable: bool = False, is_mono: bool = False, fm: Optional[FontManager] = None, field_key: Optional[str] = None, registry: Optional[dict[str, EditableWidget]] = None) -> ctk.CTkEntry | ctk.CTkLabel
def create_header_section(parent: ctk.CTkFrame, employee: EmployeeReadSchema, fm: Optional[FontManager]) -> ctk.CTkFrame
def create_personal_section(parent: ctk.CTkFrame, employee: EmployeeReadSchema, fm: Optional[FontManager], editable: bool = False) -> SectionResult
def create_contact_section(parent: ctk.CTkFrame, employee: EmployeeReadSchema, fm: Optional[FontManager], editable: bool = False) -> SectionResult
def create_work_section(parent: ctk.CTkFrame, employee: EmployeeReadSchema, fm: Optional[FontManager], editable: bool = False) -> SectionResult
def create_engagement_section(parent: ctk.CTkFrame, engagement_ids: list[UUID], fm: Optional[FontManager]) -> ctk.CTkFrame
def create_notes_section(parent: ctk.CTkFrame, notes: Optional[str], fm: Optional[FontManager], editable: bool = False) -> SectionResult
def create_metadata_section(parent: ctk.CTkFrame, employee: EmployeeReadSchema, fm: Optional[FontManager]) -> ctk.CTkFrame

# employee_dialog_coordinator.py
## Импорты
- from __future__ import annotations
- import logging
- from tkinter import messagebox
- from typing import Callable, Optional, Union
- from uuid import UUID
- import customtkinter as ctk
- from src.application.schemas.employee_schemas import EmployeeCreateSchema, EmployeeReadSchema, EmployeeUpdateSchema
- from src.core.logging_config import log_ui_event, log_user_action, log_user_error
- from src.domain.employees.employee_exceptions import DuplicateEmployeeError
- from src.presentation.async_bridge import AsyncBridge
- from src.presentation.controllers.employee_controller import EmployeeController
- from src.presentation.dialogs.employee_dialog import EmployeeDialog
## Классы
class EmployeeDialogCoordinator:
  def __init__(self, master: ctk.CTk, controller: EmployeeController, bridge: AsyncBridge, logger: logging.Logger, on_success: Callable[[], None]) -> None
  def open_create_dialog(self) -> None
  def open_card_dialog(self, employee: EmployeeReadSchema) -> None
  def _dispatch_save(self, employee_id: Optional[UUID], schema: Union[EmployeeCreateSchema, EmployeeUpdateSchema]) -> None
  def _on_card_save(self, employee_id: UUID, schema: EmployeeUpdateSchema) -> None
  def _execute_create(self, schema: EmployeeCreateSchema, attempt: int) -> None
  def _on_create_success(self, employee: EmployeeReadSchema) -> None
  def _on_create_error(self, exc: Exception, schema: EmployeeCreateSchema, attempt: int) -> None
  def _execute_update(self, employee_id: UUID, schema: EmployeeUpdateSchema) -> None
  def _on_update_success(self, employee: EmployeeReadSchema) -> None
  def _on_update_error(self, exc: Exception, employee_id: UUID, schema: EmployeeUpdateSchema) -> None
  def _reopen_dialog_with_prefill(self, employee: Optional[EmployeeReadSchema], prefill_data: dict) -> None

# employee_list_widget.py
## Импорты
- from __future__ import annotations
- import logging
- from tkinter import Menu, messagebox, ttk
- from typing import List, Optional
- from uuid import UUID
- import customtkinter as ctk
- from src.application.schemas.employee_schemas import EmployeeReadSchema
- from src.core.logging_config import log_ui_event, log_user_action, log_user_error
- from src.presentation.async_bridge import AsyncBridge
- from src.presentation.controllers.employee_controller import EmployeeController
- from src.presentation.widgets.employee_dialog_coordinator import EmployeeDialogCoordinator
## Классы
class EmployeeListWidget(ctk.CTkFrame):
  def __init__(self, master: ctk.CTk, controller: EmployeeController, bridge: AsyncBridge, logger: logging.Logger, **kwargs) -> None
  def _create_widgets(self) -> None
  def _configure_treeview_style(self) -> None
  def _on_heading_click(self, column: str) -> None
  def _get_sort_key(self, emp: EmployeeReadSchema) -> tuple
  def _on_tree_right_click(self, event) -> None
  def _move_column(self, from_idx: int, to_idx: int) -> None
  def refresh(self) -> None
  def _populate_table(self, employees: list[EmployeeReadSchema]) -> None
  def _on_refresh_error(self, exc: Exception) -> None
  def _get_selected_employee(self) -> Optional[EmployeeReadSchema]
  def _on_create_click(self) -> None
  def _on_view_click(self) -> None
  def _on_archive_click(self) -> None
  def _on_archive_success(self, updated: EmployeeReadSchema) -> None
  def _on_archive_error(self, exc: Exception) -> None
  def _on_delete_click(self) -> None
  def _confirm_delete(self, employee: EmployeeReadSchema, task_count: int) -> None
  def _on_delete_success(self, deleted_id: UUID, affected_tasks: int) -> None
  def _on_delete_error(self, exc: Exception) -> None
  def _on_refresh_click(self) -> None

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

# main_menu.py
## Импорты
- from __future__ import annotations
- import logging
- from typing import Callable
- import tkinter as tk
## Классы
class MainMenu:
  def __init__(self, root: tk.Misc, logger: logging.Logger, on_exit: Callable[[], None], on_undo: Callable[[], None], on_redo: Callable[[], None], on_refresh: Callable[[], None], on_clear_logs: Callable[[], None], on_settings: Callable[[], None], on_import: Callable[[], None], on_export: Callable[[], None], on_about: Callable[[], None]) -> None
  @property def menu(self) -> tk.Menu
  def _build_menu(self, root: tk.Misc, on_exit: Callable[[], None], on_undo: Callable[[], None], on_redo: Callable[[], None], on_refresh: Callable[[], None], on_clear_logs: Callable[[], None], on_settings: Callable[[], None], on_import: Callable[[], None], on_export: Callable[[], None], on_about: Callable[[], None]) -> tk.Menu
  @staticmethod def _build_file_menu(parent: tk.Menu, on_exit: Callable[[], None]) -> tk.Menu
  @staticmethod def _build_edit_menu(parent: tk.Menu, on_undo: Callable[[], None], on_redo: Callable[[], None]) -> tk.Menu
  @staticmethod def _build_view_menu(parent: tk.Menu, on_refresh: Callable[[], None], on_clear_logs: Callable[[], None]) -> tk.Menu
  @staticmethod def _build_tools_menu(parent: tk.Menu, on_settings: Callable[[], None], on_import: Callable[[], None], on_export: Callable[[], None]) -> tk.Menu
  @staticmethod def _build_help_menu(parent: tk.Menu, on_about: Callable[[], None]) -> tk.Menu

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

# page_factory.py
## Импорты
- from __future__ import annotations
- import logging
- from typing import Optional
- import customtkinter as ctk
- from src.presentation.async_bridge import AsyncBridge
- from src.presentation.controllers.employee_controller import EmployeeController
- from src.presentation.controllers.task_controller import TaskController
- from src.presentation.font_manager import FontManager, get_font_manager
- from src.presentation.widgets.employee_list_widget import EmployeeListWidget
- from src.presentation.widgets.task_list_widget import TaskListWidget
## Классы
class PageFactory:
  def __init__(self, content_card: ctk.CTkFrame, task_controller: TaskController, employee_controller: Optional[EmployeeController], bridge: AsyncBridge, logger: logging.Logger) -> None
  def create_all_pages(self) -> tuple[dict[str, ctk.CTkFrame], Optional[TaskListWidget], Optional[EmployeeListWidget]]
  def _create_tasks_page(self, title_font: ctk.CTkFont, fm: Optional[FontManager]) -> tuple[ctk.CTkFrame, TaskListWidget]
  def _create_employees_page(self, title_font: ctk.CTkFont, fm: Optional[FontManager]) -> tuple[ctk.CTkFrame, Optional[EmployeeListWidget]]
  def _create_employees_page_real(self, title_font: ctk.CTkFont, fm: Optional[FontManager]) -> tuple[ctk.CTkFrame, EmployeeListWidget]
  def _create_stub_page(self, title: str, message: str, title_font: ctk.CTkFont, subtitle_font: ctk.CTkFont, fm: Optional[FontManager]) -> ctk.CTkFrame

# task_list_widget.py
## Импорты
- from __future__ import annotations
- import logging
- from tkinter import messagebox, ttk
- from typing import Optional, Union
- from uuid import UUID
- import customtkinter as ctk
- from src.application.schemas.task_schemas import TaskCreateSchema, TaskReadSchema, TaskUpdateSchema
- from src.core.logging_config import log_ui_event, log_user_action, log_user_error
- from src.domain.tasks.planning_task_model import PERIOD_TYPE_RU
- from src.domain.tasks.task_exceptions import DuplicateTaskNameError
- from src.presentation.async_bridge import AsyncBridge
- from src.presentation.controllers.task_controller import TaskController
- from src.presentation.dialogs.task_dialog import TaskDialog
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
  def _dispatch_save(self, task_id: Optional[UUID], schema: Union[TaskCreateSchema, TaskUpdateSchema]) -> None
  def _execute_create(self, schema: TaskCreateSchema, attempt: int) -> None
  def _on_create_success(self, task: TaskReadSchema) -> None
  def _on_create_error(self, exc: Exception, schema: TaskCreateSchema, attempt: int) -> None
  def _execute_update(self, task_id: UUID, schema: TaskUpdateSchema) -> None
  def _on_update_success(self, task: TaskReadSchema) -> None
  def _on_update_error(self, exc: Exception, task_id: UUID) -> None
  def _reopen_edit_dialog(self, task: Optional[TaskReadSchema]) -> None
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
- import tkinter
- from typing import Any, Callable, Coroutine
- import customtkinter as ctk
## Классы
class AsyncBridge:
  def __init__(self, root: ctk.CTk, logger: logging.Logger) -> None
  def _start_worker(self) -> None
  def _run_loop(self) -> None
  def is_running(self) -> bool
  def shutdown(self) -> None
  async def _shutdown_procedure(self) -> None
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
- from src.core.logging_config import get_ctk_handler, log_ui_event, log_user_action
- from src.presentation.async_bridge import AsyncBridge
- from src.presentation.controllers.employee_controller import EmployeeController
- from src.presentation.controllers.task_controller import TaskController
- from src.presentation.font_manager import FontManager, FontSize, get_font_manager, set_font_manager
- from src.presentation.settings import Settings
- from src.presentation.widgets.employee_list_widget import EmployeeListWidget
- from src.presentation.widgets.log_panel import LogPanel
- from src.presentation.widgets.main_menu import MainMenu
- from src.presentation.widgets.navigation_sidebar import NavigationSidebar
- from src.presentation.widgets.page_factory import PageFactory
- from src.presentation.widgets.task_list_widget import TaskListWidget
- import os
## Классы
class MainWindow(ctk.CTk):
  def __init__(self, task_controller: TaskController, logger: logging.Logger, settings: Optional[Settings], employee_controller: Optional[EmployeeController], **kwargs) -> None
  def _init_font_manager(self) -> FontManager
  def _setup_window(self) -> None
  def _create_menu(self) -> None
  def _create_main_layout(self) -> None
  def _create_log_panel(self) -> None
  def attach_log_handler(self) -> None
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
  def _initial_load(self) -> None
  def _do_initial_load(self) -> None

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

# __init__.py
## Импорты
- import tkinter

# main.py
## Импорты
- from __future__ import annotations
- import asyncio
- import logging
- import sys
- from pathlib import Path
- import customtkinter as ctk
- from src.application.services.employee_link_service import EmployeeLinkService
- from src.core.logging_config import setup_logging, get_logger, attach_gui_handler
- from src.infrastructure.db.async_database_session import init_db, get_session_factory
- from src.infrastructure.repositories.employee_repository import EmployeeSQLAlchemyRepository
- from src.infrastructure.repositories.task_repository import TaskSQLAlchemyRepository
- from src.presentation.controllers.employee_controller import EmployeeController
- from src.presentation.controllers.task_controller import TaskController
- from src.presentation.main_window import MainWindow
- from src.presentation.settings import Settings
- from src.presentation.settings import AppSettings
- import os
## Функции
def main() -> None
def test_gui_update()
