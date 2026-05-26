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

#### Application (Tasks)
- `src/application/interfaces/task_repository_interface.py` — `ITaskRepository`
- `src/application/schemas/task_schemas.py`:
  - `TaskCreateSchema` (name, period_type, anchor_date, employee_ids, duty_type_ids, reference_id)
  - `TaskUpdateSchema` (id + опциональные поля)
  - `TaskReadSchema`

#### Infrastructure
- `src/infrastructure/db/async_database_session.py` — async SQLAlchemy сессии
- `src/infrastructure/db/models/task_orm_model.py` — `TaskORMModel` (UNIQUE name)
- `src/infrastructure/repositories/task_repository.py` — `TaskSQLAlchemyRepository`:
  - Маппинг `anchor_date`↔`reference_date`, `duty_type_ids`↔`engagement_ids`
  - `exists_by_name(name, exclude_id)` для защиты от дубликатов

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
- `src/presentation/dialogs/task_dialog.py` — `TaskDialog` (универсальный):
  - Режимы: создание (task=None) и редактирование (task=TaskReadSchema)
  - Унифицированный коллбэк `on_save(task_id, schema)`
- `src/presentation/widgets/log_panel.py` — `LogPanel` (сворачиваемый)
- `src/presentation/widgets/navigation_sidebar.py` — `NavigationSidebar`:
  - 5 разделов: tasks/graphs/employees/engagements/settings
  - `on_select` callback, `set_active()`, цветовые схемы Light/Dark
- `src/presentation/widgets/task_list_widget.py` — `TaskListWidget`:
  - `ttk.Treeview` (№/Название/Тип периода)
  - Кнопки: Создать/Изменить/Удалить/Обновить, двойной клик → редактирование
  - `_dispatch_save()` → `_execute_create()` / `_execute_update()`
  - Обработка `DuplicateTaskNameError` с `_reopen_edit_dialog()`
- `src/presentation/main_window.py` — `MainWindow`:
  - Навигационный сайдбар + контент-область (white-card layout)
  - 5 страниц (tasks/graphs/employees/engagements/settings)
  - Нативное `tk.Menu` (Файл/Правка/Вид/Сервис/Справка)
  - Создание `FontManager` внутри `__init__()` (требует Tk-корень)
  - `attach_log_handler()` для подключения CTkLogHandler
  - Горячие клавиши Ctrl+Q (выход), F5 (обновить)
  - Статус-бар **удалён** (не нёс полезной информации)
- `main.py` — 8-этапная инициализация:
  1. Логирование
  2. Загрузка настроек
  3. Применение темы CTk (без Tk-корня)
  4. Инициализация БД
  5. Создание инфраструктуры
  6. Создание MainWindow (создаёт AsyncBridge и FontManager)
  7. `attach_gui_handler` + `window.attach_log_handler()`
  8. Запуск mainloop

