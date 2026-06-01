# migrate_template_ids.py
"""Временный скрипт миграции: добавляет колонку template_ids в planning_tasks."""
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path("data/skedgenie.db")

def main() -> None:
    if not DB_PATH.exists():
        print(f"❌ База данных не найдена: {DB_PATH}")
        sys.exit(1)

    print(f"📂 Подключение к: {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH))

    try:
        # Проверяем, существует ли уже колонка
        cursor = conn.execute("PRAGMA table_info(planning_tasks)")
        columns = [row[1] for row in cursor.fetchall()]

        if "template_ids" in columns:
            print("✅ Колонка template_ids уже существует")
            return

        # Добавляем колонку
        conn.execute(
            "ALTER TABLE planning_tasks ADD COLUMN template_ids TEXT NOT NULL DEFAULT '[]'"
        )
        conn.commit()
        print("✅ Колонка template_ids успешно добавлена")

        # Проверяем результат
        cursor = conn.execute("PRAGMA table_info(planning_tasks)")
        columns = [row[1] for row in cursor.fetchall()]
        print(f"📋 Текущие колонки: {columns}")

    except sqlite3.Error as e:
        print(f"❌ Ошибка БД: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
