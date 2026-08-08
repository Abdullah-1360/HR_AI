"""
app/repositories/match_repository.py
Database access layer for the `candidate_matches` table.
"""
import json
import logging
from typing import Any, Dict, List
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


async def upsert_match(
    pool: asyncpg.Pool,
    *,
    job_id: str | UUID,
    candidate_id: str | UUID,
    match_score: int,
    evaluation_report: Dict[str, Any],
) -> None:
    """Insert or update a match evaluation for a (job, candidate) pair."""
    await pool.execute(
        """
        INSERT INTO candidate_matches (job_id, candidate_id, match_score, evaluation_report)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (job_id, candidate_id)
        DO UPDATE SET
            match_score        = EXCLUDED.match_score,
            evaluation_report  = EXCLUDED.evaluation_report,
            created_at         = NOW()
        """,
        str(job_id),
        str(candidate_id),
        match_score,
        json.dumps(evaluation_report),
    )


async def get_matches_for_job(
    pool: asyncpg.Pool,
    job_id: str | UUID,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """
    Return ranked match results for a job, joined with candidate basics.
    Sorted by match_score descending.
    """
    rows = await pool.fetch(
        """
        SELECT
            cm.candidate_id,
            cm.match_score,
            cm.evaluation_report,
            cm.created_at,
            c.name,
            c.email,
            c.skills,
            c.experience_years
        FROM candidate_matches cm
        JOIN candidates c ON c.id = cm.candidate_id
        WHERE cm.job_id = $1
        ORDER BY cm.match_score DESC
        LIMIT $2
        """,
        str(job_id),
        limit,
    )
    res = []
    for r in rows:
        d = dict(r)
        d["evaluation_report"] = _parse_json(d.get("evaluation_report"))
        res.append(d)
    return res


async def get_match(
    pool: asyncpg.Pool,
    job_id: str | UUID,
    candidate_id: str | UUID,
) -> Dict[str, Any] | None:
    """Fetch a single match evaluation for a (job, candidate) pair."""
    row = await pool.fetchrow(
        """
        SELECT job_id, candidate_id, match_score, evaluation_report, created_at
        FROM candidate_matches
        WHERE job_id = $1 AND candidate_id = $2
        """,
        str(job_id),
        str(candidate_id),
    )
    if not row:
        return None
    res = dict(row)
    res["evaluation_report"] = _parse_json(res.get("evaluation_report"))
    return res

