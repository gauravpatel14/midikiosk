"""Resilient async HTTP client shared by all outbound integrations.

Every external call (ABDM gateway, Bhashini/Dhruva, hospital HIS, Ollama,
triage SMS) goes through :class:`ResilientHttpClient`, which provides:

* a pooled, reused ``httpx.AsyncClient`` (TLS handshakes are expensive and the
  PRD budgets <5 s for a HIS push),
* exponential backoff with jitter on transport errors, 429 and 5xx,
* ``Retry-After`` support,
* a circuit breaker so a dead HIS endpoint stops blocking kiosk threads,
* structured logging with redaction and a per-attempt correlation id,
* typed :class:`~backend.core.exceptions.ExternalServiceError` on failure —
  never a silent ``None``.
"""

from __future__ import annotations

import asyncio
import random
import time
from typing import Any, Dict, Mapping, Optional

import httpx

from backend.core.config import settings
from backend.core.exceptions import ExternalServiceError
from backend.core.logging import get_correlation_id, get_logger

logger = get_logger(__name__)

RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}


class CircuitBreaker:
    """Minimal three-state breaker (closed -> open -> half-open)."""

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_seconds: float = 30.0,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_seconds = recovery_seconds
        self._failures = 0
        self._opened_at: Optional[float] = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> str:
        if self._opened_at is None:
            return "closed"
        if time.monotonic() - self._opened_at >= self.recovery_seconds:
            return "half_open"
        return "open"

    async def before_request(self) -> None:
        if self.state == "open":
            raise ExternalServiceError(
                self.name,
                f"{self.name} circuit breaker is open; upstream is failing",
                details={"circuit_state": "open", "failures": self._failures},
            )

    async def record_success(self) -> None:
        async with self._lock:
            if self._failures or self._opened_at:
                logger.info("circuit_closed", service=self.name)
            self._failures = 0
            self._opened_at = None

    async def record_failure(self) -> None:
        async with self._lock:
            self._failures += 1
            if self._failures >= self.failure_threshold and self._opened_at is None:
                self._opened_at = time.monotonic()
                logger.error(
                    "circuit_opened",
                    service=self.name,
                    failures=self._failures,
                    recovery_seconds=self.recovery_seconds,
                )
            elif self.state == "half_open":
                self._opened_at = time.monotonic()

    def snapshot(self) -> Dict[str, Any]:
        return {
            "service": self.name,
            "state": self.state,
            "failures": self._failures,
        }


