"""
app/ai/retrievers/vector_retriever.py
pgvector-based ANN (Approximate Nearest Neighbour) candidate retrieval.
Uses cosine similarity via the <=> operator on HNSW indexes.
"""
import logging
from typing import Any, Dict, List

import asyncpg

logger = logging.getLogger(__name__)


async def find_top_candidates(
    pool: asyncpg.Pool,
    job_embedding: List[float],
    top_k: int = 20,
) -> List[Dict[str, Any]]:
    """
    Find the top-K candidate rows most semantically similar to a job embedding.
    Returns candidate metadata (without re-fetching embeddings).

    Args:
        pool: asyncpg connection pool.
        job_embedding: 1024-dim float list (Cohere embed-english-v3.0 output).
        top_k: Maximum number of candidates to return.

    Returns:
        List of dicts with keys: id, name, email, skills, experience_years,
        parsed_resume, cosine_distance.
    """
    # Format embedding as a pgvector literal
    embedding_literal = "[" + ",".join(str(v) for v in job_embedding) + "]"

    rows = await pool.fetch(
        """
        SELECT
            id,
            name,
            email,
            skills,
            experience_years,
            parsed_resume,
            (embedding <=> $1::vector) AS cosine_distance
        FROM candidates
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> $1::vector
        LIMIT $2
        """,
        embedding_literal,
        top_k,
    )
    results = [dict(r) for r in rows]
    logger.info(
        "vector_retriever.found top_k=%d found=%d",
        top_k,
        len(results),
    )
    return results


async def find_similar_jobs(
    pool: asyncpg.Pool,
    query_embedding: List[float],
    top_k: int = 10,
) -> List[Dict[str, Any]]:
    """
    Find jobs semantically similar to a query embedding.
    Useful for duplicate detection or job recommendation.
    """
    embedding_literal = "[" + ",".join(str(v) for v in query_embedding) + "]"

    rows = await pool.fetch(
        """
        SELECT
            id,
            title,
            description,
            parsed_requirements,
            (embedding <=> $1::vector) AS cosine_distance
        FROM jobs
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> $1::vector
        LIMIT $2
        """,
        embedding_literal,
        top_k,
    )
    return [dict(r) for r in rows]
