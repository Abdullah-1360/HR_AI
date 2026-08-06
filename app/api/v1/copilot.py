"""
app/api/v1/copilot.py
REST API endpoints for the Recruiter AI Copilot.
"""
import logging
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

from app.deps import PoolDep, LLMDep, TenantDep
from app.ai.agents.copilot_agent import run_copilot_chat

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/copilot", tags=["Recruiter Copilot"])


class CopilotChatRequest(BaseModel):
    query: str = Field(..., min_length=2, description="Natural language question or command")
    job_id: Optional[str] = Field(default=None, description="Optional target job ID context")


class CandidateSummary(BaseModel):
    id: str
    name: Optional[str] = None
    skills: Optional[List[str]] = None
    experience_years: Optional[int] = None


class CopilotChatResponse(BaseModel):
    answer: str
    retrieved_candidates: List[CandidateSummary]
    total_context_candidates: int


@router.post(
    "/chat",
    response_model=CopilotChatResponse,
    summary="Ask the Recruiter AI Copilot a question",
)
async def copilot_chat_endpoint(
    request: CopilotChatRequest,
    pool: PoolDep,
    llm: LLMDep,
    tenant_id: TenantDep,
) -> CopilotChatResponse:
    """
    Ask Recruiter AI Copilot a question using conversational RAG.
    Queries the workspace candidate pool and job descriptions to provide
    context-aware talent recommendations, candidate comparisons, and skill gap analyses.
    """
    try:
        result = await run_copilot_chat(
            pool=pool,
            query=request.query,
            tenant_id=tenant_id,
            job_id=request.job_id,
            llm=llm,
        )
        return CopilotChatResponse(**result)
    except Exception as exc:
        logger.error("copilot_chat_endpoint error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
