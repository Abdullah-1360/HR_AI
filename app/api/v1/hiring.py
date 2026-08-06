"""
app/api/v1/hiring.py
REST endpoints for the AI hiring workflow:
  - POST /match         → ANN retrieval + LLM scoring
  - POST /interview     → Interview pack generation
  - POST /pipeline      → Full LangGraph hiring supervisor run
  - GET  /matches/{job_id} → Retrieve persisted ranked matches
"""
import logging
from typing import List, Optional


from fastapi import APIRouter, HTTPException, Query

from app.deps import PoolDep, LLMDep
from app.models.schemas import (
    MatchRequest,
    MatchResponse,
    RankedCandidateResponse,
    InterviewRequest,
    InterviewResponse,
    PipelineRequest,
    PipelineResponse,
)
from app.services.hiring_service import (
    match_candidates_for_job,
    create_interview_pack,
    get_ranked_matches,
)
from app.ai.graphs.hiring_graph import run_hiring_pipeline

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/hiring", tags=["Hiring"])


@router.post("/match", response_model=MatchResponse, summary="Match and rank candidates for a job")
async def match_candidates_endpoint(
    body: MatchRequest,
    pool: PoolDep,
    llm: LLMDep,
) -> MatchResponse:
    """
    Run the full candidate matching pipeline:
    1. Fetch job embedding from the DB
    2. ANN vector search → top-K candidates by semantic similarity
    3. LLM scores each candidate on skills, experience, and fit
    4. Persists scores to `candidate_matches`
    5. Returns ranked list

    This may take 10–60 seconds depending on the number of candidates and LLM latency.
    """
    try:
        ranked = await match_candidates_for_job(
            pool,
            job_id=str(body.job_id),
            top_k=body.top_k,
            llm=llm,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error("POST /hiring/match error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    ranked_response: List[RankedCandidateResponse] = [
        RankedCandidateResponse(
            candidate_id=rc.candidate_id,
            name=rc.name,
            email=rc.email,
            overall_score=rc.match.overall_score,
            skill_match_score=rc.match.skill_match_score,
            experience_score=rc.match.experience_score,
            missing_skills=rc.match.missing_skills,
            strengths=rc.match.strengths,
            reasoning=rc.match.reasoning,
            confidence=rc.match.confidence,
        )
        for rc in ranked
    ]

    return MatchResponse(
        job_id=body.job_id,
        total_evaluated=len(ranked_response),
        ranked_candidates=ranked_response,
    )


@router.get("/matches/{job_id}", response_model=MatchResponse, summary="Get persisted match results")
async def get_matches_endpoint(
    job_id: str,
    pool: PoolDep,
    limit: int = Query(default=50, ge=1, le=200),
) -> MatchResponse:
    """Return previously computed and persisted match results for a job."""
    rows = await get_ranked_matches(pool, job_id, limit=limit)
    ranked_response = [
        RankedCandidateResponse(
            candidate_id=r["candidate_id"],
            name=r.get("name"),
            email=r.get("email"),
            overall_score=r["match_score"],
            skill_match_score=r.get("evaluation_report", {}).get("skill_match_score", 0),
            experience_score=r.get("evaluation_report", {}).get("experience_score", 0),
            missing_skills=r.get("evaluation_report", {}).get("missing_skills", []),
            strengths=r.get("evaluation_report", {}).get("strengths", []),
            reasoning=r.get("evaluation_report", {}).get("reasoning", ""),
            confidence=r.get("evaluation_report", {}).get("confidence", 0.0),
        )
        for r in rows
    ]
    import uuid as _uuid
    return MatchResponse(
        job_id=_uuid.UUID(job_id),
        total_evaluated=len(ranked_response),
        ranked_candidates=ranked_response,
    )


@router.post("/interview", response_model=InterviewResponse, summary="Generate interview pack")
async def generate_interview_endpoint(
    body: InterviewRequest,
    pool: PoolDep,
    llm: LLMDep,
) -> InterviewResponse:
    """
    Generate a comprehensive interview pack for a (job, candidate) pair.
    Includes technical, behavioral, scenario, and system design questions
    with evaluation rubrics and follow-up probes.
    """
    try:
        pack = await create_interview_pack(
            pool,
            job_id=str(body.job_id),
            candidate_id=str(body.candidate_id),
            llm=llm,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error("POST /hiring/interview error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    return InterviewResponse(
        job_title=pack.job_title,
        candidate_name=pack.candidate_name,
        technical_questions=[q.model_dump() for q in pack.technical_questions],
        behavioral_questions=[q.model_dump() for q in pack.behavioral_questions],
        scenario_questions=[q.model_dump() for q in pack.scenario_questions],
        system_design_questions=[q.model_dump() for q in pack.system_design_questions],
        evaluation_rubric=pack.evaluation_rubric,
        recommended_interview_duration_mins=pack.recommended_interview_duration_mins,
    )


@router.post("/pipeline", response_model=PipelineResponse, summary="Run full hiring pipeline")
async def run_pipeline_endpoint(
    body: PipelineRequest,
    pool: PoolDep,
    llm: LLMDep,
) -> PipelineResponse:
    """
    Execute the full LangGraph hiring supervisor pipeline for a job:
    job_analysis → candidate_retrieval → matching → interview_generation

    Returns the complete hiring result in one call.
    This is the recommended endpoint for automated workflows.
    """
    try:
        state = await run_hiring_pipeline(
            pool=pool,
            job_id=str(body.job_id),
            top_k=body.top_k,
            llm=llm,
        )
    except Exception as exc:
        logger.error("POST /hiring/pipeline error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    if state.get("error"):
        raise HTTPException(status_code=422, detail=state["error"])

    ranked_response = []
    for rc_data in state.get("ranked_candidates") or []:
        match_data = rc_data.get("match", {})
        ranked_response.append(RankedCandidateResponse(
            candidate_id=rc_data["candidate_id"],
            name=rc_data.get("name"),
            email=rc_data.get("email"),
            overall_score=match_data.get("overall_score", 0),
            skill_match_score=match_data.get("skill_match_score", 0),
            experience_score=match_data.get("experience_score", 0),
            missing_skills=match_data.get("missing_skills", []),
            strengths=match_data.get("strengths", []),
            reasoning=match_data.get("reasoning", ""),
            confidence=match_data.get("confidence", 0.0),
        ))

    return PipelineResponse(
        job_id=body.job_id,
        job_title=state.get("job_title"),
        ranked_candidates=ranked_response,
        interview_pack=state.get("interview_pack"),
        error=state.get("error"),
    )


from pydantic import BaseModel, Field

class RecruiterApprovalRequest(BaseModel):
    thread_id: str = Field(..., description="LangGraph execution thread ID")
    approved: bool = Field(..., description="True to approve top candidate and generate interview pack, False to reject")
    notes: Optional[str] = Field(default=None, description="Optional recruiter review notes")


@router.post("/approve", summary="Human-in-the-Loop recruiter approval for candidate shortlist")
async def approve_candidate_shortlist_endpoint(
    body: RecruiterApprovalRequest,
    pool: PoolDep,
):
    """
    Recruiter approval endpoint to resume an interrupted HITL LangGraph execution thread.
    If approved=True, graph resumes and generates the final interview pack.
    """
    try:
        from app.ai.workflows.hiring_graph import build_hiring_graph
        app = build_hiring_graph()
        config = {"configurable": {"thread_id": body.thread_id}}

        new_status = "APPROVED" if body.approved else "REJECTED"
        app.update_state(config, {"approval_status": new_status, "recruiter_notes": body.notes})

        # Resume graph execution
        final_state = await app.ainvoke(None, config)
        return {
            "thread_id": body.thread_id,
            "status": final_state.get("approval_status"),
            "selected_candidate_id": final_state.get("selected_candidate_id"),
            "interview_pack": final_state.get("interview_pack"),
            "error": final_state.get("error"),
        }
    except Exception as exc:
        logger.error("POST /hiring/approve error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

