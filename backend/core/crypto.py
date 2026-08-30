"""Application-level cryptography for MediKiosk.

The PRD (§6.5.3, §7.4) requires AES-256 at rest and forbids storing raw
Aadhaar numbers. PostgreSQL TDE (or LUKS at the volume level) protects the
whole datafile, but that does not protect against a compromised read-replica
credential or a leaked backup. So identifying columns are *additionally*
encrypted in the application layer before they reach the database.

Primitives
----------
``FieldCipher``
    Fernet (AES-128-CBC + HMAC-SHA256) envelope with multi-key support so keys
    can be rotated without a downtime migration: new writes use the primary
    key, reads transparently try previous keys.
``hash_aadhaar``
    Irreversible SHA-256 tokenisation with a dedicated pepper. Used as a
    lookup key so a patient can be re-identified across visits without the
    number ever being recoverable.
``password hashing``
    bcrypt via passlib with an explicit 12-round cost.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime
from typing import Any, Iterable, List, Optional

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from passlib.context import CryptContext

from backend.core.config import settings
from backend.core.exceptions import ConfigurationError
from backend.core.logging import get_logger

logger = get_logger(__name__)

ENCRYPTED_PREFIX = "enc:v1:"

_pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,
)


# ---------------------------------------------------------------------------
# Field-level encryption
# ---------------------------------------------------------------------------
class FieldCipher:
    """Encrypt/decrypt short PII strings with rotation support."""

    def __init__(
        self,
        primary_key: Optional[str] = None,
        previous_keys: Optional[Iterable[str]] = None,
    ) -> None:
        primary = (primary_key if primary_key is not None else settings.FIELD_ENCRYPTION_KEY).strip()
        previous_raw = (
            list(previous_keys)
            if previous_keys is not None
            else [
                k.strip()
                for k in settings.FIELD_ENCRYPTION_KEY_PREVIOUS.split(",")
                if k.strip()
            ]
        )
        self._enabled = bool(primary)
        self._fernet: Optional[MultiFernet] = None

        if self._enabled:
            keys: List[Fernet] = []
            for raw in [primary, *previous_raw]:
                keys.append(Fernet(self._coerce_key(raw)))
            self._fernet = MultiFernet(keys)
        elif settings.is_production:
            raise ConfigurationError(
                "FIELD_ENCRYPTION_KEY must be configured before serving traffic"
            )
        else:
            logger.warning(
                "field_encryption_disabled",
                reason="FIELD_ENCRYPTION_KEY not set; PII stored in plaintext",
                env=settings.ENV,
            )

    @staticmethod
    def _coerce_key(raw: str) -> bytes:
        """Accept a Fernet key, or derive one deterministically from a passphrase."""
        candidate = raw.encode("utf-8")
        try:
            if len(base64.urlsafe_b64decode(candidate)) == 32:
                return candidate
        except Exception:  # noqa: BLE001 - not a base64 Fernet key, derive below
            pass
        digest = hashlib.sha256(candidate).digest()
        return base64.urlsafe_b64encode(digest)

    @property
    def enabled(self) -> bool:
        return self._enabled

    def encrypt(self, plaintext: Optional[str]) -> Optional[str]:
        if plaintext is None or plaintext == "":
            return plaintext
        if not self._fernet:
            return plaintext
        token = self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")
        return f"{ENCRYPTED_PREFIX}{token}"

    def decrypt(self, ciphertext: Optional[str]) -> Optional[str]:
        if ciphertext is None or ciphertext == "":
            return ciphertext
        if not ciphertext.startswith(ENCRYPTED_PREFIX):
            # Value written before encryption was enabled — return as-is so
            # rollout is non-breaking.
            return ciphertext
        if not self._fernet:
            logger.error("field_decrypt_without_key")
            return None
        token = ciphertext[len(ENCRYPTED_PREFIX) :].encode("ascii")
        try:
            return self._fernet.decrypt(token).decode("utf-8")
        except InvalidToken:
            logger.error("field_decrypt_invalid_token")
            return None

    def rotate(self, ciphertext: Optional[str]) -> Optional[str]:
        """Re-encrypt an existing token under the current primary key."""
        if not ciphertext or not ciphertext.startswith(ENCRYPTED_PREFIX) or not self._fernet:
            return ciphertext
        token = ciphertext[len(ENCRYPTED_PREFIX) :].encode("ascii")
        try:
            return f"{ENCRYPTED_PREFIX}{self._fernet.rotate(token).decode('ascii')}"
        except InvalidToken:
            logger.error("field_rotate_invalid_token")
            return ciphertext

    def encrypt_json(self, payload: Any) -> Optional[str]:
        if payload is None:
            return None
        return self.encrypt(json.dumps(payload, default=str, separators=(",", ":")))

    def decrypt_json(self, ciphertext: Optional[str]) -> Any:
        raw = self.decrypt(ciphertext)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None


_cipher: Optional[FieldCipher] = None


def get_cipher() -> FieldCipher:
    global _cipher
    if _cipher is None:
        _cipher = FieldCipher()
    return _cipher


def encrypt_field(value: Optional[str]) -> Optional[str]:
    return get_cipher().encrypt(value)


def decrypt_field(value: Optional[str]) -> Optional[str]:
    return get_cipher().decrypt(value)


# ---------------------------------------------------------------------------
# Irreversible tokenisation
# ---------------------------------------------------------------------------
def normalise_aadhaar(aadhaar: str) -> str:
    digits = "".join(ch for ch in str(aadhaar) if ch.isdigit())
    if len(digits) != 12:
        raise ValueError("Aadhaar must contain exactly 12 digits")
    if settings.ENV not in ("test", "testing", "dev", "development", "local") and settings.ABDM_ENVIRONMENT != "sandbox":
        if not verhoeff_validate(digits):
            raise ValueError("Aadhaar failed Verhoeff checksum validation")
    return digits


def hash_aadhaar(aadhaar: str, *, validate: bool = True) -> str:
    """Return a stable, irreversible lookup token for an Aadhaar number."""
    digits = (
        normalise_aadhaar(aadhaar)
        if validate
        else "".join(ch for ch in str(aadhaar) if ch.isdigit())
    )
    return hmac.new(
        settings.AADHAAR_HASH_PEPPER.encode("utf-8"),
        digits.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def hash_identifier(value: str, *, namespace: str = "generic") -> str:
    """Peppered hash for non-Aadhaar identifiers (phone, ABHA address)."""
    return hmac.new(
        settings.AADHAAR_HASH_PEPPER.encode("utf-8"),
        f"{namespace}:{value.strip().lower()}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


# ---------------------------------------------------------------------------
# Verhoeff checksum (UIDAI Aadhaar validation)
# ---------------------------------------------------------------------------
_VERHOEFF_D = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 2, 3, 4, 0, 6, 7, 8, 9, 5),
    (2, 3, 4, 0, 1, 7, 8, 9, 5, 6),
    (3, 4, 0, 1, 2, 8, 9, 5, 6, 7),
    (4, 0, 1, 2, 3, 9, 5, 6, 7, 8),
    (5, 9, 8, 7, 6, 0, 4, 3, 2, 1),
    (6, 5, 9, 8, 7, 1, 0, 4, 3, 2),
    (7, 6, 5, 9, 8, 2, 1, 0, 4, 3),
    (8, 7, 6, 5, 9, 3, 2, 1, 0, 4),
    (9, 8, 7, 6, 5, 4, 3, 2, 1, 0),
)
_VERHOEFF_P = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 5, 7, 6, 2, 8, 3, 0, 9, 4),
    (5, 8, 0, 3, 7, 9, 6, 1, 4, 2),
    (8, 9, 1, 6, 0, 4, 3, 5, 2, 7),
    (9, 4, 5, 3, 1, 2, 6, 8, 7, 0),
    (4, 2, 8, 6, 5, 7, 3, 9, 0, 1),
    (2, 7, 9, 3, 8, 0, 6, 4, 1, 5),
    (7, 0, 4, 6, 9, 1, 3, 2, 5, 8),
)
_VERHOEFF_INV = (0, 4, 3, 2, 1, 5, 6, 7, 8, 9)


def verhoeff_validate(number: str) -> bool:
    """Validate a numeric string against the Verhoeff checksum used by UIDAI."""
    if not number.isdigit():
        return False
    check = 0
    for i, digit in enumerate(reversed(number)):
        check = _VERHOEFF_D[check][_VERHOEFF_P[i % 8][int(digit)]]
    return check == 0


def verhoeff_checksum(partial: str) -> int:
    """Compute the trailing Verhoeff check digit for an 11-digit prefix."""
    check = 0
    for i, digit in enumerate(reversed(partial + "0")):
        check = _VERHOEFF_D[check][_VERHOEFF_P[i % 8][int(digit)]]
    return _VERHOEFF_INV[check]


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    if len(password) < settings.PASSWORD_MIN_LENGTH:
        raise ValueError(
            f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters"
        )
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    if not password or not password_hash:
        return False
    try:
        return _pwd_context.verify(password, password_hash)
    except Exception:  # noqa: BLE001 - malformed stored hash
        logger.warning("password_hash_verify_failed")
        return False


def needs_password_rehash(password_hash: str) -> bool:
    try:
        return _pwd_context.needs_update(password_hash)
    except Exception:  # noqa: BLE001
        return True


# ---------------------------------------------------------------------------
# Integrity helpers
# ---------------------------------------------------------------------------
def compute_consent_hash(
    patient_id: str,
    granted_at: datetime,
    version: str,
    v_and_t: bool,
    ocr: bool,
    emr: bool,
    phr: bool,
    *,
    kiosk_id: str = "",
) -> str:
    """Tamper-evident SHA-256 digest of a consent artefact (PRD §6.5.1)."""
    payload = "|".join(
        [
            patient_id,
            granted_at.isoformat(),
            version,
            str(bool(v_and_t)),
            str(bool(ocr)),
            str(bool(emr)),
            str(bool(phr)),
            kiosk_id,
        ]
    )
    return hmac.new(
        settings.JWT_SECRET_KEY.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def file_sha256(path: str, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bytes_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def hmac_sign(payload: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def hmac_verify(payload: bytes, secret: str, signature: str) -> bool:
    expected = hmac_sign(payload, secret)
    return hmac.compare_digest(expected, (signature or "").strip().lower())


def generate_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def generate_numeric_code(digits: int = 6) -> str:
    return "".join(secrets.choice("0123456789") for _ in range(digits))


__all__ = [
    "FieldCipher",
    "get_cipher",
    "encrypt_field",
    "decrypt_field",
    "hash_aadhaar",
    "hash_identifier",
    "normalise_aadhaar",
    "verhoeff_validate",
    "verhoeff_checksum",
    "hash_password",
    "verify_password",
    "needs_password_rehash",
    "compute_consent_hash",
    "file_sha256",
    "bytes_sha256",
    "hmac_sign",
    "hmac_verify",
    "generate_token",
    "generate_numeric_code",
    "ENCRYPTED_PREFIX",
]
