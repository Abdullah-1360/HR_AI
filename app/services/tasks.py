"""
app/services/tasks.py
Asynchronous background task processing and status tracking for heavy AI operations
(resume parsing, text extraction, vector embedding, and database ingestion).
"""
import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# In-memory status store for async jobs (can be backed by Redis / DB in production)
TASK_STORE: Dict[str, Dict[str, Any]] = {}


def create_task_record(task_type: str, tenant_id: str = "default") -> str:
    """Initialize a new background task tracking record."""
    task_id = str(uuid.uuid4())
    TASK_STORE[task_id] = {
        "task_id": task_id,
        "type": task_type,
        "status": "pending",
        "progress": 0,
        "message": "Task queued for processing",
        "result": None,
        "error": None,
        "tenant_id": tenant_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    return task_id


def update_task_progress(
    task_id: str,
    status: str,
    progress: int,
    message: str,
    result: Optional[Any] = None,
    error: Optional[str] = None,
) -> None:
    """Update progress and status of a background task."""
    if task_id in TASK_STORE:
        TASK_STORE[task_id].update({
            "status": status,
            "progress": min(100, max(0, progress)),
            "message": message,
            "result": result or TASK_STORE[task_id]["result"],
            "error": error or TASK_STORE[task_id]["error"],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })


def get_task_status(task_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve status of a background task."""
    return TASK_STORE.get(task_id)


async def async_parse_and_ingest_resume(
    task_id: str,
    file_bytes: bytes,
    filename: str,
    tenant_id: str = "default",
) -> None:
    """
    Background worker process for resume parsing, embedding, and storage.
    """
    try:
        update_task_progress(task_id, "processing", 10, "Extracting text from PDF...")
        await asyncio.sleep(0.1)

        from app.db.pool import get_pool
        from app.services.candidate_service import process_candidate_resume

        pool = await get_pool()

        update_task_progress(task_id, "processing", 40, "Running AI Resume Agent parsing...")
        candidate = await process_candidate_resume(
            pool=pool,
            file_bytes=file_bytes,
            filename=filename,
            tenant_id=tenant_id,
        )

        update_task_progress(
            task_id,
            status="completed",
            progress=100,
            message="Resume parsed and indexed successfully!",
            result={"candidate_id": candidate.id, "name": candidate.name},
        )
        logger.info("tasks.async_ingest_success task_id=%s candidate_id=%s", task_id, candidate.id)

    except Exception as exc:
        logger.error("tasks.async_ingest_failed task_id=%s error=%s", task_id, exc)
        update_task_progress(
            task_id,
            status="failed",
            progress=0,
            message=f"Failed to process resume: {str(exc)}",
            error=str(exc),
        )
