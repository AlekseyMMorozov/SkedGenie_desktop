# src/presentation/controllers/display_name_resolver.py
"""
Разрешение конфликтов однофамильцев для короткого имени (display_name).

Чистая функция уровня Presentation/Application:
    - Не обращается к БД и репозиториям.
    - Зависит только от Domain-модели Employee.
    - Не мутирует входные объекты (используется Employee.with_updated_display_name).

Алгоритм:
    1. Группируем сотрудников по фамилии (регистронезависимо).
    2. В группах из 2+ человек ищем совпадения базовых display_name.
    3. Для конфликтующих итеративно расширяем инициал имени
       ("И." → "Ив." → "Ива." → "Иван.").
    4. Если имя исчерпано (тёзки) — расширяем инициал отчества.
    5. Если и отчество исчерпано — оставляем как есть (крайний случай).
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Iterable, List

from src.domain.employees.employee_model import Employee


# ---------------------------------------------------------------------------
# Публичный API
# ---------------------------------------------------------------------------
def resolve_display_names(employees: Iterable[Employee]) -> List[Employee]:
    """Вернуть список сотрудников с разрешёнными конфликтами display_name.

    Для единственного сотрудника (или пустого списка) возвращается копия
    без изменений. Для однофамильцев с одинаковым базовым display_name
    инициалы расширяются до различимого состояния.

    Args:
        employees: итерируемый контейнер Domain-объектов Employee.

    Returns:
        Новый список Employee с обновлёнными display_name.
        Исходные объекты не изменяются.
    """
    items: List[Employee] = list(employees)
    if len(items) <= 1:
        return items

    groups = _group_by_surname(items)
    result: List[Employee] = []
    for group in groups.values():
        if len(group) == 1:
            result.append(group[0])
        else:
            result.extend(_expand_conflicts(group))
    return result


# ---------------------------------------------------------------------------
# Внутренние хелперы
# ---------------------------------------------------------------------------
def _group_by_surname(employees: Iterable[Employee]) -> dict[str, list[Employee]]:
    """Сгруппировать сотрудников по нижнему регистру фамилии.

    Порядок вставки сохраняется (Python 3.7+ dict). Пустая фамилия
    попадает под ключ "" — такой случай не должен возникать из-за
    валидации Domain, но обрабатывается корректно.
    """
    groups: dict[str, list[Employee]] = defaultdict(list)
    for emp in employees:
        key = (emp.last_name or "").strip().lower()
        groups[key].append(emp)
    return dict(groups)


@dataclass
class _ExpansionState:
    """Мутабельное состояние расширения инициалов для одного сотрудника."""

    employee: Employee
    first_len: int = 1   # текущая длина используемой части имени
    middle_len: int = 1  # текущая длина используемой части отчества

    def build_name(self) -> str:
        """Собрать display_name с учётом текущих длин инициалов."""
        last = (self.employee.last_name or "").strip()
        first = (self.employee.first_name or "").strip()
        middle = (self.employee.middle_name or "").strip()

        first_part = _format_initial(first, self.first_len)
        if middle:
            middle_part = _format_initial(middle, self.middle_len)
            return f"{last} {first_part} {middle_part}".strip()
        return f"{last} {first_part}".strip()

    def can_expand_first(self) -> bool:
        first = self.employee.first_name or ""
        return self.first_len < len(first)

    def can_expand_middle(self) -> bool:
        middle = self.employee.middle_name or ""
        return bool(middle) and self.middle_len < len(middle)

    def expand(self) -> bool:
        """Увеличить детализацию. Возвращает True, если расширение произошло."""
        if self.can_expand_first():
            self.first_len += 1
            return True
        if self.can_expand_middle():
            self.middle_len += 1
            return True
        return False


def _format_initial(value: str, length: int) -> str:
    """Отрезать `length` символов и добавить точку, если взята не вся строка."""
    if not value:
        return ""
    length = max(1, min(length, len(value)))
    part = value[:length]
    return f"{part}." if length < len(value) else part


def _expand_conflicts(group: List[Employee]) -> List[Employee]:
    """Разрешить конфликты display_name внутри группы однофамильцев.

    Итеративно расширяет инициалы конфликтующих сотрудников, пока
    все display_name не станут уникальными либо пока есть что расширять.
    """
    states: List[_ExpansionState] = [_ExpansionState(employee=emp) for emp in group]
    max_iterations = 32  # защита от бесконечного цикла (длина ФИО заведомо меньше)

    for _ in range(max_iterations):
        names = [s.build_name() for s in states]
        counts = Counter(names)

        # Все имена уникальны — выходим.
        if all(counts[n] == 1 for n in names):
            break

        progressed = False
        for state, name in zip(states, names):
            if counts[name] > 1 and state.expand():
                progressed = True

        # Никого расширить не удалось — выходим, чтобы не зациклиться.
        if not progressed:
            break

    return [
        state.employee.with_updated_display_name(state.build_name())
        for state in states
    ]
