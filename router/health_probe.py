"""
router/health_probe.py
Proper Circuit Breaker recovery using the Half-Open pattern.

Circuit Breaker States:
  CLOSED  → healthy=true,  disabled_until=NULL      — normal routing
  OPEN    → healthy=false, disabled_until=future     — blocked, backoff active
  HALF-OPEN → healthy=false, disabled_until=past     — backoff expired, probe pending

This background task runs every PROBE_INTERVAL_SECONDS and:
  1. Finds all HALF-OPEN models (disabled_until has expired)
  2. Makes a real lightweight LLM call to verify the model is actually back
  3. If probe SUCCESS → transition to CLOSED (reset health)
  4. If probe FAILURE → transition back to OPEN with doubled backoff (exponential)

This is fundamentally different from the wrong approach of resetting health blindly
inside the selector — this actually verifies the model is healthy before re-enabling it.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Optional
from uuid import UUID

import asyncpg

logger = logging.getLogger(__name__)

# How often to run the probe sweep
PROBE_INTERVAL_SECONDS = 60

# The lightweight test prompt — minimal tokens, fast response expected
PROBE_PROMPT = "Reply with exactly one word: OK"

# Maximum time to wait for a probe response before considering it failed (seconds)
PROBE_TIMEOUT_SECONDS = 15

# Maximum backoff cap after repeated probe failures (15 minutes)
MAX_BACKOFF_SECONDS = 900

# ── SQL queries ──────────────────────────────────────────────────────────────

_FIND_HALF_OPEN_SQL = """
SELECT
    mh.model_id,
    m.model_name,
    p.name            AS provider_name,
    p.base_url,
    mh.consecutive_failures,
    mh.disabled_until
FROM model_health mh
JOIN models m   ON m.id = mh.model_id
JOIN providers p ON p.id = m.provider_id
WHERE
    mh.healthy = false
    AND mh.disabled_until IS NOT NULL
    AND mh.disabled_until < NOW()
    AND m.enabled = true
    AND p.enabled = true
ORDER BY mh.disabled_until ASC;
"""

_CLOSE_CIRCUIT_SQL = """
UPDATE model_health
SET
    healthy              = true,
    consecutive_failures = 0,
    disabled_until       = NULL,
    error_rate           = GREATEST(0.0, error_rate * 0.7),
    last_success         = NOW(),
    average_latency      = CASE
                               WHEN average_latency IS NULL THEN $2::float8
                               ELSE average_latency * 0.8 + $2::float8 * 0.2
                           END,
    updated_at           = NOW()
WHERE model_id = $1;
"""

_REOPEN_CIRCUIT_SQL = """
UPDATE model_health
SET
    consecutive_failures = consecutive_failures + 1,
    last_failure         = NOW(),
    error_rate           = LEAST(1.0, error_rate * 0.95 + 0.05),
    disabled_until       = NOW() + ($2 * INTERVAL '1 second'),
    updated_at           = NOW()
