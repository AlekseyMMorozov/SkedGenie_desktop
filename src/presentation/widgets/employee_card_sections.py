# src/presentation/widgets/employee_card_sections.py
"""
Фабрики секций карточки сотрудника.

Чистые функции для создания UI-секций с параметром `editable`:
    - editable=False → Label (read-only)
    - editable=True → Entry/Textbox (редактируемые поля)

Ответственность:
    - Построение отдельных секций карточки (заголовок, персональные данные, контакты и т.д.).
    - Единообразное форматирование "Label: Value" через _field_row.
    - Поддержка двух режимов: просмотр и редактирование.
    - Регистрация редактируемых виджетов в общем реестре (для сбора данных в диалоге).

Границы:
    - НЕ управляет диалогом — только создаёт секции.
    - НЕ валидирует данные — делегирует Pydantic-схемам.
    - НЕ сохраняет изменения — делегирует контроллеру через callback.

Возвращаемые значения:
    Каждая фабрика возвращает кортеж:
        (section_frame, editable_widgets_dict)

    editable_widgets_dict — словарь {field_key: CTkEntry | CTkTextbox},
    содержащий только редактируемые виджеты данной секции. В режиме
    read-only словарь пустой.

Использование:
    section, widgets = create_personal_section(parent, employee, fm, editable=True)
    # widgets = {"birth_date": <CTkEntry>}
"""
from __future__ import annotations

from datetime import date
from typing import Optional, Union
from uuid import UUID

import customtkinter as ctk

from src.application.schemas.employee_schemas import EmployeeReadSchema
from src.presentation.font_manager import FontManager

# Тип виджета, который может быть редактируемым
EditableWidget = Union[ctk.CTkEntry, ctk.CTkTextbox]

# Тип возвращаемого значения фабрик секций
SectionResult = tuple[ctk.CTkFrame, dict[str, EditableWidget]]


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------
def _field_row(
    parent: ctk.CTkFrame,
    label: str,
    value: str,
    *,
    editable: bool = False,
    is_mono: bool = False,
    fm: Optional[FontManager] = None,
    field_key: Optional[str] = None,
    registry: Optional[dict[str, EditableWidget]] = None,
) -> ctk.CTkEntry | ctk.CTkLabel:
    """Создать строку "Label: Value" или "Label: [Entry]".

    Args:
        parent: Родительский фрейм.
        label: Текст метки.
        value: Значение для отображения.
        editable: Если True — создаёт CTkEntry, иначе CTkLabel.
        is_mono: Использовать моноширинный шрифт (для таб.номера, email).
        fm: FontManager для применения стилей.
        field_key: Ключ для регистрации в реестре редактируемых виджетов.
        registry: Словарь-реестр, куда будет добавлен созданный виджет.

    Returns:
        Созданный виджет (CTkEntry или CTkLabel).
    """
    row_frame = ctk.CTkFrame(parent, fg_color="transparent")
    row_frame.pack(fill="x", pady=(0, 8))

    label_font = fm.get_font("body_bold") if fm else ctk.CTkFont(weight="bold")
    label_widget = ctk.CTkLabel(
        row_frame,
        text=f"{label}:",
        font=label_font,
        anchor="w",
        width=150,
    )
    label_widget.pack(side="left")

    if editable:
        entry = ctk.CTkEntry(row_frame)
        entry.insert(0, value)
        entry.pack(side="left", fill="x", expand=True)

        # Регистрация в реестре
        if registry is not None and field_key is not None:
            registry[field_key] = entry

        return entry
    else:
        value_font = None
        if is_mono and fm:
            value_font = ctk.CTkFont(family="Consolas", size=fm.get_base_size().value)
        elif is_mono:
            value_font = ctk.CTkFont(family="Consolas", size=14)

        value_widget = ctk.CTkLabel(
            row_frame,
            text=value or "—",
            font=value_font,
            anchor="w",
        )
        value_widget.pack(side="left", fill="x", expand=True)
        return value_widget


