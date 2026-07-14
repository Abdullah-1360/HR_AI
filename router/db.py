"""
router/db.py
asyncpg connection pool — singleton, shared across the entire process.
"""

from __future__ import annotations

import asyncpg
import os
import logging

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    """Return the singleton asyncpg connection pool, creating it on first call."""
    global _pool
    if _pool is None:
        dsn = os.environ.get("DATABASE_URL")
        if not dsn:
            raise RuntimeError(
                "DATABASE_URL environment variable is not set. "
                "Add it to .env: DATABASE_URL=postgresql://hr_ai:hr_ai_secret@localhost:5432/hr_ai_router"
            )
        _pool = await asyncpg.create_pool(
            dsn=dsn,
            min_size=2,
            max_size=20,
            command_timeout=10,
            statement_cache_size=100,
        )
        logger.info("asyncpg pool created (min=2, max=20)")
    return _pool


async def close_pool() -> None:
    """Gracefully close the connection pool on shutdown."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("asyncpg pool closed")
