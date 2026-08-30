"""Declarative base with deterministic constraint naming.

Alembic autogenerate produces unstable migration diffs when constraints are
unnamed, so an explicit naming convention is mandatory for a system that will
be upgraded in place on hospital servers for years.
"""

from __future__ import annotations

from typing import Any, Dict

from sqlalchemy import MetaData
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase


# ---------------------------------------------------------------------------
# SQLite compatibility shims.
# Production runs on PostgreSQL; the test-suite and the offline kiosk cache run
# on SQLite, which has no native JSONB/UUID. These compilers let a single set
# of models target both without conditional column definitions.
# ---------------------------------------------------------------------------
@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):  # pragma: no cover
    return "JSON"


@compiles(UUID, "sqlite")
def _compile_uuid_sqlite(type_, compiler, **kw):  # pragma: no cover
    return "CHAR(36)"

naming_convention: Dict[str, str] = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=naming_convention)


class Base(DeclarativeBase):
    """Base declarative class for every MediKiosk ORM model."""

    metadata = metadata

    def to_dict(self, exclude: set[str] | None = None) -> Dict[str, Any]:
        """Shallow column dict, used for audit-log before/after snapshots."""
        exclude = exclude or set()
        result: Dict[str, Any] = {}
        for column in self.__table__.columns:  # type: ignore[attr-defined]
            if column.name in exclude:
                continue
            value = getattr(self, column.name, None)
            result[column.name] = value
        return result

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        pk = getattr(self, "id", None)
        return f"<{type(self).__name__} id={pk}>"


__all__ = ["Base", "metadata", "naming_convention"]
