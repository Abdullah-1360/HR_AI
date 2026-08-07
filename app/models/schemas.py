"""
app/models/schemas.py
API-level Pydantic request / response schemas used by the FastAPI endpoints.
These are separate from the AI structured output schemas in app/ai/schemas/.
"""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Job Schemas ────────────────────────────────────────────────────────────────

class JobCreateRequest(BaseModel):
    title: str = Field(description="Job title (e.g. 'Senior Python AI Engineer')")
    raw_description: str = Field(
        description="Full job description text. The AI will extract structured requirements."
    )


class JobResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    parsed_requirements: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class JobListResponse(BaseModel):
    items: List[JobResponse]
    total: int


# ── Candidate Schemas ──────────────────────────────────────────────────────────

class CandidateResponse(BaseModel):
    id: uuid.UUID
    name: Optional[str] = None
    email: Optional[str] = None
    skills: Optional[List[str]] = None
    experience_years: Optional[int] = None
    resume_url: Optional[str] = None
    parsed_resume: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CandidateListResponse(BaseModel):
    items: List[CandidateResponse]
    total: int


# ── Match / Hiring Schemas ─────────────────────────────────────────────────────

class MatchRequest(BaseModel):
    job_id: uuid.UUID = Field(description="UUID of the job to match candidates against")
    top_k: int = Field(default=20, ge=1, le=100, description="Number of ANN candidates to evaluate")


class RankedCandidateResponse(BaseModel):
    candidate_id: uuid.UUID
    name: Optional[str] = None
    email: Optional[str] = None
    overall_score: int
    skill_match_score: int
    experience_score: int
    missing_skills: List[str]
    strengths: List[str]
    reasoning: str
    confidence: float


class MatchResponse(BaseModel):
    job_id: uuid.UUID
    total_evaluated: int
    ranked_candidates: List[RankedCandidateResponse]


class InterviewRequest(BaseModel):
    job_id: uuid.UUID
    candidate_id: uuid.UUID


class InterviewResponse(BaseModel):
    job_title: str
    candidate_name: Optional[str] = None
    technical_questions: List[Dict[str, Any]]
    behavioral_questions: List[Dict[str, Any]]
    scenario_questions: List[Dict[str, Any]]
    system_design_questions: List[Dict[str, Any]]
    evaluation_rubric: Dict[str, str]
    recommended_interview_duration_mins: int


class PipelineRequest(BaseModel):
    job_id: uuid.UUID
    top_k: int = Field(default=20, ge=1, le=100)


class PipelineResponse(BaseModel):
    job_id: uuid.UUID
    job_title: Optional[str] = None
    ranked_candidates: List[RankedCandidateResponse]
    interview_pack: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# ── Health ─────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str
    db: str
    storage: str
