"""
app/repositories/candidate_repository.py
Database access layer for the `candidates` table.
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


async def insert_candidate(
    pool: asyncpg.Pool,
    *,
    name: str,
    email: Optional[str],
    skills: List[str],
    experience_years: int,
    resume_url: Optional[str],
    parsed_resume: Dict[str, Any],
    embedding: List[float],
    tenant_id: str = "default",
) -> Dict[str, Any]:
    """Insert a new candidate and return the created row."""
    row = await pool.fetchrow(
        """
        INSERT INTO candidates
            (name, email, skills, experience_years, resume_url, parsed_resume, embedding, tenant_id)
        VALUES ($1, $2, $3, $4, $5, $6, $7::vector, $8)
        RETURNING id, name, email, skills, experience_years, resume_url, parsed_resume, tenant_id, created_at
        """,
        name,
        email,
        skills,
        experience_years,
        resume_url,
        json.dumps(parsed_resume),
        str(embedding),
        tenant_id,
    )
    res = dict(row)
    res["parsed_resume"] = _parse_json(res.get("parsed_resume"))
    return res



async def get_candidate_by_id(
    pool: asyncpg.Pool,
    candidate_id: str | UUID,
) -> Optional[Dict[str, Any]]:
    """Fetch a single candidate by UUID. Returns None if not found."""
    row = await pool.fetchrow(
        """
        SELECT id, name, email, skills, experience_years, resume_url, parsed_resume, created_at
        FROM candidates WHERE id = $1
        """,
        str(candidate_id),
    )
    if row:
        res = dict(row)
        res["parsed_resume"] = _parse_json(res.get("parsed_resume"))
        return res
    return None


async def list_candidates(
    pool: asyncpg.Pool,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """Return a paginated list of candidates (newest first)."""
    rows = await pool.fetch(
        """
        SELECT id, name, email, skills, experience_years, resume_url, parsed_resume, created_at
        FROM candidates
        ORDER BY created_at DESC
        LIMIT $1 OFFSET $2
        """,
        limit,
        offset,
    )
    res = []
    for r in rows:
        d = dict(r)
        d["parsed_resume"] = _parse_json(d.get("parsed_resume"))
        res.append(d)
    return res


async def get_candidates_by_ids(
    pool: asyncpg.Pool,
    candidate_ids: List[str],
) -> List[Dict[str, Any]]:
    """Batch-fetch candidates by a list of UUIDs."""
    rows = await pool.fetch(
        """
        SELECT id, name, email, skills, experience_years, parsed_resume, created_at
        FROM candidates
        WHERE id = ANY($1::uuid[])
        """,
        candidate_ids,
    )
    res = []
    for r in rows:
        d = dict(r)
        d["parsed_resume"] = _parse_json(d.get("parsed_resume"))
        res.append(d)
    return res
