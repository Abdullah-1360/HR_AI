"""
tests/test_router.py
Comprehensive test suite for the multi-provider LLM router.

Test categories:
  1. DB / Selector unit tests     — pure DB logic, no real LLM calls
  2. Reservation unit tests       — quota reserve / confirm / release
  3. Health / Circuit breaker     — failure escalation, backoff, recovery
  4. Graph integration tests      — full LangGraph flow with mocked LLMs
  5. Edge cases                   — expired models, quota exhaustion, all-tiers-failed
  6. Concurrency test             — parallel requests, round-robin spread

Run with:
    uv run python -m pytest tests/ -v --tb=short
  or standalone:
    uv run python tests/test_router.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

# ── env must be loaded before any router imports ──────────────────────────────
from dotenv import load_dotenv
load_dotenv()

# ── project imports ───────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from router.db import get_pool, close_pool
from router import selector, reservation, health
from router.selector import ModelCandidate, TIER_ORDER, select_model, select_model_waterfall
from router.health import FAILURE_THRESHOLD, BACKOFF_SECONDS
from graph import RouterState, build_graph, run_graph, after_llm, after_select, after_failure

logging.basicConfig(
    level=logging.WARNING,   # suppress noisy INFO during tests
    format="%(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("tests")

# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

PASS = "✅"
FAIL = "❌"
SKIP = "⚠️ "
SEPARATOR = "─" * 70

_pool = None

async def get_test_pool():
    global _pool
    if _pool is None:
        _pool = await get_pool()
    return _pool


async def get_any_model_id(pool, tier: str = "PRIMARY_FREE") -> UUID | None:
    """Fetch the UUID of any enabled model in a given tier."""
    row = await pool.fetchrow(
        "SELECT id FROM models WHERE tier = $1::tier_enum AND enabled = true LIMIT 1",
        tier,
    )
    return row["id"] if row else None


async def get_model_by_name(pool, model_name: str) -> dict | None:
    row = await pool.fetchrow(
        "SELECT id, provider_id, tier FROM models WHERE model_name = $1",
        model_name,
    )
    return dict(row) if row else None


async def reset_model_health(pool, model_id: UUID):
    """Reset a model's health back to default after a test."""
    await pool.execute("""
        UPDATE model_health
        SET healthy=true, consecutive_failures=0, disabled_until=NULL,
            error_rate=0.0, average_latency=NULL, updated_at=NOW()
        WHERE model_id = $1
    """, model_id)


async def reset_quota_usage(pool, model_id: UUID):
    """Reset all quota usage windows for a model back to 0."""
    await pool.execute("""
        UPDATE quota_usage qu
        SET used=0, reserved=0
        FROM quota_definitions qd
        WHERE qu.quota_definition_id = qd.id AND qd.model_id = $1
    """, model_id)


async def set_quota_used(pool, model_id: UUID, used_amount: int, quota_type: str = "TOKENS"):
    """Manually set quota usage to a specific amount (for exhaustion tests)."""
    await pool.execute("""
        UPDATE quota_usage qu
        SET used = $3
        FROM quota_definitions qd
        WHERE qu.quota_definition_id = qd.id
          AND qd.model_id = $1
          AND qd.quota_type = $2::quota_type_enum
          AND qu.window_end > NOW()
    """, model_id, quota_type, used_amount)


# ═══════════════════════════════════════════════════════════════════════════════
# Test Results Tracker
# ═══════════════════════════════════════════════════════════════════════════════

class TestResults:
    def __init__(self):
        self.passed = []
        self.failed = []
        self.skipped = []

    def record(self, name: str, passed: bool, msg: str = "", skip: bool = False):
        status = SKIP if skip else (PASS if passed else FAIL)
        label = "SKIP" if skip else ("PASS" if passed else "FAIL")
        print(f"  {status} [{label}] {name}")
        if msg and (not passed or skip):
            print(f"       → {msg}")
        if skip:
            self.skipped.append(name)
        elif passed:
            self.passed.append(name)
        else:
            self.failed.append(name)

    def summary(self):
        total = len(self.passed) + len(self.failed) + len(self.skipped)
        print(f"\n{SEPARATOR}")
        print(f"RESULTS: {len(self.passed)}/{total} passed  "
              f"| {len(self.failed)} failed  | {len(self.skipped)} skipped")
        if self.failed:
            print(f"\nFailed tests:")
            for f in self.failed:
                print(f"  {FAIL} {f}")
        print(SEPARATOR)
        return len(self.failed) == 0


results = TestResults()


# ═══════════════════════════════════════════════════════════════════════════════
# 1. DATABASE / SELECTOR UNIT TESTS
# ═══════════════════════════════════════════════════════════════════════════════

async def test_db_connection():
    """Pool connects and schema is populated."""
    try:
        pool = await get_test_pool()
        count = await pool.fetchval("SELECT COUNT(*) FROM models WHERE enabled = true")
        ok = count > 0
        results.record("DB: connection and models exist", ok,
                       f"Expected >0 models, got {count}")
    except Exception as e:
        results.record("DB: connection and models exist", False, str(e))


async def test_all_tiers_populated():
    """Every tier in TIER_ORDER has at least one enabled model."""
    pool = await get_test_pool()
    for tier in TIER_ORDER:
        try:
            count = await pool.fetchval(
                "SELECT COUNT(*) FROM models WHERE tier=$1::tier_enum AND enabled=true",
                tier,
            )
            ok = count > 0
            results.record(f"DB: tier {tier} has models ({count})", ok,
                           f"No models in {tier}")
        except Exception as e:
            results.record(f"DB: tier {tier} has models", False, str(e))


async def test_health_and_score_rows_exist():
    """Every model has a model_health and routing_scores row."""
    pool = await get_test_pool()
    try:
        missing_health = await pool.fetchval("""
            SELECT COUNT(*) FROM models m
            LEFT JOIN model_health mh ON mh.model_id = m.id
            WHERE mh.model_id IS NULL AND m.enabled = true
        """)
        missing_scores = await pool.fetchval("""
            SELECT COUNT(*) FROM models m
            LEFT JOIN routing_scores rs ON rs.model_id = m.id
            WHERE rs.model_id IS NULL AND m.enabled = true
        """)
        results.record("DB: all models have health rows", missing_health == 0,
                       f"{missing_health} models missing health row")
        results.record("DB: all models have routing_scores rows", missing_scores == 0,
                       f"{missing_scores} models missing routing_scores row")
    except Exception as e:
        results.record("DB: health/scores completeness", False, str(e))


