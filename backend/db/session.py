"""Async engine, session factory and health checks.

Primary access is asynchronous (``asyncpg``) as required for the concurrency
targets in PRD §7.1 (50 kiosks per hospital, sub-second turns). A lazily
created *synchronous* engine is retained for Alembic migrations and offline
management scripts.

Pool sizing, ``pool_pre_ping`` and ``pool_recycle`` are configured so a
long-running kiosk backend survives PgBouncer/DB restarts without manual
intervention.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, contextmanager
from typing import Any, AsyncGenerator, Dict, Generator, Optional

from sqlalchemy import event, text
from sqlalchemy.engine import Engine, create_engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool, StaticPool

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.db.base import Base

logger = get_logger(__name__)

_async_engine: Optional[AsyncEngine] = None
_sync_engine: Optional[Engine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None
_sync_session_factory: Optional[sessionmaker[Session]] = None
_engine_lock = asyncio.Lock()


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def _async_engine_kwargs() -> Dict[str, Any]:
    url = settings.DATABASE_URL
    kwargs: Dict[str, Any] = {
        "echo": settings.SQL_ECHO,
        "future": True,
        "pool_pre_ping": True,
    }

    if _is_sqlite(url):
        # In-memory SQLite needs a single shared connection.
        if ":memory:" in url:
            kwargs["poolclass"] = StaticPool
            kwargs["connect_args"] = {"check_same_thread": False}
        else:
            kwargs["poolclass"] = NullPool
        return kwargs

    kwargs.update(
        {
            "pool_size": settings.DB_POOL_SIZE,
            "max_overflow": settings.DB_MAX_OVERFLOW,
            "pool_timeout": settings.DB_POOL_TIMEOUT,
            "pool_recycle": settings.DB_POOL_RECYCLE,
        }
    )
    if "asyncpg" in url:
        server_settings = {
            "application_name": f"medikiosk-{settings.ENV}",
            "jit": "off",
        }
        if settings.DB_STATEMENT_TIMEOUT_MS > 0:
            server_settings["statement_timeout"] = str(settings.DB_STATEMENT_TIMEOUT_MS)
        kwargs["connect_args"] = {
            "server_settings": server_settings,
            "timeout": float(settings.DB_POOL_TIMEOUT),
        }
    return kwargs


def get_async_engine() -> AsyncEngine:
    """Return the process-wide async engine, creating it on first use."""
    global _async_engine, _session_factory
    if _async_engine is None:
        _async_engine = create_async_engine(settings.DATABASE_URL, **_async_engine_kwargs())
        _session_factory = async_sessionmaker(
            bind=_async_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
        if _is_sqlite(settings.DATABASE_URL):
            _register_sqlite_pragmas(_async_engine.sync_engine)
        logger.info(
            "database_engine_created",
            dialect=_async_engine.dialect.name,
            pool=type(_async_engine.pool).__name__,
        )
    return _async_engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        get_async_engine()
    assert _session_factory is not None  # noqa: S101 - initialised above
    return _session_factory


def get_sync_engine() -> Engine:
    """Synchronous engine for Alembic and CLI maintenance tasks."""
    global _sync_engine, _sync_session_factory
    if _sync_engine is None:
        url = settings.DATABASE_SYNC_URL
        kwargs: Dict[str, Any] = {"echo": settings.SQL_ECHO, "future": True, "pool_pre_ping": True}
        if _is_sqlite(url):
            kwargs["poolclass"] = StaticPool if ":memory:" in url else NullPool
            kwargs["connect_args"] = {"check_same_thread": False}
        else:
            kwargs.update(
                {
                    "pool_size": max(2, settings.DB_POOL_SIZE // 4),
                    "max_overflow": 2,
                    "pool_recycle": settings.DB_POOL_RECYCLE,
                }
            )
        _sync_engine = create_engine(url, **kwargs)
        _sync_session_factory = sessionmaker(bind=_sync_engine, expire_on_commit=False, autoflush=False)
        if _is_sqlite(url):
            _register_sqlite_pragmas(_sync_engine)
    return _sync_engine


def _register_sqlite_pragmas(engine: Engine) -> None:
    """Enable FK enforcement and WAL for SQLite (tests / offline kiosk cache)."""

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection: Any, _record: Any) -> None:  # pragma: no cover
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
        except Exception:  # noqa: BLE001 - in-memory DBs reject WAL
            pass
        finally:
            cursor.close()


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a transactional async session.

    The session is committed when the handler returns cleanly and rolled back
    on any exception, so partially written clinical data is never persisted.
    """
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        if session.in_transaction():
            await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


@asynccontextmanager
async def session_scope() -> AsyncGenerator[AsyncSession, None]:
    """Async context manager for background workers and startup tasks."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        if session.in_transaction():
            await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


@contextmanager
def sync_session_scope() -> Generator[Session, None, None]:
    """Synchronous session for management scripts."""
    get_sync_engine()
    assert _sync_session_factory is not None  # noqa: S101
    session = _sync_session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# Backwards-compatible alias used by existing code/tests.
AsyncSessionLocal = get_session_factory


# ---------------------------------------------------------------------------
# Schema management
# ---------------------------------------------------------------------------
async def create_all() -> None:
    """Create tables directly (tests and first-run bootstrap only).

    Production upgrades must use ``alembic upgrade head``; this helper exists so
    the test-suite and a fresh developer machine work with zero setup.
    """
    import backend.models  # noqa: F401 - ensure models are registered

    engine = get_async_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("database_schema_created", tables=len(Base.metadata.tables))


async def drop_all() -> None:
    import backend.models  # noqa: F401

    engine = get_async_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def dispose_engines() -> None:
    """Close pools on shutdown."""
    global _async_engine, _session_factory, _sync_engine, _sync_session_factory
    if _async_engine is not None:
        await _async_engine.dispose()
        _async_engine = None
        _session_factory = None
    if _sync_engine is not None:
        _sync_engine.dispose()
        _sync_engine = None
        _sync_session_factory = None
    logger.info("database_engines_disposed")


async def check_database_health() -> Dict[str, Any]:
    """Lightweight probe used by ``/health/ready``."""
    engine = get_async_engine()
    result: Dict[str, Any] = {"dialect": engine.dialect.name, "healthy": False}
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        result["healthy"] = True
        pool = engine.pool
        if hasattr(pool, "size"):
            result["pool"] = {
                "size": pool.size(),  # type: ignore[attr-defined]
                "checked_out": pool.checkedout(),  # type: ignore[attr-defined]
            }
    except Exception as exc:  # noqa: BLE001
        result["error"] = str(exc)
        logger.error("database_health_check_failed", error=str(exc))
    return result


async def apply_migrations_if_needed() -> Optional[str]:
    """Report the current Alembic revision (never migrates implicitly).

    Automatic migration on boot is dangerous in a clinical setting; operators
    run ``alembic upgrade head`` from the deployment playbook. This function
    only surfaces the applied revision so ``/health/ready`` can warn when the
    database is behind the shipped code.
    """
    engine = get_async_engine()
    try:
        async with engine.connect() as conn:
            row = await conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
            value = row.scalar()
            return str(value) if value else None
    except Exception:  # noqa: BLE001 - table absent on fresh installs
        return None


__all__ = [
    "get_async_engine",
    "get_sync_engine",
    "get_session_factory",
    "get_db",
    "session_scope",
    "sync_session_scope",
    "AsyncSessionLocal",
    "create_all",
    "drop_all",
    "dispose_engines",
    "check_database_health",
    "apply_migrations_if_needed",
]
