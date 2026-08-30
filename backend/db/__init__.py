"""Database package: declarative base, async session management, types."""

from backend.db.base import Base, metadata, naming_convention
from backend.db.session import (
    AsyncSessionLocal,
    check_database_health,
    create_all,
    dispose_engines,
    get_async_engine,
    get_db,
    get_sync_engine,
    session_scope,
    sync_session_scope,
)
from backend.db.types import GUID, EncryptedString, JSONBType

__all__ = [
    "Base",
    "metadata",
    "naming_convention",
    "AsyncSessionLocal",
    "get_db",
    "session_scope",
    "sync_session_scope",
    "get_async_engine",
    "get_sync_engine",
    "create_all",
    "dispose_engines",
    "check_database_health",
    "GUID",
    "JSONBType",
    "EncryptedString",
]