async def test_selector_primary_free():
    """Selector picks a PRIMARY_FREE model with no exclusions."""
    pool = await get_test_pool()
    try:
        candidate = await select_model(pool, "PRIMARY_FREE", 100)
        ok = candidate is not None and candidate.tier == "PRIMARY_FREE"
        results.record("Selector: picks PRIMARY_FREE model", ok,
                       f"Got: {candidate}")
    except Exception as e:
        results.record("Selector: picks PRIMARY_FREE model", False, str(e))


async def test_selector_respects_exclusion_list():
    """Selector skips model IDs in the exclusion list."""
    pool = await get_test_pool()
    try:
        # Get all PRIMARY_FREE models
        rows = await pool.fetch(
            "SELECT id FROM models WHERE tier='PRIMARY_FREE'::tier_enum AND enabled=true"
        )
        if not rows:
            results.record("Selector: exclusion list respected", False, "No PRIMARY_FREE models found")
            return

        all_ids = [row["id"] for row in rows]

        # Exclude all of them
        candidate = await select_model(pool, "PRIMARY_FREE", 100, excluded_model_ids=all_ids)
        ok = candidate is None
        results.record("Selector: exclusion list excludes all models → None",
                       ok, f"Expected None, got {candidate}")
    except Exception as e:
        results.record("Selector: exclusion list respected", False, str(e))


async def test_selector_skips_unhealthy_models():
    """Selector skips models with healthy=false."""
    pool = await get_test_pool()
    try:
        model_id = await get_any_model_id(pool, "PRIMARY_FREE")
        if not model_id:
            results.record("Selector: skips unhealthy model", False, "No PRIMARY_FREE model found")
            return

        # Mark unhealthy
        await pool.execute(
            "UPDATE model_health SET healthy=false WHERE model_id=$1", model_id
        )

        # Get all PRIMARY_FREE models
        rows = await pool.fetch(
            "SELECT id FROM models WHERE tier='PRIMARY_FREE'::tier_enum AND enabled=true"
        )
        all_ids = [row["id"] for row in rows]

        # Selector should not pick the unhealthy one when it's the only one excluded
        candidate = await select_model(pool, "PRIMARY_FREE", 100,
                                       excluded_model_ids=[mid for mid in all_ids if mid != model_id])
        was_unhealthy_selected = (candidate is not None and candidate.model_id == model_id)
        results.record("Selector: skips model with healthy=false",
                       not was_unhealthy_selected,
                       f"Unhealthy model was selected: {candidate}")
    except Exception as e:
        results.record("Selector: skips unhealthy model", False, str(e))
    finally:
        if model_id:
            await reset_model_health(pool, model_id)


async def test_selector_skips_circuit_breaker():
    """Selector skips models with disabled_until in the future."""
    pool = await get_test_pool()
    model_id = None
    try:
        model_id = await get_any_model_id(pool, "PRIMARY_FREE")
        if not model_id:
            results.record("Selector: skips circuit-breaker model", False, "No model found")
            return

        future = datetime.now(timezone.utc) + timedelta(minutes=5)
        await pool.execute(
            "UPDATE model_health SET healthy=false, disabled_until=$2 WHERE model_id=$1",
            model_id, future,
        )

        # Exclude all other PRIMARY_FREE models except this one
        rows = await pool.fetch(
            "SELECT id FROM models WHERE tier='PRIMARY_FREE'::tier_enum AND enabled=true"
        )
        other_ids = [row["id"] for row in rows if row["id"] != model_id]

        candidate = await select_model(pool, "PRIMARY_FREE", 100, excluded_model_ids=other_ids)
        ok = candidate is None or candidate.model_id != model_id
        results.record("Selector: skips model in circuit-breaker cooldown", ok,
                       f"CB model was selected: {candidate}")
    except Exception as e:
        results.record("Selector: skips circuit-breaker model", False, str(e))
    finally:
        if model_id:
            await reset_model_health(pool, model_id)


async def test_selector_skips_expired_model():
    """Selector skips models whose lifecycle.expires_at has passed."""
    pool = await get_test_pool()
    model_id = None
    try:
        model_id = await get_any_model_id(pool, "SECONDARY_FREE")
        if not model_id:
            results.record("Selector: skips expired model", False, "No SECONDARY_FREE model")
            return

        past = datetime.now(timezone.utc) - timedelta(hours=1)
        await pool.execute(
            "UPDATE model_lifecycle SET expires_at=$2 WHERE model_id=$1",
            model_id, past,
        )
        await pool.execute(
            "UPDATE model_availability SET available=false, expires_at=$2 WHERE model_id=$1",
            model_id, past,
        )

        candidate = await select_model(pool, "SECONDARY_FREE", 100)
        ok = candidate is None or candidate.model_id != model_id
        results.record("Selector: skips model past expires_at", ok,
                       f"Expired model was selected: {candidate}")
    except Exception as e:
        results.record("Selector: skips expired model", False, str(e))
    finally:
        if model_id:
            await pool.execute(
                "UPDATE model_lifecycle SET expires_at=NULL WHERE model_id=$1", model_id
            )
            await pool.execute(
                "UPDATE model_availability SET available=true, expires_at=NULL WHERE model_id=$1",
                model_id,
            )


async def test_selector_round_robin():
    """Repeated selects in PRIMARY_FREE spread across multiple models."""
    pool = await get_test_pool()
    try:
        rows = await pool.fetch(
            "SELECT COUNT(*) as cnt FROM models WHERE tier='PRIMARY_FREE'::tier_enum AND enabled=true"
        )
        model_count = rows[0]["cnt"]
        if model_count < 2:
            results.record("Selector: round-robin distribution", False,
                           f"Need >=2 PRIMARY_FREE models, found {model_count}",
                           skip=True)
            return

        # Reset average_latency for all models in PRIMARY_FREE to prevent test bleeding
        await pool.execute("""
            UPDATE model_health
            SET average_latency = NULL, healthy = true, consecutive_failures = 0, disabled_until = NULL
            WHERE model_id IN (
                SELECT id FROM models WHERE tier = 'PRIMARY_FREE'::tier_enum
            )
        """)

        # Run N selections and collect model IDs
        selected_ids = set()
        for _ in range(model_count * 3):
            candidate = await select_model(pool, "PRIMARY_FREE", 100)
            if candidate:
                selected_ids.add(candidate.model_id)

        ok = len(selected_ids) >= 2
        results.record(
            f"Selector: round-robin spreads across ≥2 models (got {len(selected_ids)})",
            ok,
            f"Only {len(selected_ids)} distinct model(s) selected across {model_count*3} calls",
        )
    except Exception as e:
        results.record("Selector: round-robin distribution", False, str(e))


