# src/presentation/widgets/page_factory.py
"""Фабрика создания страниц приложения."""
from __future__ import annotations

import logging
from typing import Optional

import customtkinter as ctk

from src.application.services.engagement_color_service import EngagementColorService
from src.presentation.async_bridge import AsyncBridge
from src.presentation.controllers.employee_controller import EmployeeController
from src.presentation.controllers.task_controller import TaskController
from src.presentation.controllers.engagement_type_controller import EngagementTypeController
from src.presentation.controllers.engagement_template_controller import EngagementTemplateController
from src.presentation.font_manager import FontManager, get_font_manager
from src.presentation.widgets.employee_list_widget import EmployeeListWidget
from src.presentation.widgets.task_list_widget import TaskListWidget
from src.presentation.widgets.engagement_management_widget import EngagementManagementWidget


class PageFactory:
    """Создает страницы для основного окна."""

    # ✅ Константы разделов для идентификации страниц
    SECTION_TASKS: str = "tasks"
    SECTION_GRAPHS: str = "graphs"
    SECTION_EMPLOYEES: str = "employees"
    SECTION_ENGAGEMENTS: str = "engagements"
    SECTION_SETTINGS: str = "settings"

    def __init__(
            self,
            content_card: ctk.CTkFrame,
            task_controller: TaskController,
            employee_controller: Optional[EmployeeController],
            engagement_type_controller: Optional[EngagementTypeController],
            engagement_template_controller: Optional[EngagementTemplateController],
            bridge: AsyncBridge,
            logger: logging.Logger,
            color_service: EngagementColorService,
    ) -> None:
        self._content_card = content_card
        self._task_controller = task_controller
        self._employee_controller = employee_controller
        self._engagement_type_controller = engagement_type_controller
        self._engagement_template_controller = engagement_template_controller
        self._bridge = bridge
        self._logger = logger
        self._color_service = color_service

    def create_all_pages(self) -> tuple[
        dict[str, ctk.CTkFrame], Optional[TaskListWidget], Optional[EmployeeListWidget]]:
        fm = get_font_manager()
        pages: dict[str, ctk.CTkFrame] = {}
        task_widget = None
        employee_widget = None

        # Страница задач
        tasks_page, task_widget = self._create_tasks_page(
            fm.get_font("page_title") if fm else ctk.CTkFont(size=24, weight="bold"), fm
        )
        pages[self.SECTION_TASKS] = tasks_page

        # Страница сотрудников
        employees_page, employee_widget = self._create_employees_page(
            fm.get_font("page_title") if fm else ctk.CTkFont(size=24, weight="bold"), fm
        )
        if employees_page:
            pages[self.SECTION_EMPLOYEES] = employees_page

        # Страница задействований
        engagements_page = self._create_engagements_page(
            fm.get_font("page_title") if fm else ctk.CTkFont(size=24, weight="bold"), fm
        )
        pages[self.SECTION_ENGAGEMENTS] = engagements_page

        # Заглушка для графиков (пока не реализовано)
        graphs_page = self._create_stub_page(
            "Графики", "Раздел в разработке",
            fm.get_font("page_title") if fm else ctk.CTkFont(size=24, weight="bold"),
            fm.get_font("subtitle") if fm else ctk.CTkFont(size=16),
            fm
        )
        pages[self.SECTION_GRAPHS] = graphs_page

        # Заглушка для настроек
        settings_page = self._create_stub_page(
            "Настройки", "Раздел в разработке",
            fm.get_font("page_title") if fm else ctk.CTkFont(size=24, weight="bold"),
            fm.get_font("subtitle") if fm else ctk.CTkFont(size=16),
            fm
        )
        pages[self.SECTION_SETTINGS] = settings_page

        return pages, task_widget, employee_widget

    def _create_tasks_page(self, title_font: ctk.CTkFont, fm: Optional[FontManager]) -> tuple[
        ctk.CTkFrame, TaskListWidget]:
        page = ctk.CTkFrame(self._content_card, fg_color="transparent")

        header = ctk.CTkLabel(page, text="Планирование задач", font=title_font, anchor="w")
        header.pack(fill="x", padx=20, pady=(20, 10))

        widget = TaskListWidget(
            master=page,
            controller=self._task_controller,
            bridge=self._bridge,
            logger=self._logger,
            employee_controller=self._employee_controller,
        )
        widget.pack(fill="both", expand=True)
        return page, widget

    def _create_employees_page(self, title_font: ctk.CTkFont, fm: Optional[FontManager]) -> tuple[
        ctk.CTkFrame, Optional[EmployeeListWidget]]:
        if not self._employee_controller:
            stub = self._create_stub_page(
                "Сотрудники", "Модуль сотрудников недоступен",
                title_font,
                fm.get_font("subtitle") if fm else ctk.CTkFont(size=16),
                fm
            )
            return stub, None
        return self._create_employees_page_real(title_font, fm)

    def _create_employees_page_real(self, title_font: ctk.CTkFont, fm: Optional[FontManager]) -> tuple[
        ctk.CTkFrame, EmployeeListWidget]:
        page = ctk.CTkFrame(self._content_card, fg_color="transparent")

        header = ctk.CTkLabel(page, text="Личный состав", font=title_font, anchor="w")
        header.pack(fill="x", padx=20, pady=(20, 10))

        widget = EmployeeListWidget(
            master=page,
            controller=self._employee_controller,
            bridge=self._bridge,
            logger=self._logger,
            task_controller=self._task_controller,
        )
        widget.pack(fill="both", expand=True)
        return page, widget

    def _create_engagements_page(self, title_font: ctk.CTkFont, fm: Optional[FontManager]) -> ctk.CTkFrame:
        page = ctk.CTkFrame(self._content_card, fg_color="transparent")

        if not self._engagement_type_controller or not self._engagement_template_controller:
            return self._create_stub_page(
                "Задействования", "Модуль задействований недоступен",
                title_font,
                fm.get_font("subtitle") if fm else ctk.CTkFont(size=16),
                fm
            )

        widget = EngagementManagementWidget(
            master=page,
            type_controller=self._engagement_type_controller,
            template_controller=self._engagement_template_controller,
            bridge=self._bridge,
            logger=self._logger,
            color_service=self._color_service,
        )
        widget.pack(fill="both", expand=True)
        return page

    def _create_stub_page(self, title: str, message: str, title_font: ctk.CTkFont, subtitle_font: ctk.CTkFont,
                          fm: Optional[FontManager]) -> ctk.CTkFrame:
        page = ctk.CTkFrame(self._content_card, fg_color="transparent")
        ctk.CTkLabel(page, text=title, font=title_font).pack(pady=(40, 10))
        ctk.CTkLabel(page, text=message, font=subtitle_font, text_color="gray").pack()
        return page
