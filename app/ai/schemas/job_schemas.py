"""
app/ai/schemas/job_schemas.py
Pydantic structured output schema for the Job Understanding Agent.
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class ParsedJob(BaseModel):
    """Structured representation of a job posting, extracted by the Job Understanding Agent."""

    title: str = Field(description="Canonical job title")
    required_skills: List[str] = Field(
        description="Hard-required technical and domain skills"
    )
    preferred_skills: List[str] = Field(
        default_factory=list,
        description="Nice-to-have skills or bonuses",
    )
    experience_years_min: int = Field(
        default=0,
        description="Minimum years of relevant experience required",
    )
    seniority: str = Field(
        description="Seniority level: junior | mid | senior | lead | principal"
    )
    responsibilities: List[str] = Field(
        description="Key day-to-day responsibilities of the role"
    )
    salary_range: Optional[str] = Field(
        default=None,
        description="Salary range string if mentioned (e.g. '$120k–$150k')",
    )
    location: Optional[str] = Field(
        default=None,
        description="Job location or 'Remote' / 'Hybrid'",
    )
    work_authorization: Optional[str] = Field(
        default=None,
        description="Work authorization requirement if stated",
    )