async def test_selector_waterfall_falls_to_secondary():
    """Waterfall skips to SECONDARY_FREE when all PRIMARY_FREE are excluded."""
    pool = await get_test_pool()
    try:
        rows = await pool.fetch(
            "SELECT id FROM models WHERE tier='PRIMARY_FREE'::tier_enum AND enabled=true"
        )
        primary_ids = [row["id"] for row in rows]

        candidate = await select_model_waterfall(
            pool, estimated_tokens=100, excluded_model_ids=primary_ids
        )
        ok = candidate is not None and candidate.tier == "SECONDARY_FREE"
        results.record("Selector: waterfall falls to SECONDARY_FREE", ok,
                       f"Got tier={candidate.tier if candidate else None}")
    except Exception as e:
        results.record("Selector: waterfall fallback", False, str(e))


async def test_selector_waterfall_none_when_all_exhausted():
    """Waterfall returns None when all tiers are excluded."""
    pool = await get_test_pool()
    try:
        rows = await pool.fetch("SELECT id FROM models WHERE enabled=true")
        all_ids = [row["id"] for row in rows]
        candidate = await select_model_waterfall(pool, 100, excluded_model_ids=all_ids)
        results.record("Selector: waterfall returns None when all excluded",
                       candidate is None, f"Expected None, got {candidate}")
    except Exception as e:
        results.record("Selector: waterfall all exhausted", False, str(e))


