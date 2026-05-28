# src/presentation/controllers/employee_controller.py
"""
Контроллер сотрудников — тонкий фасад для CRUD-операций.

Уровень: Presentation (UI orchestration).
Не содержит бизнес-логики — делегирует операции:
    - IEmployeeRepository — для persistence
    - EmployeeLinkService — для оркестрации связей с задачами
    - resolve_display_names — для разрешения конфликтов однофамильцев

Ответственность:
    - Координация потоков данных между UI и Application/Domain слоями.
    - Валидация входных данных через Pydantic-схемы.
    - Логирование действий пользователя (log_user_action/log_user_error).
    - Преобразование Domain-моделей в ReadSchema для UI.

Границы:
    - НЕ принимает решений о бизнес-правилах — делегирует сервисам.
    - НЕ обращается к БД напрямую — только через репозитории.
    - НЕ взаимодействует с UI-виджетами — возвращает данные и ошибки.
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
    """Фасад для операций над сотрудниками.

    Инкапсулирует все зависимости (репозиторий, link-сервис, логгер)
    и предоставляет унифицированный API для Presentation-слоя.
    """

    def __init__(
        self,
        employee_repository: IEmployeeRepository,
        link_service: EmployeeLinkService,
        logger: logging.Logger,
    ) -> None:
        """Инициализация контроллера.

        Args:
            employee_repository: репозиторий для persistence сотрудников.
            link_service: сервис оркестрации связей сотрудник↔задача.
            logger: логгер для записи действий и ошибок.
        """
        self._repo = employee_repository
        self._link_svc = link_service
        self._log = logger

    # ------------------------------------------------------------------
    # Чтение
    # ------------------------------------------------------------------
    async def get_all_employees(self) -> List[EmployeeReadSchema]:
        """Получить всех сотрудников с разрешёнными конфликтами display_name.

        Применяет `resolve_display_names` для корректного отображения
        однофамильцев в таблицах и графиках.

        Returns:
            Список EmployeeReadSchema с уникальными display_name.

        Raises:
            Exception: пробрасывается после логирования.
        """
        try:
            employees = await self._repo.get_all()
            resolved = resolve_display_names(employees)
            schemas = [self._to_read_schema(emp) for emp in resolved]
            self._log.debug("Retrieved %d employees (all)", len(schemas))
            return schemas

        except Exception:
            self._log.exception("Failed to retrieve all employees")
            raise

    async def get_active_employees(self) -> List[EmployeeReadSchema]:
        """Получить только активных сотрудников (is_active=True).

        Используется для выпадающих списков в диалогах создания задач,
        где архивные сотрудники не должны отображаться.

        Returns:
            Список активных EmployeeReadSchema с разрешёнными конфликтами.

        Raises:
            Exception: пробрасывается после логирования.
        """
        try:
            employees = await self._repo.get_active_only()
            resolved = resolve_display_names(employees)
            schemas = [self._to_read_schema(emp) for emp in resolved]
            self._log.debug("Retrieved %d active employees", len(schemas))
            return schemas

        except Exception:
            self._log.exception("Failed to retrieve active employees")
            raise

    async def get_employee_by_id(
        self, employee_id: UUID
    ) -> Optional[EmployeeReadSchema]:
        """Получить одного сотрудника по ID.

        Args:
            employee_id: UUID сотрудника.

        Returns:
            EmployeeReadSchema или None, если не найден.

        Raises:
            Exception: пробрасывается после логирования.
        """
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
    async def create_employee(
        self, schema: EmployeeCreateSchema
    ) -> EmployeeReadSchema:
        """Создать нового сотрудника.

        Проверяет уникальность email и tab_number через репозиторий.
        При нарушении ограничений выбрасывает DuplicateEmployeeError.

        Args:
            schema: валидированные данные для создания.

        Returns:
            EmployeeReadSchema созданного сотрудника.

        Raises:
            DuplicateEmployeeError: если email или tab_number уже заняты.
            EmployeeDomainError: если нарушены бизнес-правила Domain.
            Exception: пробрасывается после логирования.
        """
        try:
            # Проверка уникальности email
            if schema.email:
                exists = await self._repo.exists_by_email(
                    email=schema.email, exclude_id=None
                )
                if exists:
                    raise DuplicateEmployeeError(
                        duplicate_field="email",
                        duplicate_value=schema.email,
                    )

            # Проверка уникальности tab_number
            if schema.tab_number:
                exists = await self._repo.exists_by_tab_number(
                    tab_number=schema.tab_number, exclude_id=None
                )
                if exists:
                    raise DuplicateEmployeeError(
                        duplicate_field="tab_number",
                        duplicate_value=schema.tab_number,
                    )

            # Создание Domain-модели
            employee = Employee(
                last_name=schema.last_name,
                first_name=schema.first_name,
                middle_name=schema.middle_name,
                position=schema.position,
                rank=schema.rank,
                tab_number=schema.tab_number,
                email=schema.email,
                phone=schema.phone,
                birth_date=schema.birth_date,
                is_active=schema.is_active,
                notes=schema.notes,
                engagement_ids=schema.engagement_ids or [],
            )

            created = await self._repo.create(employee)
            log_user_action(
                self._log,
                action="CREATE_EMPLOYEE",
                details=f"Created employee '{created.display_name}' (ID: {created.id})",
            )
            return self._to_read_schema(created)

        except (DuplicateEmployeeError, EmployeeDomainError):
            # Бизнес-ошибки пробрасываем без дополнительного логирования
            raise

        except IntegrityError as e:
            # Нарушение UNIQUE-ограничений на уровне БД
            self._log.error("Database integrity error during employee creation: %s", e)
            raise DuplicateEmployeeError(
                duplicate_field="unknown",
                duplicate_value="N/A",
            ) from e

        except Exception:
            self._log.exception("Failed to create employee")
            log_user_error(
                self._log,
                action="CREATE_EMPLOYEE",
                error="Unexpected error during employee creation",
            )
            raise

    # ------------------------------------------------------------------
    # Обновление
    # ------------------------------------------------------------------
    async def update_employee(
        self, employee_id: UUID, schema: EmployeeUpdateSchema
    ) -> EmployeeReadSchema:
        """Обновить существующего сотрудника.

        Проверяет уникальность email и tab_number (исключая самого себя).
        Частичное обновление: обновляются только переданные поля.

        Args:
            employee_id: UUID обновляемого сотрудника.
            schema: валидированные данные для обновления.

        Returns:
            EmployeeReadSchema обновлённого сотрудника.

        Raises:
            ValueError: если сотрудник не найден.
            DuplicateEmployeeError: если email или tab_number уже заняты.
            EmployeeDomainError: если нарушены бизнес-правила Domain.
            Exception: пробрасывается после логирования.
        """
        try:
            employee = await self._repo.get_by_id(employee_id)
            if employee is None:
                raise ValueError(f"Employee {employee_id} not found")

            # Проверка уникальности email (исключая самого себя)
            if schema.email is not None and schema.email != employee.email:
                exists = await self._repo.exists_by_email(
                    email=schema.email, exclude_id=employee_id
                )
                if exists:
                    raise DuplicateEmployeeError(
                        duplicate_field="email",
                        duplicate_value=schema.email,
                    )

            # Проверка уникальности tab_number (исключая самого себя)
            if schema.tab_number is not None and schema.tab_number != employee.tab_number:
                exists = await self._repo.exists_by_tab_number(
                    tab_number=schema.tab_number, exclude_id=employee_id
                )
                if exists:
                    raise DuplicateEmployeeError(
                        duplicate_field="tab_number",
                        duplicate_value=schema.tab_number,
                    )

            # Частичное обновление полей
            update_data = schema.model_dump(exclude_unset=True)
            for field_name, value in update_data.items():
                setattr(employee, field_name, value)

            updated = await self._repo.update(employee)
            log_user_action(
                self._log,
                action="UPDATE_EMPLOYEE",
                details=f"Updated employee '{updated.display_name}' (ID: {updated.id})",
            )
            return self._to_read_schema(updated)

        except (ValueError, DuplicateEmployeeError, EmployeeDomainError):
            # Бизнес-ошибки пробрасываем без дополнительного логирования
            raise

        except IntegrityError as e:
            self._log.error("Database integrity error during employee update: %s", e)
            raise DuplicateEmployeeError(
                duplicate_field="unknown",
                duplicate_value="N/A",
            ) from e

        except Exception:
            self._log.exception("Failed to update employee %s", employee_id)
            log_user_error(
                self._log,
                action="UPDATE_EMPLOYEE",
                error=f"Unexpected error during employee update (ID: {employee_id})",
            )
            raise

    # ------------------------------------------------------------------
    # Архивация / Активация
    # ------------------------------------------------------------------
    async def toggle_active(self, employee_id: UUID) -> EmployeeReadSchema:
        """Переключить статус активности сотрудника (архивация/восстановление).

        Args:
            employee_id: UUID сотрудника.

        Returns:
            EmployeeReadSchema с обновлённым статусом.

        Raises:
            ValueError: если сотрудник не найден.
            Exception: пробрасывается после логирования.
        """
        try:
            employee = await self._repo.get_by_id(employee_id)
            if employee is None:
                raise ValueError(f"Employee {employee_id} not found")

            employee.toggle_active()
            updated = await self._repo.update(employee)

            action = "ARCHIVE_EMPLOYEE" if not updated.is_active else "RESTORE_EMPLOYEE"
            log_user_action(
                self._log,
                action=action,
                details=f"Toggled active status for '{updated.display_name}' (ID: {updated.id}), now is_active={updated.is_active}",
            )
            return self._to_read_schema(updated)

        except ValueError:
            raise

        except Exception:
            self._log.exception("Failed to toggle active status for employee %s", employee_id)
            log_user_error(
                self._log,
                action="TOGGLE_ACTIVE",
                error=f"Failed to toggle active status for employee {employee_id}",
            )
            raise

    # ------------------------------------------------------------------
    # Проверка использования (делегирование EmployeeLinkService)
    # ------------------------------------------------------------------
    async def get_usage_info(self, employee_id: UUID) -> EmployeeUsageInfo:
        """Получить информацию об использовании сотрудника в задачах.

        Делегирует EmployeeLinkService для подсчёта задач и проверки
        существования сотрудника.

        Args:
            employee_id: UUID сотрудника.

        Returns:
            EmployeeUsageInfo с количеством задач и флагом существования.

        Raises:
            Exception: пробрасывается после логирования.
        """
        try:
            return await self._link_svc.get_usage_info(employee_id)

        except Exception:
            self._log.exception(
                "Failed to retrieve usage info for employee %s", employee_id
            )
            raise

    # ------------------------------------------------------------------
    # Удаление
    # ------------------------------------------------------------------
    async def delete_employee(self, employee_id: UUID) -> int:
        """Удалить сотрудника с CASCADE-очисткой связей в задачах.

        Сценарий:
            1. Вызвать get_usage_info() для проверки количества задач.
            2. Если task_count > 0 — запросить подтверждение у пользователя.
            3. Вызвать cascade_remove_from_tasks() для очистки связей.
            4. Вызвать repository.delete() для физического удаления.

        Args:
            employee_id: UUID сотрудника.

        Returns:
            Количество задач, из которых был удалён сотрудник (0 если не использовался).

        Raises:
            ValueError: если сотрудник не найден.
            Exception: пробрасывается после логирования.
        """
        try:
            # Проверка существования
            employee = await self._repo.get_by_id(employee_id)
            if employee is None:
                raise ValueError(f"Employee {employee_id} not found")

            display_name = employee.display_name

            # CASCADE-удаление из задач
            affected = await self._link_svc.cascade_remove_from_tasks(employee_id)

            # Физическое удаление из БД
            await self._repo.delete(employee_id)

            log_user_action(
                self._log,
                action="DELETE_EMPLOYEE",
                details=f"Deleted employee '{display_name}' (ID: {employee_id}), detached from {affected} task(s)",
            )
            return affected

        except ValueError:
            raise

        except Exception:
            self._log.exception("Failed to delete employee %s", employee_id)
            log_user_error(
                self._log,
                action="DELETE_EMPLOYEE",
                error=f"Failed to delete employee {employee_id}",
            )
            raise

    # ------------------------------------------------------------------
    # Удаление из конкретной задачи (делегирование EmployeeLinkService)
    # ------------------------------------------------------------------
    async def remove_from_task(self, employee_id: UUID, task_id: UUID) -> bool:
        """Удалить сотрудника из конкретной задачи (точечное удаление).

        Сотрудник остаётся в БД, изменяется только PlanningTask.employee_ids.

        Args:
            employee_id: UUID сотрудника.
            task_id: UUID задачи.

        Returns:
            True — если связь была удалена,
            False — если сотрудник не был привязан к задаче.

        Raises:
            Exception: пробрасывается после логирования.
        """
        try:
            removed = await self._link_svc.remove_from_task(employee_id, task_id)

            if removed:
                log_user_action(
                    self._log,
                    action="REMOVE_EMPLOYEE_FROM_TASK",
                    details=f"Removed employee {employee_id} from task {task_id}",
                )
            return removed

        except Exception:
            self._log.exception(
                "Failed to remove employee %s from task %s", employee_id, task_id
            )
            log_user_error(
                self._log,
                action="REMOVE_FROM_TASK",
                error=f"Failed to remove employee {employee_id} from task {task_id}",
            )
            raise

    # ------------------------------------------------------------------
    # Преобразование Domain → Schema
    # ------------------------------------------------------------------
    def _to_read_schema(self, employee: Employee) -> EmployeeReadSchema:
        """Преобразовать Domain-модель Employee в EmployeeReadSchema.

        Заполняет вычисляемое поле ``full_name`` из Domain-метода
        ``get_full_name()``. Поле ``display_name`` берётся напрямую
        из модели (может быть расширено через resolve_display_names).

        Args:
            employee: Domain-объект.

        Returns:
            Pydantic-схема для передачи в UI.
        """
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