# ---------------------------------------------------------------------------
# Секция: Заголовок (ФИО + статус)
# ---------------------------------------------------------------------------
def create_header_section(
    parent: ctk.CTkFrame,
    employee: EmployeeReadSchema,
    fm: Optional[FontManager],
) -> ctk.CTkFrame:
    """Создать заголовок карточки с полным ФИО и статусом (всегда read-only)."""
    section = ctk.CTkFrame(parent, fg_color="transparent")
    section.pack(fill="x", pady=(0, 20))

    title_font = fm.get_font("title") if fm else ctk.CTkFont(size=20, weight="bold")
    full_name = employee.get_full_name()

    name_label = ctk.CTkLabel(
        section,
        text=full_name,
        font=title_font,
        anchor="w",
    )
    name_label.pack(fill="x")

    status_text = "Активен" if employee.is_active else "В архиве"
    status_color = "green" if employee.is_active else "gray"

    status_frame = ctk.CTkFrame(section, fg_color="transparent")
    status_frame.pack(fill="x", pady=(5, 0))

    status_label = ctk.CTkLabel(
        status_frame,
        text=f"Статус: {status_text}",
        text_color=status_color,
        anchor="w",
    )
    status_label.pack(side="left")

    if employee.display_name and employee.display_name != full_name:
        display_label = ctk.CTkLabel(
            status_frame,
            text=f"Короткое имя: {employee.display_name}",
            text_color="gray",
            anchor="e",
        )
        display_label.pack(side="right")

    return section


# ---------------------------------------------------------------------------
# Секция: Персональные данные
# ---------------------------------------------------------------------------
def create_personal_section(
    parent: ctk.CTkFrame,
    employee: EmployeeReadSchema,
    fm: Optional[FontManager],
    *,
    editable: bool = False,
) -> SectionResult:
    """Создать секцию персональных данных (дата рождения)."""
    section = ctk.CTkFrame(parent)
    section.pack(fill="x", pady=(0, 15))

    section_title_font = fm.get_font("subtitle") if fm else ctk.CTkFont(size=16, weight="bold")
    section_title = ctk.CTkLabel(
        section,
        text="Персональные данные",
        font=section_title_font,
        anchor="w",
    )
    section_title.pack(fill="x", padx=10, pady=(10, 5))

    content_frame = ctk.CTkFrame(section, fg_color="transparent")
    content_frame.pack(fill="x", padx=10, pady=(0, 10))

    widgets: dict[str, EditableWidget] = {}
    birth_date_str = employee.birth_date.isoformat() if employee.birth_date else ""
    _field_row(
        content_frame,
        "Дата рождения",
        birth_date_str,
        editable=editable,
        fm=fm,
        field_key="birth_date",
        registry=widgets,
    )

    return section, widgets


# ---------------------------------------------------------------------------
# Секция: Контакты
# ---------------------------------------------------------------------------
def create_contact_section(
    parent: ctk.CTkFrame,
    employee: EmployeeReadSchema,
    fm: Optional[FontManager],
    *,
    editable: bool = False,
) -> SectionResult:
    """Создать секцию контактных данных (email, телефон)."""
    section = ctk.CTkFrame(parent)
    section.pack(fill="x", pady=(0, 15))

    section_title_font = fm.get_font("subtitle") if fm else ctk.CTkFont(size=16, weight="bold")
    section_title = ctk.CTkLabel(
        section,
        text="Контактные данные",
        font=section_title_font,
        anchor="w",
    )
    section_title.pack(fill="x", padx=10, pady=(10, 5))

    content_frame = ctk.CTkFrame(section, fg_color="transparent")
    content_frame.pack(fill="x", padx=10, pady=(0, 10))

    widgets: dict[str, EditableWidget] = {}
    _field_row(
        content_frame,
        "Email",
        employee.email or "",
        editable=editable,
        is_mono=True,
        fm=fm,
        field_key="email",
        registry=widgets,
    )
    _field_row(
        content_frame,
        "Телефон",
        employee.phone or "",
        editable=editable,
        is_mono=True,
        fm=fm,
        field_key="phone",
        registry=widgets,
    )

    return section, widgets


# ---------------------------------------------------------------------------
# Секция: Работа
# ---------------------------------------------------------------------------
def create_work_section(
    parent: ctk.CTkFrame,
    employee: EmployeeReadSchema,
    fm: Optional[FontManager],
    *,
    editable: bool = False,
) -> SectionResult:
    """Создать секцию рабочих данных (должность, табельный номер)."""
    section = ctk.CTkFrame(parent)
    section.pack(fill="x", pady=(0, 15))

    section_title_font = fm.get_font("subtitle") if fm else ctk.CTkFont(size=16, weight="bold")
    section_title = ctk.CTkLabel(
        section,
        text="Рабочие данные",
        font=section_title_font,
        anchor="w",
    )
    section_title.pack(fill="x", padx=10, pady=(10, 5))

    content_frame = ctk.CTkFrame(section, fg_color="transparent")
    content_frame.pack(fill="x", padx=10, pady=(0, 10))

    widgets: dict[str, EditableWidget] = {}
    _field_row(
        content_frame,
        "Должность",
        employee.position or "",
        editable=editable,
        fm=fm,
        field_key="position",
        registry=widgets,
    )
    _field_row(
        content_frame,
        "Табельный номер",
        employee.tab_number or "",
        editable=editable,
        is_mono=True,
        fm=fm,
        field_key="tab_number",
        registry=widgets,
    )

    return section, widgets


