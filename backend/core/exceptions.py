"""Typed exception hierarchy mapped onto HTTP responses.

Every service raises a :class:`MediKioskError` subclass instead of returning
``None`` on failure. ``backend.main`` installs a single exception handler that
converts these into RFC-7807-style JSON problem documents with a correlation id
so hospital IT can trace an incident from a kiosk screenshot to a log line.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class MediKioskError(Exception):
    """Base class for all deliberate application errors."""

    status_code: int = 500
    error_code: str = "internal_error"
    #: Safe, patient-facing message. Never contains PII or stack details.
    default_message: str = "An internal error occurred."

    def __init__(
        self,
        message: Optional[str] = None,
        *,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        self.message = message or self.default_message
        self.details = details or {}
        self.cause = cause
        super().__init__(self.message)

    def to_dict(self, correlation_id: Optional[str] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "error": self.error_code,
            "message": self.message,
        }
        if self.details:
            payload["details"] = self.details
        if correlation_id:
            payload["correlation_id"] = correlation_id
        return payload


class ConfigurationError(MediKioskError):
    status_code = 500
    error_code = "configuration_error"
    default_message = "The service is misconfigured. Contact hospital IT."


class ValidationError(MediKioskError):
    status_code = 422
    error_code = "validation_error"
    default_message = "The submitted data is invalid."


class NotFoundError(MediKioskError):
    status_code = 404
    error_code = "not_found"
    default_message = "The requested record does not exist."


class ConflictError(MediKioskError):
    status_code = 409
    error_code = "conflict"
    default_message = "The record already exists or is in a conflicting state."


class AuthenticationError(MediKioskError):
    status_code = 401
    error_code = "authentication_failed"
    default_message = "Authentication is required."


class AuthorizationError(MediKioskError):
    status_code = 403
    error_code = "authorization_failed"
    default_message = "You are not permitted to perform this action."


class ConsentRequiredError(MediKioskError):
    """Raised when a DPDP-relevant operation lacks a valid consent artefact."""

    status_code = 403
    error_code = "consent_required"
    default_message = "Patient consent has not been granted for this operation."


class RateLimitError(MediKioskError):
    status_code = 429
    error_code = "rate_limited"
    default_message = "Too many requests. Please retry shortly."


class ExternalServiceError(MediKioskError):
    """A dependency (ABDM, Bhashini, HIS, Ollama) returned an error."""

    status_code = 502
    error_code = "external_service_error"
    default_message = "An upstream service returned an error."

    def __init__(
        self,
        service: str,
        message: Optional[str] = None,
        *,
        status: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        merged = {"service": service}
        if status is not None:
            merged["upstream_status"] = status
        if details:
            merged.update(details)
        self.service = service
        self.upstream_status = status
        super().__init__(message or f"{service} request failed.", details=merged, cause=cause)


class ServiceUnavailableError(MediKioskError):
    """A required local subsystem (model, engine, socket) is not available."""

    status_code = 503
    error_code = "service_unavailable"
    default_message = "A required subsystem is currently unavailable."


class DocumentProcessingError(MediKioskError):
    status_code = 422
    error_code = "document_processing_failed"
    default_message = "The uploaded document could not be processed."


class SpeechProcessingError(MediKioskError):
    status_code = 422
    error_code = "speech_processing_failed"
    default_message = "The audio could not be processed."


__all__ = [
    "MediKioskError",
    "ConfigurationError",
    "ValidationError",
    "NotFoundError",
    "ConflictError",
    "AuthenticationError",
    "AuthorizationError",
    "ConsentRequiredError",
    "RateLimitError",
    "ExternalServiceError",
    "ServiceUnavailableError",
    "DocumentProcessingError",
    "SpeechProcessingError",
]
