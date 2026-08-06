"""
app/ai/schemas/match_schemas.py
Pydantic structured output schemas for the Candidate Matching Agent.
"""
from typing import Any, List, Optional
from pydantic import BaseModel, Field, field_validator


class MatchResult(BaseModel):
    """LLM-generated evaluation of how well a candidate fits a job."""

    overall_score: int = Field(
        ge=0, le=100,
        description="Composite match score from 0 (no fit) to 100 (perfect fit)",
    )
    skill_match_score: int = Field(
        ge=0, le=100,
        description="Score based on technical skill overlap",
    )
    experience_score: int = Field(
        ge=0, le=100,
        description="Score based on years and relevance of experience",
    )
    education_score: int = Field(
        ge=0, le=100,
        description="Score based on educational background",
    )
    missing_skills: List[str] = Field(
        default_factory=list,
        description="Required skills the candidate does not appear to have",
    )
    strengths: List[str] = Field(
        default_factory=list,
        description="Key strengths that make the candidate a good fit",
    )
    potential_risks: List[str] = Field(
        default_factory=list,
        description="Risks or concerns about hiring this candidate",
    )
    reasoning: str = Field(
        description="Paragraph explaining the evaluation rationale"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Model's confidence in this evaluation (0.0–1.0)",
    )
    recommended_interview_focus: Optional[str] = Field(
        default=None,
        description="Areas to probe during the interview",
    )

    @field_validator("recommended_interview_focus", mode="before")
    @classmethod
    def coerce_interview_focus(cls, v: Any) -> Any:
        if isinstance(v, list):
            return "; ".join(str(item) for item in v)
        return v


class RankedCandidate(BaseModel):
    """A candidate with their match result, used in ranking output."""

    candidate_id: str
    name: Optional[str] = None
    email: Optional[str] = None
    match: MatchResult
