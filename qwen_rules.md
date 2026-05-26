# Снимок состояния проекта: Десктопный планировщик смен, нарядов, дежурств (SkedGenie_desktop)

**Дата обновления:** 2026-05-26
**Приоритет:** Высокий
**Язык:** Python
**Архитектура:** Onion/Clean (Domain → Application → Infrastructure → Presentation)
**UI:** CustomTkinter

## ✅ Текущее состояние

### Реализовано

#### Core
- `src/core/logging_config.py` — система логирования:
  - `CTkLogHandler` с буфером и фильтрацией БД-логов
  - `DatabaseLogFilter` — "БД в интерфейс не логируется"
  - Функции: `setup_logging`, `get_logger`, `log_user_action`, `log_user_error`, `log_ui_event`
  - `attach_gui_handler(root)` — отложенное подключение к GUI
  - `RotatingFileHandler` (5 МБ × 3 бэкапа)

#### Domain (Tasks)
- `src/domain/tasks/planning_task_model.py`:
  - `PeriodType` (WEEK/MONTH/QUARTER/YEAR/CUSTOM) с `localized`
  - `PlanningTask` (Pydantic v2, `@model_validator` для расчёта `period_start`/`period_end`)
- `src/domain/tasks/task_exceptions.py`:
  - `TaskDomainError`, `InvalidTaskNameError`, `InvalidTaskPeriodError`
  - `EmptyTaskReferenceError`, `DuplicateTaskNameError`

#### Domain (Employees)
- `src/domain/employees/employee_model.py`:
  - `Employee` (Pydantic v2, `@model_validator` для `display_name`)
  - Методы: `get_full_name()`, `toggle_active()`, `with_updated_display_name()`, `clone()`
- `src/domain/employees/employee_exceptions.py`:
  - `EmployeeDomainError`, `InvalidEmployeeNameError`
  - `DuplicateEmployeeError` (с `duplicate_field`, `duplicate_value`)
  - `EmployeeInUseError` (с `task_count`)

#### Application (Tasks)
- `src/application/interfaces/task_repository_interface.py` — `ITaskRepository`
- `src/application/schemas/task_schemas.py`:
  - `TaskCreateSchema` (name, period_type, anchor_date, employee_ids, duty_type_ids, reference_id)
  - `TaskUpdateSchema` (id + опциональные поля)
  - `TaskReadSchema`

#### Application (Employees)
- `src/application/interfaces/employee_repository_interface.py` — `IEmployeeRepository`
- `src/application/schemas/employee_schemas.py`:
  - `EmployeeCreateSchema` (валидация ФИО, email, телефона, tab_number)
  - `EmployeeUpdateSchema`, `EmployeeReadSchema`
- `src/application/services/employee_link_service.py` — оркестрация связей сотрудник↔задача:
  - `EmployeeUsageInfo` (dataclass: employee_id, task_count, exists)
  - `get_usage_info()`, `get_task_count()` — проверка использования
  - `remove_from_task()` — точечное удаление из одной задачи
  - `cascade_remove_from_tasks()` — CASCADE-удаление из всех задач
- `src/application/services/display_name_resolver.py` — чистая функция разрешения конфликтов однофамильцев:
  - `resolve_display_names(employees)` — основной API
  - `_ExpansionState` — мутабельное состояние расширения инициалов
  - Алгоритм: группировка по фамилии → расширение имени → расширение отчества

#### Infrastructure
- `src/infrastructure/db/async_database_session.py` — async SQLAlchemy сессии
- `src/infrastructure/db/models/task_orm_model.py` — `TaskORMModel` (UNIQUE name)
- `src/infrastructure/db/models/employee_orm_model.py` — `EmployeeORMModel` (UNIQUE email, tab_number)
- `src/infrastructure/repositories/task_repository.py` — `TaskSQLAlchemyRepository`:
  - Маппинг `anchor_date`↔`reference_date`, `duty_type_ids`↔`engagement_ids`
  - `exists_by_name(name, exclude_id)` для защиты от дубликатов
- `src/infrastructure/repositories/employee_repository.py` — `EmployeeSQLAlchemyRepository`:
  - `exists_by_email()`, `exists_by_tab_number()` для проверки уникальности
  - `get_active_only()` для фильтрации архивных сотрудников