# ---------------------------------------------------------------------------
# Секция: Допуски к задействованиям
# ---------------------------------------------------------------------------
def create_engagement_section(
    parent: ctk.CTkFrame,
    engagement_ids: list[UUID],
    fm: Optional[FontManager],
) -> ctk.CTkFrame:
    """Создать секцию допусков к задействованиям (всегда read-only)."""
    section = ctk.CTkFrame(parent)
    section.pack(fill="x", pady=(0, 15))

    section_title_font = fm.get_font("subtitle") if fm else ctk.CTkFont(size=16, weight="bold")
    section_title = ctk.CTkLabel(
        section,
        text="Допуски к задействованиям",
        font=section_title_font,
        anchor="w",
    )
    section_title.pack(fill="x", padx=10, pady=(10, 5))

    content_frame = ctk.CTkFrame(section, fg_color="transparent")
    content_frame.pack(fill="x", padx=10, pady=(0, 10))

    if not engagement_ids:
        empty_label = ctk.CTkLabel(
            content_frame,
            text="Допуски не назначены",
            text_color="gray",
            anchor="w",
        )
        empty_label.pack(fill="x")
    else:
        # Заглушка: показываем UUID (позже — названия Engagement)
        for eng_id in engagement_ids:
            eng_label = ctk.CTkLabel(
                content_frame,
                text=f"• {eng_id}",
                anchor="w",
            )
            eng_label.pack(fill="x", pady=(0, 3))

    return section


# ---------------------------------------------------------------------------
# Секция: Заметки
# ---------------------------------------------------------------------------
def create_notes_section(
    parent: ctk.CTkFrame,
    notes: Optional[str],
    fm: Optional[FontManager],
    *,
    editable: bool = False,
) -> SectionResult:
    """Создать секцию заметок."""
    section = ctk.CTkFrame(parent)
    section.pack(fill="x", pady=(0, 15))

    section_title_font = fm.get_font("subtitle") if fm else ctk.CTkFont(size=16, weight="bold")
    section_title = ctk.CTkLabel(
        section,
        text="Заметки",
        font=section_title_font,
        anchor="w",
    )
    section_title.pack(fill="x", padx=10, pady=(10, 5))

    content_frame = ctk.CTkFrame(section, fg_color="transparent")
    content_frame.pack(fill="x", padx=10, pady=(0, 10))

    widgets: dict[str, EditableWidget] = {}

    if editable:
        textbox = ctk.CTkTextbox(content_frame, height=100)
        textbox.insert("1.0", notes or "")
        textbox.pack(fill="x")
        widgets["notes"] = textbox
    else:
        if notes:
            notes_label = ctk.CTkLabel(
                content_frame,
                text=notes,
                anchor="w",
                justify="left",
                wraplength=500,
            )
            notes_label.pack(fill="x")
        else:
            empty_label = ctk.CTkLabel(
                content_frame,
                text="Заметки отсутствуют",
                text_color="gray",
                anchor="w",
            )
            empty_label.pack(fill="x")

    return section, widgets


# ---------------------------------------------------------------------------
# Секция: Метаданные
# ---------------------------------------------------------------------------
def create_metadata_section(
    parent: ctk.CTkFrame,
    employee: EmployeeReadSchema,
    fm: Optional[FontManager],
) -> ctk.CTkFrame:
    """Создать секцию метаданных (created_at, updated_at) — всегда read-only."""
    section = ctk.CTkFrame(parent)
    section.pack(fill="x", pady=(0, 15))

    section_title_font = fm.get_font("subtitle") if fm else ctk.CTkFont(size=16, weight="bold")
    section_title = ctk.CTkLabel(
        section,
        text="Метаданные",
        font=section_title_font,
        anchor="w",
    )
    section_title.pack(fill="x", padx=10, pady=(10, 5))

    content_frame = ctk.CTkFrame(section, fg_color="transparent")
    content_frame.pack(fill="x", padx=10, pady=(0, 10))

    created_str = employee.created_at.strftime("%Y-%m-%d %H:%M:%S") if employee.created_at else ""
    _field_row(
        content_frame,
        "Создан",
        created_str,
        editable=False,
        is_mono=True,
        fm=fm,
    )

    if employee.updated_at:
        updated_str = employee.updated_at.strftime("%Y-%m-%d %H:%M:%S")
        _field_row(
            content_frame,
            "Обновлён",
            updated_str,
            editable=False,
            is_mono=True,
            fm=fm,
        )

    return section