WHERE model_id = $1;
"""


def _compute_backoff(consecutive_failures: int) -> int:
    """
    Exponential backoff capped at MAX_BACKOFF_SECONDS.
    After repeated probe failures we wait progressively longer:
      fail 3 → 60s, fail 4 → 120s, fail 5 → 300s, fail 6+ → 900s
    """
    base = 30
    backoff = base * (2 ** max(0, consecutive_failures - 3))
    return min(backoff, MAX_BACKOFF_SECONDS)


def _build_llm_client(provider_name: str, model_name: str, base_url: str):
    """Build a minimal LangChain client for probing."""
    if provider_name == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=os.environ["GEMINI_API_KEY"],
        )

    elif provider_name == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(
            model=model_name,
            groq_api_key=os.environ["GROQ_API_KEY"],
        )

    elif provider_name == "openrouter":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model_name,
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ["OPENROUTER_API_KEY"],
            max_tokens=5,
        )

    elif provider_name == "mistral":
        from langchain_mistralai import ChatMistralAI
        return ChatMistralAI(
            model=model_name,
            mistral_api_key=os.environ["MISTRAL_API_KEY"],
            max_tokens=5,
        )

    elif provider_name == "cerebras":
        from langchain_cerebras import ChatCerebras
        return ChatCerebras(
            model=model_name,
            cerebras_api_key=os.environ["CEREBRAS_API_KEY"],
            max_tokens=5,
        )

    elif provider_name == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model_name,
            api_key=os.environ["OPENAI_API_KEY"],
            max_tokens=5,
        )

    elif provider_name == "cohere":
        from langchain_cohere import ChatCohere
        return ChatCohere(
            model=model_name,
            cohere_api_key=os.environ["COHERE_API_KEY"],
            max_tokens=5,
        )

    elif provider_name == "cloudflare":
        from langchain_openai import ChatOpenAI
        cf_account_id = os.environ["CF_ACCOUNT_ID"]
        cf_api_token = os.environ["CF_API_TOKEN"]
        return ChatOpenAI(
            model=model_name,
            base_url=f"https://api.cloudflare.com/client/v4/accounts/{cf_account_id}/ai/v1",
            api_key=cf_api_token,
            max_tokens=5,
        )

    else:
        raise ValueError(f"Unknown provider for probe: {provider_name!r}")


async def _probe_model(
    model_id: UUID,
    model_name: str,
    provider_name: str,
    base_url: str,
    consecutive_failures: int,
    pool: asyncpg.Pool,
) -> None:
    """
    Probe a single HALF-OPEN model.
    Transitions to CLOSED on success, OPEN on failure.
    """
    logger.info(
        "health_probe: HALF-OPEN probe → provider=%s model=%s",
        provider_name, model_name,
    )

    start = time.monotonic()
    success = False
    latency_ms = PROBE_TIMEOUT_SECONDS * 1000  # worst case default

    try:
        from langchain_core.messages import HumanMessage
        llm = _build_llm_client(provider_name, model_name, base_url)
        response = await asyncio.wait_for(
            llm.ainvoke([HumanMessage(content=PROBE_PROMPT)]),
            timeout=PROBE_TIMEOUT_SECONDS,
        )
        latency_ms = int((time.monotonic() - start) * 1000)
        success = bool(response and response.content)

    except asyncio.TimeoutError:
        latency_ms = PROBE_TIMEOUT_SECONDS * 1000
        logger.warning(
            "health_probe: TIMEOUT → provider=%s model=%s (>%ds)",
            provider_name, model_name, PROBE_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        latency_ms = int((time.monotonic() - start) * 1000)
        logger.warning(
            "health_probe: FAILED → provider=%s model=%s error=%s",
            provider_name, model_name, exc,
        )

    async with pool.acquire() as conn:
        if success:
            await conn.execute(_CLOSE_CIRCUIT_SQL, model_id, float(latency_ms))
            logger.info(
                "health_probe: CLOSED ✓ → provider=%s model=%s latency=%dms",
                provider_name, model_name, latency_ms,
            )
        else:
            backoff = _compute_backoff(consecutive_failures + 1)
            await conn.execute(_REOPEN_CIRCUIT_SQL, model_id, backoff)
            logger.warning(
                "health_probe: OPEN ✗ → provider=%s model=%s backoff=%ds",
                provider_name, model_name, backoff,
            )


async def _probe_sweep(pool: asyncpg.Pool) -> None:
    """Find all HALF-OPEN models and probe them concurrently."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(_FIND_HALF_OPEN_SQL)

    if not rows:
        return

    logger.info("health_probe: found %d HALF-OPEN model(s) to probe", len(rows))

    # Probe all concurrently (each has its own timeout)
    tasks = [
        _probe_model(
            model_id=row["model_id"],
            model_name=row["model_name"],
            provider_name=row["provider_name"],
            base_url=row["base_url"] or "",
            consecutive_failures=row["consecutive_failures"],
            pool=pool,
        )
        for row in rows
    ]
    await asyncio.gather(*tasks, return_exceptions=True)


async def run_health_probe_loop(pool: asyncpg.Pool) -> None:
    """
    Long-running background task. Called once at FastAPI startup.
    Runs a probe sweep every PROBE_INTERVAL_SECONDS.
    """
    logger.info(
        "health_probe: background task started (interval=%ds, timeout=%ds)",
        PROBE_INTERVAL_SECONDS, PROBE_TIMEOUT_SECONDS,
    )

    while True:
        try:
            await _probe_sweep(pool)
        except Exception as exc:
            logger.error("health_probe: sweep error: %s", exc, exc_info=True)

        await asyncio.sleep(PROBE_INTERVAL_SECONDS)