#### Presentation (Tasks + GUI-инфраструктура)
- `src/presentation/async_bridge.py` — `AsyncBridge` с graceful shutdown:
  - `is_running()`, `run(coro, on_success, on_error)`, `shutdown()`
  - `_shutdown_procedure()` — отмена pending задач, `shutdown_asyncgens()`, `call_soon_threadsafe(loop.stop)`
- `src/presentation/font_manager.py` — `FontManager`:
  - `FontSize` enum (SMALL=12, MEDIUM=14, LARGE=16)
  - Роли: caption/body/body_bold/subtitle/title
  - `get_font_manager()` / `set_font_manager()`
- `src/presentation/settings.py` — `Settings`:
  - `AppSettings` (font_size, appearance_mode, color_theme)
  - Атомарное сохранение через `tempfile`
- `src/presentation/controllers/task_controller.py` — `TaskController`:
  - Проверка `exists_by_name` перед созданием/обновлением
  - Логирование через `log_user_action`/`log_user_error`
- `src/presentation/controllers/employee_controller.py` — `EmployeeController` (тонкий фасад):
  - Делегирует CRUD операции `IEmployeeRepository`
  - Делегирует проверку использования `EmployeeLinkService`
  - Использует `resolve_display_names()` для разрешения конфликтов
- `src/presentation/dialogs/task_dialog.py` — `TaskDialog` (универсальный):
  - Режимы: создание (task=None) и редактирование (task=TaskReadSchema)
  - Унифицированный коллбэк `on_save(task_id, schema)`
- `src/presentation/dialogs/employee_dialog.py` — `EmployeeDialog` (создание):
  - Параметр `prefill_data` для повторного открытия после ошибки
  - Валидация через `EmployeeCreateSchema` / `EmployeeUpdateSchema`
- `src/presentation/dialogs/employee_card_dialog.py` — `EmployeeCardDialog` (просмотр/редактирование):
  - Режимы: `mode="view"` (read-only) и `mode="edit"` (inline редактирование)
  - Inline переключение через `_switch_mode()` с полной пересборкой UI
  - Кнопка "Изменить" в view mode → переключает в edit mode
  - `_collect_editable_data()` — сбор данных из реестра виджетов
- `src/presentation/widgets/log_panel.py` — `LogPanel` (сворачиваемый)
- `src/presentation/widgets/navigation_sidebar.py` — `NavigationSidebar`:
  - 5 разделов: tasks/graphs/employees/engagements/settings
  - `on_select` callback, `set_active()`, цветовые схемы Light/Dark
- `src/presentation/widgets/task_list_widget.py` — `TaskListWidget`:
  - `ttk.Treeview` (№/Название/Тип периода)
  - Кнопки: Создать/Изменить/Удалить/Обновить, двойной клик → редактирование
  - `_dispatch_save()` → `_execute_create()` / `_execute_update()`
  - Обработка `DuplicateTaskNameError` с `_reopen_edit_dialog()`
- `src/presentation/widgets/employee_list_widget.py` — `EmployeeListWidget`:
  - `ttk.Treeview` (№/ФИО/Должность/Статус)
  - Кнопки: Создать/Просмотреть/Удалить/Архивировать/Обновить
  - Двойной клик → открытие карточки (view mode)
  - Делегирование диалогов `EmployeeDialogCoordinator`
- `src/presentation/widgets/employee_dialog_coordinator.py` — `EmployeeDialogCoordinator`:
  - `open_create_dialog()` — открытие диалога создания
  - `open_card_dialog()` — открытие карточки (view mode)
  - `_dispatch_save()` — диспетчеризация сохранения (создание)
  - `_on_card_save()` — сохранение из карточки (inline редактирование)
  - Обработка `DuplicateEmployeeError` с повторным открытием диалога
- `src/presentation/widgets/employee_card_sections.py` — фабрики секций карточки:
  - `create_header_section()` — ФИО + статус (всегда read-only)
  - `create_personal_section()` — дата рождения
  - `create_contact_section()` — email, телефон
  - `create_work_section()` — должность, табельный номер
  - `create_engagement_section()` — допуски (пока read-only)
  - `create_notes_section()` — заметки
  - `create_metadata_section()` — created_at, updated_at (всегда read-only)
  - Параметр `editable: bool` для переключения view/edit
  - Возврат `tuple[CTkFrame, dict[str, EditableWidget]]` для регистрации виджетов
