"""
router/selector.py
Round-robin + latency-weighted model selection.

Selection algorithm (from plan.md, extended):
  1. Filter: enabled, healthy, not in circuit-breaker cooldown, available,
             not expired (lifecycle + availability), not in exclusion list, correct tier
  2. Filter: all active quota windows have headroom >= estimated_tokens
  3. ORDER BY: average_latency ASC (prefer faster), overall_score DESC (quality tiebreak),
               last_selected_at ASC NULLS FIRST (round-robin spread)
  4. LIMIT 1, FOR UPDATE OF models SKIP LOCKED (atomic round-robin)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

import asyncpg
from .reservation import ensure_active_windows

logger = logging.getLogger(__name__)

# Tier waterfall order — matches plan.md routing tiers
TIER_ORDER = [
    "PRIMARY_FREE",
    "SECONDARY_FREE",
    "LIMITED_FREE",
    "PAID",
    "LOCAL",
]

# Selector SQL: direct port of plan.md's conceptual query, extended for
# round-robin (last_selected_at), lifecycle expiry, and RPS token-bucket.
_SELECT_SQL = """
SELECT
    m.id              AS model_id,
    m.model_name,
    m.provider_id,
    p.name            AS provider_name,
    p.base_url,
    mh.average_latency,
    rs.overall_score,
    m.tier
FROM models m
JOIN providers p             ON p.id = m.provider_id
JOIN model_health mh         ON mh.model_id = m.id
JOIN routing_scores rs       ON rs.model_id = m.id
JOIN model_availability ma   ON ma.model_id = m.id
JOIN model_lifecycle ml      ON ml.model_id = m.id
WHERE
    m.enabled = true
    AND p.enabled = true
    AND mh.healthy = true
    AND (mh.disabled_until IS NULL OR mh.disabled_until < NOW())
    AND ma.available = true
    AND (ma.expires_at IS NULL OR ma.expires_at > NOW())
    AND (ml.expires_at IS NULL OR ml.expires_at > NOW())
    AND (ml.deprecated_at IS NULL OR ml.deprecated_at::timestamptz > NOW())
    AND m.id != ALL($1::uuid[])
    AND m.tier = $2::tier_enum
    AND (
        $4::text[] IS NULL 
        OR (
            SELECT COUNT(DISTINCT mt.tag) 
            FROM model_tags mt 
            WHERE mt.model_id = m.id AND mt.tag = ANY($4::text[])
        ) = array_length($4::text[], 1)
    )
    AND (
        -- Model has no quota definitions (e.g. LOCAL tier) OR all active windows have headroom
        NOT EXISTS (
            SELECT 1 FROM quota_definitions qd2
            WHERE qd2.model_id = m.id AND qd2.active = true
        )
        OR NOT EXISTS (
            SELECT 1
            FROM quota_definitions qd
            JOIN quota_usage qu ON qu.quota_definition_id = qd.id
            WHERE qd.model_id = m.id
              AND qd.active = true
              AND qu.window_end > NOW()
              AND (
                  (qd.quota_type = 'TOKENS' AND (qu.used + qu.reserved + $3) > qd.limit_value)
                  OR
                  (qd.quota_type = 'REQUESTS' AND (qu.used + qu.reserved + 1) > qd.limit_value)
              )
        )
    )
ORDER BY
    mh.average_latency   ASC  NULLS LAST,
    rs.overall_score     DESC,
    m.last_selected_at   ASC  NULLS FIRST
LIMIT 1
FOR UPDATE OF m SKIP LOCKED
"""

_UPDATE_LAST_SELECTED_SQL = """
UPDATE models SET last_selected_at = NOW() WHERE id = $1
"""


@dataclass
class ModelCandidate:
    model_id: UUID
    model_name: str
    provider_id: UUID
    provider_name: str
    base_url: str
    average_latency: Optional[float]
    overall_score: float
    tier: str


async def select_model(
    pool: asyncpg.Pool,
    tier: str,
    estimated_tokens: int,
    excluded_model_ids: list[UUID] | None = None,
    required_tags: list[str] | None = None,
) -> Optional[ModelCandidate]:
    """
    Select the best model for a given tier using round-robin + latency weighting.
    Returns None if no eligible model is found in this tier.

    Uses FOR UPDATE SKIP LOCKED so concurrent workers don't pick the same model,
    enabling atomic round-robin across multiple workers.
    """
    excluded = excluded_model_ids or []
    # If required_tags is empty, treat it as None/NULL in SQL
    tags = required_tags if required_tags else None

    async with pool.acquire() as conn:
        async with conn.transaction():
            await ensure_active_windows(conn)
            row = await conn.fetchrow(
                _SELECT_SQL,
                excluded,
                tier,
                estimated_tokens,
                tags,
            )
            if row is None:
                return None

            # Atomically update last_selected_at to advance the round-robin pointer
            await conn.execute(_UPDATE_LAST_SELECTED_SQL, row["model_id"])

    logger.debug(
        "Selected model=%s provider=%s tier=%s latency=%.1fms",
        row["model_name"],
        row["provider_name"],
        tier,
        row["average_latency"] or 0,
    )

    return ModelCandidate(
        model_id=row["model_id"],
        model_name=row["model_name"],
        provider_id=row["provider_id"],
        provider_name=row["provider_name"],
        base_url=row["base_url"],
        average_latency=row["average_latency"],
        overall_score=row["overall_score"],
        tier=row["tier"],
    )


async def select_model_waterfall(
    pool: asyncpg.Pool,
    estimated_tokens: int,
    excluded_model_ids: list[UUID] | None = None,
    required_tags: list[str] | None = None,
) -> Optional[ModelCandidate]:
    """
    Walk the tier waterfall (PRIMARY_FREE → LOCAL) and return the first
    eligible model found. Returns None only if all tiers are exhausted.
    """
    excluded = excluded_model_ids or []
    for tier in TIER_ORDER:
        candidate = await select_model(pool, tier, estimated_tokens, excluded, required_tags)
        if candidate is not None:
            return candidate
        logger.debug("Tier %s exhausted, falling to next tier", tier)
    return None
