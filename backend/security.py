"""Authentication, authorisation and audit primitives.

Implements PRD §6.5.3 / §7.4:

* OAuth2 password flow for staff (physician / nurse / admin) with **access +
  refresh** tokens, JTI tracking and Redis-backed revocation.
* Separate short-lived kiosk tokens bound to a kiosk id and shared secret.
* Role-based access control via :func:`require_roles` dependencies.
* Login throttling (``MAX_LOGIN_ATTEMPTS`` per ``LOGIN_LOCKOUT_MINUTES``).
* An append-only audit writer used by every mutating endpoint.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence

import jwt
from fastapi import Depends, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.cache import cache
from backend.core.config import settings
from backend.core.crypto import (  # re-exported for backwards compatibility
    compute_consent_hash,
    generate_token,
    hash_aadhaar,
    hash_password,
    needs_password_rehash,
    verify_password,
)
from backend.core.exceptions import AuthenticationError, AuthorizationError
from backend.core.logging import get_logger, set_request_context
from backend.db.session import get_db

logger = get_logger(__name__)

bearer_scheme = HTTPBearer(auto_error=False)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/staff/login", auto_error=False)

TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"
TOKEN_TYPE_KIOSK = "kiosk"

#: Coarse capability groups referenced by routers.
ROLE_CLINICAL = ("PHYSICIAN", "AYUSH_PRACTITIONER")
ROLE_TRIAGE = ("TRIAGE_NURSE", "KIOSK_ASSISTANT", "PHYSICIAN", "AYUSH_PRACTITIONER", "ADMINISTRATOR")
ROLE_ADMIN = ("ADMINISTRATOR",)
ROLE_AUDIT = ("ADMINISTRATOR", "AUDITOR")


# ---------------------------------------------------------------------------
# Token issuing
# ---------------------------------------------------------------------------
def _encode(payload: Dict[str, Any]) -> str:
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def _base_claims(subject: str, token_type: str, expires_in: timedelta) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    return {
        "sub": subject,
        "typ": token_type,
        "jti": uuid.uuid4().hex,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "iat": now,
        "nbf": now,
        "exp": now + expires_in,
    }


def create_access_token(
    subject: str,
    *,
    role: str,
    claims: Optional[Dict[str, Any]] = None,
    expires_in: Optional[timedelta] = None,
) -> str:
    payload = _base_claims(
        subject,
        TOKEN_TYPE_ACCESS,
        expires_in or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    payload["role"] = role
    if claims:
        payload.update(claims)
    return _encode(payload)


def create_refresh_token(subject: str, *, role: str) -> str:
    payload = _base_claims(
        subject, TOKEN_TYPE_REFRESH, timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )
    payload["role"] = role
    return _encode(payload)


def create_kiosk_access_token(
    kiosk_id: str,
    additional_claims: Optional[Dict[str, Any]] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Issue a kiosk-scoped token (station identity, not a human user)."""
    payload = _base_claims(
        f"kiosk:{kiosk_id}",
        TOKEN_TYPE_KIOSK,
        expires_delta or timedelta(minutes=settings.KIOSK_TOKEN_EXPIRE_MINUTES),
    )
    payload["kiosk_id"] = kiosk_id
    payload["role"] = "KIOSK"
    if additional_claims:
        payload.update(additional_claims)
    return _encode(payload)