- `src/presentation/widgets/main_menu.py` — `MainMenu` (выделено из MainWindow):
  - Нативное `tk.Menu` с 5 подменю (Файл/Правка/Вид/Сервис/Справка)
  - Callback-параметры для всех действий меню
  - `@property menu` для установки в окно
- `src/presentation/widgets/page_factory.py` — `PageFactory` (выделено из MainWindow):
  - Константы `SECTION_*` для ID разделов
  - `create_all_pages()` — создание всех 5 страниц
  - Возврат `tuple[pages, task_widget, employee_widget]`
  - Fallback на заглушку при `None` контроллере
- `src/presentation/main_window.py` — `MainWindow` (тонкий фасад):
  - Tk-корень и настройка окна
  - Композиция: `MainMenu`, `NavigationSidebar`, `PageFactory`, `LogPanel`
  - Переключение страниц через `_show_page()`
  - Горячие клавиши: Ctrl+Q (выход), F5 (обновить)
  - `attach_log_handler()` для подключения CTkLogHandler
- `main.py` — 8-этапная инициализация:
  1. Логирование
  2. Загрузка настроек
  3. Применение темы CTk (без Tk-корня)
  4. Инициализация БД
  5. Создание инфраструктуры (Tasks + Employees)
  6. Создание MainWindow (создаёт AsyncBridge и FontManager)
  7. `attach_gui_handler` + `window.attach_log_handler()`
  8. Запуск mainloop

### Архитектурные решения

