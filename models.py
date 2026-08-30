import sys
import backend.models
from backend.models import (
    AuditLog,
    Consent,
    Document,
    DocumentType,
    ExtractedEntity,
    HistorySession,
    Patient,
    RedFlag,
    RedFlagSeverity,
    Summary,
    User,
)

sys.modules[__name__] = backend.models

__all__ = [
    "AuditLog",
    "Consent",
    "Document",
    "DocumentType",
    "ExtractedEntity",
    "HistorySession",
    "Patient",
    "RedFlag",
    "RedFlagSeverity",
    "Summary",
    "User",
]
