"""
Файл: src/infrastructure/db/async_database_session.py
Описание: Настройка асинхронного движка SQLAlchemy и сессионной фабрики.
Архитектура: Infrastructure слой. Изолирует работу с БД от бизнес-логики.
"""
from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Базовый класс для ORM-моделей. Не инстанцируется напрямую."""
    pass


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine(database_url: str) -> AsyncEngine:
    """Получить или создать асинхронный движок БД."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            database_url,
            echo=False,
            future=True,
            pool_pre_ping=True,
        )
    return _engine


def get_session_factory(database_url: str) -> async_sessionmaker[AsyncSession]:
    """Получить фабрику сессий (ленивая инициализация)."""
    global _session_factory
    if _session_factory is None:
        engine = get_engine(database_url)
        _session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Контекстный менеджер для получения сессии."""
    factory = get_session_factory("sqlite+aiosqlite:///./data/skedgenie.db")
    async with factory() as session:
        yield session


async def init_db(dev_reset: bool = False) -> None:
    """Инициализировать схему БД. При dev_reset — сбросить данные."""
    engine = get_engine("sqlite+aiosqlite:///./data/skedgenie.db")

    if dev_reset:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

