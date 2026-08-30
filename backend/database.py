"""Backward-compatible database shim.

The canonical implementation now lives in :mod:`backend.db`. This module is
retained so existing imports (``from backend.database import Base, get_db``)
and the historical test-suite keep working. New code should import from
``backend.db``.
"""

from __future__ import annotations

from backend.db.base import Base, metadata
from backend.db.session import (
    AsyncSessionLocal,
    apply_migrations_if_needed,
    check_database_health,
    create_all,
    dispose_engines,
    drop_all,
    get_async_engine,
    get_db,
    get_session_factory,
    get_sync_engine,
    session_scope,
    sync_session_scope,
)

#: Historical alias — ``init_db`` used to create tables synchronously.
init_db = create_all

__all__ = [
    "Base",
    "metadata",
    "get_db",
    "session_scope",
    "sync_session_scope",
    "AsyncSessionLocal",
    "get_session_factory",
    "get_async_engine",
    "get_sync_engine",
    "create_all",
    "drop_all",
    "init_db",
    "dispose_engines",
    "check_database_health",
    "apply_migrations_if_needed",
]
