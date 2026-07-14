"""
router/reservation.py
Quota reservation using SELECT FOR UPDATE SKIP LOCKED.

Flow:
  1. reserve()   — atomically grab quota headroom; returns reservation_id or None
  2. confirm()   — on success: move reserved → used, actual tokens committed
  3. release()   — on failure: subtract reserved amount back
  4. expire_stale() — background cleanup of timed-out reservations
"""

from __future__ import annotations
import logging
from uuid import UUID, uuid4
from typing import Optional
from datetime import datetime, timezone, timedelta
import asyncpg

logger = logging.getLogger(__name__)

def _window_bounds(window: str) -> tuple[datetime, datetime]:
    """Return (window_start, window_end) for the current period of the given window."""
    now = datetime.now(timezone.utc)

    if window == "SECOND":
        start = now.replace(microsecond=0)
        end = start + timedelta(seconds=1)
    elif window == "MINUTE":
        start = now.replace(second=0, microsecond=0)
        end = start + timedelta(minutes=1)
    elif window == "HOUR":
        start = now.replace(minute=0, second=0, microsecond=0)
        end = start + timedelta(hours=1)
    elif window == "DAY":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
    elif window == "MONTH":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if now.month == 12:
            end = start.replace(year=now.year + 1, month=1)
        else:
            end = start.replace(month=now.month + 1)
    else:  # LIFETIME, CUSTOM
        start = now
        end = now.replace(year=now.year + 10)

    return start, end

async def ensure_active_windows(conn: asyncpg.Connection):
    """Find all active quota_definitions that don't have a current quota_usage row and insert them."""
    rows = await conn.fetch("""
        SELECT qd.id, qd.quota_window
        FROM quota_definitions qd
        LEFT JOIN quota_usage qu ON qu.quota_definition_id = qd.id AND qu.window_end > NOW()
        WHERE qd.active = true AND qu.id IS NULL
    """)
    if not rows:
        return
    
    for row in rows:
        qd_id = row["id"]
        window = row["quota_window"]
        start, end = _window_bounds(window)
        await conn.execute("""
            INSERT INTO quota_usage (quota_definition_id, used, reserved, window_start, window_end)
            VALUES ($1, 0, 0, $2, $3)
            ON CONFLICT (quota_definition_id, window_start) DO NOTHING
        """, qd_id, start, end)

_RESERVE_ALL_SQL = """
WITH eligible_quotas AS (
    SELECT
        qu.id AS usage_id,
        qd.id AS definition_id,
        CASE
            WHEN qd.quota_type = 'TOKENS' THEN $2
            ELSE 1
        END AS amount
    FROM quota_definitions qd
    JOIN quota_usage qu ON qu.quota_definition_id = qd.id
    WHERE qd.model_id = $1
      AND qd.active = true
      AND qu.window_end > NOW()
      AND (
          (qd.quota_type = 'TOKENS' AND (qu.used + qu.reserved + $2) <= qd.limit_value)
          OR
          (qd.quota_type = 'REQUESTS' AND (qu.used + qu.reserved + 1) <= qd.limit_value)
      )
    FOR UPDATE OF qu SKIP LOCKED
),
expected_count AS (
    SELECT COUNT(*) as cnt FROM quota_definitions WHERE model_id = $1 AND active = true
),
matched_count AS (
    SELECT COUNT(*) as cnt FROM eligible_quotas
),
reservations_to_make AS (
    SELECT eq.usage_id, eq.definition_id, eq.amount
    FROM eligible_quotas eq
    WHERE (SELECT cnt FROM expected_count) = (SELECT cnt FROM matched_count)
)
UPDATE quota_usage qu
SET reserved = qu.reserved + rtm.amount
FROM reservations_to_make rtm
WHERE qu.id = rtm.usage_id
RETURNING rtm.definition_id, rtm.amount
"""

_CONFIRM_SQL = """
WITH res AS (
    UPDATE reservations
    SET state = 'completed'
    WHERE request_uuid = $1 AND state = 'pending'
    RETURNING model_id, quota_definition_id, reserved_amount
)
UPDATE quota_usage qu
SET
    used     = qu.used + CASE WHEN qd.quota_type = 'TOKENS' THEN $2 ELSE 1 END,
    reserved = GREATEST(0, qu.reserved - res.reserved_amount)
FROM res
JOIN quota_definitions qd ON qd.id = res.quota_definition_id
WHERE qu.quota_definition_id = res.quota_definition_id
  AND qu.window_end > NOW()
"""

