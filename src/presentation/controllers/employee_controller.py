# src/presentation/controllers/employee_controller.py
"""
Контроллер сотрудников — тонкий фасад для CRUD-операций.

Уровень: Presentation. Делегирует операции в IEmployeeRepository,
EmployeeLinkService и resolve_display_names.
"""
from __future__ import annotations

import logging
from typing import List, Optional
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from src.application.interfaces.employee_repository_interface import IEmployeeRepository
from src.application.schemas.employee_schemas import (
    EmployeeCreateSchema,
    EmployeeReadSchema,
    EmployeeUpdateSchema,
)
from src.application.services.employee_link_service import EmployeeLinkService, EmployeeUsageInfo
from src.core.logging_config import log_user_action, log_user_error
from src.domain.employees.employee_exceptions import DuplicateEmployeeError, EmployeeDomainError
from src.domain.employees.employee_model import Employee
from src.presentation.controllers.display_name_resolver import resolve_display_names


class EmployeeController:
    """Фасад для операций над сотрудниками."""

    def __init__(
        self,
        employee_repository: IEmployeeRepository,
        link_service: EmployeeLinkService,
        logger: logging.Logger,
    ) -> None:
        self._repo = employee_repository
        self._link_svc = link_service
        self._log = logger

    # ------------------------------------------------------------------
    # Чтение
    # ------------------------------------------------------------------
    async def get_all_employees(self) -> List[EmployeeReadSchema]:
        """Все сотрудники с разрешёнными конфликтами display_name."""
        try:
            employees = await self._repo.get_all()
            schemas = [self._to_read_schema(e) for e in resolve_display_names(employees)]
            self._log.debug("Retrieved %d employees (all)", len(schemas))
            return schemas
        except Exception:
            self._log.exception("Failed to retrieve all employees")
            raise

    async def get_active_employees(self) -> List[EmployeeReadSchema]:
        """Только активные сотрудники (для выпадающих списков)."""
        try:
            employees = await self._repo.get_active_only()
            schemas = [self._to_read_schema(e) for e in resolve_display_names(employees)]
            self._log.debug("Retrieved %d active employees", len(schemas))
            return schemas
        except Exception:
            self._log.exception("Failed to retrieve active employees")
            raise

    async def get_employee_by_id(self, employee_id: UUID) -> Optional[EmployeeReadSchema]:
        """Один сотрудник по ID."""
        try:
            employee = await self._repo.get_by_id(employee_id)
            if employee is None:
                self._log.warning("Employee %s not found", employee_id)
                return None
            return self._to_read_schema(employee)
        except Exception:
            self._log.exception("Failed to retrieve employee %s", employee_id)
            raise

    # ------------------------------------------------------------------
    # Создание
    # ------------------------------------------------------------------
    async def create_employee(self, schema: EmployeeCreateSchema) -> EmployeeReadSchema:
        """Создать сотрудника с проверкой уникальности email/tab_number."""
        try:
            if schema.email and await self._repo.exists_by_email(schema.email, None):
                raise DuplicateEmployeeError("email", schema.email)
            if schema.tab_number and await self._repo.exists_by_tab_number(schema.tab_number, None):
                raise DuplicateEmployeeError("tab_number", schema.tab_number)

            employee = Employee(
                last_name=schema.last_name, first_name=schema.first_name,
                middle_name=schema.middle_name, position=schema.position,
                rank=schema.rank, tab_number=schema.tab_number,
                email=schema.email, phone=schema.phone,
                birth_date=schema.birth_date, is_active=schema.is_active,
                notes=schema.notes, engagement_ids=schema.engagement_ids or [],
            )
            created = await self._repo.create(employee)
            log_user_action(self._log, "CREATE_EMPLOYEE",
                            f"Created '{created.display_name}' (ID: {created.id})")
            return self._to_read_schema(created)
        except (DuplicateEmployeeError, EmployeeDomainError):
            raise
        except IntegrityError as e:
            self._log.error("Integrity error during employee creation: %s", e)
            raise DuplicateEmployeeError("unknown", "N/A") from e
        except Exception:
            self._log.exception("Failed to create employee")
            log_user_error(self._log, "CREATE_EMPLOYEE", "Unexpected error")
            raise

    # ------------------------------------------------------------------
    # Обновление
    # ------------------------------------------------------------------
    async def update_employee(
        self, employee_id: UUID, schema: EmployeeUpdateSchema,
    ) -> EmployeeReadSchema:
        """Частичное обновление сотрудника."""
        try:
            employee = await self._repo.get_by_id(employee_id)
            if employee is None:
                raise ValueError(f"Employee {employee_id} not found")

            if schema.email is not None and schema.email != employee.email:
                if await self._repo.exists_by_email(schema.email, employee_id):
                    raise DuplicateEmployeeError("email", schema.email)
            if schema.tab_number is not None and schema.tab_number != employee.tab_number:
                if await self._repo.exists_by_tab_number(schema.tab_number, employee_id):
                    raise DuplicateEmployeeError("tab_number", schema.tab_number)

            for field_name, value in schema.model_dump(exclude_unset=True).items():
                setattr(employee, field_name, value)

            updated = await self._repo.update(employee)
            log_user_action(self._log, "UPDATE_EMPLOYEE",
                            f"Updated '{updated.display_name}' (ID: {updated.id})")
            return self._to_read_schema(updated)
        except (ValueError, DuplicateEmployeeError, EmployeeDomainError):
            raise
        except IntegrityError as e:
            self._log.error("Integrity error during employee update: %s", e)
            raise DuplicateEmployeeError("unknown", "N/A") from e
        except Exception:
            self._log.exception("Failed to update employee %s", employee_id)
            log_user_error(self._log, "UPDATE_EMPLOYEE", f"ID: {employee_id}")
            raise

    # ------------------------------------------------------------------
    # Архивация / Активация
    # ------------------------------------------------------------------
    async def toggle_active(self, employee_id: UUID) -> EmployeeReadSchema:
        """Переключить статус активности (архивация/восстановление)."""
        try:
            employee = await self._repo.get_by_id(employee_id)
            if employee is None:
                raise ValueError(f"Employee {employee_id} not found")
            employee.toggle_active()
            updated = await self._repo.update(employee)
            action = "ARCHIVE_EMPLOYEE" if not updated.is_active else "RESTORE_EMPLOYEE"
            log_user_action(self._log, action,
                            f"'{updated.display_name}' (ID: {updated.id}), active={updated.is_active}")
            return self._to_read_schema(updated)
        except ValueError:
            raise
        except Exception:
            self._log.exception("Failed to toggle active for %s", employee_id)
            log_user_error(self._log, "TOGGLE_ACTIVE", f"ID: {employee_id}")
            raise

    # ------------------------------------------------------------------
    # Использование и связи
    # ------------------------------------------------------------------
    async def get_usage_info(self, employee_id: UUID) -> EmployeeUsageInfo:
        """Информация об использовании сотрудника в задачах."""
        try:
            return await self._link_svc.get_usage_info(employee_id)
        except Exception:
            self._log.exception("Failed to retrieve usage info for %s", employee_id)
            raise

    async def remove_from_task(self, employee_id: UUID, task_id: UUID) -> bool:
        """Точечное удаление сотрудника из задачи."""
        try:
            removed = await self._link_svc.remove_from_task(employee_id, task_id)
            if removed:
                log_user_action(self._log, "REMOVE_EMPLOYEE_FROM_TASK",
                                f"Employee {employee_id} from task {task_id}")
            return removed
        except Exception:
            self._log.exception("Failed to remove %s from task %s", employee_id, task_id)
            log_user_error(self._log, "REMOVE_FROM_TASK", f"emp={employee_id}, task={task_id}")
            raise

    # ------------------------------------------------------------------
    # Управление шаблонами задействований
    # ------------------------------------------------------------------
    async def add_engagement_template(
        self, employee_id: UUID, template_id: UUID,
    ) -> bool:
        """Добавить шаблон задействования сотруднику.

        Returns:
            True — если шаблон был добавлен, False — если уже был.
        """
        try:
            added = await self._repo.add_engagement_template(employee_id, template_id)
            if added:
                log_user_action(self._log, "ADD_ENGAGEMENT_TO_EMPLOYEE",
                                f"Template {template_id} → Employee {employee_id}")
            return added
        except Exception:
            self._log.exception("Failed to add engagement template to employee %s", employee_id)
            log_user_error(self._log, "ADD_ENGAGEMENT", f"emp={employee_id}, tpl={template_id}")
            raise

    async def remove_engagement_template(
        self, employee_id: UUID, template_id: UUID,
    ) -> bool:
        """Удалить шаблон задействования у сотрудника.

        Returns:
            True — если шаблон был удалён, False — если его не было.
        """
        try:
            removed = await self._repo.remove_engagement_template(employee_id, template_id)
            if removed:
                log_user_action(self._log, "REMOVE_ENGAGEMENT_FROM_EMPLOYEE",
                                f"Template {template_id} ← Employee {employee_id}")
            return removed
        except Exception:
            self._log.exception("Failed to remove engagement template from employee %s", employee_id)
            log_user_error(self._log, "REMOVE_ENGAGEMENT", f"emp={employee_id}, tpl={template_id}")
            raise

    # ------------------------------------------------------------------
    # Удаление
    # ------------------------------------------------------------------
    async def delete_employee(self, employee_id: UUID) -> int:
        """Удалить сотрудника с CASCADE-очисткой связей в задачах."""
        try:
            employee = await self._repo.get_by_id(employee_id)
            if employee is None:
                raise ValueError(f"Employee {employee_id} not found")
            affected = await self._link_svc.cascade_remove_from_tasks(employee_id)
            await self._repo.delete(employee_id)
            log_user_action(self._log, "DELETE_EMPLOYEE",
                            f"Deleted '{employee.display_name}' (ID: {employee_id}), "
                            f"detached from {affected} task(s)")
            return affected
        except ValueError:
            raise
        except Exception:
            self._log.exception("Failed to delete employee %s", employee_id)
            log_user_error(self._log, "DELETE_EMPLOYEE", f"ID: {employee_id}")
            raise

    # ------------------------------------------------------------------
    # Преобразование Domain → Schema
    # ------------------------------------------------------------------
    def _to_read_schema(self, employee: Employee) -> EmployeeReadSchema:
        """Domain-модель → EmployeeReadSchema."""
        return EmployeeReadSchema(
            id=employee.id,
            last_name=employee.last_name,
            first_name=employee.first_name,
            middle_name=employee.middle_name,
            display_name=employee.display_name,
            full_name=employee.get_full_name(),
            position=employee.position,
            rank=employee.rank,
            tab_number=employee.tab_number,
            email=employee.email,
            phone=employee.phone,
            birth_date=employee.birth_date,
            is_active=employee.is_active,
            notes=employee.notes,
            engagement_ids=employee.engagement_ids,
            created_at=employee.created_at,
            updated_at=employee.updated_at,
        )
