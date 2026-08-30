"""Async cache layer with Redis primary and in-process fallback.

Cached objects (PRD §7.1 performance budgets):

* language packs / question banks — avoids re-reading and re-localising the
  ontology on every kiosk turn,
* ABDM gateway access tokens — the gateway rate-limits ``/sessions``,
* Bhashini pipeline configuration — a slow ULCA call that changes rarely,
* dialogue session state — so a kiosk can resume after a process restart and so
  multiple backend replicas share one session (PRD §6.1 session persistence).

If Redis is unreachable the layer degrades to a bounded in-process TTL dict
rather than failing the request: kiosks must keep working during a Redis blip.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple, TypeVar

from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")

try:  # pragma: no cover - import guard
    from redis import asyncio as aioredis

    REDIS_AVAILABLE = True
except Exception:  # noqa: BLE001 - redis is optional at runtime
    aioredis = None  # type: ignore[assignment]
    REDIS_AVAILABLE = False


class _MemoryCache:
    """Bounded TTL dictionary used when Redis is unavailable."""

    def __init__(self, max_entries: int = 5000) -> None:
        self._store: Dict[str, Tuple[float, str]] = {}
        self._max = max_entries
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[str]:
        async with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None
            expires_at, value = entry
            if expires_at and expires_at < time.time():
                self._store.pop(key, None)
                return None
            return value

    async def set(self, key: str, value: str, ttl: Optional[int]) -> None:
        async with self._lock:
            if len(self._store) >= self._max:
                # Evict the soonest-to-expire entries (cheap approximation of LRU).
                for stale_key in sorted(self._store, key=lambda k: self._store[k][0])[
                    : max(1, self._max // 10)
                ]:
                    self._store.pop(stale_key, None)
            self._store[key] = (time.time() + ttl if ttl else 0.0, value)

    async def delete(self, *keys: str) -> int:
        async with self._lock:
            removed = 0
            for key in keys:
                if self._store.pop(key, None) is not None:
                    removed += 1
            return removed

    async def clear_prefix(self, prefix: str) -> int:
        async with self._lock:
            targets = [k for k in self._store if k.startswith(prefix)]
            for key in targets:
                self._store.pop(key, None)
            return len(targets)

    async def incr(self, key: str, ttl: Optional[int]) -> int:
        async with self._lock:
            entry = self._store.get(key)
            current = 0
            if entry and (not entry[0] or entry[0] >= time.time()):
                try:
                    current = int(entry[1])
                except ValueError:
                    current = 0
            current += 1
            expires = entry[0] if entry and entry[0] else (time.time() + ttl if ttl else 0.0)
            self._store[key] = (expires, str(current))
            return current


class CacheService:
    """Namespaced JSON cache with Redis primary + memory fallback."""

    def __init__(self) -> None:
        self._redis: Any = None
        self._memory = _MemoryCache()
        self._namespace = settings.CACHE_NAMESPACE
        self._redis_healthy = False
        self._connect_lock = asyncio.Lock()

    # -- lifecycle ------------------------------------------------------
    async def connect(self) -> None:
        if not settings.REDIS_ENABLED or not REDIS_AVAILABLE:
            logger.info(
                "cache_using_memory_backend",
                redis_enabled=settings.REDIS_ENABLED,
                redis_installed=REDIS_AVAILABLE,
            )
            return
        async with self._connect_lock:
            if self._redis_healthy:
                return
            try:
                self._redis = aioredis.from_url(
                    settings.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=3,
                    socket_timeout=3,
                    health_check_interval=30,
                    retry_on_timeout=True,
                )
                await self._redis.ping()
                self._redis_healthy = True
                logger.info("cache_redis_connected", url=settings.REDIS_URL.split("@")[-1])
            except Exception as exc:  # noqa: BLE001
                self._redis = None
                self._redis_healthy = False
                logger.warning("cache_redis_unavailable", error=str(exc))

    async def close(self) -> None:
        if self._redis is not None:
            try:
                await self._redis.aclose()
            except Exception:  # noqa: BLE001
                pass
            self._redis = None
            self._redis_healthy = False

    async def ping(self) -> bool:
        if self._redis is None:
            return False
        try:
            await self._redis.ping()
            self._redis_healthy = True
            return True
        except Exception:  # noqa: BLE001
            self._redis_healthy = False
            return False

    @property
    def backend(self) -> str:
        return "redis" if self._redis_healthy else "memory"

    # -- key helpers ----------------------------------------------------
    def _key(self, key: str) -> str:
        return f"{self._namespace}:{key}"

    # -- primitives -----------------------------------------------------
    async def get(self, key: str) -> Optional[Any]:
        namespaced = self._key(key)
        raw: Optional[str] = None
        if self._redis_healthy and self._redis is not None:
            try:
                raw = await self._redis.get(namespaced)
            except Exception as exc:  # noqa: BLE001
                logger.warning("cache_get_failed", key=key, error=str(exc))
                self._redis_healthy = False
        if raw is None:
            raw = await self._memory.get(namespaced)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        namespaced = self._key(key)
        ttl = settings.CACHE_TTL_SECONDS if ttl is None else ttl
        payload = json.dumps(value, default=str, separators=(",", ":"))
        stored = False
        if self._redis_healthy and self._redis is not None:
            try:
                if ttl and ttl > 0:
                    await self._redis.set(namespaced, payload, ex=ttl)
                else:
                    await self._redis.set(namespaced, payload)
                stored = True
            except Exception as exc:  # noqa: BLE001
                logger.warning("cache_set_failed", key=key, error=str(exc))
                self._redis_healthy = False
        # Always mirror into memory so a Redis outage keeps hot data available.
        await self._memory.set(namespaced, payload, ttl)
        if not stored:
            logger.debug("cache_set_memory_only", key=key)

    async def delete(self, *keys: str) -> int:
        namespaced = [self._key(k) for k in keys]
        removed = 0
        if self._redis_healthy and self._redis is not None:
            try:
                removed = await self._redis.delete(*namespaced)
            except Exception as exc:  # noqa: BLE001
                logger.warning("cache_delete_failed", error=str(exc))
                self._redis_healthy = False
        removed = max(removed, await self._memory.delete(*namespaced))
        return removed

    async def clear_prefix(self, prefix: str) -> int:
        pattern = self._key(prefix)
        removed = 0
        if self._redis_healthy and self._redis is not None:
            try:
                async for found in self._redis.scan_iter(match=f"{pattern}*", count=500):
                    await self._redis.delete(found)
                    removed += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("cache_clear_prefix_failed", error=str(exc))
                self._redis_healthy = False
        removed += await self._memory.clear_prefix(pattern)
        return removed

    async def get_or_set(
        self,
        key: str,
        factory: Callable[[], Awaitable[T]],
        ttl: Optional[int] = None,
    ) -> T:
        """Return a cached value or compute, store and return it."""
        cached = await self.get(key)
        if cached is not None:
            return cached  # type: ignore[return-value]
        value = await factory()
        if value is not None:
            await self.set(key, value, ttl)
        return value

    async def increment(self, key: str, ttl: Optional[int] = None) -> int:
        """Atomic counter used by the rate limiter and login-attempt guard."""
        namespaced = self._key(key)
        if self._redis_healthy and self._redis is not None:
            try:
                pipe = self._redis.pipeline()
                pipe.incr(namespaced, 1)
                if ttl:
                    pipe.expire(namespaced, ttl, nx=True)
                results = await pipe.execute()
                return int(results[0])
            except Exception as exc:  # noqa: BLE001
                logger.warning("cache_incr_failed", error=str(exc))
                self._redis_healthy = False
        return await self._memory.incr(namespaced, ttl)


cache = CacheService()


__all__ = ["CacheService", "cache", "REDIS_AVAILABLE"]
