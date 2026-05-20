# src/infrastructure/db/async_database_session.py

"""Настройка асинхронного соединения с БД, сессий и инициализации схем."""

from __future__ import annotations

from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

# Базовый класс для всех ORM-моделей проекта.
# Используется для регистрации метаданных (таблиц) перед созданием схемы.
Base = DeclarativeBase()

# Путь к базе данных (по умолчанию SQLite в папке data рядом с корнем проекта)
DB_PATH = Path(__file__).parent.parent.parent / "data" / "skedgenie.db"
DB_URL = f"sqlite+aiosqlite:///{DB_PATH}"

# Глобальные переменные для синглтон-паттерна движка и фабрики
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine(database_url: str = DB_URL) -> AsyncEngine:
    """Возвращает или создает асинхронный движок SQLAlchemy.

    :param database_url: Строка подключения к БД (по умолчанию aiosqlite).
    :return: Экземпляр AsyncEngine.
    """
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            database_url,
            echo=False,  # Включите True для отладки SQL-запросов
            pool_pre_ping=True,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Возвращает или создает фабрику асинхронных сессий.

    :return: Экземпляр async_sessionmaker.
    """
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Генератор контекста сессии.

    Позволяет использовать сессию как асинхронный контекстный менеджер
    в сервисном слое или middleware.
    """
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def init_db(dev_reset: bool = False) -> None:
    """Инициализирует базу данных, создавая таблицы по метаданным моделей.

    :param dev_reset: Если True, удаляет все таблицы перед созданием.
                      Используется для сброса состояния на этапе разработки.
    """
    engine = get_engine()
    async with engine.begin() as conn:
        if dev_reset:
            # Удаляем все таблицы, зарегистрированные в Base.metadata
            await conn.run_sync(Base.metadata.drop_all)
        # Создаем таблицы, которых еще нет в БД
        await conn.run_sync(Base.metadata.create_all)

