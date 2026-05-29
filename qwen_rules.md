Дата обновления: 2026-05-29
Приоритет: Высокий
Язык: Python
Архитектура: Onion/Clean (Domain → Application → Infrastructure → Presentation)
UI: CustomTkinter
✅ Текущее состояние
Core
src/core/logging_config.py — система логирования:
CTkLogHandler с буфером и фильтрацией БД-логов
DatabaseLogFilter — "БД в интерфейс не логируется"
Функции: setup_logging, get_logger, log_user_action, log_user_error, log_ui_event
attach_gui_handler(root) — отложенное подключение к GUI
RotatingFileHandler (5 МБ × 3 бэкапа)
Domain (Tasks)
src/domain/tasks/planning_task_model.py:
PeriodType (WEEK/MONTH/QUARTER/YEAR/CUSTOM) с localized
PlanningTask (Pydantic v2, @model_validator для расчёта period_start/period_end)
src/domain/tasks/task_exceptions.py:
TaskDomainError, InvalidTaskNameError, InvalidTaskPeriodError
EmptyTaskReferenceError, DuplicateTaskNameError
Domain (Employees)
src/domain/employees/employee_model.py:
Employee (Pydantic v2, @model_validator для display_name)
Поле: rank: Optional[str] (Звание)
Методы: get_full_name(), toggle_active(), with_updated_display_name(), clone()
src/domain/employees/employee_exceptions.py:
EmployeeDomainError, InvalidEmployeeNameError
DuplicateEmployeeError (с duplicate_field, duplicate_value)
EmployeeInUseError (с task_count)
Application (Tasks)
src/application/interfaces/task_repository_interface.py — ITaskRepository
Добавлены методы: add_employee_to_task, get_tasks_by_employee
src/application/schemas/task_schemas.py:
TaskCreateSchema, TaskUpdateSchema, TaskReadSchema
Application (Employees)
src/application/interfaces/employee_repository_interface.py — IEmployeeRepository
src/application/schemas/employee_schemas.py:
EmployeeCreateSchema, EmployeeUpdateSchema, EmployeeReadSchema
Поле: rank: Optional[str] во всех схемах
src/application/services/employee_link_service.py — оркестрация связей сотрудник↔задача:
EmployeeUsageInfo (dataclass: employee_id, task_count, exists)
get_usage_info(), get_task_count() — проверка использования
remove_from_task() — точечное удаление из одной задачи
cascade_remove_from_tasks() — CASCADE-удаление из всех задач
src/application/services/display_name_resolver.py — чистая функция разрешения конфликтов однофамильцев
Infrastructure
src/infrastructure/db/async_database_session.py — async SQLAlchemy сессии
DEV_RESET_DB = False (отключён авто-сброс БД для тестирования)
src/infrastructure/db/models/task_orm_model.py — TaskORMModel (UNIQUE name)
src/infrastructure/db/models/employee_orm_model.py — EmployeeORMModel
Колонка: rank VARCHAR(100)
src/infrastructure/repositories/task_repository.py — TaskSQLAlchemyRepository
Реализованы: add_employee_to_task, get_tasks_by_employee, _add_employee_to_orm
src/infrastructure/repositories/employee_repository.py — EmployeeSQLAlchemyRepository:
Маппинг поля rank в _to_orm, _to_domain, update
Presentation (Controllers)
src/presentation/controllers/task_controller.py — TaskController
Добавлен метод: add_employee_to_task
src/presentation/controllers/employee_controller.py — EmployeeController:
Передача rank в _to_read_schema и create_employee
Presentation (Dialogs)
src/presentation/dialogs/task_dialog.py — TaskDialog:
Интеграция выбора сотрудников через EmployeeSelectDialog
Кнопка «Сотрудники» показывает количество выбранных
src/presentation/dialogs/employee_dialog.py — EmployeeDialog (унифицированный create/view/edit):
Поле ввода: «Звание» в правой колонке рядом с «Должностью»
Кнопка «Задачи» (только в режимах view/edit) для открытия списка задач сотрудника
src/presentation/dialogs/employee_select_dialog.py — модальный мультиселект сотрудников
src/presentation/dialogs/employee_tasks_dialog.py — диалог управления задачами сотрудника:
Список задач с сортировкой и перестановкой столбцов
Кнопки «Удалить из задачи» и «Добавить в задачу»
Вспомогательный класс _TaskSelectDialog для выбора задачи при добавлении
Presentation (Widgets)
src/presentation/widgets/task_list_widget.py — TaskListWidget (тонкий фасад)
Делегирует управление диалогами в TaskDialogCoordinator
src/presentation/widgets/task_dialog_coordinator.py — TaskDialogCoordinator:
Управление жизненным циклом TaskDialog
Загрузка актуальных данных задачи перед редактированием (fix stale data)
Диспетчеризация сохранения и обработка ошибок
src/presentation/widgets/employee_list_widget.py — EmployeeListWidget:
Столбцы: №, Должность, Звание, ФИО, Статус
Сортировка по клику, перестановка столбцов через ПКМ
Принимает task_controller для передачи в координатор
src/presentation/widgets/employee_dialog_coordinator.py — EmployeeDialogCoordinator:
Открытие карточки сотрудника с кнопкой «Задачи»
Открытие EmployeeTasksDialog с загрузкой задач
Обработка добавления/удаления сотрудника из задач (_handle_add_to_task, _handle_remove_from_task)
src/presentation/widgets/page_factory.py — PageFactory:
Передает task_controller в EmployeeListWidget и employee_controller в TaskListWidget
src/presentation/async_bridge.py — AsyncBridge с graceful shutdown
src/presentation/font_manager.py — FontManager
src/presentation/settings.py — Settings
src/presentation/widgets/log_panel.py — LogPanel
src/presentation/widgets/navigation_sidebar.py — NavigationSidebar
src/presentation/widgets/main_menu.py — MainMenu
src/presentation/main_window.py — MainWindow (тонкий фасад)
main.py — 8-этапная инициализация (DEV_RESET_DB = False)
🏗 Архитектурные решения
Общие
AsyncBridge: daemon-поток с asyncio loop на всё время жизни приложения
FontManager: создаётся внутри MainWindow (CTkFont требует Tk-корень)
Navigation Sidebar вместо CTkTabview
White-card layout: светло-серый фон окна (#F3F3F3) + белые карточки контента
DEV_RESET_DB = False: БД сохраняется между запусками, сброс только вручную
Координаторы: Выделены TaskDialogCoordinator и EmployeeDialogCoordinator для разгрузки виджетов
Tasks
TaskDialogCoordinator: Перезагружает задачу из БД перед открытием диалога редактирования, чтобы избежать работы с устаревшими данными (stale state).
Выбор сотрудников: Реализован через EmployeeSelectDialog с чекбоксами.
Связи: Хранятся как JSON-массив UUID в поле employee_ids. Операции добавления/удаления выполняются через специализированные методы репозитория.
Employees
Поле «Звание» (rank): Опциональное, хранится в БД, отображается в таблице и карточке.
Таблица сотрудников: Сортировка по любому столбцу, изменение порядка столбцов через ПКМ.
Карточка сотрудника: Кнопка «Задачи» открывает отдельный диалог EmployeeTasksDialog.
Управление задачами из карточки:
Просмотр всех задач сотрудника.
Удаление из задачи (точечное, без удаления сотрудника).
Добавление в задачу через вспомогательный диалог выбора.
Мягкое удаление: Через архивацию (is_active=False).
🎯 Следующие задачи / Известные проблемы
Engagements (Задействования): Подготовить переиспользуемый паттерн MultiSelectDialog для выбора задействований (аналогично сотрудникам).
Графики (Schedule): Реализация конкретной привязки во времени (следующий крупный этап).
Рефакторинг EmployeeTasksDialog: Вынести _TaskSelectDialog в отдельный файл или универсальный компонент, если он понадобится elsewhere.
Оптимизация запросов: Текущая реализация get_tasks_by_employee и add_employee_to_task загружает все задачи и фильтрует в Python. При росте данных потребуется миграция на PostgreSQL с jsonb @> или нормализация связей.
📜 Принятые правила в ходе работы
Поэтапная работа: Один файл за итерацию, с подтверждением перед правкой.
Источники истины: structure.md и ответы пользователя. Ничего не придумывать.
Надёжность: Из всех вариантов всегда выбирать самый надёжный и простой.
Обработка исключений: Всегда использовать с логированием.
SRP: Размер файла ≤ 300 строк. Выделять координаторы.
Архитектура: Domain не зависит от ORM/UI. Infrastructure зависит от Application.
Асинхронность: Никаких прямых обращений к БД из UI. Только через AsyncBridge.
Pydantic v2: Для валидации и DTO. ORM изолирована в Infrastructure.
Кодстайл: PEP 8, type hints, f-строки, логирование, двойной отступ между методами, пустая строка в конце.
Документация: Путь к файлу в комментарии первой строки, докстринги модулей/классов. Комментарии краткие.
Обратная совместимость: Не менять публичные интерфейсы без согласования.
Логирование: Не удалять существующее. Добавлять на границах сервисов.
Переиспользование: Использовать повторно существующий код где возможно.
Экономия токенов: Пояснения краткие и информативные.