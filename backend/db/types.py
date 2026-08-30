"""Portable SQLAlchemy column types.

The production target is PostgreSQL, but the test-suite runs on SQLite
(in-memory / aiosqlite) so CI needs no database server. These ``TypeDecorator``
implementations pick the native PostgreSQL type when available and fall back to
a portable representation otherwise.

``EncryptedString`` additionally applies Fernet envelope encryption on write and
transparently decrypts on read, satisfying "encrypted at rest" for the specific
columns that carry direct identifiers (PRD §6.5.3).
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy import CHAR, JSON, String, Text, TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.engine import Dialect


class GUID(TypeDecorator):
    """UUID column: native ``uuid`` on PostgreSQL, ``CHAR(36)`` elsewhere."""

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect) -> Any:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value: Any, dialect: Dialect) -> Any:
        if value is None:
            return None
        if not isinstance(value, uuid.UUID):
            value = uuid.UUID(str(value))
        if dialect.name == "postgresql":
            return value
        return str(value)

    def process_result_value(self, value: Any, dialect: Dialect) -> Optional[uuid.UUID]:
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))


class JSONBType(TypeDecorator):
    """JSON column: ``JSONB`` on PostgreSQL, generic ``JSON`` elsewhere."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect) -> Any:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB(astext_type=Text()))
        return dialect.type_descriptor(JSON())


class EncryptedString(TypeDecorator):
    """Application-level encrypted text column.

    Values are stored as ``enc:v1:<fernet-token>``. Rows written before a key
    was provisioned remain readable because :meth:`FieldCipher.decrypt` passes
    through values without the prefix.
    """

    impl = String
    cache_ok = True

    def __init__(self, length: int = 512, **kwargs: Any) -> None:
        # Ciphertext is longer than plaintext; reserve headroom.
        super().__init__(length=length, **kwargs)

    def load_dialect_impl(self, dialect: Dialect) -> Any:
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value: Any, dialect: Dialect) -> Any:
        if value is None:
            return None
        from backend.core.crypto import get_cipher

        return get_cipher().encrypt(str(value))

    def process_result_value(self, value: Any, dialect: Dialect) -> Optional[str]:
        if value is None:
            return None
        from backend.core.crypto import get_cipher

        return get_cipher().decrypt(str(value))


__all__ = ["GUID", "JSONBType", "EncryptedString"]
