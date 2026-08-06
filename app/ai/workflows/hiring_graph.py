"""
app/ai/workflows/hiring_graph.py
LangGraph Orchestrator for the AI Recruitment Operating System.
Features:
  - Multi-agent orchestration (Job Agent → Hybrid Retrieval → DEI Anonymizer → Matching Agent → Interview Agent)
  - Human-in-the-Loop (HITL) recruiter approval checkpoints using LangGraph MemorySaver
  - Configurable DEI Blind Resume Screening mode
"""
import logging
from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.ai.schemas.job_schemas import ParsedJob
from app.ai.schemas.resume_schemas import ParsedResume
from app.ai.schemas.match_schemas import MatchResult, RankedCandidate
from app.ai.agents.anonymizer_agent import anonymize_parsed_resume
from app.ai.agents.matching_agent import rank_candidates
from app.ai.agents.interview_agent import generate_interview_pack

logger = logging.getLogger(__name__)


# ── State Definition ──────────────────────────────────────────────────────────
class HiringWorkflowState(TypedDict):
    # Inputs
    job_id: str
    parsed_job: Optional[Dict[str, Any]]
    candidate_rows: List[Dict[str, Any]]
    dei_blind_mode: bool
    tenant_id: str

    # Intermediate agent outputs
    processed_candidates: List[Dict[str, Any]]
    ranked_candidates: List[Dict[str, Any]]

    # Human-in-the-Loop (HITL) approval state
    approval_status: str  # "PENDING_APPROVAL" | "APPROVED" | "REJECTED"
    recruiter_notes: Optional[str]

    # Final output
    selected_candidate_id: Optional[str]
    interview_pack: Optional[Dict[str, Any]]
    error: Optional[str]


# ── Node Definitions ──────────────────────────────────────────────────────────
async def dei_anonymizer_node(state: HiringWorkflowState) -> Dict[str, Any]:
    """Node: Applies DEI Blind Resume Screening if enabled."""
    candidates = state.get("candidate_rows", [])
    dei_enabled = state.get("dei_blind_mode", False)

    processed = []
    for c in candidates:
        pr_raw = c.get("parsed_resume") or {}
        try:
            parsed_resume = ParsedResume(**pr_raw) if isinstance(pr_raw, dict) else ParsedResume.model_validate_json(pr_raw)
            if dei_enabled:
                parsed_resume = anonymize_parsed_resume(parsed_resume, candidate_index_id=str(c.get("id")))
            processed.append({"id": str(c["id"]), "parsed_resume": parsed_resume.model_dump()})
        except Exception as exc:
            logger.warning("hiring_graph.anonymizer_skip candidate_id=%s reason=%s", c.get("id"), exc)

    logger.info("hiring_graph.dei_anonymizer_node count=%d dei_enabled=%s", len(processed), dei_enabled)
    return {"processed_candidates": processed}


async def candidate_matching_node(state: HiringWorkflowState) -> Dict[str, Any]:
    """Node: Scores and ranks candidates using Candidate Matching Agent."""
    job_data = state.get("parsed_job")
    if not job_data:
        return {"error": "Missing parsed_job requirement"}

    parsed_job = ParsedJob(**job_data)
    processed = state.get("processed_candidates", [])

    pairs = []
    for p in processed:
        try:
            pairs.append((p["id"], ParsedResume(**p["parsed_resume"])))
        except Exception as exc:
            logger.warning("hiring_graph.matching_skip id=%s reason=%s", p.get("id"), exc)

    ranked: List[RankedCandidate] = await rank_candidates(parsed_job, pairs)
    ranked_dicts = [rc.model_dump() for rc in ranked]

    top_candidate_id = ranked_dicts[0]["candidate_id"] if ranked_dicts else None

    logger.info("hiring_graph.matching_node ranked_count=%d top_id=%s", len(ranked_dicts), top_candidate_id)
    return {
        "ranked_candidates": ranked_dicts,
        "selected_candidate_id": top_candidate_id,
        "approval_status": "PENDING_APPROVAL",  # Triggers HITL interrupt state
    }


async def recruiter_approval_node(state: HiringWorkflowState) -> Dict[str, Any]:
    """Node: Human-in-the-Loop approval checkpoint."""
    status = state.get("approval_status", "PENDING_APPROVAL")
    logger.info("hiring_graph.recruiter_approval_node status=%s", status)
    return {"approval_status": status}


async def interview_pack_node(state: HiringWorkflowState) -> Dict[str, Any]:
    """Node: Generates tailored interview pack for approved top candidate."""
    if state.get("approval_status") != "APPROVED":
        return {"error": "Workflow ended: Recruiter did not approve candidate shortlist."}

    job_data = state.get("parsed_job")
    top_candidate_id = state.get("selected_candidate_id")

    if not job_data or not top_candidate_id:
        return {"error": "Missing job data or selected candidate"}

    parsed_job = ParsedJob(**job_data)

    # Find top candidate resume
    top_parsed_resume = None
    for p in state.get("processed_candidates", []):
        if p["id"] == top_candidate_id:
            top_parsed_resume = ParsedResume(**p["parsed_resume"])
            break

    if not top_parsed_resume:
        return {"error": "Top candidate parsed resume not found"}

    interview_pack = await generate_interview_pack(parsed_job, top_parsed_resume)
    logger.info("hiring_graph.interview_pack_node generated_for candidate_id=%s", top_candidate_id)

    return {"interview_pack": interview_pack.model_dump()}


def route_after_approval(state: HiringWorkflowState) -> str:
    """Conditional edge router checking recruiter approval decision."""
    status = state.get("approval_status", "PENDING_APPROVAL")
    if status == "APPROVED":
        return "interview_pack_node"
    return END


# ── Graph Compilation ─────────────────────────────────────────────────────────
def build_hiring_graph():
    """Build and compile the hiring graph with MemorySaver checkpointer."""
    workflow = StateGraph(HiringWorkflowState)

    workflow.add_node("dei_anonymizer_node", dei_anonymizer_node)
    workflow.add_node("candidate_matching_node", candidate_matching_node)
    workflow.add_node("recruiter_approval_node", recruiter_approval_node)
    workflow.add_node("interview_pack_node", interview_pack_node)

    workflow.add_edge(START, "dei_anonymizer_node")
    workflow.add_edge("dei_anonymizer_node", "candidate_matching_node")
    workflow.add_edge("candidate_matching_node", "recruiter_approval_node")

    workflow.add_conditional_edges(
        "recruiter_approval_node",
        route_after_approval,
        {
            "interview_pack_node": "interview_pack_node",
            END: END,
        },
    )

    workflow.add_edge("interview_pack_node", END)

    checkpointer = MemorySaver()
    app = workflow.compile(checkpointer=checkpointer)
    return app
