"""
app/services/hiring_service.py
Hiring workflow orchestration service.
Handles matching, ranking, and interview generation without the full LangGraph supervisor
(used by individual REST endpoints). Full pipeline uses hiring_graph.py.
"""
import json
import logging
from typing import Any, Dict, List, Optional

import asyncpg

from router.chat_model import ChatRouter
from app.ai.agents.matching_agent import score_candidate, rank_candidates
from app.ai.agents.interview_agent import generate_interview_pack
from app.ai.schemas.job_schemas import ParsedJob
from app.ai.schemas.resume_schemas import ParsedResume
from app.ai.schemas.match_schemas import RankedCandidate
from app.ai.schemas.interview_schemas import InterviewPack
from app.ai.retrievers.vector_retriever import find_top_candidates
from app.services.hybrid_search import hybrid_search_candidates
from app.repositories.job_repository import get_job_by_id, get_job_embedding
from app.repositories.candidate_repository import get_candidates_by_ids
from app.repositories.match_repository import upsert_match, get_matches_for_job

logger = logging.getLogger(__name__)


async def match_candidates_for_job(
    pool: asyncpg.Pool,
    job_id: str,
    top_k: int = 20,
    tenant_id: str = "default",
    llm: Optional[ChatRouter] = None,
) -> List[RankedCandidate]:
    """
    Run the full candidate matching pipeline for a job:
      1. Retrieve job embedding from DB
      2. Hybrid search (Dense Vector + BM25 Lexical RRF + Cohere Rerank v3)
      3. Load structured parsed_resume for each candidate
      4. LLM score each candidate concurrently
      5. Persist match scores
      6. Return sorted RankedCandidate list
    """
    # Step 1: Load job
    job_row = await get_job_by_id(pool, job_id)
    if not job_row:
        raise ValueError(f"Job {job_id} not found")

    parsed_job = ParsedJob(**job_row["parsed_requirements"])
    job_title_and_desc = f"{job_row.get('title', '')} {job_row.get('description', '')}"

    # Step 2: Get job embedding
    job_embedding = await get_job_embedding(pool, job_id)
    if not job_embedding:
        raise ValueError(f"Job {job_id} has no embedding — was it created with the service?")

    # Step 3: Hybrid Search Retrieval (Dense + Sparse RRF + Cohere Rerank)
    hybrid_results = await hybrid_search_candidates(
        pool,
        job_embedding=job_embedding,
        query_text=job_title_and_desc,
        tenant_id=tenant_id,
        top_k=top_k,
    )
    if not hybrid_results:
        # Fallback to vector search if hybrid returned empty (e.g. initial dev state)
        hybrid_results = await find_top_candidates(pool, job_embedding, top_k=top_k)

    if not hybrid_results:
        logger.warning("hiring_service.match no candidates found for job=%s", job_id)
        return []


    # Step 4: Build (id, ParsedResume) pairs for scoring
    candidate_ids = [str(r["id"]) for r in hybrid_results]
    candidate_rows = await get_candidates_by_ids(pool, candidate_ids)


    pairs: List[tuple[str, ParsedResume]] = []
    for row in candidate_rows:
        try:
            pr_data = row["parsed_resume"]
            if isinstance(pr_data, str):
                pr_data = json.loads(pr_data)
            parsed_resume = ParsedResume(**pr_data)
            pairs.append((str(row["id"]), parsed_resume))
        except Exception as exc:
            logger.warning(
                "hiring_service.skip_candidate id=%s reason=%s", row["id"], exc
            )

    # Step 5: Concurrent LLM scoring + ranking
    ranked = await rank_candidates(parsed_job, pairs, llm=llm)

    # Step 6: Persist to DB
    for rc in ranked:
        await upsert_match(
            pool,
            job_id=job_id,
            candidate_id=rc.candidate_id,
            match_score=rc.match.overall_score,
            evaluation_report=rc.match.model_dump(),
        )

    logger.info(
        "hiring_service.matched job=%s candidates_ranked=%d", job_id, len(ranked)
    )
    return ranked


async def create_interview_pack(
    pool: asyncpg.Pool,
    job_id: str,
    candidate_id: str,
    llm: Optional[ChatRouter] = None,
) -> InterviewPack:
    """
    Generate an interview pack for a (job, candidate) pair.
    Uses the persisted match evaluation as context if available.
    """
    from app.repositories.match_repository import get_match

    job_row = await get_job_by_id(pool, job_id)
    if not job_row:
        raise ValueError(f"Job {job_id} not found")

    candidate_rows = await get_candidates_by_ids(pool, [candidate_id])
    if not candidate_rows:
        raise ValueError(f"Candidate {candidate_id} not found")

    parsed_job = ParsedJob(**job_row["parsed_requirements"])
    pr_data = candidate_rows[0]["parsed_resume"]
    if isinstance(pr_data, str):
        pr_data = json.loads(pr_data)
    parsed_resume = ParsedResume(**pr_data)

    # Load prior match result if available
    match_row = await get_match(pool, job_id, candidate_id)
    match_result = None
    if match_row:
        from app.ai.schemas.match_schemas import MatchResult
        try:
            er = match_row["evaluation_report"]
            if isinstance(er, str):
                er = json.loads(er)
            match_result = MatchResult(**er)
        except Exception:
            pass

    return await generate_interview_pack(
        job=parsed_job,
        candidate=parsed_resume,
        match_result=match_result,
        llm=llm,
    )


async def get_ranked_matches(
    pool: asyncpg.Pool,
    job_id: str,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Return persisted ranked matches for a job from the DB."""
    return await get_matches_for_job(pool, job_id, limit=limit)
