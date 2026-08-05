"""
app/ai/agents/matching_agent.py
Candidate Matching Agent — scores candidate-to-job fit using LLM reasoning.
Uses ChatRouter with required_tags=['reasoning'] for deep multi-criteria evaluation.
"""
import logging
from typing import List, Optional

from router.chat_model import ChatRouter
from app.ai.prompts.matching_prompts import CANDIDATE_MATCH_PROMPT
from app.ai.schemas.job_schemas import ParsedJob
from app.ai.schemas.resume_schemas import ParsedResume
from app.ai.schemas.match_schemas import MatchResult, RankedCandidate

logger = logging.getLogger(__name__)


def _format_work_history(parsed_resume: ParsedResume) -> str:
    if not parsed_resume.work_history:
        return "Not specified"
    parts = []
    for w in parsed_resume.work_history:
        highlights = "; ".join(w.highlights[:3]) if w.highlights else "—"
        parts.append(f"  • {w.role} @ {w.company} ({w.duration}): {highlights}")
    return "\n".join(parts)


def _format_education(parsed_resume: ParsedResume) -> str:
    if not parsed_resume.education:
        return "Not specified"
    return "; ".join(
        f"{e.degree} from {e.institution}" + (f" ({e.year})" if e.year else "")
        for e in parsed_resume.education
    )


async def score_candidate(
    job: ParsedJob,
    candidate: ParsedResume,
    llm: Optional[ChatRouter] = None,
) -> MatchResult:
    """
    Score a single candidate against a job using LLM structured evaluation.

    Args:
        job: Structured job requirements.
        candidate: Structured candidate profile.
        llm: ChatRouter instance. Creates one if not provided.

    Returns:
        MatchResult with numeric scores and reasoning.
    """
    if llm is None:
        llm = ChatRouter(
            default_required_tags=["reasoning"],
            default_estimated_tokens=2500,
        )

    structured_llm = llm.with_structured_output(MatchResult)
    chain = CANDIDATE_MATCH_PROMPT | structured_llm

    logger.info(
        "matching_agent.score candidate=%r job=%r",
        candidate.name,
        job.title,
    )

    result: MatchResult = await chain.ainvoke({
        "job_title": job.title,
        "required_skills": ", ".join(job.required_skills),
        "preferred_skills": ", ".join(job.preferred_skills),
        "experience_years_min": job.experience_years_min,
        "seniority": job.seniority,
        "responsibilities": "\n".join(f"  • {r}" for r in job.responsibilities),
        "candidate_name": candidate.name or "Unknown",
        "experience_years": candidate.experience_years,
        "candidate_skills": ", ".join(candidate.skills),
        "work_history": _format_work_history(candidate),
        "education": _format_education(candidate),
        "projects": ", ".join(candidate.projects) or "None listed",
    })

    logger.info(
        "matching_agent.scored candidate=%r overall=%d confidence=%.2f",
        candidate.name,
        result.overall_score,
        result.confidence,
    )
    return result


async def rank_candidates(
    job: ParsedJob,
    candidates: List[tuple[str, ParsedResume]],  # (candidate_id, parsed_resume)
    llm: Optional[ChatRouter] = None,
) -> List[RankedCandidate]:
    """
    Score and rank multiple candidates concurrently.

    Args:
        job: Structured job requirements.
        candidates: List of (candidate_id, ParsedResume) tuples.
        llm: Shared ChatRouter instance.

    Returns:
        Sorted list of RankedCandidate (highest overall_score first).
    """
    import asyncio

    if llm is None:
        llm = ChatRouter(
            default_required_tags=["reasoning"],
            default_estimated_tokens=2500,
        )

    async def _score_one(cid: str, parsed: ParsedResume) -> RankedCandidate:
        match = await score_candidate(job, parsed, llm=llm)
        return RankedCandidate(
            candidate_id=cid,
            name=parsed.name,
            email=parsed.email,
            match=match,
        )

    ranked = await asyncio.gather(*[_score_one(cid, p) for cid, p in candidates])
    return sorted(ranked, key=lambda r: r.match.overall_score, reverse=True)
