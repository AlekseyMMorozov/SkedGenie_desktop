# src/application/services/employee_link_service.py
"""
Сервис оркестрации связей «сотрудник ↔ задача».

Уровень: Application (Use-case orchestration).
Не содержит бизнес-правил Domain и не обращается к БД напрямую —
делегирует операции репозиториям через их интерфейсы.

Ответственность:
    - Подсчёт задач, в которых задействован сотрудник.
    - Точечное удаление сотрудника из одной конкретной задачи
      (сценарий: меню «График» → «Удалить сотрудника из задачи»).
    - CASCADE-удаление сотрудника из всех задач
      (сценарий: меню «Сотрудники» → «Удалить» с подтверждением).

Границы:
    - НЕ принимает решений о том, удалять ли сотрудника из БД —
      это ответственность EmployeeController.
    - НЕ валидирует Domain-модели — это ответственность Pydantic-схем.
    - НЕ взаимодействует с UI — только возвращает результаты.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from src.application.interfaces.employee_repository_interface import IEmployeeRepository
from src.application.interfaces.task_repository_interface import ITaskRepository


@dataclass(frozen=True, slots=True)
class EmployeeUsageInfo:
    """Информация об использовании сотрудника в задачах.

    Используется EmployeeController для принятия решения о сценарии удаления:
        - task_count == 0  → физическое удаление без предупреждений.
        - task_count > 0   → запрос CASCADE-подтверждения у пользователя.

    Attributes:
        employee_id: UUID сотрудника.
        task_count:  количество задач, ссылающихся на сотрудника.
        exists:      существует ли сотрудник в БД.
    """

    employee_id: UUID
    task_count: int
    exists: bool


class EmployeeLinkService:
    """Оркестратор связей между сотрудниками и задачами.

    Инкапсулирует все операции, затрагивающие обе агрегатные сущности,
    обеспечивая единый контракт для Presentation-слоя и гарантируя,
    что логика «сотрудник используется в N задачах» не расползается
    по контроллерам и диалогам.
    """

    def __init__(
        self,
        employee_repository: IEmployeeRepository,
        task_repository: ITaskRepository,
        logger: logging.Logger,
    ) -> None:
        self._emp_repo = employee_repository
        self._task_repo = task_repository
        self._log = logger

    # ------------------------------------------------------------------
    # Чтение
    # ------------------------------------------------------------------
    async def get_usage_info(self, employee_id: UUID) -> EmployeeUsageInfo:
        """Получить сводку об использовании сотрудника в задачах.

        Выполняет две независимые проверки: существование сотрудника
        и количество ссылающихся на него задач. Результат упаковывается
        в неизменяемый dataclass для удобной передачи в UI-слой.

        Args:
            employee_id: идентификатор сотрудника.

        Returns:
            EmployeeUsageInfo с актуальными счётчиками.

        Raises:
            Exception: пробрасывается дальше после логирования —
                       контроллер решает, как реагировать.
        """
        try:
            employee = await self._emp_repo.get_by_id(employee_id)
            task_count = await self._task_repo.count_tasks_using_employee(employee_id)

            info = EmployeeUsageInfo(
                employee_id=employee_id,
                task_count=task_count,
                exists=employee is not None,
            )
            self._log.debug(
                "Usage info for employee %s: exists=%s, task_count=%d",
                employee_id, info.exists, info.task_count,
            )
            return info

        except Exception:
            self._log.exception(
                "Failed to retrieve usage info for employee %s", employee_id,
            )
            raise

    async def get_task_count(self, employee_id: UUID) -> int:
        """Короткая форма: только количество задач.

        Удобно для проверок в условиях (`if await svc.get_task_count(...) > 0`).
        """
        info = await self.get_usage_info(employee_id)
        return info.task_count

    # ------------------------------------------------------------------
    # Точечное удаление (из одной задачи)
    # ------------------------------------------------------------------
    async def remove_from_task(self, employee_id: UUID, task_id: UUID) -> bool:
        """Удалить сотрудника из конкретной задачи.

        Сценарии использования:
            - Меню «График» → «Удалить сотрудника».
            - Меню «Задачи» → «Удалить из задачи».

        Сотрудник остаётся в БД, изменяется только поле
        `PlanningTask.employee_ids` в целевой задаче.

        Args:
            employee_id: UUID сотрудника.
            task_id:     UUID задачи.

        Returns:
            True — если связь была удалена,
            False — если сотрудник не был привязан к задаче.

        Raises:
            Exception: пробрасывается после логирования.
        """
        try:
            removed = await self._task_repo.remove_employee_from_task(
                employee_id=employee_id,
                task_id=task_id,
            )
            if removed:
                self._log.info(
                    "Employee %s removed from task %s (point removal)",
                    employee_id, task_id,
                )
            else:
                self._log.warning(
                    "Attempted to remove employee %s from task %s, "
                    "but no link existed",
                    employee_id, task_id,
                )
            return removed

        except Exception:
            self._log.exception(
                "Failed to remove employee %s from task %s",
                employee_id, task_id,
            )
            raise

    # ------------------------------------------------------------------
    # CASCADE-удаление (из всех задач)
    # ------------------------------------------------------------------
    async def cascade_remove_from_tasks(self, employee_id: UUID) -> int:
        """Удалить сотрудника из всех задач, где он задействован.

        Сценарий:
            Меню «Сотрудники» → «Удалить» → подтверждение CASCADE.

        Операция идемпотентна: повторный вызов для уже «отвязанного»
        сотрудника вернёт 0 и не сломает систему.

        Args:
            employee_id: UUID сотрудника.

        Returns:
            Количество задач, из которых был удалён сотрудник.

        Raises:
            Exception: пробрасывается после логирования.
        """
        try:
            affected = await self._task_repo.remove_employee_from_all_tasks(
                employee_id=employee_id,
            )
            if affected > 0:
                self._log.info(
                    "CASCADE removal: employee %s detached from %d task(s)",
                    employee_id, affected,
                )
            else:
                self._log.debug(
                    "CASCADE removal: employee %s was not linked to any task",
                    employee_id,
                )
            return affected

        except Exception:
            self._log.exception(
                "CASCADE removal failed for employee %s", employee_id,
            )
            raise
