"""Distributed Scheduler Lock for Multi-Worker Uvicorn Deployment.

Ensures only a single APScheduler instance executes retention and cleanup jobs
across multiple processes using Redis distributed locks (with TTL) or POSIX
file locks via fcntl.
"""

from __future__ import annotations

import os
import time
import uuid
from typing import Optional

from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger(__name__)


class SchedulerLock:
    """Manages cross-worker mutual exclusion for APScheduler."""

    def __init__(
        self,
        lock_file: str = "/tmp/medikiosk_scheduler.lock",
        ttl_seconds: int = 60,
        lock_key: str = "medikiosk:scheduler:leader_lock",
    ) -> None:
        self.lock_file = lock_file
        self.ttl_seconds = ttl_seconds
        self.lock_key = lock_key
        self.lock_id = str(uuid.uuid4())
        self.is_acquired = False
        self._file_fd: Optional[int] = None
        self._backend: str = "none"
        self._redis_client = None

    def acquire(self) -> bool:
        """Attempt to acquire either Redis distributed lock or file lock."""
        # 1. Try Redis if configured and enabled
        if getattr(settings, "REDIS_URL", None) and getattr(settings, "REDIS_ENABLED", True):
            try:
                import redis
                client = redis.Redis.from_url(
                    settings.REDIS_URL,
                    socket_connect_timeout=0.5,
                    socket_timeout=0.5,
                )
                client.ping()
                # Acquire with NX and EX TTL
                acquired = client.set(
                    name=self.lock_key,
                    value=self.lock_id,
                    nx=True,
                    ex=self.ttl_seconds,
                )
                if acquired:
                    self._redis_client = client
                    self._backend = "redis"
                    self.is_acquired = True
                    logger.info("scheduler_lock_acquired_redis", lock_key=self.lock_key, lock_id=self.lock_id)
                    return True
                else:
                    logger.info("scheduler_lock_busy_redis", lock_key=self.lock_key)
                    return False
            except Exception as exc:
                logger.warning("scheduler_lock_redis_failed_falling_back_to_file", error=str(exc))

        # 2. Fallback to file-based lock via fcntl
        try:
            import fcntl
            fd = os.open(self.lock_file, os.O_CREAT | os.O_RDWR, 0o666)
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._file_fd = fd
            self._backend = "file"
            self.is_acquired = True
            logger.info("scheduler_lock_acquired_file", lock_file=self.lock_file, fd=fd)
            return True
        except (BlockingIOError, OSError, IOError) as exc:
            logger.info("scheduler_lock_busy_file", lock_file=self.lock_file, reason=str(exc))
            return False

    def renew(self) -> bool:
        """Renew active lock TTL."""
        if not self.is_acquired:
            return False

        if self._backend == "redis" and self._redis_client is not None:
            try:
                val = self._redis_client.get(self.lock_key)
                val_str = val.decode("utf-8") if isinstance(val, (bytes, bytearray)) else (val or "")
                if val_str == self.lock_id:
                    self._redis_client.expire(self.lock_key, self.ttl_seconds)
                    return True
                else:
                    self.is_acquired = False
                    return False
            except Exception as exc:
                logger.warning("scheduler_lock_renew_redis_failed", error=str(exc))
                self.is_acquired = False
                return False

        elif self._backend == "file":
            return self._file_fd is not None

        return False

    def release(self) -> None:
        """Release held lock."""
        if not self.is_acquired:
            return

        if self._backend == "redis" and self._redis_client is not None:
            try:
                val = self._redis_client.get(self.lock_key)
                val_str = val.decode("utf-8") if isinstance(val, (bytes, bytearray)) else (val or "")
                if val_str == self.lock_id:
                    self._redis_client.delete(self.lock_key)
            except Exception as exc:
                logger.warning("scheduler_lock_release_redis_error", error=str(exc))
            finally:
                self.is_acquired = False

        elif self._backend == "file" and self._file_fd is not None:
            try:
                import fcntl
                fcntl.flock(self._file_fd, fcntl.LOCK_UN)
                os.close(self._file_fd)
            except Exception as exc:
                logger.warning("scheduler_lock_release_file_error", error=str(exc))
            finally:
                self._file_fd = None
                self.is_acquired = False

        logger.info("scheduler_lock_released", backend=self._backend)

    def __enter__(self) -> "SchedulerLock":
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()
