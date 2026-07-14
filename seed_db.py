#!/usr/bin/env python3
"""
seed_db.py
Reads providers.yaml and populates the PostgreSQL database.
Idempotent: safe to run multiple times (INSERT ... ON CONFLICT DO UPDATE).

Usage:
    uv run python seed_db.py
    uv run python seed_db.py --dry-run
"""

from __future__ import annotations

import asyncio
import argparse
import logging
import os
import sys
from datetime import date, datetime
from pathlib import Path

import asyncpg
import yaml
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PROVIDERS_YAML = Path(__file__).parent / "providers.yaml"

TIER_PRIORITY_MAP = {
    "PRIMARY_FREE":   10,
    "SECONDARY_FREE": 20,
    "LIMITED_FREE":   30,
    "PAID":           40,
    "LOCAL":          50,
}

# Maps YAML quota_type → DB quota_type
QUOTA_TYPE_MAP = {"REQUESTS": "REQUESTS", "TOKENS": "TOKENS"}

# Maps YAML window → DB window enum
WINDOW_MAP = {
    "SECOND":   "SECOND",
    "MINUTE":   "MINUTE",
    "HOUR":     "HOUR",
    "DAY":      "DAY",
    "MONTH":    "MONTH",
    "LIFETIME": "LIFETIME",
    "CUSTOM":   "CUSTOM",
}


async def seed(dry_run: bool = False) -> None:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        logger.error("DATABASE_URL not set in environment")
        sys.exit(1)

    data = yaml.safe_load(PROVIDERS_YAML.read_text())
    providers_data = data["providers"]

    conn = await asyncpg.connect(dsn)
    try:
        logger.info("Connected to PostgreSQL")
        for p in providers_data:
            await seed_provider(conn, p, dry_run)
        logger.info("✅ Seeding complete.")
    finally:
        await conn.close()


async def seed_provider(conn: asyncpg.Connection, p: dict, dry_run: bool) -> None:
    name = p["name"]
    logger.info("Seeding provider: %s", name)

    if not dry_run:
        provider_id = await conn.fetchval("""
            INSERT INTO providers (
                name, display_name, provider_type, tier, priority,
                enabled, base_url,
                supports_streaming, supports_tools, supports_images, supports_reasoning
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
            ON CONFLICT (name) DO UPDATE SET
                display_name       = EXCLUDED.display_name,
                provider_type      = EXCLUDED.provider_type::provider_type_enum,
                tier               = EXCLUDED.tier::tier_enum,
                priority           = EXCLUDED.priority,
                enabled            = EXCLUDED.enabled,
                base_url           = EXCLUDED.base_url,
                supports_streaming = EXCLUDED.supports_streaming,
                supports_tools     = EXCLUDED.supports_tools,
                supports_images    = EXCLUDED.supports_images,
                supports_reasoning = EXCLUDED.supports_reasoning,
                updated_at         = NOW()
            RETURNING id
        """,
            name,
            p["display_name"],
            p["provider_type"],
            p["tier"],
            TIER_PRIORITY_MAP.get(p["tier"], 99),
            p.get("enabled", True),
            p.get("base_url"),
            p.get("supports_streaming", False),
            p.get("supports_tools", False),
            p.get("supports_images", False),
            p.get("supports_reasoning", False),
        )

        # Seed API key from environment
        env_key_name = f"{name.upper()}_API_KEY"
        api_key = os.environ.get(env_key_name, "")
        if api_key:
            await conn.execute("""
                INSERT INTO provider_credentials (provider_id, key_name, encrypted_key, active)
                VALUES ($1, $2, $3, true)
                ON CONFLICT DO NOTHING
            """, provider_id, env_key_name, api_key)
            logger.info("  ✓ Stored credential: %s", env_key_name)
        else:
            logger.warning("  ⚠ No env var %s found", env_key_name)
    else:
        provider_id = "dry-run-uuid"

    for model in p.get("models", []):
        await seed_model(conn, provider_id, model, dry_run)


