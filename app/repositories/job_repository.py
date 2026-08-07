"""
app/repositories/job_repository.py
Database access layer for the `jobs` table.
All methods accept an asyncpg Pool and return plain dicts or None.
"""
import json
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

import asyncpg

logger = logging.getLogger(__name__)


def _parse_json(val: Any) -> Any:
    """Parse JSON string to dict/list if needed."""
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            pass
    return val


async def insert_job(
    pool: asyncpg.Pool,
    *,
    title: str,
    description: str,
    parsed_requirements: Dict[str, Any],
    embedding: List[float],
) -> Dict[str, Any]:
    """Insert a new job and return the created row as a dict."""
    row = await pool.fetchrow(
        """
        INSERT INTO jobs (title, description, parsed_requirements, embedding)
        VALUES ($1, $2, $3, $4::vector)
        RETURNING id, title, description, parsed_requirements, created_at
        """,
        title,
        description,
        json.dumps(parsed_requirements),
        str(embedding),
    )
    res = dict(row)
    res["parsed_requirements"] = _parse_json(res.get("parsed_requirements"))
    return res


async def get_job_by_id(
    pool: asyncpg.Pool,
    job_id: str | UUID,
) -> Optional[Dict[str, Any]]:
    """Fetch a single job by UUID. Returns None if not found."""
    row = await pool.fetchrow(
        """
        SELECT id, title, description, parsed_requirements, created_at
        FROM jobs WHERE id = $1
        """,
        str(job_id),
    )
    if row:
        res = dict(row)
        res["parsed_requirements"] = _parse_json(res.get("parsed_requirements"))
        return res
    return None


async def list_jobs(
    pool: asyncpg.Pool,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """Return a paginated list of jobs (newest first)."""
    rows = await pool.fetch(
        """
        SELECT id, title, description, parsed_requirements, created_at
        FROM jobs
        ORDER BY created_at DESC
        LIMIT $1 OFFSET $2
        """,
        limit,
        offset,
    )
    res = []
    for r in rows:
        d = dict(r)
        d["parsed_requirements"] = _parse_json(d.get("parsed_requirements"))
        res.append(d)
    return res


async def get_job_embedding(
    pool: asyncpg.Pool,
    job_id: str | UUID,
) -> Optional[List[float]]:
    """Return only the embedding vector for a job (for ANN search)."""
    row = await pool.fetchrow(
        "SELECT embedding::text FROM jobs WHERE id = $1",
        str(job_id),
    )
    if not row or row["embedding"] is None:
        return None
    raw = row["embedding"].strip("[]")
    return [float(x) for x in raw.split(",")]