_RELEASE_SQL = """
WITH res AS (
    UPDATE reservations
    SET state = 'released'
    WHERE request_uuid = $1 AND state = 'pending'
    RETURNING quota_definition_id, reserved_amount
)
UPDATE quota_usage qu
SET reserved = GREATEST(0, qu.reserved - res.reserved_amount)
FROM res
WHERE qu.quota_definition_id = res.quota_definition_id
  AND qu.window_end > NOW()
"""

_EXPIRE_STALE_SQL = """
WITH expired AS (
    UPDATE reservations
    SET state = 'expired'
    WHERE state = 'pending' AND expires_at < NOW()
    RETURNING id, quota_definition_id, reserved_amount
)
UPDATE quota_usage qu
SET reserved = GREATEST(0, qu.reserved - expired.reserved_amount)
FROM expired
WHERE qu.quota_definition_id = expired.quota_definition_id
  AND qu.window_end > NOW()
"""

_CHECK_HAS_QUOTAS_SQL = """
SELECT EXISTS (
    SELECT 1 FROM quota_definitions WHERE model_id = $1 AND active = true
)
"""

async def reserve(
    pool: asyncpg.Pool,
    request_uuid: UUID,
    model_id: UUID,
    estimated_tokens: int,
) -> Optional[UUID]:
    """
    Attempt to reserve quota for `model_id`.

    Strategy:
    1. Lock and reserve all quota definitions for the model that have headroom
    2. Verify all expected active quota definitions were successfully locked/reserved
    3. If any quota was exhausted/locked, fail reservation (return None)
    4. Otherwise, record reservations in the DB and return the request_uuid

    Returns the request_uuid on success, or None if quota is exhausted.
    """
    async with pool.acquire() as conn:
        async with conn.transaction():
            await ensure_active_windows(conn)

            rows = await conn.fetch(_RESERVE_ALL_SQL, model_id, estimated_tokens)

            has_quotas = await conn.fetchval(_CHECK_HAS_QUOTAS_SQL, model_id)
            if has_quotas and not rows:
                logger.debug(
                    "reserve: quota exhausted or locked for model=%s",
                    model_id,
                )
                return None

            for row in rows:
                await conn.execute("""
                    INSERT INTO reservations (
                        id, request_uuid, model_id, quota_definition_id, reserved_amount, state, expires_at
                    ) VALUES ($1, $2, $3, $4, $5, 'pending', NOW() + INTERVAL '60 seconds')
                """, uuid4(), request_uuid, model_id, row["definition_id"], row["amount"])

            logger.debug(
                "reserve: reserved for model=%s request_uuid=%s",
                model_id,
                request_uuid,
            )
            return request_uuid


async def confirm(
    pool: asyncpg.Pool,
    reservation_id: UUID,
    actual_tokens: int,
) -> None:
    """
    Confirm a reservation after a successful LLM call.
    Moves reserved → used with the actual token count.
    """
    async with pool.acquire() as conn:
        await conn.execute(_CONFIRM_SQL, reservation_id, actual_tokens)
    logger.debug(
        "confirm: reservation=%s committed actual_tokens=%d",
        reservation_id,
        actual_tokens,
    )


async def release(
    pool: asyncpg.Pool,
    reservation_id: UUID,
) -> None:
    """
    Release a reservation after a failed LLM call.
    Returns the reserved amount back to the quota pool.
    """
    async with pool.acquire() as conn:
        await conn.execute(_RELEASE_SQL, reservation_id)
    logger.debug("release: reservation=%s released", reservation_id)


async def expire_stale_reservations(pool: asyncpg.Pool) -> None:
    """
    Background cleanup: expire reservations that never completed.
    Call this periodically (e.g. every 30s) to avoid quota leaks.
    """
    async with pool.acquire() as conn:
        await conn.execute(_EXPIRE_STALE_SQL)
    logger.debug("expire_stale_reservations: cleaned up expired reservations")
