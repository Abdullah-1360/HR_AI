"""
app/ai/schemas/resume_schemas.py
Pydantic structured output schema for the Resume Parsing Agent.
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class Education(BaseModel):
    degree: str
    institution: str
    year: Optional[int] = None


class WorkExperience(BaseModel):
    company: str
    role: str
    duration: str
    highlights: List[str] = Field(default_factory=list)


class ParsedResume(BaseModel):
    """Structured representation of a candidate's resume."""

    name: str = Field(description="Full name of the candidate")
    email: Optional[str] = Field(default=None, description="Email address")
    phone: Optional[str] = Field(default=None, description="Phone number")
    location: Optional[str] = Field(default=None, description="City / region")
    linkedin: Optional[str] = Field(default=None, description="LinkedIn profile URL")
    github: Optional[str] = Field(default=None, description="GitHub profile URL")
    skills: List[str] = Field(
        description="All technical and domain skills mentioned in the resume"
    )
    experience_years: int = Field(
        default=0,
        description="Total years of professional experience (estimated)",
    )
    work_history: List[WorkExperience] = Field(
        default_factory=list,
        description="Chronological list of work experiences",
    )
    education: List[Education] = Field(
        default_factory=list,
        description="Education history",
    )
    projects: List[str] = Field(
        default_factory=list,
        description="Notable personal or open-source projects",
    )
    certifications: List[str] = Field(
        default_factory=list,
        description="Professional certifications or courses",
    )
    summary: Optional[str] = Field(
        default=None,
        description="One-paragraph professional summary generated from the resume",
    )
