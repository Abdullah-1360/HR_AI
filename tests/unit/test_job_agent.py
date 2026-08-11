"""
tests/unit/test_job_agent.py
Unit tests for the Job Understanding Agent.
Uses mocked ChatRouter to avoid real LLM calls.
"""
import asyncio
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.ai.schemas.job_schemas import ParsedJob


SAMPLE_JD = """
We are hiring a Senior Python AI Engineer to join our ML Platform team.

Requirements:
- 5+ years of Python experience
- Experience with LangChain, LangGraph, or similar LLM frameworks
- Proficiency in FastAPI or Django
- PostgreSQL / pgvector experience preferred
- AWS or GCP cloud deployment experience

Responsibilities:
- Build and maintain AI agent pipelines
- Collaborate with data scientists on model integration
- Own backend API design

Salary: $130k–$160k | Location: Remote | Seniority: Senior
"""

MOCK_PARSED_JOB = ParsedJob(
    title="Senior Python AI Engineer",
    required_skills=["Python", "LangChain", "FastAPI", "PostgreSQL"],
    preferred_skills=["pgvector", "AWS", "GCP"],
    experience_years_min=5,
    seniority="senior",
    responsibilities=["Build AI agent pipelines", "Model integration", "API design"],
    salary_range="$130k–$160k",
    location="Remote",
)


def test_analyze_job_returns_parsed_job():
    """analyze_job returns a ParsedJob with expected fields (mocked LLM)."""
    from app.ai.agents.job_agent import analyze_job

    mock_chain = AsyncMock(return_value=MOCK_PARSED_JOB)

    with patch("app.ai.agents.job_agent.ChatRouter") as MockChatRouter:
        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = MagicMock()
        mock_llm.with_structured_output.return_value.__or__ = lambda self, other: mock_chain
        MockChatRouter.return_value = mock_llm

        # Directly call with mocked chain via patching the chain __or__
        # We patch at a higher level: the full chain invocation
        with patch("app.ai.agents.job_agent.JOB_ANALYSIS_PROMPT") as MockPrompt:
            MockPrompt.__or__ = MagicMock(return_value=MagicMock(ainvoke=AsyncMock(return_value=MOCK_PARSED_JOB)))
            result = asyncio.run(analyze_job(SAMPLE_JD, title="Senior Python AI Engineer"))

    assert isinstance(result, ParsedJob)
    print(f"  ✅ analyze_job returns ParsedJob: title={result.title!r}")


def test_parsed_job_schema_validation():
    """ParsedJob schema validates correctly with required fields."""
    job = ParsedJob(
        title="ML Engineer",
        required_skills=["Python", "PyTorch"],
        seniority="mid",
        responsibilities=["Train models"],
    )
    assert job.title == "ML Engineer"
    assert "Python" in job.required_skills
    assert job.experience_years_min == 0  # default
    assert job.preferred_skills == []      # default
    print("  ✅ ParsedJob schema: defaults and required fields correct")


def test_parsed_job_rejects_bad_data():
    """ParsedJob raises ValidationError when required fields are missing."""
    from pydantic import ValidationError
    try:
        ParsedJob()  # missing required fields
        assert False, "Should have raised ValidationError"
    except ValidationError:
        print("  ✅ ParsedJob schema: raises ValidationError on missing required fields")


if __name__ == "__main__":
    print("\n── Job Agent Unit Tests ──────────────────────────────────────")
    test_parsed_job_schema_validation()
    test_parsed_job_rejects_bad_data()
    test_analyze_job_returns_parsed_job()
    print("── All passed ───────────────────────────────────────────────\n")
