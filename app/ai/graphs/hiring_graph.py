"""
app/ai/graphs/hiring_graph.py
Hiring Platform LangGraph Supervisor.

Graph:
    START → job_analysis_node → candidate_retrieval_node → matching_node
          → interview_node → END

HiringState carries the full context for one hiring workflow run.
Each node delegates to the corresponding service/agent function.
The underlying ChatRouter transparently routes all LLM calls through
the model router graph (fallback, quota, health — all handled automatically).
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

import asyncpg
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict

from router.chat_model import ChatRouter
from app.ai.agents.job_agent import analyze_job
from app.ai.agents.interview_agent import generate_interview_pack
from app.ai.agents.matching_agent import rank_candidates
from app.ai.retrievers.vector_retriever import find_top_candidates
from app.ai.schemas.job_schemas import ParsedJob
from app.ai.schemas.match_schemas import RankedCandidate
from app.ai.schemas.interview_schemas import InterviewPack
from app.ai.schemas.resume_schemas import ParsedResume
from app.repositories.job_repository import get_job_by_id, get_job_embedding
from app.repositories.candidate_repository import get_candidates_by_ids
from app.repositories.match_repository import upsert_match

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════════════
# State
# ═════════════════════════════════════════════════════════════════════════════

class HiringState(TypedDict):
    # ── Inputs ────────────────────────────────────────────────────────────────
    job_id: str
    top_k: int                              # how many candidates to retrieve via ANN

    # ── Job analysis ──────────────────────────────────────────────────────────
    job_title: Optional[str]
    job_description: Optional[str]
    parsed_job: Optional[Dict[str, Any]]   # ParsedJob.model_dump()

    # ── Candidate retrieval ───────────────────────────────────────────────────
    retrieved_candidate_ids: List[str]

    # ── Matching ──────────────────────────────────────────────────────────────
    ranked_candidates: List[Dict[str, Any]]  # RankedCandidate.model_dump() list

    # ── Interview ─────────────────────────────────────────────────────────────
    # Generated for the top-ranked candidate only
    interview_pack: Optional[Dict[str, Any]]

    # ── Control ───────────────────────────────────────────────────────────────
    error: Optional[str]


# ═════════════════════════════════════════════════════════════════════════════
# Node helpers
# ═════════════════════════════════════════════════════════════════════════════

def _get_pool(config: RunnableConfig) -> asyncpg.Pool:
    pool = (config.get("configurable") or {}).get("pool")
    if not pool:
        raise RuntimeError("asyncpg pool must be passed via config['configurable']['pool']")
    return pool


def _get_llm(config: RunnableConfig) -> ChatRouter:
    llm = (config.get("configurable") or {}).get("llm")
    return llm or ChatRouter()


# ═════════════════════════════════════════════════════════════════════════════
# Nodes
# ═════════════════════════════════════════════════════════════════════════════

async def job_analysis_node(state: HiringState, config: RunnableConfig) -> HiringState:
    """Load job from DB and run the Job Understanding Agent."""
    pool = _get_pool(config)
    llm = _get_llm(config)

    try:
        job_row = await get_job_by_id(pool, state["job_id"])
        if not job_row:
            return {**state, "error": f"Job {state['job_id']} not found"}

        # If already parsed (job created via service), skip re-analysis
        parsed_requirements = job_row.get("parsed_requirements")
        if parsed_requirements:
            if isinstance(parsed_requirements, str):
                parsed_requirements = json.loads(parsed_requirements)
            return {
                **state,
                "job_title": job_row["title"],
                "job_description": job_row["description"],
                "parsed_job": parsed_requirements,
            }

        # Otherwise analyse the description
        parsed = await analyze_job(
            raw_description=job_row["description"],
            title=job_row["title"],
            llm=llm,
        )
        return {
            **state,
            "job_title": job_row["title"],
            "job_description": job_row["description"],
            "parsed_job": parsed.model_dump(),
        }
    except Exception as exc:
        logger.error("hiring_graph.job_analysis_node error: %s", exc)
        return {**state, "error": str(exc)}


async def candidate_retrieval_node(state: HiringState, config: RunnableConfig) -> HiringState:
    """Retrieve top-K candidate IDs via pgvector ANN search."""
    if state.get("error"):
        return state

    pool = _get_pool(config)
    try:
        job_embedding = await get_job_embedding(pool, state["job_id"])
        if not job_embedding:
            return {**state, "error": f"Job {state['job_id']} has no embedding"}

        ann_results = await find_top_candidates(pool, job_embedding, top_k=state.get("top_k", 20))
        candidate_ids = [str(r["id"]) for r in ann_results]

        logger.info("hiring_graph.retrieval found=%d", len(candidate_ids))
        return {**state, "retrieved_candidate_ids": candidate_ids}
    except Exception as exc:
        logger.error("hiring_graph.candidate_retrieval_node error: %s", exc)
        return {**state, "error": str(exc)}


async def matching_node(state: HiringState, config: RunnableConfig) -> HiringState:
    """Score and rank retrieved candidates using the Matching Agent."""
    if state.get("error"):
        return state

    pool = _get_pool(config)
    llm = _get_llm(config)

    try:
        candidate_rows = await get_candidates_by_ids(pool, state["retrieved_candidate_ids"])
        parsed_job = ParsedJob(**state["parsed_job"])

        pairs: List[tuple[str, ParsedResume]] = []
        for row in candidate_rows:
            pr_data = row["parsed_resume"]
            if isinstance(pr_data, str):
                pr_data = json.loads(pr_data)
            pairs.append((str(row["id"]), ParsedResume(**pr_data)))

        ranked: List[RankedCandidate] = await rank_candidates(parsed_job, pairs, llm=llm)

        # Persist scores
        await asyncio.gather(*[
            upsert_match(
                pool,
                job_id=state["job_id"],
                candidate_id=rc.candidate_id,
                match_score=rc.match.overall_score,
                evaluation_report=rc.match.model_dump(),
            )
            for rc in ranked
        ])

        logger.info("hiring_graph.matching ranked=%d", len(ranked))
        return {**state, "ranked_candidates": [rc.model_dump() for rc in ranked]}
    except Exception as exc:
        logger.error("hiring_graph.matching_node error: %s", exc)
        return {**state, "error": str(exc)}


async def interview_node(state: HiringState, config: RunnableConfig) -> HiringState:
    """Generate an interview pack for the top-ranked candidate."""
    if state.get("error") or not state.get("ranked_candidates"):
        return state

    llm = _get_llm(config)

    try:
        top = state["ranked_candidates"][0]
        parsed_job = ParsedJob(**state["parsed_job"])

        # Reconstruct ParsedResume from the ranked candidate's match data
        # (full parsed_resume is not stored in state — rebuild from name/email only for prompt)
        from app.ai.schemas.match_schemas import MatchResult, RankedCandidate as RC
        rc = RC(**top)
        candidate_stub = ParsedResume(
            name=rc.name or "Candidate",
            email=rc.email,
            skills=[],
            experience_years=0,
        )
        match_result = rc.match

        pack: InterviewPack = await generate_interview_pack(
            job=parsed_job,
            candidate=candidate_stub,
            match_result=match_result,
            llm=llm,
        )
        logger.info("hiring_graph.interview_pack generated for candidate=%s", rc.candidate_id)
        return {**state, "interview_pack": pack.model_dump()}
    except Exception as exc:
        logger.error("hiring_graph.interview_node error: %s", exc)
        # Non-fatal — pipeline result still valid without interview pack
        return {**state, "interview_pack": None}


# ═════════════════════════════════════════════════════════════════════════════
# Edge logic
# ═════════════════════════════════════════════════════════════════════════════

def after_job_analysis(state: HiringState) -> str:
    return "fail_node" if state.get("error") else "candidate_retrieval_node"


def after_retrieval(state: HiringState) -> str:
    if state.get("error"):
        return "fail_node"
    if not state.get("retrieved_candidate_ids"):
        return "end_node"   # no candidates in DB yet
    return "matching_node"


def after_matching(state: HiringState) -> str:
    if state.get("error"):
        return "fail_node"
    if not state.get("ranked_candidates"):
        return "end_node"
    return "interview_node"


async def fail_node(state: HiringState) -> HiringState:
    logger.error("hiring_graph.FAILED error=%s", state.get("error"))
    return state


async def end_node(state: HiringState) -> HiringState:
    logger.info("hiring_graph.DONE ranked=%d", len(state.get("ranked_candidates") or []))
    return state


# ═════════════════════════════════════════════════════════════════════════════
# Graph assembly
# ═════════════════════════════════════════════════════════════════════════════

def build_hiring_graph():
    """Compile the hiring supervisor LangGraph."""
    workflow = StateGraph(HiringState)

    workflow.add_node("job_analysis_node",          job_analysis_node)
    workflow.add_node("candidate_retrieval_node",   candidate_retrieval_node)
    workflow.add_node("matching_node",              matching_node)
    workflow.add_node("interview_node",             interview_node)
    workflow.add_node("fail_node",                  fail_node)
    workflow.add_node("end_node",                   end_node)

    workflow.add_edge(START, "job_analysis_node")
    workflow.add_conditional_edges("job_analysis_node", after_job_analysis, {
        "candidate_retrieval_node": "candidate_retrieval_node",
        "fail_node": "fail_node",
    })
    workflow.add_conditional_edges("candidate_retrieval_node", after_retrieval, {
        "matching_node": "matching_node",
        "end_node": "end_node",
        "fail_node": "fail_node",
    })
    workflow.add_conditional_edges("matching_node", after_matching, {
        "interview_node": "interview_node",
        "end_node": "end_node",
        "fail_node": "fail_node",
    })
    workflow.add_edge("interview_node", "end_node")
    workflow.add_edge("end_node", END)
    workflow.add_edge("fail_node", END)

    return workflow.compile()


# ═════════════════════════════════════════════════════════════════════════════
# Public helper
# ═════════════════════════════════════════════════════════════════════════════

async def run_hiring_pipeline(
    pool: asyncpg.Pool,
    job_id: str,
    top_k: int = 20,
    llm: Optional[ChatRouter] = None,
) -> Dict[str, Any]:
    """
    Run the full hiring pipeline for a given job_id.
    Returns the final HiringState dict.
    """
    graph = build_hiring_graph()

    initial_state: HiringState = {
        "job_id": job_id,
        "top_k": top_k,
        "job_title": None,
        "job_description": None,
        "parsed_job": None,
        "retrieved_candidate_ids": [],
        "ranked_candidates": [],
        "interview_pack": None,
        "error": None,
    }

    result = await graph.ainvoke(
        initial_state,
        config={"configurable": {"pool": pool, "llm": llm or ChatRouter()}},
    )
    return result
