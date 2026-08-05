"""
app/ai/agents/copilot_agent.py
Recruiter Copilot Agent — Conversational RAG assistant for talent acquisition.
Answers recruiter queries, analyzes candidate pools, compares candidates,
and suggests hiring strategies using multi-provider LLM routing.
"""
import logging
import json
from typing import Any, Dict, List, Optional
import asyncpg

from router.chat_model import ChatRouter
from app.utils.embedder import embed_document
from app.services.hybrid_search import hybrid_search_candidates

logger = logging.getLogger(__name__)

COPILOT_SYSTEM_PROMPT = """You are the Recruiter AI Copilot, an expert AI assistant for Talent Acquisition and Recruitment.
Analyze the candidate profiles provided in the context and answer the recruiter's prompt concisely, professionally, and accurately.

Key Responsibilities:
1. Recommend top candidates based on technical skills, years of experience, and relevant roles.
2. Highlight key strengths, skill gaps, or potential trade-offs.
3. Provide actionable hiring advice or interview questions if requested.

CONTEXT (RETRIEVED CANDIDATE PROFILES):
{context}

RECRUITER QUERY:
{query}
"""


async def run_copilot_chat(
    pool: asyncpg.Pool,
    query: str,
    tenant_id: str = "default",
    job_id: Optional[str] = None,
    llm: Optional[ChatRouter] = None,
) -> Dict[str, Any]:
    """
    Run conversational Copilot query with RAG candidate context.

    Args:
        pool: asyncpg database pool.
        query: Natural language query from recruiter.
        tenant_id: Tenant workspace ID.
        job_id: Optional job context ID.
        llm: ChatRouter instance.

    Returns:
        Dict with keys: answer, retrieved_candidates, total_context_candidates.
    """
    logger.info("copilot_agent.chat query=%r tenant_id=%s", query, tenant_id)

    # Step 1: Embed recruiter query
    try:
        query_embedding = await embed_document(query)
    except Exception as exc:
        logger.warning("copilot_agent.embed_failed fallback_to_empty error=%s", exc)
        query_embedding = [0.0] * 1024

    # Step 2: Hybrid Search retrieval for relevant candidate context
    retrieved = await hybrid_search_candidates(
        pool,
        job_embedding=query_embedding,
        query_text=query,
        tenant_id=tenant_id,
        top_k=10,
    )

    # Format context for RAG prompt
    context_blocks = []
    for c in retrieved:
        skills = ", ".join(c.get("skills") or [])
        exp = c.get("experience_years", 0)
        pr = c.get("parsed_resume") or {}
        if isinstance(pr, str):
            try:
                pr = json.loads(pr)
            except Exception:
                pr = {}
        summary = pr.get("summary") or "N/A"
        block = f"- Candidate ID: {c.get('id')}\n  Name: {c.get('name', 'Unnamed')}\n  Experience: {exp} years\n  Skills: {skills}\n  Summary: {summary}"
        context_blocks.append(block)

    context_str = "\n\n".join(context_blocks) if context_blocks else "No matching candidate profiles found in the workspace database."

    # Step 3: LLM generation
    if llm is None:
        llm = ChatRouter(
            default_required_tags=["tools"],
            default_estimated_tokens=1500,
        )

    formatted_prompt = COPILOT_SYSTEM_PROMPT.format(
        context=context_str,
        query=query,
    )

    try:
        response = await llm.ainvoke(formatted_prompt)
        answer = response.content if hasattr(response, "content") else str(response)
    except Exception as exc:
        logger.error("copilot_agent.llm_failed error=%s", exc)
        answer = f"I retrieved {len(retrieved)} relevant candidate profiles, but encountered an LLM provider error when generating the full analysis. Retrieved candidates: " + ", ".join(c.get("name", "Unnamed") for c in retrieved)

    return {
        "answer": answer,
        "retrieved_candidates": [
            {
                "id": str(c["id"]),
                "name": c.get("name"),
                "skills": c.get("skills"),
                "experience_years": c.get("experience_years"),
            }
            for c in retrieved
        ],
        "total_context_candidates": len(retrieved),
    }
