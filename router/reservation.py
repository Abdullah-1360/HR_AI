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

import asyncpg

logger = logging.getLogger(__name__)

_RESERVE_TOKENS_SQL = """
WITH quota AS (
    SELECT
        qu.id           AS usage_id,
        qu.used,
        qu.reserved,
        qu.window_end,
        qd.limit_value,
        qd.id           AS definition_id
    FROM quota_definitions qd
    JOIN quota_usage qu ON qu.quota_definition_id = qd.id
    WHERE qd.model_id = $1
      AND qd.quota_type = 'TOKENS'
      AND qd.active = true
      AND qu.window_end > NOW()
      AND (qu.used + qu.reserved + $2) <= qd.limit_value
    ORDER BY qd.quota_window
    LIMIT 1
    FOR UPDATE OF qu SKIP LOCKED
)
UPDATE quota_usage qu
SET reserved = qu.reserved + $2
FROM quota
WHERE qu.id = quota.usage_id
RETURNING quota.definition_id, qu.id AS usage_id
"""

_RESERVE_REQUESTS_SQL = """
WITH quota AS (
    SELECT
        qu.id           AS usage_id,
        qd.id           AS definition_id
    FROM quota_definitions qd
    JOIN quota_usage qu ON qu.quota_definition_id = qd.id
    WHERE qd.model_id = $1
      AND qd.quota_type = 'REQUESTS'
      AND qd.active = true
      AND qu.window_end > NOW()
      AND (qu.used + qu.reserved + 1) <= qd.limit_value
    ORDER BY qd.quota_window
    LIMIT 1
    FOR UPDATE OF qu SKIP LOCKED
)
UPDATE quota_usage qu
SET reserved = qu.reserved + 1
FROM quota
WHERE qu.id = quota.usage_id
RETURNING quota.definition_id, qu.id AS usage_id
"""

_INSERT_RESERVATION_SQL = """
INSERT INTO reservations (
    id, request_uuid, model_id, quota_definition_id, reserved_amount, state, expires_at
) VALUES ($1, $2, $3, $4, $5, 'pending', NOW() + INTERVAL '60 seconds')
RETURNING id
"""

_CONFIRM_SQL = """
WITH res AS (
    UPDATE reservations
    SET state = 'completed'
    WHERE id = $1 AND state = 'pending'
    RETURNING model_id, quota_definition_id, reserved_amount
)
UPDATE quota_usage qu
SET
    used     = qu.used + $2,        -- actual tokens used
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
    WHERE id = $1 AND state = 'pending'
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
    1. If model has TOKENS quota → try to reserve estimated_tokens
    2. Else if model has REQUESTS quota → reserve 1 request slot
    3. Else (LOCAL / no quota) → create a trivial reservation (always succeeds)

    Returns the reservation UUID on success, or None if quota is exhausted
    (SKIP LOCKED means another worker claimed it or quota is exhausted).
    """
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Phase 1: Try token-based reservation
            row = await conn.fetchrow(_RESERVE_TOKENS_SQL, model_id, estimated_tokens)

            if row is None:
                # Phase 2: Try request-based reservation
                row = await conn.fetchrow(_RESERVE_REQUESTS_SQL, model_id)

            if row is None:
                # Phase 3: Check if model has any quotas at all
                has_quotas = await conn.fetchval(_CHECK_HAS_QUOTAS_SQL, model_id)
                if has_quotas:
                    # Quota is genuinely exhausted
                    logger.debug(
                        "reserve: quota exhausted for model=%s tokens=%d",
                        model_id,
                        estimated_tokens,
                    )
                    return None
                # No quotas defined → trivial reservation (LOCAL tier, OpenRouter no-quota models)
                definition_id = None
                reserved_amount = 0
            else:
                definition_id = row["definition_id"]
                reserved_amount = estimated_tokens if "reserved_amount" not in row else row.get("reserved_amount", estimated_tokens)

            reservation_id = uuid4()
            # For models without quota definitions, use a placeholder that still logs the request
            if definition_id is None:
                await conn.execute("""
                    INSERT INTO reservations (id, request_uuid, model_id, quota_definition_id,
                                              reserved_amount, state, expires_at)
                    SELECT $1, $2, $3, id, 0, 'pending', NOW() + INTERVAL '60 seconds'
                    FROM quota_definitions WHERE model_id = $3 AND active = true LIMIT 1
                    -- If no quota_definitions at all, skip the insert (no constraint needed)
                """, reservation_id, request_uuid, model_id)
                # If truly no quotas, just insert without a quota_definition_id link isn't possible
                # due to FK. Instead, skip the reservation row and return a synthetic ID.
                logger.debug(
                    "reserve: no-quota model=%s, synthetic reservation=%s",
                    model_id,
                    reservation_id,
                )
                return reservation_id

            await conn.execute(
                _INSERT_RESERVATION_SQL,
                reservation_id,
                request_uuid,
                model_id,
                definition_id,
                reserved_amount,
            )
            logger.debug(
                "reserve: reserved for model=%s reservation=%s",
                model_id,
                reservation_id,
            )
            return reservation_id


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
