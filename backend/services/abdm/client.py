"""ABDM gateway client: OAuth2 sessions, request signing and payload crypto.

Reference behaviour implemented here (ABDM M1/M2/M3 specifications):

* ``POST {gateway}/v0.5/sessions`` with ``clientId`` / ``clientSecret`` returns
  a bearer ``accessToken`` valid for ``expiresIn`` seconds. The token is cached
  in Redis (shared across backend replicas) and refreshed with a safety leeway.
* Every gateway call carries ``REQUEST-ID`` (UUID v4), ``TIMESTAMP``
  (RFC-3339 UTC) and ``X-CM-ID`` headers. HIP-scoped calls additionally carry
  ``X-HIP-ID``.
* Aadhaar numbers and OTP values must be RSA-OAEP/PKCS1v15 encrypted with the
  ABDM public certificate before transmission — raw values never leave the
  process in cleartext.

Everything degrades explicitly: if ABDM is not configured the service raises
:class:`ExternalServiceError` instead of silently returning fabricated data, so
a kiosk shows "ABHA lookup unavailable — continue as walk-in" rather than
inventing a patient identity.
"""

from __future__ import annotations

import base64
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from backend.core.cache import cache
from backend.core.config import settings
from backend.core.exceptions import ConfigurationError, ExternalServiceError
from backend.core.http import ResilientHttpClient
from backend.core.logging import get_logger

logger = get_logger(__name__)

TOKEN_CACHE_KEY = "abdm:gateway:token"
PUBLIC_KEY_CACHE_KEY = "abdm:gateway:public_key"