def decode_token(token: str, *, expected_type: Optional[str] = None) -> Dict[str, Any]:
    """Verify signature, issuer, audience, expiry and token type."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            issuer=settings.JWT_ISSUER,
            audience=settings.JWT_AUDIENCE,
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Session has expired. Please authenticate again.") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError(f"Invalid authentication token: {exc}") from exc

    if expected_type and payload.get("typ") != expected_type:
        raise AuthenticationError(
            f"Expected a {expected_type} token but received {payload.get('typ')!r}"
        )
    return payload


# ---------------------------------------------------------------------------
# Revocation (logout / compromised token)
# ---------------------------------------------------------------------------
def _revocation_key(jti: str) -> str:
    return f"auth:revoked:{jti}"


async def revoke_token(payload: Dict[str, Any]) -> None:
    jti = payload.get("jti")
    if not jti:
        return
    exp = payload.get("exp")
    ttl = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
    if isinstance(exp, (int, float)):
        ttl = max(60, int(exp - datetime.now(timezone.utc).timestamp()))
    await cache.set(_revocation_key(str(jti)), {"revoked_at": datetime.now(timezone.utc).isoformat()}, ttl)


async def is_token_revoked(payload: Dict[str, Any]) -> bool:
    jti = payload.get("jti")
    if not jti:
        return False
    return await cache.get(_revocation_key(str(jti))) is not None


# ---------------------------------------------------------------------------
# Login throttling
# ---------------------------------------------------------------------------
async def register_failed_login(identifier: str) -> int:
    key = f"auth:login_fail:{identifier.lower()}"
    return await cache.increment(key, settings.LOGIN_LOCKOUT_MINUTES * 60)


async def clear_failed_logins(identifier: str) -> None:
    await cache.delete(f"auth:login_fail:{identifier.lower()}")


async def assert_not_locked_out(identifier: str) -> None:
    attempts = await cache.get(f"auth:login_fail:{identifier.lower()}")
    try:
        count = int(attempts) if attempts is not None else 0
    except (TypeError, ValueError):
        count = 0
    if count >= settings.MAX_LOGIN_ATTEMPTS:
        raise AuthenticationError(
            "Account temporarily locked after repeated failed logins. "
            f"Retry in {settings.LOGIN_LOCKOUT_MINUTES} minutes."
        )


# ---------------------------------------------------------------------------
# Principals
# ---------------------------------------------------------------------------
class Principal:
    """Authenticated caller: either a staff user or a kiosk station."""

    __slots__ = ("subject", "role", "kiosk_id", "user_id", "claims", "token_type")

    def __init__(self, payload: Dict[str, Any]) -> None:
        self.claims = payload
        self.subject = str(payload.get("sub", ""))
        self.role = str(payload.get("role", "UNKNOWN")).upper()
        self.token_type = str(payload.get("typ", ""))
        self.kiosk_id = payload.get("kiosk_id")
        self.user_id: Optional[uuid.UUID] = None
        if self.token_type == TOKEN_TYPE_ACCESS:
            try:
                self.user_id = uuid.UUID(self.subject)
            except (ValueError, TypeError):
                self.user_id = None

    @property
    def is_kiosk(self) -> bool:
        return self.token_type == TOKEN_TYPE_KIOSK

    def has_role(self, roles: Sequence[str]) -> bool:
        return self.role in {r.upper() for r in roles}

    def describe(self) -> Dict[str, Any]:
        return {"subject": self.subject, "role": self.role, "kiosk_id": self.kiosk_id}


async def _extract_token(
    credentials: Optional[HTTPAuthorizationCredentials],
    oauth_token: Optional[str],
) -> str:
    token = credentials.credentials if credentials else oauth_token
    if not token:
        raise AuthenticationError("Missing Authorization Bearer token")
    return token


async def get_principal(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    oauth_token: Optional[str] = Depends(oauth2_scheme),
) -> Principal:
    """Authenticate any caller (kiosk or staff) and populate log context."""
    token = await _extract_token(credentials, oauth_token)
    payload = decode_token(token)
    if payload.get("typ") == TOKEN_TYPE_REFRESH:
        raise AuthenticationError("Refresh tokens cannot be used to call the API")
    if await is_token_revoked(payload):
        raise AuthenticationError("This session has been revoked")

    principal = Principal(payload)
    set_request_context(kiosk_id=principal.kiosk_id, actor_id=principal.subject)
    request.state.principal = principal
    return principal


async def verify_kiosk_token(
    principal: Principal = Depends(get_principal),
) -> Dict[str, Any]:
    """Dependency for kiosk-facing endpoints.

    Staff tokens are also accepted so a nurse can drive a kiosk flow from the
    triage dashboard during assisted registration.
    """
    if not principal.is_kiosk and not principal.has_role(ROLE_TRIAGE):
        raise AuthorizationError("This endpoint requires a kiosk or clinical staff token")
    return principal.claims


def require_roles(*roles: str):
    """Build a dependency enforcing that the caller holds one of ``roles``."""
    allowed = {r.upper() for r in roles}

    async def _dependency(principal: Principal = Depends(get_principal)) -> Principal:
        if principal.role not in allowed:
            logger.warning(
                "rbac_denied",
                required=sorted(allowed),
                actual=principal.role,
                subject=principal.subject,
            )
            raise AuthorizationError(
                f"Role {principal.role} is not permitted; requires one of {sorted(allowed)}"
            )
        return principal

    return _dependency


require_clinician = require_roles(*ROLE_CLINICAL)
require_triage = require_roles(*ROLE_TRIAGE)
require_admin = require_roles(*ROLE_ADMIN)
require_auditor = require_roles(*ROLE_AUDIT)


async def authenticate_staff(
    db: AsyncSession, username: str, password: str
) -> "Any":
    """Validate staff credentials, applying lockout and rehash-on-login."""
    from backend.models import User  # local import avoids a cycle

    identifier = username.strip().lower()
    await assert_not_locked_out(identifier)

    result = await db.execute(
        select(User).where((User.username == identifier) | (User.email == identifier))
    )
    user = result.scalar_one_or_none()

    if user is None or not verify_password(password, user.password_hash):
        attempts = await register_failed_login(identifier)
        logger.warning("staff_login_failed", identifier=identifier, attempts=attempts)
        raise AuthenticationError("Invalid username or password")

    if not user.is_active:
        raise AuthenticationError("This account has been deactivated")

    if needs_password_rehash(user.password_hash):
        user.password_hash = hash_password(password)

    user.last_login_at = datetime.now(timezone.utc)
    user.failed_login_count = 0
    await clear_failed_logins(identifier)
    return user


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------
async def write_audit(
    db: AsyncSession,
    *,
    action: str,
    entity_name: str,
    entity_id: Optional[str] = None,
    patient_id: Optional[uuid.UUID] = None,
    session_id: Optional[uuid.UUID] = None,
    user_id: Optional[uuid.UUID] = None,
    kiosk_id: Optional[str] = None,
    request: Optional[Request] = None,
    previous_state: Optional[Dict[str, Any]] = None,
    new_state: Optional[Dict[str, Any]] = None,
    flush: bool = True,
) -> None:
    """Append an immutable audit record (retained 7 years per PRD §7.4)."""
    from backend.core.logging import get_correlation_id, mask_value
    from backend.models import AuditLog

    ip_address = None
    user_agent = None
    if request is not None:
        client = request.client
        ip_address = request.headers.get("x-forwarded-for", client.host if client else None)
        if ip_address:
            ip_address = ip_address.split(",")[0].strip()[:45]
        user_agent = (request.headers.get("user-agent") or "")[:255] or None

    entry = AuditLog(
        id=uuid.uuid4(),
        user_id=user_id,
        patient_id=patient_id,
        session_id=session_id,
        action=action,
        entity_name=entity_name,
        entity_id=entity_id,
        kiosk_id=kiosk_id,
        ip_address=ip_address,
        user_agent=user_agent,
        correlation_id=get_correlation_id(),
        previous_state={k: mask_value(k, v) for k, v in previous_state.items()}
        if previous_state
        else None,
        new_state={k: mask_value(k, v) for k, v in new_state.items()} if new_state else None,
        timestamp=datetime.now(timezone.utc),
    )
    db.add(entry)
    if flush:
        await db.flush()
    logger.info("audit", action=action, entity=entity_name, entity_id=entity_id or "")


def principal_audit_fields(principal: Optional[Principal]) -> Dict[str, Any]:
    """Extract ``user_id`` / ``kiosk_id`` audit fields from a principal."""
    if principal is None:
        return {}
    return {"user_id": principal.user_id, "kiosk_id": principal.kiosk_id}


__all__ = [
    "Principal",
    "bearer_scheme",
    "oauth2_scheme",
    "TOKEN_TYPE_ACCESS",
    "TOKEN_TYPE_REFRESH",
    "TOKEN_TYPE_KIOSK",
    "ROLE_CLINICAL",
    "ROLE_TRIAGE",
    "ROLE_ADMIN",
    "ROLE_AUDIT",
    "create_access_token",
    "create_refresh_token",
    "create_kiosk_access_token",
    "decode_token",
    "revoke_token",
    "is_token_revoked",
    "get_principal",
    "verify_kiosk_token",
    "require_roles",
    "require_clinician",
    "require_triage",
    "require_admin",
    "require_auditor",
    "authenticate_staff",
    "write_audit",
    "principal_audit_fields",
    "hash_password",
    "verify_password",
    "hash_aadhaar",
    "compute_consent_hash",
    "generate_token",
    "get_db",
]