class ResilientHttpClient:
    """Pooled HTTP client with retries and a circuit breaker per service."""

    _clients: Dict[str, "ResilientHttpClient"] = {}

    def __init__(
        self,
        service_name: str,
        base_url: str = "",
        *,
        timeout: float = 15.0,
        max_retries: int = 3,
        verify: bool = True,
        default_headers: Optional[Mapping[str, str]] = None,
        failure_threshold: int = 5,
        recovery_seconds: float = 30.0,
        max_connections: int = 50,
    ) -> None:
        self.service_name = service_name
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max(1, max_retries)
        self.default_headers = dict(default_headers or {})
        self.breaker = CircuitBreaker(service_name, failure_threshold, recovery_seconds)
        self._verify = verify
        self._limits = httpx.Limits(
            max_connections=max_connections, max_keepalive_connections=max_connections // 2 or 1
        )
        self._client: Optional[httpx.AsyncClient] = None
        self._client_lock = asyncio.Lock()

    # -- registry -------------------------------------------------------
    @classmethod
    def get(cls, service_name: str, **kwargs: Any) -> "ResilientHttpClient":
        """Return (and memoise) a client for ``service_name``."""
        existing = cls._clients.get(service_name)
        if existing is None:
            existing = cls(service_name, **kwargs)
            cls._clients[service_name] = existing
        return existing

    @classmethod
    async def close_all(cls) -> None:
        for client in list(cls._clients.values()):
            await client.aclose()
        cls._clients.clear()

    @classmethod
    def health_snapshot(cls) -> Dict[str, Any]:
        return {name: c.breaker.snapshot() for name, c in cls._clients.items()}

    # -- lifecycle ------------------------------------------------------
    async def _ensure_client(self) -> httpx.AsyncClient:
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if (
            self._client is not None
            and not self._client.is_closed
            and getattr(self, "_bound_loop", None) is current_loop
        ):
            return self._client

        kwargs: Dict[str, Any] = {
            "timeout": httpx.Timeout(self.timeout, connect=min(10.0, self.timeout)),
            "limits": self._limits,
            "verify": self._verify,
            "follow_redirects": True,
            "headers": {
                "User-Agent": f"MediKiosk/{settings.APP_VERSION} (+{settings.HOSPITAL_FACILITY_ID})",
                **self.default_headers,
            },
        }
        if self.base_url:
            kwargs["base_url"] = self.base_url
        self._client = httpx.AsyncClient(**kwargs)
        self._bound_loop = current_loop
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
        self._client = None

    # -- core request ---------------------------------------------------
    async def request(
        self,
        method: str,
        url: str,
        *,
        json_body: Any = None,
        content: Optional[bytes] = None,
        data: Any = None,
        params: Optional[Mapping[str, Any]] = None,
        headers: Optional[Mapping[str, str]] = None,
        timeout: Optional[float] = None,
        expected_status: Optional[set[int]] = None,
        retries: Optional[int] = None,
        raise_on_error: bool = True,
    ) -> httpx.Response:
        """Perform an HTTP request with retries and breaker protection."""
        await self.breaker.before_request()
        client = await self._ensure_client()
        attempts = retries if retries is not None else self.max_retries
        merged_headers: Dict[str, str] = dict(headers or {})
        cid = get_correlation_id()
        if cid:
            merged_headers.setdefault("X-Correlation-Id", cid)

        last_error: Optional[BaseException] = None
        last_response: Optional[httpx.Response] = None

        for attempt in range(1, attempts + 1):
            started = time.monotonic()
            try:
                response = await client.request(
                    method.upper(),
                    url,
                    json=json_body,
                    content=content,
                    data=data,
                    params=params,
                    headers=merged_headers,
                    timeout=timeout or self.timeout,
                )
                elapsed_ms = round((time.monotonic() - started) * 1000, 1)
                last_response = response

                ok = (
                    response.status_code in expected_status
                    if expected_status
                    else response.is_success
                )
                if ok:
                    await self.breaker.record_success()
                    logger.debug(
                        "http_request_ok",
                        service=self.service_name,
                        method=method.upper(),
                        url=str(response.request.url),
                        status=response.status_code,
                        elapsed_ms=elapsed_ms,
                        attempt=attempt,
                    )
                    return response

                retryable = response.status_code in RETRYABLE_STATUS
                logger.warning(
                    "http_request_error_status",
                    service=self.service_name,
                    method=method.upper(),
                    url=str(response.request.url),
                    status=response.status_code,
                    elapsed_ms=elapsed_ms,
                    attempt=attempt,
                    retryable=retryable,
                    body_preview=response.text[:300],
                )
                if not retryable or attempt >= attempts:
                    break
                await self._sleep_backoff(attempt, response)
            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPError) as exc:
                last_error = exc
                logger.warning(
                    "http_request_transport_error",
                    service=self.service_name,
                    method=method.upper(),
                    url=url,
                    attempt=attempt,
                    error=str(exc),
                )
                if attempt >= attempts:
                    break
                await self._sleep_backoff(attempt, None)

        await self.breaker.record_failure()

        if not raise_on_error and last_response is not None:
            return last_response

        if last_response is not None:
            raise ExternalServiceError(
                self.service_name,
                f"{self.service_name} responded with HTTP {last_response.status_code}",
                status=last_response.status_code,
                details={"body_preview": last_response.text[:500], "attempts": attempts},
            )
        raise ExternalServiceError(
            self.service_name,
            f"{self.service_name} is unreachable: {last_error}",
            details={"attempts": attempts},
            cause=last_error,
        )

    async def _sleep_backoff(self, attempt: int, response: Optional[httpx.Response]) -> None:
        delay = min(8.0, 0.4 * (2 ** (attempt - 1)))
        if response is not None:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    delay = min(30.0, float(retry_after))
                except ValueError:
                    pass
        delay += random.uniform(0, 0.25)  # jitter avoids kiosk thundering herd
        await asyncio.sleep(delay)

    # -- convenience ----------------------------------------------------
    async def get_json(self, url: str, **kwargs: Any) -> Any:
        response = await self.request("GET", url, **kwargs)
        return self._decode_json(response)

    async def post_json(self, url: str, json_body: Any = None, **kwargs: Any) -> Any:
        response = await self.request("POST", url, json_body=json_body, **kwargs)
        return self._decode_json(response)

    async def put_json(self, url: str, json_body: Any = None, **kwargs: Any) -> Any:
        response = await self.request("PUT", url, json_body=json_body, **kwargs)
        return self._decode_json(response)

    def _decode_json(self, response: httpx.Response) -> Any:
        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError as exc:
            raise ExternalServiceError(
                self.service_name,
                "Upstream returned a non-JSON response",
                status=response.status_code,
                details={"body_preview": response.text[:300]},
                cause=exc,
            ) from exc


__all__ = ["ResilientHttpClient", "CircuitBreaker", "RETRYABLE_STATUS"]
