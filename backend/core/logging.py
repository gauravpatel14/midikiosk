"""Structured logging with request correlation and PII redaction.

Hospital deployments must keep 7 years of audit logs (PRD §7.4) while never
writing raw identifiers (Aadhaar, ABHA, phone numbers) into application logs.
This module wires ``structlog`` on top of the stdlib logger so:

* every log line carries the ``correlation_id`` of the originating request,
* Aadhaar / ABHA / phone / OTP values are masked by a processor before render,
* output is JSON in production (ready for Loki/ELK) and human readable locally.
"""

from __future__ import annotations

import logging
import logging.config
import re
import sys
import uuid
from contextvars import ContextVar
from typing import Any, Dict, MutableMapping, Optional

import structlog

from backend.core.config import settings

# ---------------------------------------------------------------------------
# Request-scoped context
# ---------------------------------------------------------------------------
_correlation_id: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)
_kiosk_id: ContextVar[Optional[str]] = ContextVar("kiosk_id", default=None)
_actor_id: ContextVar[Optional[str]] = ContextVar("actor_id", default=None)


def new_correlation_id() -> str:
    return uuid.uuid4().hex


def set_correlation_id(value: Optional[str]) -> str:
    cid = value or new_correlation_id()
    _correlation_id.set(cid)
    return cid


def get_correlation_id() -> Optional[str]:
    return _correlation_id.get()


def set_request_context(
    *, kiosk_id: Optional[str] = None, actor_id: Optional[str] = None
) -> None:
    if kiosk_id is not None:
        _kiosk_id.set(kiosk_id)
    if actor_id is not None:
        _actor_id.set(actor_id)


def clear_request_context() -> None:
    _correlation_id.set(None)
    _kiosk_id.set(None)
    _actor_id.set(None)


# ---------------------------------------------------------------------------
# PII redaction
# ---------------------------------------------------------------------------
_AADHAAR_RE = re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b")
_ABHA_NUM_RE = re.compile(r"\b\d{2}-\d{4}-\d{4}-\d{4}\b")
_PHONE_RE = re.compile(r"\b(?:\+?91[\s-]?)?[6-9]\d{9}\b")
_OTP_RE = re.compile(r"(?i)\b(otp|txncode|token)[\"'\s:=]+([A-Za-z0-9._\-]{4,})")
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b")

SENSITIVE_KEYS = {
    "aadhaar",
    "aadhaar_number",
    "aadhar",
    "otp",
    "otp_value",
    "password",
    "new_password",
    "current_password",
    "client_secret",
    "api_key",
    "secret",
    "shared_secret",
    "authorization",
    "access_token",
    "refresh_token",
    "token",
    "encrypted_aadhaar",
    "audio_content",
    "audiocontent",
    "raw_text",
    "data",
}


def mask_text(value: str) -> str:
    """Mask direct identifiers inside an arbitrary string."""
    masked = _ABHA_NUM_RE.sub("<abha-redacted>", value)
    masked = _AADHAAR_RE.sub("<aadhaar-redacted>", masked)
    masked = _PHONE_RE.sub("<phone-redacted>", masked)
    masked = _EMAIL_RE.sub("<email-redacted>", masked)
    masked = _OTP_RE.sub(lambda m: f"{m.group(1)}=<redacted>", masked)
    return masked


def mask_value(key: str, value: Any, _depth: int = 0) -> Any:
    if _depth > 6:
        return "<max-depth>"
    lowered = key.lower()
    if lowered in SENSITIVE_KEYS:
        return "<redacted>"
    if isinstance(value, str):
        if len(value) > 4096:
            return mask_text(value[:4096]) + "…<truncated>"
        return mask_text(value)
    if isinstance(value, dict):
        return {k: mask_value(k, v, _depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [mask_value(key, v, _depth + 1) for v in value]
    return value


def _redact_processor(
    _logger: Any, _name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    return {k: mask_value(k, v) for k, v in event_dict.items()}


def _context_processor(
    _logger: Any, _name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    cid = _correlation_id.get()
    if cid:
        event_dict.setdefault("correlation_id", cid)
    kiosk = _kiosk_id.get()
    if kiosk:
        event_dict.setdefault("kiosk_id", kiosk)
    actor = _actor_id.get()
    if actor:
        event_dict.setdefault("actor_id", actor)
    event_dict.setdefault("service", "medikiosk-backend")
    event_dict.setdefault("env", settings.ENV)
    return event_dict


def _safe_add_logger_name(
    logger_obj: Any, name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    event_dict["logger"] = getattr(logger_obj, "name", None) or event_dict.get("logger") or "medikiosk"
    return event_dict


_CONFIGURED = False


def configure_logging(force: bool = False) -> None:
    """Idempotently configure stdlib + structlog pipelines."""
    global _CONFIGURED
    if _CONFIGURED and not force:
        return

    level = getattr(logging, settings.LOG_LEVEL, logging.INFO)

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        _safe_add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        _context_processor,
        _redact_processor,
    ]

    renderer = (
        structlog.processors.JSONRenderer()
        if settings.LOG_JSON
        else structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())
    )

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
        force=True,
    )
    # Third-party loggers that are noisy at INFO.
    for noisy in ("httpx", "httpcore", "urllib3", "asyncio", "PIL"):
        logging.getLogger(noisy).setLevel(max(level, logging.WARNING))
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.SQL_ECHO else logging.WARNING
    )

    _CONFIGURED = True


def get_logger(name: Optional[str] = None) -> Any:
    """Return a bound structlog logger."""
    configure_logging()
    return structlog.get_logger(name or "medikiosk")


def log_context(**kwargs: Any) -> Dict[str, Any]:
    """Convenience helper returning a redacted keyword dict for one-off logs."""
    return {k: mask_value(k, v) for k, v in kwargs.items()}


__all__ = [
    "configure_logging",
    "get_logger",
    "get_correlation_id",
    "set_correlation_id",
    "new_correlation_id",
    "set_request_context",
    "clear_request_context",
    "mask_text",
    "mask_value",
    "log_context",
]
