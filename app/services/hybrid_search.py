"""
app/services/hybrid_search.py
Hybrid retrieval service combining dense vector search (pgvector),
sparse full-text search (tsvector / BM25), Reciprocal Rank Fusion (RRF),
and Cohere Re-ranking v3.
"""
import logging
import json
from typing import Any, Dict, List, Optional
import asyncpg

from app.core.config import get_settings

logger = logging.getLogger(__name__)


async def hybrid_search_candidates(
    pool: asyncpg.Pool,
    job_embedding: List[float],
    query_text: str,
    tenant_id: str = "default",
    top_k: int = 20,
    rrf_k: float = 60.0,
) -> List[Dict[str, Any]]:
    """
    Hybrid Search combining:
      1. Dense Vector Similarity (pgvector HNSW HNSW <=> cosine distance)
      2. Sparse Lexical Full-Text Search (PostgreSQL tsvector / ts_rank_cd)
      3. Reciprocal Rank Fusion (RRF) scoring algorithm
      4. Second-stage Cohere Rerank v3 re-scoring (if COHERE_API_KEY is configured)

    Args:
        pool: asyncpg connection pool.
        job_embedding: 1024-dim float list from embedding provider.
        query_text: Search keywords or job title/requirements text.
        tenant_id: Multi-tenant workspace identifier.
        top_k: Number of candidates to return.
        rrf_k: RRF smoothing constant (default: 60.0).

    Returns:
        List of candidate dicts sorted by hybrid rank score.
    """
    # Clean natural language prompt keywords for tsquery (e.g. "find a AI developer" -> "ai & developer")
    stop_words = {"find", "show", "me", "a", "an", "the", "for", "with", "search", "looking", "need", "get", "who", "have", "has", "can", "candidates"}
    words = [w.lower() for w in query_text.replace("'", "").replace('"', '').split() if w.lower() not in stop_words and len(w) > 1]
    tsquery_text = " & ".join(words) if words else query_text.lower()
    tsquery_or_text = " | ".join(words) if words else query_text.lower()



    embedding_literal = "[" + ",".join(str(v) for v in job_embedding) + "]"
    is_dummy_embedding = all(v == 0.0 for v in job_embedding)


    query = f"""
    WITH dense_search AS (
        SELECT id, ROW_NUMBER() OVER (ORDER BY embedding <=> $1::vector) AS dense_rank
        FROM candidates
        WHERE embedding IS NOT NULL 
          AND (tenant_id = $2 OR tenant_id = 'default' OR tenant_id = 'default_tenant' OR $2 = 'default')
          AND {"FALSE" if is_dummy_embedding else "TRUE"}
        ORDER BY embedding <=> $1::vector
        LIMIT 50
    ),
    sparse_search AS (
        SELECT id, ROW_NUMBER() OVER (ORDER BY ts_rank_cd(search_vector, to_tsquery('english', $3)) DESC) AS sparse_rank
        FROM candidates
        WHERE search_vector @@ to_tsquery('english', $3)
          AND (tenant_id = $2 OR tenant_id = 'default' OR tenant_id = 'default_tenant' OR $2 = 'default')
        ORDER BY ts_rank_cd(search_vector, to_tsquery('english', $3)) DESC
        LIMIT 50
    )
    SELECT
        c.id,
        c.name,
        c.email,
        c.skills,
        c.experience_years,
        c.parsed_resume,
        c.tenant_id,
        (COALESCE(1.0 / ($4 + d.dense_rank), 0.0) + COALESCE(2.0 / ($4 + s.sparse_rank), 0.0)) AS rrf_score
    FROM candidates c
    LEFT JOIN dense_search d ON c.id = d.id
    LEFT JOIN sparse_search s ON c.id = s.id
    WHERE (d.id IS NOT NULL OR s.id IS NOT NULL)
      AND (c.tenant_id = $2 OR c.tenant_id = 'default' OR c.tenant_id = 'default_tenant' OR $2 = 'default')
    ORDER BY rrf_score DESC
    LIMIT $5;
    """


    try:
        rows = await pool.fetch(
            query,
            embedding_literal,
            tenant_id,
            tsquery_text,
            rrf_k,
            top_k * 2,
        )
        if not rows:
            rows = await pool.fetch(
                query,
                embedding_literal,
                tenant_id,
                tsquery_or_text,
                rrf_k,
                top_k * 2,
            )
    except Exception:
        # Fallback to plainto_tsquery if custom tsquery parsing fails
        fallback_query = query.replace("to_tsquery('english', $3)", "plainto_tsquery('english', $3)")
        rows = await pool.fetch(
            fallback_query,
            embedding_literal,
            tenant_id,
            query_text,
            rrf_k,
            top_k * 2,
        )



    candidates = [dict(r) for r in rows]

    if not candidates:
        logger.warning("hybrid_search.no_results query='%s' tenant_id='%s'", query_text, tenant_id)
        return []

    # Second-stage Re-ranking using Cohere Rerank v3 if key available
    settings = get_settings()
    if settings.cohere_api_key:
        try:
            import cohere
            co = cohere.ClientV2(api_key=settings.cohere_api_key)

            docs = []
            for c in candidates:
                skills_str = ", ".join(c.get("skills") or [])
                pr = c.get("parsed_resume") or {}
                if isinstance(pr, str):
                    try:
                        pr = json.loads(pr)
                    except Exception:
                        pr = {}
                summary = pr.get("summary") or pr.get("experience") or ""
                docs.append(f"Name: {c.get('name', '')}. Skills: {skills_str}. Experience: {summary}")

            logger.info("hybrid_search.cohere_rerank_start docs_count=%d", len(docs))
            response = co.rerank(
                model="rerank-english-v3.0",
                query=query_text,
                documents=docs,
                top_n=top_k,
            )

            reranked_candidates = []
            for result in response.results:
                candidate = candidates[result.index]
                candidate["rerank_score"] = float(result.relevance_score)
                reranked_candidates.append(candidate)

            logger.info("hybrid_search.cohere_rerank_complete top_returned=%d", len(reranked_candidates))
            return reranked_candidates
        except Exception as exc:
            logger.warning("hybrid_search.cohere_rerank_failed fallback_to_rrf error=%s", exc)

    return candidates[:top_k]