async def test_selector_respects_tags():
    """Selector only picks models that have all required tags."""
    pool = await get_test_pool()
    try:
        candidate = await select_model_waterfall(pool, 100, required_tags=["vision"])
        if candidate is None:
            results.record("Selector: respects required_tags", False, "No model found with 'vision' tag")
            return

        has_tag = await pool.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM model_tags mt
                WHERE mt.model_id = $1 AND mt.tag = 'vision'
            )
        """, candidate.model_id)
        results.record("Selector: respects required_tags ('vision')", has_tag,
                       f"Selected model {candidate.model_name} lacks the required 'vision' tag")
    except Exception as e:
        results.record("Selector: respects required_tags", False, str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# 2. RESERVATION UNIT TESTS
# ═══════════════════════════════════════════════════════════════════════════════

async def test_reservation_reserve_and_confirm():
    """Reserve quota, then confirm: reserved→0, used increases."""
    pool = await get_test_pool()
    model_id = None
    try:
        # Use Gemini which has TOKEN quotas
        m = await get_model_by_name(pool, "gemini-2.5-flash")
        if not m:
            results.record("Reservation: reserve+confirm", False, "gemini-2.5-flash not found")
            return
        model_id = m["id"]
        await reset_quota_usage(pool, model_id)

        req_id = uuid4()
        before = await pool.fetchrow("""
            SELECT qu.used, qu.reserved FROM quota_usage qu
            JOIN quota_definitions qd ON qu.quota_definition_id = qd.id
            WHERE qd.model_id = $1 AND qd.quota_type='TOKENS' AND qu.window_end > NOW()
            LIMIT 1
        """, model_id)

        rid = await reservation.reserve(pool, req_id, model_id, 100)
        ok1 = rid is not None
        results.record("Reservation: reserve() returns UUID", ok1, f"Got {rid}")

        if rid:
            mid_reserved = await pool.fetchval("""
                SELECT qu.reserved FROM quota_usage qu
                JOIN quota_definitions qd ON qu.quota_definition_id = qd.id
                WHERE qd.model_id = $1 AND qd.quota_type='TOKENS' AND qu.window_end > NOW()
                LIMIT 1
            """, model_id)
            ok2 = (mid_reserved or 0) >= 100
            results.record("Reservation: reserved field incremented after reserve()", ok2,
                           f"reserved={mid_reserved}, expected>=100")

            await reservation.confirm(pool, rid, 80)
            after = await pool.fetchrow("""
                SELECT qu.used, qu.reserved FROM quota_usage qu
                JOIN quota_definitions qd ON qu.quota_definition_id = qd.id
                WHERE qd.model_id = $1 AND qd.quota_type='TOKENS' AND qu.window_end > NOW()
                LIMIT 1
            """, model_id)
            ok3 = after["used"] >= 80 and after["reserved"] < mid_reserved
            results.record("Reservation: confirm() moves reserved→used", ok3,
                           f"used={after['used']}, reserved={after['reserved']}")
    except Exception as e:
        results.record("Reservation: reserve+confirm", False, str(e))
    finally:
        if model_id:
            await reset_quota_usage(pool, model_id)


async def test_reservation_release():
    """Reserve then release: reserved returns to 0."""
    pool = await get_test_pool()
    model_id = None
    try:
        m = await get_model_by_name(pool, "gemini-2.5-flash")
        if not m:
            results.record("Reservation: release()", False, "gemini-2.5-flash not found")
            return
        model_id = m["id"]
        await reset_quota_usage(pool, model_id)

        rid = await reservation.reserve(pool, uuid4(), model_id, 200)
        if not rid:
            results.record("Reservation: release()", False, "reserve() returned None")
            return

        before_reserved = await pool.fetchval("""
            SELECT qu.reserved FROM quota_usage qu
            JOIN quota_definitions qd ON qu.quota_definition_id = qd.id
            WHERE qd.model_id = $1 AND qd.quota_type='TOKENS' AND qu.window_end > NOW()
            LIMIT 1
        """, model_id)

        await reservation.release(pool, rid)

        after_reserved = await pool.fetchval("""
            SELECT qu.reserved FROM quota_usage qu
            JOIN quota_definitions qd ON qu.quota_definition_id = qd.id
            WHERE qd.model_id = $1 AND qd.quota_type='TOKENS' AND qu.window_end > NOW()
            LIMIT 1
        """, model_id)

        ok = (after_reserved or 0) < (before_reserved or 0)
        results.record("Reservation: release() decrements reserved", ok,
                       f"before={before_reserved}, after={after_reserved}")
    except Exception as e:
        results.record("Reservation: release()", False, str(e))
    finally:
        if model_id:
            await reset_quota_usage(pool, model_id)


async def test_reservation_quota_exhaustion_blocks_select():
    """When quota is maxed out, selector skips that model."""
    pool = await get_test_pool()
    model_id = None
    try:
        m = await get_model_by_name(pool, "gemini-2.5-flash")
        if not m:
            results.record("Reservation: quota exhaustion blocks selector", False, "model not found")
            return
        model_id = m["id"]
        await reset_quota_usage(pool, model_id)

        # Get the TOKENS/MINUTE limit
        limit = await pool.fetchval("""
            SELECT qd.limit_value FROM quota_definitions qd
            WHERE qd.model_id = $1 AND qd.quota_type='TOKENS'
              AND qd.quota_window='MINUTE'::quota_window_enum AND qd.active=true
            LIMIT 1
        """, model_id)

        if not limit:
            results.record("Reservation: quota exhaustion blocks selector", False,
                           "No TOKENS/MINUTE quota for gemini-2.5-flash", skip=True)
            return

        # Fill quota to the brim
        await set_quota_used(pool, model_id, int(limit), "TOKENS")

        # Now selector should not pick this model (requesting 1 token should fail quota check)
        rows = await pool.fetch(
            "SELECT id FROM models WHERE tier='PRIMARY_FREE'::tier_enum AND enabled=true AND id != $1",
            model_id,
        )
        other_ids = [r["id"] for r in rows]
        candidate = await select_model(pool, "PRIMARY_FREE", 1, excluded_model_ids=other_ids)
        ok = candidate is None or candidate.model_id != model_id
        results.record("Reservation: exhausted quota → model skipped by selector", ok,
                       f"Exhausted model was still selected: {candidate}")
    except Exception as e:
        results.record("Reservation: quota exhaustion blocks selector", False, str(e))
    finally:
        if model_id:
            await reset_quota_usage(pool, model_id)


async def test_reservation_stale_expiry():
    """expire_stale_reservations() cleans up pending reservations past expires_at."""
    pool = await get_test_pool()
    model_id = None
    try:
        m = await get_model_by_name(pool, "gemini-2.5-flash")
        if not m:
            results.record("Reservation: stale expiry cleanup", False, "model not found")
            return
        model_id = m["id"]
        await reset_quota_usage(pool, model_id)

        # Create a reservation manually with expires_at in the past
        rid = uuid4()
        req_id = uuid4()
        qd_id = await pool.fetchval("""
            SELECT id FROM quota_definitions WHERE model_id=$1 AND quota_type='TOKENS' LIMIT 1
        """, model_id)
        if not qd_id:
            results.record("Reservation: stale expiry cleanup", False, "no quota_def", skip=True)
            return

        await pool.execute("""
            INSERT INTO reservations (id, request_uuid, model_id, quota_definition_id,
                                       reserved_amount, state, expires_at)
            VALUES ($1, $2, $3, $4, 100, 'pending', NOW() - INTERVAL '2 minutes')
        """, rid, req_id, model_id, qd_id)

        # Also inflate reserved
        await pool.execute("""
            UPDATE quota_usage SET reserved = reserved + 100
            WHERE quota_definition_id = $1 AND window_end > NOW()
        """, qd_id)

        before_reserved = await pool.fetchval(
            "SELECT reserved FROM quota_usage WHERE quota_definition_id=$1 AND window_end > NOW()",
            qd_id,
        )

        await reservation.expire_stale_reservations(pool)

        state = await pool.fetchval("SELECT state FROM reservations WHERE id=$1", rid)
        after_reserved = await pool.fetchval(
            "SELECT reserved FROM quota_usage WHERE quota_definition_id=$1 AND window_end > NOW()",
            qd_id,
        )

        ok = state == "expired" and (after_reserved or 0) < (before_reserved or 0)
        results.record("Reservation: stale expiry cleans up and decrements reserved", ok,
                       f"state={state}, before_reserved={before_reserved}, after_reserved={after_reserved}")
    except Exception as e:
        results.record("Reservation: stale expiry cleanup", False, str(e))
    finally:
        if model_id:
            await reset_quota_usage(pool, model_id)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. HEALTH / CIRCUIT BREAKER TESTS
# ═══════════════════════════════════════════════════════════════════════════════

async def test_health_success_updates_latency():
    """update_success() sets average_latency via EMA."""
    pool = await get_test_pool()
    model_id = None
    try:
        model_id = await get_any_model_id(pool, "PRIMARY_FREE")
        if not model_id:
            results.record("Health: success updates latency EMA", False, "no model")
            return
        await reset_model_health(pool, model_id)

        await health.update_success(pool, model_id, 500.0)
        lat = await pool.fetchval(
            "SELECT average_latency FROM model_health WHERE model_id=$1", model_id
        )
        results.record("Health: first success sets average_latency=500ms",
                       abs((lat or 0) - 500.0) < 1.0, f"Got {lat}")

        # Second call should EMA towards new value
        await health.update_success(pool, model_id, 1000.0)
        lat2 = await pool.fetchval(
            "SELECT average_latency FROM model_health WHERE model_id=$1", model_id
        )
        # EMA: 500 * 0.8 + 1000 * 0.2 = 600
        expected = 500 * 0.8 + 1000 * 0.2
        results.record("Health: EMA latency calculation correct",
                       abs((lat2 or 0) - expected) < 2.0,
                       f"Expected ~{expected:.1f}, got {lat2}")
    except Exception as e:
        results.record("Health: success updates latency EMA", False, str(e))
    finally:
        if model_id:
            await reset_model_health(pool, model_id)


async def test_health_failure_increments_counter():
    """update_failure() increments consecutive_failures."""
    pool = await get_test_pool()
    model_id = None
    try:
        model_id = await get_any_model_id(pool, "PRIMARY_FREE")
        if not model_id:
            results.record("Health: failure increments counter", False, "no model")
            return
        await reset_model_health(pool, model_id)

        for i in range(1, FAILURE_THRESHOLD):
            await health.update_failure(pool, model_id)
            count = await pool.fetchval(
                "SELECT consecutive_failures FROM model_health WHERE model_id=$1", model_id
            )
            healthy = await pool.fetchval(
                "SELECT healthy FROM model_health WHERE model_id=$1", model_id
            )
            ok = count == i and healthy is True
            results.record(
                f"Health: failure #{i} → consecutive={i}, still healthy",
                ok, f"count={count}, healthy={healthy}",
            )
    except Exception as e:
        results.record("Health: failure increments counter", False, str(e))
    finally:
        if model_id:
            await reset_model_health(pool, model_id)


async def test_health_circuit_breaker_opens():
    """After FAILURE_THRESHOLD failures, model is marked unhealthy with disabled_until."""
    pool = await get_test_pool()
    model_id = None
    try:
        model_id = await get_any_model_id(pool, "PRIMARY_FREE")
        if not model_id:
            results.record("Health: circuit breaker opens", False, "no model")
            return
        await reset_model_health(pool, model_id)

        for _ in range(FAILURE_THRESHOLD):
            await health.update_failure(pool, model_id)

        row = await pool.fetchrow(
            "SELECT healthy, consecutive_failures, disabled_until FROM model_health WHERE model_id=$1",
            model_id,
        )
        ok = (
            row["healthy"] is False
            and row["consecutive_failures"] >= FAILURE_THRESHOLD
            and row["disabled_until"] is not None
            and row["disabled_until"] > datetime.now(timezone.utc)
        )
        results.record(
            f"Health: circuit breaker opens after {FAILURE_THRESHOLD} failures",
            ok,
            f"healthy={row['healthy']}, disabled_until={row['disabled_until']}",
        )
    except Exception as e:
        results.record("Health: circuit breaker opens", False, str(e))
    finally:
        if model_id:
            await reset_model_health(pool, model_id)


async def test_health_circuit_breaker_backoff_progression():
    """Backoff increases exponentially: 30s, 120s, 300s, 900s."""
    from router.health import _backoff_seconds, FAILURE_THRESHOLD, BACKOFF_SECONDS
    cases = [
        (FAILURE_THRESHOLD,     BACKOFF_SECONDS[0]),
        (FAILURE_THRESHOLD + 1, BACKOFF_SECONDS[1]),
        (FAILURE_THRESHOLD + 2, BACKOFF_SECONDS[2]),
        (FAILURE_THRESHOLD + 3, BACKOFF_SECONDS[3]),
        (FAILURE_THRESHOLD + 99, BACKOFF_SECONDS[-1]),  # capped
    ]
    for failures, expected_backoff in cases:
        got = _backoff_seconds(failures)
        ok = got == expected_backoff
        results.record(
            f"Health: backoff({failures} failures) = {expected_backoff}s",
            ok, f"Got {got}s",
        )


async def test_health_recovery_after_success():
    """update_success() after circuit breaker resets consecutive_failures to 0."""
    pool = await get_test_pool()
    model_id = None
    try:
        model_id = await get_any_model_id(pool, "PRIMARY_FREE")
        if not model_id:
            results.record("Health: recovery resets circuit breaker", False, "no model")
            return
        await reset_model_health(pool, model_id)

        # Trip the circuit breaker
        for _ in range(FAILURE_THRESHOLD):
            await health.update_failure(pool, model_id)

        # Simulate recovery
        await health.update_success(pool, model_id, 300.0)

        row = await pool.fetchrow(
            "SELECT healthy, consecutive_failures, disabled_until FROM model_health WHERE model_id=$1",
            model_id,
        )
        ok = (
            row["healthy"] is True
            and row["consecutive_failures"] == 0
            and row["disabled_until"] is None
        )
        results.record("Health: success after CB resets to healthy=True, failures=0", ok,
                       f"healthy={row['healthy']}, failures={row['consecutive_failures']}, until={row['disabled_until']}")
    except Exception as e:
        results.record("Health: recovery resets circuit breaker", False, str(e))
    finally:
        if model_id:
            await reset_model_health(pool, model_id)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. GRAPH CONDITIONAL EDGE LOGIC (pure unit — no DB, no LLM)
# ═══════════════════════════════════════════════════════════════════════════════

def test_edge_after_llm_success():
    state = {
        "llm_error": None, "response": "hello", "attempt": 1
    }
    result = after_llm(state)
    ok = result == "update_node"
    results.record("Edge: after_llm with success → update_node", ok, f"Got '{result}'")


def test_edge_after_llm_failure_retries():
    state = {
        "llm_error": "timeout", "response": None, "attempt": 1
    }
    result = after_llm(state)
    ok = result == "handle_failure_node"
    results.record("Edge: after_llm with failure (attempt<MAX) → handle_failure_node", ok, f"Got '{result}'")


def test_edge_after_llm_failure_max_retries():
    from graph import MAX_RETRIES
    state = {
        "llm_error": "all failed", "response": None, "attempt": MAX_RETRIES
    }
    result = after_llm(state)
    ok = result == "fail_node"
    results.record(f"Edge: after_llm with failure at MAX_RETRIES={MAX_RETRIES} → fail_node", ok, f"Got '{result}'")


def test_edge_after_select_success():
    state = {"error": None, "reservation_id": "abc-123"}
    result = after_select(state)
    ok = result == "llm_node"
    results.record("Edge: after_select with reservation → llm_node", ok, f"Got '{result}'")


def test_edge_after_select_no_reservation():
    state = {"error": None, "reservation_id": None}
    result = after_select(state)
    ok = result == "router_node"
    results.record("Edge: after_select without reservation → router_node (retry)", ok, f"Got '{result}'")


def test_edge_after_select_fatal_error():
    state = {"error": "NoModelAvailable", "reservation_id": None}
    result = after_select(state)
    ok = result == "fail_node"
    results.record("Edge: after_select with fatal error → fail_node", ok, f"Got '{result}'")


def test_edge_after_failure_retries():
    state = {"error": None, "attempt": 2, "failed_models": ["some-uuid"]}
    result = after_failure(state)
    ok = result == "router_node"
    results.record("Edge: after_failure without error → router_node", ok, f"Got '{result}'")


def test_edge_after_failure_fatal():
    state = {"error": "NoModelAvailable", "attempt": 3}
    result = after_failure(state)
    ok = result == "fail_node"
    results.record("Edge: after_failure with routing error → fail_node", ok, f"Got '{result}'")


# ═══════════════════════════════════════════════════════════════════════════════
# 5. GRAPH INTEGRATION TESTS (mocked LLM, real DB)
# ═══════════════════════════════════════════════════════════════════════════════

async def test_graph_happy_path_mocked():
    """Full graph run with mocked LLM call — verifies routing + state transitions."""
    from router.router import RouterNode
    from langchain_core.messages import AIMessage

    mock_response = AIMessage(content="Test response from mock LLM")
    mock_response.usage_metadata = {"input_tokens": 50, "output_tokens": 30}

    with patch.object(RouterNode, "_build_llm_client") as mock_build:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_build.return_value = mock_llm

        try:
            result = await run_graph("Hello, mock test!", estimated_tokens=100)
            ok = (
                result.get("response") == "Test response from mock LLM"
                and result.get("error") is None
                and result.get("selected_model") is not None
                and result.get("selected_provider") is not None
            )
            results.record(
                f"Graph: happy path → response received from {result.get('selected_provider')}/{result.get('selected_model')}",
                ok,
                f"error={result.get('error')}, response={result.get('response')[:50] if result.get('response') else None}",
            )
        except Exception as e:
            results.record("Graph: happy path mocked", False, str(e))


async def test_graph_llm_failure_triggers_retry():
    """Graph retries on LLM failure and picks a different model."""
    from router.router import RouterNode
    from langchain_core.messages import AIMessage

    call_count = 0
    models_tried = []

    async def fake_invoke(messages):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("Simulated LLM timeout")
        return AIMessage(content="Recovered on retry")

    with patch.object(RouterNode, "_build_llm_client") as mock_build:
        mock_llm = MagicMock()
        mock_llm.ainvoke = fake_invoke
        mock_build.return_value = mock_llm

        try:
            result = await run_graph("Retry test", estimated_tokens=100)
            ok = (
                call_count >= 2
                and result.get("response") == "Recovered on retry"
                and result.get("attempt", 1) >= 2
            )
            results.record(
                f"Graph: LLM failure → retry on attempt {result.get('attempt')}",
                ok,
                f"calls={call_count}, attempt={result.get('attempt')}, error={result.get('error')}",
            )
        except Exception as e:
            results.record("Graph: LLM failure triggers retry", False, str(e))


async def test_graph_all_retries_exhausted():
    """Graph returns error state when all retries fail."""
    from router.router import RouterNode

    async def always_fail(messages):
        raise Exception("Always fails")

    with patch.object(RouterNode, "_build_llm_client") as mock_build:
        mock_llm = MagicMock()
        mock_llm.ainvoke = always_fail
        mock_build.return_value = mock_llm

        try:
            from graph import MAX_RETRIES
            result = await run_graph("Fail everything", estimated_tokens=50)
            ok = (
                result.get("response") is None
                and result.get("error") is not None
            )
            results.record(
                "Graph: all retries exhausted → error state, no response",
                ok,
                f"response={result.get('response')}, error={result.get('error')}",
            )
        except Exception as e:
            results.record("Graph: all retries exhausted", False, str(e))


async def test_graph_state_fields_populated():
    """After a successful graph run, all key state fields are populated."""
    from router.router import RouterNode
    from langchain_core.messages import AIMessage

    mock_response = AIMessage(content="field check response")
    mock_response.usage_metadata = {"input_tokens": 10, "output_tokens": 5}

    with patch.object(RouterNode, "_build_llm_client") as mock_build:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_build.return_value = mock_llm

        try:
            result = await run_graph("state fields test", estimated_tokens=100)
            required_fields = [
                "selected_model", "selected_provider", "selected_model_id",
                "selected_provider_id", "selected_tier", "request_uuid",
                "response", "latency_ms",
            ]
            missing = [f for f in required_fields if result.get(f) is None]
            ok = len(missing) == 0
            results.record("Graph: all required state fields populated after success",
                           ok, f"Missing: {missing}")
        except Exception as e:
            results.record("Graph: state fields populated", False, str(e))


async def test_graph_request_log_written():
    """Successful graph run writes an entry to request_log table."""
    from router.router import RouterNode
    from langchain_core.messages import AIMessage
    pool = await get_test_pool()

    mock_response = AIMessage(content="log test response")
    mock_response.usage_metadata = {"input_tokens": 20, "output_tokens": 10}

    with patch.object(RouterNode, "_build_llm_client") as mock_build:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_build.return_value = mock_llm

        try:
            result = await run_graph("log write test", estimated_tokens=100)
            req_uuid = result.get("request_uuid")

            if req_uuid:
                count = await pool.fetchval(
                    "SELECT COUNT(*) FROM request_log WHERE request_uuid=$1::uuid",
                    UUID(req_uuid),
                )
                ok = count >= 1
                results.record("Graph: successful run writes to request_log", ok,
                               f"request_log rows for uuid={req_uuid}: {count}")
            else:
                results.record("Graph: request_log written", False, "No request_uuid in state")
        except Exception as e:
            results.record("Graph: request_log written", False, str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# 6. EDGE CASES
# ═══════════════════════════════════════════════════════════════════════════════

async def test_edge_zero_token_request():
    """Graph handles estimated_tokens=0 without crashing."""
    from router.router import RouterNode
    from langchain_core.messages import AIMessage

    mock_response = AIMessage(content="zero token test")
    with patch.object(RouterNode, "_build_llm_client") as mock_build:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_build.return_value = mock_llm
        try:
            result = await run_graph("zero tokens", estimated_tokens=0)
            ok = result.get("error") is None
            results.record("Edge: estimated_tokens=0 doesn't crash router", ok,
                           f"error={result.get('error')}")
        except Exception as e:
            results.record("Edge: estimated_tokens=0", False, str(e))


async def test_edge_very_large_token_request():
    """Router skips models whose quota can't fit a huge token request."""
    pool = await get_test_pool()
    try:
        # Request 999_999_999 tokens — no model can fit this
        candidate = await select_model_waterfall(pool, estimated_tokens=999_999_999)
        # Only models with no quotas (e.g. LOCAL) or LIFETIME quotas might match
        # This verifies the system doesn't crash, and either returns None or LOCAL
        ok = candidate is None or candidate.tier in ("LOCAL", "SECONDARY_FREE")
        results.record(
            f"Edge: huge token request → {'no model' if candidate is None else candidate.tier}",
            ok, f"Got {candidate}",
        )
    except Exception as e:
        results.record("Edge: very large token request", False, str(e))


