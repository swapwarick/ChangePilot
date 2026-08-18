"""Async database engine and session factory with automatic local SQLite fallback.

If PostgreSQL (port 5432) is not reachable (e.g. Docker is offline),
automatically falls back to a local SQLite database (`changepilot.db`)
so the application works seamlessly out-of-the-box.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.database.tables import Base

logger = logging.getLogger(__name__)

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_init_lock = asyncio.Lock()


def _sync_schema_columns(sync_conn):
    from sqlalchemy import inspect
    inspector = inspect(sync_conn)
    for table_name, table in Base.metadata.tables.items():
        if inspector.has_table(table_name):
            existing_cols = {col["name"] for col in inspector.get_columns(table_name)}
            for col in table.columns:
                if col.name not in existing_cols:
                    col_type = col.type.compile(sync_conn.dialect)
                    try:
                        sync_conn.execute(text(f'ALTER TABLE "{table_name}" ADD COLUMN "{col.name}" {col_type}'))
                        logger.info("Added missing column %s.%s (%s)", table_name, col.name, col_type)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("Could not add column %s.%s: %s", table_name, col.name, exc)


async def _init_db_engine():
    global _engine, _session_factory
    if _engine is not None:
        return _engine

    async with _init_lock:
        if _engine is not None:
            return _engine

        settings = get_settings()
        pg_url = settings.database_url

        # Attempt PostgreSQL connection
        try:
            test_engine = create_async_engine(pg_url, echo=False, connect_args={"connect_timeout": 5})
            async with test_engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            await test_engine.dispose()

            logger.info("Connected to PostgreSQL database successfully.")
            _engine = create_async_engine(pg_url, echo=settings.app_env == "development")
            async with _engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
                await conn.run_sync(_sync_schema_columns)
            _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
            return _engine
        except Exception as exc:  # noqa: BLE001
            logger.warning("PostgreSQL connection unavailable (%s). Falling back to local SQLite database.", exc)

        # SQLite Fallback with busy timeout and non-blocking locking configuration
        sqlite_url = "sqlite+aiosqlite:///./changepilot.db"
        _engine = create_async_engine(
            sqlite_url,
            echo=False,
            connect_args={"timeout": 30.0, "check_same_thread": False},
        )
        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.run_sync(_sync_schema_columns)
        logger.info("Local SQLite database initialized at ./changepilot.db")
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
        return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        raise RuntimeError("Database engine not initialized yet.")
    return _session_factory


async def _get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that yields an ``AsyncSession``."""
    if _engine is None or _session_factory is None:
        await _init_db_engine()

    assert _session_factory is not None
    async with _session_factory() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(_get_db)]

