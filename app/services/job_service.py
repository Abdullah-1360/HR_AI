"""
app/services/job_service.py
Business logic for job creation — orchestrates job agent + embedder + repository.
"""
import logging
from typing import Any, Dict, Optional

import asyncpg

from router.chat_model import ChatRouter
from app.ai.agents.job_agent import analyze_job
from app.ai.schemas.job_schemas import ParsedJob
from app.repositories.job_repository import insert_job, get_job_by_id, list_jobs
from app.utils.embedder import embed_document

logger = logging.getLogger(__name__)


async def create_job(
    pool: asyncpg.Pool,
    *,
    title: str,
    raw_description: str,
    llm: Optional[ChatRouter] = None,
) -> Dict[str, Any]:
    """
    Full job creation pipeline:
      1. Analyse raw JD → ParsedJob (Job Understanding Agent)
      2. Generate semantic embedding of the description
      3. Persist to DB

    Returns the created job row as a dict with `parsed_requirements` included.
    """
    logger.info("job_service.create title=%r", title)

    # Step 1: Structured extraction
    parsed: ParsedJob = await analyze_job(
        raw_description=raw_description,
        title=title,
        llm=llm,
    )

    # Step 2: Embedding
    embedding = await embed_document(raw_description)

    # Step 3: Persist
    job_row = await insert_job(
        pool,
        title=parsed.title or title,
        description=raw_description,
        parsed_requirements=parsed.model_dump(),
        embedding=embedding,
    )

    logger.info("job_service.created job_id=%s", job_row["id"])
    return job_row


async def get_job(pool: asyncpg.Pool, job_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a job by ID. Returns None if not found."""
    return await get_job_by_id(pool, job_id)


async def list_all_jobs(
    pool: asyncpg.Pool,
    limit: int = 50,
    offset: int = 0,
) -> list[Dict[str, Any]]:
    """Return paginated job listing."""
    return await list_jobs(pool, limit=limit, offset=offset)