### Архитектурные решения
- **AsyncBridge**: daemon-поток с asyncio loop на всё время жизни приложения
- **FontManager**: создаётся внутри MainWindow (CTkFont требует Tk-корень)
- **TaskDialog**: универсальный, заменяет `CreateTaskDialog` (файл удалён)
- **Navigation Sidebar** вместо `CTkTabview` (современный паттерн, решает проблему с шириной)
- **White-card layout**: светло-серый фон окна (#F3F3F3) + белые карточки контента

## 🎯 Следующая задача

## 🎯 Следующая задача: CRUD над Сотрудниками

### Форматы отображения имени
- **Короткий (`display_name`)** — для графиков и таблиц:
  - С отчеством: `"Фамилия И.О."` (например, "Иванов И.С.")
  - Без отчества: `"Фамилия И."` (например, "Иванов И.")
  - Вычисляется автоматически в Domain через `@model_validator`
  - При конфликтах однофамильцев Application-слой
    (`EmployeeController.resolve_display_names()`) расширяет инициал
    имени до различимых первых букв: "Иванов Вик. С." vs "Иванов Вит. С."
- **Длинный (`get_full_name()`)** — для карточки сотрудника и отчётов:
  - Полное ФИО: `"Фамилия Имя Отчество"` (например, "Иванов Иван Сергеевич")
  - Вычисляется методом `Employee.get_full_name()`

### Поля Domain-модели `Employee`
| Поле | Тип | Обязательное | Комментарий |
|------|-----|:------------:|-------------|
| `id` | UUID | ✅ | Первичный ключ |
| `last_name` | str | ✅ | Фамилия (1–100 символов) |
| `first_name` | str | ✅ | Имя (1–100 символов) |
| `middle_name` | str \| None | ❌ | Отчество (до 100 символов) |
| `display_name` | str | ✅ | Вычисляемое, для графика |
| `position` | str \| None | ❌ | Должность |
| `tab_number` | str \| None | ❌ | Табельный номер |
| `email` | str \| None | ❌ | Email |
| `phone` | str \| None | ❌ | Телефон |
| `birth_date` | date \| None | ❌ | Дата рождения |
| `is_active` | bool | ✅ | Статус: Активен / В архиве |
| `notes` | str \| None | ❌ | Заметки (до 2000 символов) |
| `engagement_ids` | List[UUID] | ✅ | Допуски к задействованиям (many-to-many) |
| `created_at` | datetime | ✅ | Дата создания |
| `updated_at` | datetime \| None | ❌ | Дата обновления |

### Ограничения уникальности (Infrastructure)
- `email` — UNIQUE, если не NULL
- `tab_number` — UNIQUE, если не NULL
- Проверка дубликатов в репозитории через `exists_by_email` / `exists_by_tab_number`

### Связи
- **Many-to-many с `Engagement`** через `engagement_ids` (реализуется отдельной таблицей в Infrastructure)
- **Soft-связь с `PlanningTask`** через `PlanningTask.employee_ids` (список UUID)

### Логика удаления

| Контекст | Действие |
|----------|----------|
| **Меню "Сотрудники" → Удалить** | CASCADE: удаление из всех `PlanningTask.employee_ids` с предупреждением и подтверждением от пользователя |
| **Меню "График" → Удалить сотрудника** | Удаление UUID только из конкретной задачи (сотрудник остаётся в БД) |
| **Меню "Задачи" → Удалить из задачи** | Удаление UUID только из конкретной задачи |
| **Меню "Задействования" → Лишить допуска** | Удаление engagement_id из `Employee.engagement_ids` |
| **Архивация** | `is_active = False` — сотрудник не участвует в планировании, но данные сохраняются |

### UI: вкладка "Сотрудники"
- Таблица с колонками: **№ | ФИО (короткий `display_name`) | Должность | Статус**
- Кнопки: Создать / Изменить / Удалить / Обновить / Архивировать
- Двойной клик или кнопка "Карточка" → модальное окно с полной информацией:
  - Полное ФИО, все контактные данные, должность
  - Табельный номер, дата рождения
  - Статус и заметки
  - Список допусков к задействованиям (названия Engagement)
- Диалог создания/редактирования: универсальный `EmployeeDialog`

### План работ (11 итераций)
1. ✅ `src/domain/employees/employee_model.py`
2. ✅ `src/domain/employees/employee_exceptions.py`
3. `src/application/schemas/employee_schemas.py`
4. `src/application/interfaces/employee_repository_interface.py`
5. `src/infrastructure/db/models/employee_orm_model.py`
6. `src/infrastructure/db/models/employee_engagement_link.py` (many-to-many таблица)
7. `src/infrastructure/repositories/employee_repository.py`
8. `src/presentation/controllers/employee_controller.py`
9. `src/presentation/dialogs/employee_dialog.py`
10. `src/presentation/dialogs/employee_card_dialog.py` (просмотр полной карточки)
11. `src/presentation/widgets/employee_list_widget.py`
12. `src/presentation/main_window.py` — замена заглушки employees
13. `main.py` — wiring `EmployeeController` + `EmployeeListWidget`

### Архитектурные решения
- **Разделение ответственности**: Domain не знает о других сотрудниках, разрешение конфликтов `display_name` — в Application
- **Мягкое удаление через архивацию**: `is_active=False` вместо физического удаления из БД
- **Полное удаление только с подтверждением**: если сотрудник используется в задачах — показывается список задач и запрашивается подтверждение CASCADE

## 📋 План работ по Сотрудникам (поэтапно, по одному файлу за итерацию)

1. `src/domain/employees/employee_model.py` — Domain модель `Employee`
2. `src/domain/employees/employee_exceptions.py` — исключения (`EmployeeDomainError`, `DuplicateEmployeeError` и т.п.)
3. `src/application/schemas/employee_schemas.py` — DTO (`EmployeeCreateSchema`/`EmployeeUpdateSchema`/`EmployeeReadSchema`)
4. `src/application/interfaces/employee_repository_interface.py` — `IEmployeeRepository`
5. `src/infrastructure/db/models/employee_orm_model.py` — `EmployeeORMModel`
6. `src/infrastructure/repositories/employee_repository.py` — `EmployeeSQLAlchemyRepository`
7. `src/presentation/controllers/employee_controller.py` — `EmployeeController`
8. `src/presentation/dialogs/employee_dialog.py` — `EmployeeDialog` (универсальный)
9. `src/presentation/widgets/employee_list_widget.py` — `EmployeeListWidget`
10. `src/presentation/main_window.py` — замена заглушки страницы employees
11. `main.py` — wiring `EmployeeController` + `EmployeeListWidget`

## 📜 Принятые правила в ходе работы

- **Поэтапная работа:** один файл за итерацию, с подтверждением перед правкой
- **Ничего не придумывать.** Источники истины: `structure.md` и ответы пользователя
- **Из всех вариантов всегда выбирать самый надёжный**
- **Всегда использовать обработку исключений с логированием**
- **Логически разделять код на отдельные файлы**
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