async def test_edge_disabled_provider_not_selected():
    """Models from a disabled provider are not selected."""
    pool = await get_test_pool()
    try:
        # Disable Groq provider temporarily
        await pool.execute("UPDATE providers SET enabled=false WHERE name='groq'")

        # All Groq models should not be selected
        rows = await pool.fetch(
            "SELECT m.id FROM models m JOIN providers p ON p.id=m.provider_id WHERE p.name='groq'"
        )
        groq_ids = {row["id"] for row in rows}

        candidate = await select_model(pool, "PRIMARY_FREE", 100)
        ok = candidate is None or candidate.model_id not in groq_ids
        results.record("Edge: disabled provider's models not selected", ok,
                       f"Groq model selected despite provider disabled: {candidate}")
    except Exception as e:
        results.record("Edge: disabled provider not selected", False, str(e))
    finally:
        await pool.execute("UPDATE providers SET enabled=true WHERE name='groq'")


async def test_edge_tencent_expiry_approaching():
    """tencent/hy3:free with expires_at=2026-07-21 shows in availability table correctly."""
    pool = await get_test_pool()
    try:
        row = await pool.fetchrow("""
            SELECT m.model_name, ml.expires_at, ma.available
            FROM models m
            JOIN model_lifecycle ml ON ml.model_id = m.id
            JOIN model_availability ma ON ma.model_id = m.id
            WHERE m.model_name = 'tencent/hy3:free'
        """)
        if not row:
            results.record("Edge: tencent/hy3:free expiry tracked", False,
                           "Model not found in DB", skip=True)
            return
        # Expiry should be set and still in the future (expires 2026-07-21)
        ok = row["expires_at"] is not None
        results.record(
            f"Edge: tencent/hy3:free has expires_at={row['expires_at'].date() if row['expires_at'] else None}",
            ok, "expires_at should not be NULL",
        )
    except Exception as e:
        results.record("Edge: tencent/hy3:free expiry tracked", False, str(e))


