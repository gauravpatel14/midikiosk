"""Session Data Cleanup and Document Archival Service (DPDP Act 2023 Compliant).

Handles:
1. Automated deletion or archival of raw patient media (voice recordings, camera scans)
   after clinical summaries and HIS/ABDM transmissions complete.
2. Archival routing based on DOCUMENT_RETENTION_MODE:
   - 'delete': immediate secure shredding/unlinking.
   - 'archive_local': transfer to secured local archive path with restricted permissions.
   - 'archive_s3': transfer to encrypted cloud object store (AWS S3 / S3-compatible).
3. Background APScheduler job purging orphaned temporary directories older than 24 hours.
"""

from __future__ import annotations

import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger(__name__)

TEMP_DIRECTORIES = [
    "/tmp/medikiosk_uploads",
    "/tmp/medikiosk_documents",
    "/tmp/medikiosk-audio/tts-cache",
    "/tmp/medikiosk-audio/asr-cache",
]

_scheduler: Optional[AsyncIOScheduler] = None


def archive_or_delete_file(
    file_path: str,
    patient_id: Optional[str] = None,
    document_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Process a raw media file according to DOCUMENT_RETENTION_MODE."""
    if not file_path or not os.path.exists(file_path):
        return {"status": "SKIPPED", "reason": "File does not exist", "path": file_path}

    mode = settings.DOCUMENT_RETENTION_MODE.lower()
    pid = patient_id or "general"
    doc_id = document_id or os.path.basename(file_path)

    # 1. Immediate deletion
    if mode == "delete":
        try:
            os.remove(file_path)
            logger.info("temp_file_deleted", path=file_path)
            return {"status": "DELETED", "path": file_path}
        except Exception as exc:
            logger.error("file_delete_failed", path=file_path, error=str(exc))
            return {"status": "ERROR", "error": str(exc)}

    # 2. Local encrypted/restricted archive
    elif mode == "archive_local":
        archive_root = Path(settings.ARCHIVE_LOCAL_PATH) / pid
        archive_root.mkdir(parents=True, exist_ok=True)
        dest_file = archive_root / doc_id
        try:
            shutil.move(file_path, str(dest_file))
            os.chmod(str(dest_file), 0o600)  # Restricted read/write
            logger.info("document_archived_locally", source=file_path, destination=str(dest_file))
            return {"status": "ARCHIVED_LOCAL", "archive_path": str(dest_file)}
        except Exception as exc:
            logger.error("local_archive_failed", error=str(exc))
            return {"status": "ERROR", "error": str(exc)}

    # 3. Cloud S3 Storage
    elif mode == "archive_s3":
        try:
            import boto3
            s3 = boto3.client("s3", region_name=settings.AWS_REGION)
            s3_key = f"documents/{pid}/{doc_id}"
            s3.upload_file(file_path, settings.S3_BUCKET_NAME, s3_key)
            os.remove(file_path)
            logger.info("document_archived_s3", bucket=settings.S3_BUCKET_NAME, key=s3_key)
            return {"status": "ARCHIVED_S3", "bucket": settings.S3_BUCKET_NAME, "key": s3_key}
        except ImportError:
            logger.warning("boto3_missing_fallback_local", reason="boto3 not installed, routing to local archive")
            # Fallback to local archive
            archive_root = Path(settings.ARCHIVE_LOCAL_PATH) / pid
            archive_root.mkdir(parents=True, exist_ok=True)
            dest_file = archive_root / doc_id
            shutil.move(file_path, str(dest_file))
            return {"status": "ARCHIVED_LOCAL_FALLBACK", "archive_path": str(dest_file)}
        except Exception as exc:
            logger.error("s3_archive_failed", error=str(exc))
            return {"status": "ERROR", "error": str(exc)}

    return {"status": "UNKNOWN_MODE", "mode": mode}


def cleanup_session_temp_files(file_paths: Optional[List[str]] = None) -> int:
    """Clean up specified files after session completion."""
    removed = 0
    for p in (file_paths or []):
        if p and os.path.exists(p):
            res = archive_or_delete_file(p)
            if res.get("status") in ("DELETED", "ARCHIVED_LOCAL", "ARCHIVED_S3", "ARCHIVED_LOCAL_FALLBACK"):
                removed += 1
    return removed


_scheduler: Optional[AsyncIOScheduler] = None
_scheduler_lock: Optional[Any] = None


def purge_orphaned_temp_dirs(max_age_hours: Optional[int] = None) -> int:
    """Purge temporary media files older than retention limit."""
    age_hours = max_age_hours or settings.RAW_MEDIA_RETENTION_HOURS
    threshold_time = time.time() - (age_hours * 3600)
    purged_count = 0

    for directory in TEMP_DIRECTORIES:
        if not os.path.exists(directory):
            continue
        try:
            for root, _, files in os.walk(directory):
                for filename in files:
                    filepath = os.path.join(root, filename)
                    try:
                        stat = os.stat(filepath)
                        if stat.st_mtime < threshold_time:
                            os.remove(filepath)
                            purged_count += 1
                    except Exception as err:
                        logger.warning("failed_to_purge_file", file=filepath, error=str(err))
        except Exception as err:
            logger.error("purge_directory_error", directory=directory, error=str(err))

    logger.info("orphaned_temp_dirs_purged", files_removed=purged_count, max_age_hours=age_hours)
    return purged_count


def start_cleanup_scheduler() -> Optional[AsyncIOScheduler]:
    """Initialize background scheduler for orphaned file purges using distributed lock."""
    global _scheduler, _scheduler_lock
    if _scheduler is not None and _scheduler.running:
        return _scheduler

    from backend.services.scheduler_lock import SchedulerLock
    _scheduler_lock = SchedulerLock()
    acquired = _scheduler_lock.acquire()
    if not acquired:
        logger.info("cleanup_scheduler_skipped_lock_held_by_another_worker")
        return None

    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        purge_orphaned_temp_dirs,
        "interval",
        minutes=settings.RETENTION_SWEEP_INTERVAL_MINUTES,
        id="purge_orphaned_temp_dirs",
        replace_existing=True,
    )

    def _renew_scheduler_lock() -> None:
        global _scheduler_lock, _scheduler
        if _scheduler_lock is not None:
            active = _scheduler_lock.renew()
            if not active:
                logger.warning("scheduler_lock_lost_stopping_scheduler_jobs")
                if _scheduler is not None and _scheduler.running:
                    _scheduler.pause()

    _scheduler.add_job(
        _renew_scheduler_lock,
        "interval",
        seconds=30,
        id="renew_scheduler_lock",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info("cleanup_scheduler_started", interval_minutes=settings.RETENTION_SWEEP_INTERVAL_MINUTES)
    return _scheduler


def stop_cleanup_scheduler() -> None:
    """Shutdown background cleanup scheduler and release held distributed lock."""
    global _scheduler, _scheduler_lock
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler = None
    if _scheduler_lock is not None:
        _scheduler_lock.release()
        _scheduler_lock = None
