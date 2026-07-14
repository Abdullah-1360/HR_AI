"""
router/health.py
Circuit breaker + health tracking for model_health table.

Rules:
  - 3 consecutive failures → disabled_until = NOW() + backoff
  - Backoff: 30s → 2m → 5m → 15m (exponential, capped at 15m)
  - Success → reset consecutive_failures, update average_latency (EMA)
  - average_latency uses Exponential Moving Average (α = 0.2) for stability
"""

from __future__ import annotations

import logging
import math
from uuid import UUID

import asyncpg

logger = logging.getLogger(__name__)

# Circuit breaker thresholds
FAILURE_THRESHOLD = 3                   # failures before disabling
BACKOFF_SECONDS = [30, 120, 300, 900]   # 30s, 2m, 5m, 15m
EMA_ALPHA = 0.2                         # weight for new latency sample

_INIT_HEALTH_SQL = """
INSERT INTO model_health (model_id)
VALUES ($1)
ON CONFLICT (model_id) DO NOTHING
"""

_SUCCESS_SQL = """
UPDATE model_health
SET
    healthy              = true,
    consecutive_failures = 0,
    disabled_until       = NULL,
    last_success         = NOW(),
    average_latency      = CASE
                               WHEN average_latency IS NULL THEN $2::float8
                               ELSE average_latency * (1.0 - $3::float8) + $2::float8 * $3::float8
                           END,
    error_rate           = GREATEST(0.0, error_rate * 0.95),
    updated_at           = NOW()
WHERE model_id = $1
"""

_FAILURE_SQL = """
UPDATE model_health
SET
    last_failure         = NOW(),
    consecutive_failures = consecutive_failures + 1,
    error_rate           = LEAST(1.0, error_rate * 0.95 + 0.05),
    healthy              = CASE
                               WHEN consecutive_failures + 1 >= $2 THEN false
                               ELSE healthy
                           END,
    disabled_until       = CASE
                               WHEN consecutive_failures + 1 >= $2
                               THEN NOW() + ($3 * INTERVAL '1 second')
                               ELSE disabled_until
                           END,
    updated_at           = NOW()
WHERE model_id = $1
RETURNING consecutive_failures, healthy, disabled_until
"""

_RESET_HEALTH_SQL = """
UPDATE model_health
SET
    healthy              = true,
    consecutive_failures = 0,
    disabled_until       = NULL,
    error_rate           = 0.0,
    updated_at           = NOW()
WHERE model_id = $1
"""


def _backoff_seconds(consecutive_failures: int) -> int:
    """Return exponential backoff duration in seconds."""
    idx = min(consecutive_failures - FAILURE_THRESHOLD, len(BACKOFF_SECONDS) - 1)
    return BACKOFF_SECONDS[max(0, idx)]


async def ensure_health_record(pool: asyncpg.Pool, model_id: UUID) -> None:
    """Create a model_health row if one doesn't exist yet."""
    async with pool.acquire() as conn:
        await conn.execute(_INIT_HEALTH_SQL, model_id)


async def update_success(
    pool: asyncpg.Pool,
    model_id: UUID,
    latency_ms: float,
) -> None:
    """
    Record a successful request:
    - Reset consecutive_failures
    - Update average_latency via EMA
    - Decay error_rate
    """
    async with pool.acquire() as conn:
        await conn.execute(_SUCCESS_SQL, model_id, latency_ms, EMA_ALPHA)
    logger.debug("health.success model=%s latency=%.1fms", model_id, latency_ms)


async def update_failure(
    pool: asyncpg.Pool,
    model_id: UUID,
) -> None:
    """
    Record a failed request:
    - Increment consecutive_failures
    - If >= FAILURE_THRESHOLD: mark unhealthy and set disabled_until (circuit breaker)
    - Backoff is exponential based on how many times threshold has been exceeded
    """
    # First get current consecutive_failures to compute backoff
    async with pool.acquire() as conn:
        current = await conn.fetchval(
            "SELECT consecutive_failures FROM model_health WHERE model_id = $1",
            model_id,
        )
        if current is None:
            await conn.execute(_INIT_HEALTH_SQL, model_id)
            current = 0

        backoff = _backoff_seconds(current + 1)
        row = await conn.fetchrow(_FAILURE_SQL, model_id, FAILURE_THRESHOLD, backoff)

    if row:
        logger.warning(
            "health.failure model=%s consecutive=%d healthy=%s disabled_until=%s",
            model_id,
            row["consecutive_failures"],
            row["healthy"],
            row["disabled_until"],
        )
        if not row["healthy"]:
            logger.warning(
                "CIRCUIT BREAKER OPEN: model=%s disabled for %ds",
                model_id,
                backoff,
            )


async def reset_health(pool: asyncpg.Pool, model_id: UUID) -> None:
    """Manually reset health state (e.g. after admin intervention)."""
    async with pool.acquire() as conn:
        await conn.execute(_RESET_HEALTH_SQL, model_id)
    logger.info("health.reset model=%s", model_id)