async def test_edge_local_model_no_quota_needed():
    """LOCAL tier model (llama.cpp) is selectable even with huge token count."""
    pool = await get_test_pool()
    try:
        # Exclude ALL non-LOCAL models
        rows = await pool.fetch(
            "SELECT id FROM models WHERE tier != 'LOCAL'::tier_enum"
        )
        non_local_ids = [r["id"] for r in rows]

        candidate = await select_model_waterfall(
            pool, estimated_tokens=999_999, excluded_model_ids=non_local_ids
        )
        ok = candidate is not None and candidate.tier == "LOCAL"
        results.record("Edge: LOCAL tier model selected with no quota restriction", ok,
                       f"Got {candidate}")
    except Exception as e:
        results.record("Edge: LOCAL model no quota needed", False, str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# 7. CONCURRENCY TEST — parallel requests don't double-select same model
# ═══════════════════════════════════════════════════════════════════════════════

async def test_concurrency_round_robin_parallel():
    """10 concurrent selector calls don't all pick the same model (round-robin working)."""
    pool = await get_test_pool()
    try:
        N = 10
        tasks = [select_model(pool, "PRIMARY_FREE", 50) for _ in range(N)]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        candidates = [r for r in results_list if isinstance(r, ModelCandidate)]
        errors = [r for r in results_list if isinstance(r, Exception)]

        model_ids = [c.model_id for c in candidates if c]
        unique_models = set(model_ids)

        ok = len(errors) == 0 and len(unique_models) >= 2
        results.record(
            f"Concurrency: {N} parallel selects → {len(unique_models)} distinct models, {len(errors)} errors",
            ok,
            f"errors={errors[:2] if errors else None}",
        )
    except Exception as e:
        results.record("Concurrency: parallel round-robin", False, str(e))


async def test_concurrency_no_double_reservation():
    """Two concurrent reserve() calls on same model don't both succeed when quota is 1."""
    pool = await get_test_pool()
    model_id = None
    try:
        m = await get_model_by_name(pool, "gemini-2.5-flash")
        if not m:
            results.record("Concurrency: no double reservation", False, "model not found")
            return
        model_id = m["id"]
        await reset_quota_usage(pool, model_id)

        # Set the quota to exactly 1 token (so only one reservation fits)
        await pool.execute("""
            UPDATE quota_usage qu
            SET used = qd.limit_value - 1, reserved = 0
            FROM quota_definitions qd
            WHERE qu.quota_definition_id = qd.id
              AND qd.model_id = $1
              AND qd.quota_type = 'TOKENS'
              AND qd.quota_window = 'MINUTE'::quota_window_enum
              AND qu.window_end > NOW()
        """, model_id)

        req1, req2 = uuid4(), uuid4()
        r1, r2 = await asyncio.gather(
            reservation.reserve(pool, req1, model_id, 1),
            reservation.reserve(pool, req2, model_id, 1),
        )

        # At most one should succeed (SKIP LOCKED ensures no double reservation)
        successes = sum(1 for r in [r1, r2] if r is not None)
        ok = successes <= 1
        results.record(
            f"Concurrency: only 1 of 2 concurrent reserves succeeds when quota=1 (got {successes} successes)",
            ok,
            f"r1={r1}, r2={r2} — both shouldn't be non-None",
        )
    except Exception as e:
        results.record("Concurrency: no double reservation", False, str(e))
    finally:
        if model_id:
            await reset_quota_usage(pool, model_id)


# ═══════════════════════════════════════════════════════════════════════════════
# 9. CHATROUTER WRAPPER
# ═══════════════════════════════════════════════════════════════════════════════

async def test_chat_router_happy_path():
    """ChatRouter custom ChatModel successfully routes and invokes through the graph."""
    from router.chat_model import ChatRouter
    from router.router import RouterNode
    from langchain_core.messages import AIMessage, HumanMessage

    mock_response = AIMessage(content="Hello from ChatRouter")
    mock_response.usage_metadata = {"input_tokens": 10, "output_tokens": 5}

    with patch.object(RouterNode, "_build_llm_client") as mock_build:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_build.return_value = mock_llm

        try:
            llm = ChatRouter()
            response = await llm.ainvoke([HumanMessage(content="Test chat router")])
            ok = (
                response is not None
                and response.content == "Hello from ChatRouter"
                and response.response_metadata.get("model_name") is not None
            )
            results.record("ChatRouter: custom chat model wrapper works", ok, f"Response: {response}")
        except Exception as e:
            results.record("ChatRouter: custom chat model wrapper works", False, str(e))


async def test_chat_router_respects_tags():
    """ChatRouter correctly passes down required_tags configured in invoke config."""
    from router.chat_model import ChatRouter
    from router.router import RouterNode
    from langchain_core.messages import AIMessage, HumanMessage

    mock_response = AIMessage(content="Hello from tagged model")
    mock_response.usage_metadata = {"input_tokens": 10, "output_tokens": 5}

    captured_state = {}

    # Patch select to capture the input state
    async def select_spy(self, state):
        nonlocal captured_state
        captured_state = state.copy()
        return {
            **state,
            "selected_model": "gemini-2.5-flash",
            "selected_provider": "gemini",
            "selected_model_id": "7f204af6-ce5d-4d3f-8f6f-ad725c3d1e68",
            "selected_provider_id": "5285741e-355b-439d-b45d-da45cc0cd887",
            "selected_base_url": "http://mock",
            "selected_tier": "PRIMARY_FREE",
            "reservation_id": "22ffabcd-1234-5678-abcd-1234567890ab",
        }

    with patch.object(RouterNode, "select", select_spy), \
         patch.object(RouterNode, "_build_llm_client") as mock_build:
         
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_build.return_value = mock_llm

        try:
            llm = ChatRouter()
            await llm.ainvoke(
                [HumanMessage(content="Test tags")],
                config={"configurable": {"required_tags": ["vision", "coding"]}}
            )
            ok = captured_state.get("required_tags") == ["vision", "coding"]
            results.record("ChatRouter: passes config required_tags to state", ok,
                           f"Captured state required_tags: {captured_state.get('required_tags')}")
        except Exception as e:
            results.record("ChatRouter: passes config required_tags to state", False, str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# 8. STRUCTURED LOG FORMAT
# ═══════════════════════════════════════════════════════════════════════════════

async def test_logger_output_is_valid_json(capsys=None):
    """logger.log_request() emits valid JSON to stdout."""
    import io
    from contextlib import redirect_stdout
    from router.logger import log_request
    pool = await get_test_pool()

    # Get a real model/provider for the FK constraint
    row = await pool.fetchrow("""
        SELECT m.id as mid, m.provider_id as pid
        FROM models m WHERE m.enabled=true LIMIT 1
    """)
    if not row:
        results.record("Logger: emits valid JSON", False, "no model found", skip=True)
        return

    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            await log_request(
                pool,
                request_uuid=uuid4(),
                provider_id=row["pid"],
                model_id=row["mid"],
                provider_name="test_provider",
                model_name="test_model",
                tier="PRIMARY_FREE",
                status="success",
                attempt=1,
                prompt_tokens=10,
                completion_tokens=20,
                latency_ms=500,
                http_status=200,
            )

        output = buf.getvalue().strip()
        parsed = json.loads(output)
        ok = (
            parsed.get("provider") == "test_provider"
            and parsed.get("status") == "success"
            and parsed.get("total_tokens") == 30
            and "ts" in parsed
            and "uuid" in parsed
        )
        results.record("Logger: output is valid JSON with all expected fields", ok,
                       f"Parsed: {parsed}")
    except Exception as e:
        results.record("Logger: emits valid JSON", False, str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN TEST RUNNER
# ═══════════════════════════════════════════════════════════════════════════════

async def run_all_tests():
    print(f"\n{'═'*70}")
    print("  HR AI ROUTER — COMPREHENSIVE TEST SUITE")
    print(f"{'═'*70}\n")

    sections = [
        ("1. DATABASE / SELECTOR", [
            test_db_connection,
            test_all_tiers_populated,
            test_health_and_score_rows_exist,
            test_selector_primary_free,
            test_selector_respects_exclusion_list,
            test_selector_skips_unhealthy_models,
            test_selector_skips_circuit_breaker,
            test_selector_skips_expired_model,
            test_selector_round_robin,
            test_selector_waterfall_falls_to_secondary,
            test_selector_waterfall_none_when_all_exhausted,
            test_selector_respects_tags,
        ]),
        ("2. RESERVATION", [
            test_reservation_reserve_and_confirm,
            test_reservation_release,
            test_reservation_quota_exhaustion_blocks_select,
            test_reservation_stale_expiry,
        ]),
        ("3. HEALTH / CIRCUIT BREAKER", [
            test_health_success_updates_latency,
            test_health_failure_increments_counter,
            test_health_circuit_breaker_opens,
            test_health_circuit_breaker_backoff_progression,
            test_health_recovery_after_success,
        ]),
        ("4. GRAPH EDGE LOGIC (unit)", [
            test_edge_after_llm_success,
            test_edge_after_llm_failure_retries,
            test_edge_after_llm_failure_max_retries,
            test_edge_after_select_success,
            test_edge_after_select_no_reservation,
            test_edge_after_select_fatal_error,
            test_edge_after_failure_retries,
            test_edge_after_failure_fatal,
        ]),
        ("5. GRAPH INTEGRATION (mocked LLM)", [
            test_graph_happy_path_mocked,
            test_graph_llm_failure_triggers_retry,
            test_graph_all_retries_exhausted,
            test_graph_state_fields_populated,
            test_graph_request_log_written,
        ]),
        ("6. EDGE CASES", [
            test_edge_zero_token_request,
            test_edge_very_large_token_request,
            test_edge_disabled_provider_not_selected,
            test_edge_tencent_expiry_approaching,
            test_edge_local_model_no_quota_needed,
        ]),
        ("7. CONCURRENCY", [
            test_concurrency_round_robin_parallel,
            test_concurrency_no_double_reservation,
        ]),
        ("8. STRUCTURED LOGGING", [
            test_logger_output_is_valid_json,
        ]),
        ("9. CHATROUTER WRAPPER", [
            test_chat_router_happy_path,
            test_chat_router_respects_tags,
        ]),
    ]

    for section_name, tests in sections:
        print(f"\n{SEPARATOR}")
        print(f"  {section_name}")
        print(SEPARATOR)
        for test_fn in tests:
            try:
                if asyncio.iscoroutinefunction(test_fn):
                    await test_fn()
                else:
                    test_fn()
            except Exception as e:
                results.record(test_fn.__name__, False, f"Unhandled exception: {e}")

    all_passed = results.summary()
    await close_pool()
    return all_passed


if __name__ == "__main__":
    ok = asyncio.run(run_all_tests())
    sys.exit(0 if ok else 1)
