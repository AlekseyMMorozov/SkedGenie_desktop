# src/presentation/widgets/page_factory.py
"""
Фабрика страниц контента для MainWindow.

Создаёт все 5 страниц разделов (tasks/graphs/employees/engagements/settings)
и возвращает их в виде словаря для переключения.

Ответственность:
    - Создание реальных виджетов (TaskListWidget, EmployeeListWidget).
    - Создание заглушек для нереализованных разделов.
    - Единый источник истины для ID разделов (константы SECTION_*).
    - Применение FontManager к заголовкам страниц.

Границы:
    - НЕ управляет переключением страниц — это ответственность MainWindow.
    - НЕ создаёт контроллеры — принимает их через конструктор.
    - НЕ обрабатывает события UI — делегирует виджетам.

Использование:
    factory = PageFactory(content_card, task_controller, employee_controller, bridge, logger)
    pages, task_widget, emp_widget = factory.create_all_pages()
"""
from __future__ import annotations

import logging
from typing import Optional

import customtkinter as ctk

from src.presentation.async_bridge import AsyncBridge
from src.presentation.controllers.employee_controller import EmployeeController
from src.presentation.controllers.task_controller import TaskController
from src.presentation.font_manager import FontManager, get_font_manager
from src.presentation.widgets.employee_list_widget import EmployeeListWidget
from src.presentation.widgets.task_list_widget import TaskListWidget


