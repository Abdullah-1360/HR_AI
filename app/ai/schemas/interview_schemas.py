"""
app/ai/schemas/interview_schemas.py
Pydantic structured output schemas for the Interview Generation Agent.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class InterviewQuestion(BaseModel):
    question: str
    category: str = Field(
        description="technical | behavioral | scenario | system_design | coding"
    )
    difficulty: str = Field(description="easy | medium | hard")
    what_good_looks_like: str = Field(
        description="Description of what an ideal answer includes"
    )
    follow_ups: List[str] = Field(
        default_factory=list,
        description="Suggested follow-up probing questions",
    )


class InterviewPack(BaseModel):
    """Full interview kit generated for a (job, candidate) pair."""

    job_title: str
    candidate_name: Optional[str] = None
    technical_questions: List[InterviewQuestion] = Field(
        default_factory=list,
        description="Technical depth questions specific to the role",
    )
    behavioral_questions: List[InterviewQuestion] = Field(
        default_factory=list,
        description="STAR-format behavioral / soft-skills questions",
    )
    scenario_questions: List[InterviewQuestion] = Field(
        default_factory=list,
        description="Situational / case-study questions",
    )
    system_design_questions: List[InterviewQuestion] = Field(
        default_factory=list,
        description="Architecture or system design open-ended questions (senior roles)",
    )
    evaluation_rubric: Dict[str, str] = Field(
        default_factory=dict,
        description="category → what constitutes a hire/no-hire answer",
    )
    recommended_interview_duration_mins: int = Field(
        default=60,
        description="Suggested total interview duration in minutes",
    )

    @field_validator("evaluation_rubric", mode="before")
    @classmethod
    def coerce_rubric(cls, v: Any) -> Any:
        if isinstance(v, dict):
            coerced = {}
            for key, val in v.items():
                if isinstance(val, dict):
                    # Format nested dictionary to string (e.g. "- Novice: ... \n- Expert: ...")
                    coerced[key] = "\n".join(f"- {sub_key.title()}: {sub_val}" for sub_key, sub_val in val.items())
                else:
                    coerced[key] = str(val)
            return coerced
        return v