async def seed_model(
    conn: asyncpg.Connection,
    provider_id,
    m: dict,
    dry_run: bool,
) -> None:
    model_name = m["model_name"]
    logger.info("  Seeding model: %s", model_name)

    if dry_run:
        return

    model_id = await conn.fetchval("""
        INSERT INTO models (
            provider_id, model_name, display_name, tier, enabled,
            context_window, max_output_tokens,
            vision, tools, reasoning, embedding, speech, moderation, coding, chat
        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)
        ON CONFLICT (provider_id, model_name) DO UPDATE SET
            display_name      = EXCLUDED.display_name,
            tier              = EXCLUDED.tier::tier_enum,
            enabled           = EXCLUDED.enabled,
            context_window    = EXCLUDED.context_window,
            max_output_tokens = EXCLUDED.max_output_tokens,
            vision            = EXCLUDED.vision,
            tools             = EXCLUDED.tools,
            reasoning         = EXCLUDED.reasoning,
            embedding         = EXCLUDED.embedding,
            speech            = EXCLUDED.speech,
            moderation        = EXCLUDED.moderation,
            coding            = EXCLUDED.coding,
            chat              = EXCLUDED.chat,
            updated_at        = NOW()
        RETURNING id
    """,
        provider_id,
        model_name,
        m.get("display_name", model_name),
        m["tier"],
        m.get("enabled", True),
        m.get("context_window"),
        m.get("max_output_tokens"),
        m.get("vision", False),
        m.get("tools", False),
        m.get("reasoning", False),
        m.get("embedding", False),
        m.get("speech", False),
        m.get("moderation", False),
        m.get("coding", False),
        m.get("chat", True),
    )

    # Tags
    for tag in m.get("tags", []):
        await conn.execute("""
            INSERT INTO model_tags (model_id, tag) VALUES ($1, $2)
            ON CONFLICT (model_id, tag) DO NOTHING
        """, model_id, tag)

    # Lifecycle
    lc = m.get("lifecycle", {})
    introduced_at = lc.get("introduced_at")
    expires_at_str = lc.get("expires_at")
    expires_at = datetime.fromisoformat(expires_at_str) if expires_at_str else None
    await conn.execute("""
        INSERT INTO model_lifecycle (model_id, introduced_at, expires_at, last_verified_at, verification_source)
        VALUES ($1, $2, $3, NOW(), 'providers.yaml')
        ON CONFLICT (model_id) DO UPDATE SET
            introduced_at       = EXCLUDED.introduced_at,
            expires_at          = EXCLUDED.expires_at,
            last_verified_at    = NOW(),
            verification_source = 'providers.yaml'
    """, model_id,
        date.fromisoformat(introduced_at) if introduced_at else None,
        expires_at,
    )

    # Model availability
    available = expires_at is None or expires_at > datetime.now(expires_at.tzinfo)
    await conn.execute("""
        INSERT INTO model_availability (model_id, available, expires_at, last_checked)
        VALUES ($1, $2, $3, NOW())
        ON CONFLICT (model_id) DO UPDATE SET
            available    = EXCLUDED.available,
            expires_at   = EXCLUDED.expires_at,
            last_checked = NOW()
    """, model_id, available, expires_at)

    # Model health (initial)
    await conn.execute("""
        INSERT INTO model_health (model_id, healthy, average_latency, error_rate,
                                   consecutive_failures)
        VALUES ($1, true, NULL, 0.0, 0)
        ON CONFLICT (model_id) DO NOTHING
    """, model_id)

    # Routing scores (initial: cost_score = 100 for free, 50 for paid)
    is_free = "FREE" in m["tier"] or m["tier"] == "LOCAL"
    cost_score = 100.0 if is_free else 50.0
    await conn.execute("""
        INSERT INTO routing_scores (model_id, quality_score, speed_score,
                                     availability_score, cost_score, overall_score)
        VALUES ($1, 50.0, 50.0, 50.0, $2, $3)
        ON CONFLICT (model_id) DO NOTHING
    """, model_id, cost_score, (50.0 + cost_score) / 2)

    # Quota definitions + initial usage windows
    for q in m.get("quotas", []):
        window = q["window"]
        qtype = q["quota_type"]
        limit_val = q["limit_value"]
        qexpires_str = q.get("expires_at")
        qexpires = datetime.fromisoformat(qexpires_str) if qexpires_str else None

        def_id = await conn.fetchval("""
            INSERT INTO quota_definitions (model_id, quota_type, quota_window, limit_value, expires_at, active)
            VALUES ($1, $2::quota_type_enum, $3::quota_window_enum, $4, $5, true)
            ON CONFLICT DO NOTHING
            RETURNING id
        """, model_id, qtype, window, limit_val, qexpires)

        if def_id:
            # Create initial usage window
            window_start, window_end = _window_bounds(window)
            await conn.execute("""
                INSERT INTO quota_usage (quota_definition_id, used, reserved, window_start, window_end)
                VALUES ($1, 0, 0, $2, $3)
                ON CONFLICT (quota_definition_id, window_start) DO NOTHING
            """, def_id, window_start, window_end)
            logger.info("    ✓ Quota: %s/%s limit=%d", qtype, window, limit_val)


def _window_bounds(window: str):
    """Return (window_start, window_end) for the current period of the given window."""
    from datetime import timezone, timedelta
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
        # First day of next month
        if now.month == 12:
            end = start.replace(year=now.year + 1, month=1)
        else:
            end = start.replace(month=now.month + 1)
    else:  # LIFETIME, CUSTOM
        start = now
        end = now.replace(year=now.year + 10)

    return start, end


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed the HR AI router database")
    parser.add_argument("--dry-run", action="store_true", help="Parse YAML only, no DB writes")
    args = parser.parse_args()
    asyncio.run(seed(dry_run=args.dry_run))
