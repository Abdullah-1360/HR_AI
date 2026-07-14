"""
router/logger.py
Structured JSON logging for every LLM request.

Writes to:
  1. request_log PostgreSQL table (persistent analytics)
  2. stdout as JSON lines (for log aggregators / dev inspection)

JSON log format:
  {
    "ts": "2026-07-14T10:00:00Z",
    "uuid": "...",
    "provider": "gemini",
    "model": "gemini-2.5-flash",
    "tier": "PRIMARY_FREE",
    "status": "success",
    "attempt": 1,
    "prompt_tokens": 150,
    "completion_tokens": 300,
    "total_tokens": 450,
    "latency_ms": 820,
    "ttft_ms": 120,
    "http_status": 200
  }
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from uuid import UUID
from typing import Optional

import asyncpg

_sql_logger = logging.getLogger("router.logger")

_INSERT_SQL = """
INSERT INTO request_log (
    request_uuid, provider_id, model_id, status,
    prompt_tokens, completion_tokens, total_tokens,
    latency_ms, ttft_ms, http_status, error_message, attempt
) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
"""


async def log_request(
    pool: asyncpg.Pool,
    *,
    request_uuid: UUID,
    provider_id: UUID,
    model_id: UUID,
    provider_name: str,
    model_name: str,
    tier: str,
    status: str,                    # "success" | "failure" | "retry"
    attempt: int = 1,
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
    latency_ms: Optional[int] = None,
    ttft_ms: Optional[int] = None,
    http_status: Optional[int] = None,
    error_message: Optional[str] = None,
) -> None:
    """
    Persist a request log entry to PostgreSQL AND emit a JSON log line to stdout.
    Non-blocking: DB errors are caught and logged but never crash the router.
    """
    total_tokens = None
    if prompt_tokens is not None and completion_tokens is not None:
        total_tokens = prompt_tokens + completion_tokens

    # 1. Emit structured JSON to stdout
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "uuid": str(request_uuid),
        "provider": provider_name,
        "model": model_name,
        "tier": tier,
        "status": status,
        "attempt": attempt,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "latency_ms": latency_ms,
        "ttft_ms": ttft_ms,
        "http_status": http_status,
        "error": error_message,
    }
    # Remove None values for cleaner output
    record = {k: v for k, v in record.items() if v is not None}
    print(json.dumps(record), flush=True)

    # 2. Persist to DB (best-effort)
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                _INSERT_SQL,
                request_uuid,
                provider_id,
                model_id,
                status,
                prompt_tokens,
                completion_tokens,
                total_tokens,
                latency_ms,
                ttft_ms,
                http_status,
                error_message,
                attempt,
            )
    except Exception as exc:
        _sql_logger.error("Failed to persist request_log: %s", exc)