class PageFactory:
    """Фабрика страниц контента для MainWindow."""

    # ID разделов (должны совпадать с NavigationSidebar._SECTIONS)
    SECTION_TASKS: str = "tasks"
    SECTION_GRAPHS: str = "graphs"
    SECTION_EMPLOYEES: str = "employees"
    SECTION_ENGAGEMENTS: str = "engagements"
    SECTION_SETTINGS: str = "settings"

    _CONTENT_PADDING: int = 15

    def __init__(
        self,
        content_card: ctk.CTkFrame,
        task_controller: TaskController,
        employee_controller: Optional[EmployeeController],
        bridge: AsyncBridge,
        logger: logging.Logger,
    ) -> None:
        """Инициализация фабрики.

        Args:
            content_card: Родительский контейнер для страниц (белая карточка).
            task_controller: Контроллер задач (обязательный).
            employee_controller: Контроллер сотрудников (может быть None).
            bridge: AsyncBridge для выполнения async-операций.
            logger: Логгер для записи событий.
        """
        self._content_card = content_card
        self._task_controller = task_controller
        self._employee_controller = employee_controller
        self._bridge = bridge
        self._logger = logger

    def create_all_pages(self) -> tuple[
        dict[str, ctk.CTkFrame],
        Optional[TaskListWidget],
        Optional[EmployeeListWidget],
    ]:
        """Создать все страницы контента.

        Returns:
            Кортеж из трёх элементов:
                - pages: словарь {section_id: CTkFrame} для переключения.
                - task_widget: TaskListWidget (для refresh) или None.
                - employee_widget: EmployeeListWidget (для refresh) или None.
        """
        fm = get_font_manager()
        title_font = fm.get_font("title") if fm else ctk.CTkFont(
            size=20, weight="bold",
        )
        subtitle_font = fm.get_font("subtitle") if fm else ctk.CTkFont(size=16)

        pages: dict[str, ctk.CTkFrame] = {}
        task_widget: Optional[TaskListWidget] = None
        employee_widget: Optional[EmployeeListWidget] = None

        # --- Страница "Задачи" ---
        tasks_page, task_widget = self._create_tasks_page(
            title_font=title_font,
            fm=fm,
        )
        pages[self.SECTION_TASKS] = tasks_page

        # --- Страница "Графики" (заглушка) ---
        pages[self.SECTION_GRAPHS] = self._create_stub_page(
            title="Графики",
            message="Модуль 'Графики' находится в разработке",
            title_font=title_font,
            subtitle_font=subtitle_font,
            fm=fm,
        )

        # --- Страница "Сотрудники" ---
        employees_page, employee_widget = self._create_employees_page(
            title_font=title_font,
            fm=fm,
        )
        pages[self.SECTION_EMPLOYEES] = employees_page

        # --- Страница "Задействования" (заглушка) ---
        pages[self.SECTION_ENGAGEMENTS] = self._create_stub_page(
            title="Задействования",
            message="Модуль 'Задействования' находится в разработке",
            title_font=title_font,
            subtitle_font=subtitle_font,
            fm=fm,
        )

        # --- Страница "Настройки" (заглушка) ---
        pages[self.SECTION_SETTINGS] = self._create_stub_page(
            title="Настройки",
            message="Модуль 'Настройки' находится в разработке",
            title_font=title_font,
            subtitle_font=subtitle_font,
            fm=fm,
        )

        self._logger.debug(
            "PageFactory: создано %d страниц контента",
            len(pages),
        )

        return pages, task_widget, employee_widget

    # ------------------------------------------------------------------
    # Страница "Задачи"
    # ------------------------------------------------------------------
    def _create_tasks_page(
        self,
        title_font: ctk.CTkFont,
        fm: Optional[FontManager],
    ) -> tuple[ctk.CTkFrame, TaskListWidget]:
        """Создать страницу 'Задачи' с реальным TaskListWidget.

        Args:
            title_font: Шрифт для заголовка.
            fm: FontManager для регистрации виджетов (может быть None).

        Returns:
            Кортеж (page_frame, task_list_widget).
        """
        page = ctk.CTkFrame(self._content_card, fg_color="transparent")
        page.pack_propagate(False)

        header = ctk.CTkLabel(
            page,
            text="Задачи планирования",
            font=title_font,
            anchor="w",
        )
        header.pack(
            fill="x",
            padx=self._CONTENT_PADDING,
            pady=(self._CONTENT_PADDING, 5),
        )
        if fm:
            fm.register_widget(header, "title")

        task_widget = TaskListWidget(
            master=page,
            controller=self._task_controller,
            bridge=self._bridge,
            logger=self._logger,
            employee_controller=self._employee_controller,
        )
        task_widget.pack(
            fill="both",
            expand=True,
            padx=self._CONTENT_PADDING,
            pady=(0, self._CONTENT_PADDING),
        )

        self._logger.info("PageFactory: страница 'Задачи' создана (TaskListWidget)")
        return page, task_widget

    # ------------------------------------------------------------------
    # Страница "Сотрудники"
    # ------------------------------------------------------------------
    def _create_employees_page(
        self,
        title_font: ctk.CTkFont,
        fm: Optional[FontManager],
    ) -> tuple[ctk.CTkFrame, Optional[EmployeeListWidget]]:
        """Создать страницу 'Сотрудники'.

        Если employee_controller передан — создаёт EmployeeListWidget.
        Иначе — создаёт заглушку с предупреждением.

        Args:
            title_font: Шрифт для заголовка.
            fm: FontManager для регистрации виджетов (может быть None).

        Returns:
            Кортеж (page_frame, employee_list_widget или None).
        """
        if self._employee_controller is not None:
            return self._create_employees_page_real(title_font, fm)
        else:
            self._logger.warning(
                "PageFactory: employee_controller не передан, "
                "страница 'Сотрудники' останется заглушкой"
            )
            subtitle_font = fm.get_font("subtitle") if fm else ctk.CTkFont(size=16)
            page = self._create_stub_page(
                title="Сотрудники",
                message="Модуль 'Сотрудники' недоступен: не инициализирован контроллер",
                title_font=title_font,
                subtitle_font=subtitle_font,
                fm=fm,
            )
            return page, None

    def _create_employees_page_real(
        self,
        title_font: ctk.CTkFont,
        fm: Optional[FontManager],
    ) -> tuple[ctk.CTkFrame, EmployeeListWidget]:
        """Создать страницу 'Сотрудники' с реальным EmployeeListWidget.

        Args:
            title_font: Шрифт для заголовка.
            fm: FontManager для регистрации виджетов (может быть None).

        Returns:
            Кортеж (page_frame, employee_list_widget).
        """
        page = ctk.CTkFrame(self._content_card, fg_color="transparent")
        page.pack_propagate(False)

        header = ctk.CTkLabel(
            page,
            text="Сотрудники",
            font=title_font,
            anchor="w",
        )
        header.pack(
            fill="x",
            padx=self._CONTENT_PADDING,
            pady=(self._CONTENT_PADDING, 5),
        )
        if fm:
            fm.register_widget(header, "title")

        # Тип гарантированно не None — проверка была в _create_employees_page().
        assert self._employee_controller is not None

        employee_widget = EmployeeListWidget(
            master=page,
            controller=self._employee_controller,
            bridge=self._bridge,
            logger=self._logger,
            task_controller=self._task_controller,  # ✅ Передаем task_controller
        )
        employee_widget.pack(
            fill="both",
            expand=True,
            padx=self._CONTENT_PADDING,
            pady=(0, self._CONTENT_PADDING),
        )

        self._logger.info(
            "PageFactory: страница 'Сотрудники' создана (EmployeeListWidget)"
        )
        return page, employee_widget

    # ------------------------------------------------------------------
    # Заглушка
    # ------------------------------------------------------------------
    def _create_stub_page(
        self,
        title: str,
        message: str,
        title_font: ctk.CTkFont,
        subtitle_font: ctk.CTkFont,
        fm: Optional[FontManager],
    ) -> ctk.CTkFrame:
        """Создать страницу-заглушку с заголовком и сообщением.

        Args:
            title: Текст заголовка.
            message: Текст сообщения.
            title_font: Шрифт для заголовка.
            subtitle_font: Шрифт для сообщения.
            fm: FontManager для регистрации виджетов (может быть None).

        Returns:
            Готовый фрейм-страница.
        """
        page = ctk.CTkFrame(self._content_card, fg_color="transparent")

        header = ctk.CTkLabel(
            page,
            text=title,
            font=title_font,
            anchor="w",
        )
        header.pack(
            fill="x",
            padx=self._CONTENT_PADDING,
            pady=(self._CONTENT_PADDING, 5),
        )
        if fm:
            fm.register_widget(header, "title")

        stub_label = ctk.CTkLabel(
            page,
            text=message,
            font=subtitle_font,
        )
        stub_label.pack(expand=True)
        if fm:
            fm.register_widget(stub_label, "subtitle")

        return page
