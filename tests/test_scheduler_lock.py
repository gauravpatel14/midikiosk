"""Test Distributed Scheduler Lock for APScheduler Multi-Worker Redundancy."""

import multiprocessing
import os
import tempfile
from pathlib import Path
import pytest

from backend.services.scheduler_lock import SchedulerLock


def _try_acquire_in_subprocess(lock_file: str, queue: multiprocessing.Queue):
    """Attempt to acquire lock inside an isolated subprocess."""
    lock = SchedulerLock(lock_file=lock_file)
    success = lock.acquire()
    queue.put(success)
    if success:
        lock.release()


def test_file_lock_mutual_exclusion_between_processes():
    """Verify that when one worker holds the lock, a second worker process cannot acquire it."""
    with tempfile.NamedTemporaryFile(suffix=".lock", delete=False) as f:
        lock_file = f.name

    try:
        # Worker 1 acquires lock
        worker1_lock = SchedulerLock(lock_file=lock_file)
        acquired1 = worker1_lock.acquire()
        assert acquired1 is True
        assert worker1_lock.is_acquired is True

        # Worker 2 in a separate process tries to acquire the same lock
        q = multiprocessing.Queue()
        p = multiprocessing.Process(target=_try_acquire_in_subprocess, args=(lock_file, q))
        p.start()
        p.join(timeout=5)

        acquired2 = q.get(timeout=2)
        assert acquired2 is False, "Worker 2 in child process should NOT acquire lock while Worker 1 holds it"

        # Worker 1 releases lock
        worker1_lock.release()
        assert worker1_lock.is_acquired is False

        # Now Worker 3 in separate process attempts and should succeed
        p2 = multiprocessing.Process(target=_try_acquire_in_subprocess, args=(lock_file, q))
        p2.start()
        p2.join(timeout=5)

        acquired3 = q.get(timeout=2)
        assert acquired3 is True, "Worker 3 should successfully acquire lock after Worker 1 releases it"
    finally:
        Path(lock_file).unlink(missing_ok=True)


def test_scheduler_lock_renew():
    """Verify that an acquired file lock renew returns True, and unacquired returns False."""
    with tempfile.NamedTemporaryFile(suffix=".lock", delete=False) as f:
        lock_file = f.name

    try:
        lock = SchedulerLock(lock_file=lock_file)
        assert lock.renew() is False

        lock.acquire()
        assert lock.renew() is True

        lock.release()
        assert lock.renew() is False
    finally:
        Path(lock_file).unlink(missing_ok=True)


def test_scheduler_lock_context_manager():
    """Verify context manager acquisition and release semantics."""
    with tempfile.NamedTemporaryFile(suffix=".lock", delete=False) as f:
        lock_file = f.name

    try:
        with SchedulerLock(lock_file=lock_file) as lock:
            assert lock.is_acquired is True
        assert lock.is_acquired is False
    finally:
        Path(lock_file).unlink(missing_ok=True)