#### Общие
- **AsyncBridge**: daemon-поток с asyncio loop на всё время жизни приложения
- **FontManager**: создаётся внутри MainWindow (CTkFont требует Tk-корень)
- **Navigation Sidebar** вместо `CTkTabview` (современный паттерн, решает проблему с шириной)
- **White-card layout**: светло-серый фон окна (#F3F3F3) + белые карточки контента

#### Tasks
- **TaskDialog**: универсальный, заменяет `CreateTaskDialog` (файл удалён)
- **Проверка дубликатов**: `exists_by_name()` перед созданием/обновлением

#### Employees
- **Разделение ответственности**: Domain не знает о других сотрудниках, разрешение конфликтов `display_name` — в Application (`display_name_resolver.py`)
- **Мягкое удаление через архивацию**: `is_active=False` вместо физического удаления из БД
- **Полное удаление только с подтверждением**: если сотрудник используется в задачах — показывается количество задач и запрашивается подтверждение CASCADE
- **Тонкий фасад EmployeeController**: делегирует специфичную логику `EmployeeLinkService` и `resolve_display_names()`
- **Координатор диалогов**: `EmployeeDialogCoordinator` управляет жизненным циклом `EmployeeDialog` и `EmployeeCardDialog`
- **Inline редактирование**: `EmployeeCardDialog` поддерживает переключение view↔edit без закрытия диалога
- **Фабрики секций**: `employee_card_sections.py` возвращает реестр редактируемых виджетов для сбора данных

#### MainWindow (рефакторинг SRP)
- **Выделение MainMenu**: построение структуры меню вынесено в отдельный компонент
- **Выделение PageFactory**: создание страниц контента вынесено в отдельный компонент
- **MainWindow как тонкий фасад**: только Tk-корень, layout, lifecycle, композиция

## 🎯 Следующая задача

### Опции для выбора

1. **Модуль "Задействования" (Engagements)** — следующая агрегатная сущность:
   - Domain: `Engagement` (название, описание, цвет)
   - Many-to-many с `Employee` через `engagement_ids`
   - UI: таблица задействований, диалог создания/редактирования
   - Интеграция с `EmployeeCardDialog` (отображение названий вместо UUID)

2. **Модуль "Графики" (Graphs)** — визуализация планирования:
   - Domain: `Schedule`, `Shift`, `Assignment`
   - Gantt-диаграмма или таблица-календарь
   - Проверка жёстких правил (пересечения, минимальный отдых)
   - Автоматическое распределение сотрудников

3. **Улучшение Employee-модуля**:
   - Создать `employee_engagement_link.py` (many-to-many таблица)
   - Реализовать редактирование `engagement_ids` в `EmployeeCardDialog`
   - Добавить фильтрацию таблицы (активные/архивные)
   - Поиск по ФИО/должности

4. **Тестирование и стабилизация**:
   - Написать unit-тесты для критичных компонентов
   - Провести полное ручное тестирование всех 12 тест-кейсов
   - Исправить обнаруженные баги
   - Оптимизировать производительность (если есть проблемы)

5. **Настройки (Settings)**:
   - Диалог настроек (шрифт, тема, цвет)
   - Сохранение в `data/settings.json`
   - Применение настроек без перезапуска

## 📋 План работ по Сотрудникам (ЗАВЕРШЁН)

✅ `src/domain/employees/employee_model.py` — Domain модель `Employee`
✅ `src/domain/employees/employee_exceptions.py` — исключения (`EmployeeDomainError`, `DuplicateEmployeeError` и т.п.)
✅ `src/application/schemas/employee_schemas.py` — DTO (`EmployeeCreateSchema`/`EmployeeUpdateSchema`/`EmployeeReadSchema`)
✅ `src/application/interfaces/employee_repository_interface.py` — `IEmployeeRepository`
✅ `src/infrastructure/db/models/employee_orm_model.py` — `EmployeeORMModel`
❌ `src/infrastructure/db/models/employee_engagement_link.py` (many-to-many таблица — отложено до модуля Engagements)
✅ `src/infrastructure/repositories/employee_repository.py` — `EmployeeSQLAlchemyRepository`
✅ `src/application/services/display_name_resolver.py` — разрешение конфликтов однофамильцев
✅ `src/application/services/employee_link_service.py` — оркестрация связей сотрудник↔задача
✅ `src/presentation/controllers/employee_controller.py` — `EmployeeController` (тонкий фасад)
✅ `src/presentation/dialogs/employee_dialog.py` — `EmployeeDialog` (создание с prefill_data)
✅ `src/presentation/dialogs/employee_card_dialog.py` — карточка с inline view↔edit
✅ `src/presentation/widgets/employee_card_sections.py` — фабрики секций карточки
✅ `src/presentation/widgets/employee_dialog_coordinator.py` — координатор диалогов
✅ `src/presentation/widgets/employee_list_widget.py` — `EmployeeListWidget`
✅ `src/presentation/widgets/main_menu.py` — выделено из MainWindow (SRP)
✅ `src/presentation/widgets/page_factory.py` — выделено из MainWindow (SRP)
✅ `src/presentation/main_window.py` — утончён до тонкого фасада
✅ `main.py` — wiring `EmployeeController` + `EmployeeLinkService`

## 📜 Принятые правила в ходе работы

- **Поэтапная работа:** один файл за итерацию, с подтверждением перед правкой
- **Ничего не придумывать.** Источники истины: `structure.md` и ответы пользователя
- **Из всех вариантов всегда выбирать самый надёжный и простой**
- **Всегда использовать обработку исключений с логированием**
- **Логически разделять код на отдельные файлы (SRP), размер файла не больше 300 строк (пример: MainWindow → MainMenu + PageFactory)** 
- **Архитектура:** Domain не зависит от ORM/UI. Infrastructure зависит от Application
- **Стек:** Асинхронное ядро (asyncio), готовое к миграции на PostgreSQL/веб. Никаких прямых обращений к БД — только через репозитории
- **Pydantic v2:** для валидации и DTO в Domain/Application. ORM-модели изолированы в Infrastructure. Маппинг в репозитории
- **Имена файлов:** точно отражают содержимое (без аббревиатур)
- **Кодстайл:** PEP 8, type hints, f-строки, логирование (DEBUG/INFO/WARNING/ERROR)
- **Документация:** докстринги модулей/классов, краткие комментарии по бизнес-логике, путь в заголовке файла
- **Обратная совместимость:** Не менять публичные интерфейсы без согласования
- **Логирование:** Не удалять существующее. Добавлять на границах сервисов
- **Тестирование:** На текущем этапе функциональная проверка через UI
- **Генерация:** Сверять имена/сигнатуры с контрактом. Максимально переиспользовать код
- **Координация:** Выделять оркестрацию диалогов в отдельные координаторы (пример: EmployeeDialogCoordinator)