def utc_timestamp() -> str:
    """ABDM expects ``2026-08-29T10:15:30.123Z``."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


class AbdmClient:
    """Low-level authenticated transport for all ABDM APIs."""

    def __init__(self) -> None:
        self._http = ResilientHttpClient.get(
            "abdm-gateway",
            timeout=settings.ABDM_REQUEST_TIMEOUT,
            max_retries=settings.ABDM_MAX_RETRIES,
            failure_threshold=5,
            recovery_seconds=45.0,
        )
        self._public_key: Optional[rsa.RSAPublicKey] = None

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    @property
    def enabled(self) -> bool:
        return settings.abdm_configured

    def _require_enabled(self) -> None:
        if not self.enabled:
            raise ConfigurationError(
                "ABDM integration is not configured. Set ABDM_CLIENT_ID and "
                "ABDM_CLIENT_SECRET (and ABDM_ENVIRONMENT) to enable ABHA features.",
                details={
                    "abdm_enabled": settings.ABDM_ENABLED,
                    "offline_mode": settings.OFFLINE_MODE,
                },
            )

    # ------------------------------------------------------------------
    # Session token
    # ------------------------------------------------------------------
    async def get_access_token(self, *, force_refresh: bool = False) -> str:
        """Return a valid gateway bearer token, refreshing when needed."""
        self._require_enabled()

        if not force_refresh:
            cached = await cache.get(TOKEN_CACHE_KEY)
            if isinstance(cached, dict) and cached.get("access_token"):
                return str(cached["access_token"])

        url = f"{settings.ABDM_GATEWAY_URL}/v0.5/sessions"
        payload = {
            "clientId": settings.ABDM_CLIENT_ID,
            "clientSecret": settings.ABDM_CLIENT_SECRET,
            "grantType": "client_credentials",
        }
        data = await self._http.post_json(
            url,
            json_body=payload,
            headers={
                "Content-Type": "application/json",
                "X-CM-ID": settings.ABDM_CM_ID,
                "REQUEST-ID": str(uuid.uuid4()),
                "TIMESTAMP": utc_timestamp(),
            },
        )

        token = data.get("accessToken") or data.get("access_token")
        if not token:
            raise ExternalServiceError(
                "abdm-gateway",
                "Gateway session response did not contain an access token",
                details={"keys": sorted(data.keys()) if isinstance(data, dict) else []},
            )

        expires_in = int(data.get("expiresIn") or data.get("expires_in") or 1800)
        ttl = max(60, expires_in - settings.ABDM_TOKEN_LEEWAY_SECONDS)
        await cache.set(
            TOKEN_CACHE_KEY,
            {"access_token": token, "token_type": data.get("tokenType", "bearer")},
            ttl,
        )
        logger.info("abdm_token_acquired", expires_in=expires_in, cache_ttl=ttl)
        return str(token)

    async def invalidate_token(self) -> None:
        await cache.delete(TOKEN_CACHE_KEY)

    # ------------------------------------------------------------------
    # Request helpers
    # ------------------------------------------------------------------
    def build_headers(
        self,
        token: str,
        *,
        include_hip: bool = False,
        extra: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "REQUEST-ID": str(uuid.uuid4()),
            "TIMESTAMP": utc_timestamp(),
            "X-CM-ID": settings.ABDM_CM_ID,
        }
        if include_hip:
            headers["X-HIP-ID"] = settings.ABDM_HIP_ID
        if extra:
            headers.update(extra)
        return headers

    async def request(
        self,
        method: str,
        url: str,
        *,
        json_body: Any = None,
        params: Optional[Dict[str, Any]] = None,
        include_hip: bool = False,
        extra_headers: Optional[Dict[str, str]] = None,
        expected_status: Optional[set[int]] = None,
    ) -> Any:
        """Authenticated ABDM call with one automatic retry on 401."""
        self._require_enabled()
        token = await self.get_access_token()
        headers = self.build_headers(token, include_hip=include_hip, extra=extra_headers)

        response = await self._http.request(
            method,
            url,
            json_body=json_body,
            params=params,
            headers=headers,
            expected_status=expected_status,
            raise_on_error=False,
        )

        if response.status_code == 401:
            logger.info("abdm_token_expired_retrying")
            token = await self.get_access_token(force_refresh=True)
            headers = self.build_headers(token, include_hip=include_hip, extra=extra_headers)
            response = await self._http.request(
                method,
                url,
                json_body=json_body,
                params=params,
                headers=headers,
                expected_status=expected_status,
                raise_on_error=False,
            )

        acceptable = expected_status or {200, 201, 202, 204}
        if response.status_code not in acceptable and not response.is_success:
            raise ExternalServiceError(
                "abdm-gateway",
                self._extract_error_message(response),
                status=response.status_code,
                details={"url": url},
            )

        if response.status_code == 204 or not response.content:
            return {}
        try:
            return response.json()
        except ValueError:
            return {"raw": response.text}

    @staticmethod
    def _extract_error_message(response: Any) -> str:
        try:
            body = response.json()
        except Exception:  # noqa: BLE001
            return f"ABDM returned HTTP {response.status_code}"
        if isinstance(body, dict):
            for key in ("message", "error", "details"):
                value = body.get(key)
                if isinstance(value, str) and value:
                    return value
                if isinstance(value, list) and value:
                    first = value[0]
                    if isinstance(first, dict) and first.get("message"):
                        return str(first["message"])
            if isinstance(body.get("error"), dict):
                return str(body["error"].get("message", "ABDM request failed"))
        return f"ABDM returned HTTP {response.status_code}"

    # ------------------------------------------------------------------
    # Aadhaar / OTP payload encryption
    # ------------------------------------------------------------------
    async def _load_public_key(self) -> rsa.RSAPublicKey:
        if self._public_key is not None:
            return self._public_key

        pem: Optional[str] = settings.ABDM_PUBLIC_KEY_PEM or None
        if not pem:
            cached = await cache.get(PUBLIC_KEY_CACHE_KEY)
            if isinstance(cached, str) and cached:
                pem = cached

        if not pem:
            # ABDM exposes the certificate on an unauthenticated endpoint.
            response = await self._http.request(
                "GET",
                settings.ABDM_PUBLIC_KEY_URL,
                headers={"Accept": "text/plain"},
            )
            pem = response.text.strip()
            if pem:
                await cache.set(PUBLIC_KEY_CACHE_KEY, pem, 86400)

        if not pem:
            raise ConfigurationError(
                "ABDM public certificate unavailable; set ABDM_PUBLIC_KEY_PEM"
            )

        pem_body = pem.strip()
        if "BEGIN" not in pem_body:
            pem_body = (
                "-----BEGIN PUBLIC KEY-----\n"
                + "\n".join(pem_body[i : i + 64] for i in range(0, len(pem_body), 64))
                + "\n-----END PUBLIC KEY-----\n"
            )

        loaded = serialization.load_pem_public_key(pem_body.encode("utf-8"))
        if not isinstance(loaded, rsa.RSAPublicKey):
            raise ConfigurationError("ABDM certificate is not an RSA public key")
        self._public_key = loaded
        return loaded

    async def encrypt_sensitive(self, value: str) -> str:
        """RSA-encrypt an Aadhaar number / OTP for transport to ABDM."""
        key = await self._load_public_key()
        raw = value.encode("utf-8")
        try:
            cipher = key.encrypt(
                raw,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA1()),
                    algorithm=hashes.SHA1(),
                    label=None,
                ),
            )
        except Exception:  # noqa: BLE001 - fall back to PKCS1v15 for older certs
            cipher = key.encrypt(raw, padding.PKCS1v15())
        return base64.b64encode(cipher).decode("ascii")

    async def health(self) -> Dict[str, Any]:
        """Non-throwing health probe surfaced on ``/health/ready``."""
        state = {
            "configured": self.enabled,
            "environment": settings.ABDM_ENVIRONMENT,
            "circuit": self._http.breaker.snapshot(),
        }
        if not self.enabled:
            state["status"] = "disabled"
            return state
        try:
            await self.get_access_token()
            state["status"] = "ok"
        except Exception as exc:  # noqa: BLE001
            state["status"] = "degraded"
            state["error"] = str(exc)
        return state


abdm_client = AbdmClient()

__all__ = ["AbdmClient", "abdm_client", "utc_timestamp"]
