"""
tests/unit/test_matching_agent.py
Unit tests for the Candidate Matching Agent and related schemas.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.ai.schemas.job_schemas import ParsedJob
from app.ai.schemas.resume_schemas import ParsedResume, WorkExperience
from app.ai.schemas.match_schemas import MatchResult, RankedCandidate


SAMPLE_JOB = ParsedJob(
    title="Senior Python AI Engineer",
    required_skills=["Python", "LangChain", "FastAPI"],
    preferred_skills=["pgvector", "AWS"],
    experience_years_min=5,
    seniority="senior",
    responsibilities=["Build AI pipelines", "Design REST APIs"],
)

SAMPLE_RESUME = ParsedResume(
    name="Alice Smith",
    email="alice@example.com",
    skills=["Python", "FastAPI", "PostgreSQL", "Django"],
    experience_years=6,
    work_history=[
        WorkExperience(
            company="TechCorp",
            role="Backend Engineer",
            duration="2018–2024",
            highlights=["Built REST APIs", "Deployed on AWS"],
        )
    ],
)


def test_match_result_schema():
    """MatchResult validates and enforces score bounds."""
    match = MatchResult(
        overall_score=82,
        skill_match_score=75,
        experience_score=90,
        education_score=70,
        missing_skills=["LangChain"],
        strengths=["Strong Python", "FastAPI experience"],
        potential_risks=[],
        reasoning="Strong Python and FastAPI background; lacks LLM framework experience.",
        confidence=0.85,
    )
    assert match.overall_score == 82
    assert 0 <= match.confidence <= 1.0
    assert "LangChain" in match.missing_skills
    print(f"  ✅ MatchResult schema: valid (score={match.overall_score}, confidence={match.confidence})")


def test_match_result_score_bounds():
    """MatchResult raises ValidationError for out-of-range scores."""
    from pydantic import ValidationError
    try:
        MatchResult(
            overall_score=150,  # invalid
            skill_match_score=50,
            experience_score=50,
            education_score=50,
            reasoning="test",
            confidence=0.5,
        )
        assert False, "Should have raised ValidationError"
    except ValidationError:
        print("  ✅ MatchResult: raises ValidationError for score > 100")


def test_ranked_candidate_schema():
    """RankedCandidate wraps MatchResult with candidate identity."""
    match = MatchResult(
        overall_score=75,
        skill_match_score=70,
        experience_score=80,
        education_score=65,
        reasoning="Good fit overall",
        confidence=0.78,
    )
    rc = RankedCandidate(
        candidate_id="abc-123",
        name="Bob Jones",
        email="bob@example.com",
        match=match,
    )
    assert rc.candidate_id == "abc-123"
    assert rc.match.overall_score == 75
    print(f"  ✅ RankedCandidate schema: valid (id={rc.candidate_id}, score={rc.match.overall_score})")


def test_format_work_history():
    """_format_work_history formats work history correctly."""
    from app.ai.agents.matching_agent import _format_work_history
    output = _format_work_history(SAMPLE_RESUME)
    assert "TechCorp" in output
    assert "Backend Engineer" in output
    print(f"  ✅ _format_work_history: output contains expected company/role")


def test_format_education_empty():
    """_format_education returns 'Not specified' when empty."""
    from app.ai.agents.matching_agent import _format_education
    resume = ParsedResume(name="Test", skills=[])
    output = _format_education(resume)
    assert output == "Not specified"
    print("  ✅ _format_education: returns 'Not specified' for empty education")


if __name__ == "__main__":
    print("\n── Matching Agent Unit Tests ─────────────────────────────────")
    test_match_result_schema()
    test_match_result_score_bounds()
    test_ranked_candidate_schema()
    test_format_work_history()
    test_format_education_empty()
    print("── All passed ───────────────────────────────────────────────\n")
