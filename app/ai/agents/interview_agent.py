"""
app/ai/agents/interview_agent.py
Interview Generation Agent — creates a comprehensive interview pack for a (job, candidate) pair.
"""
import logging
from typing import List, Optional

from router.chat_model import ChatRouter
from app.ai.prompts.interview_prompts import INTERVIEW_GENERATION_PROMPT
from app.ai.schemas.job_schemas import ParsedJob
from app.ai.schemas.resume_schemas import ParsedResume
from app.ai.schemas.interview_schemas import InterviewPack
from app.ai.schemas.match_schemas import MatchResult

logger = logging.getLogger(__name__)


async def generate_interview_pack(
    job: ParsedJob,
    candidate: ParsedResume,
    match_result: Optional[MatchResult] = None,
    llm: Optional[ChatRouter] = None,
) -> InterviewPack:
    """
    Generate a tailored interview pack for a (job, candidate) pair.

    Args:
        job: Structured job requirements.
        candidate: Structured candidate profile.
        match_result: Optional prior match evaluation to guide focus areas.
        llm: ChatRouter instance. Creates one if not provided.

    Returns:
        InterviewPack with questions, follow-ups, and evaluation rubric.
    """
    if llm is None:
        llm = ChatRouter(
            default_estimated_tokens=3000,
        )

    structured_llm = llm.with_structured_output(InterviewPack)
    chain = INTERVIEW_GENERATION_PROMPT | structured_llm

    # Derive probe areas from match result if available
    strengths: List[str] = []
    probe_areas: str = "General competencies relevant to the role"
    if match_result:
        strengths = match_result.strengths[:3]
        probe_areas = (
            match_result.recommended_interview_focus
            or ", ".join(match_result.missing_skills[:3])
            or "General technical depth"
        )

    logger.info(
        "interview_agent.generate job=%r candidate=%r",
        job.title,
        candidate.name,
    )

    result: InterviewPack = await chain.ainvoke({
        "job_title": job.title,
        "seniority": job.seniority,
        "required_skills": ", ".join(job.required_skills),
        "responsibilities": "\n".join(f"  • {r}" for r in job.responsibilities),
        "candidate_name": candidate.name or "Candidate",
        "experience_years": candidate.experience_years,
        "candidate_skills": ", ".join(candidate.skills),
        "strengths": ", ".join(strengths) if strengths else "Not yet assessed",
        "probe_areas": probe_areas,
    })

    logger.info(
        "interview_agent.done job=%r questions=%d",
        job.title,
        len(result.technical_questions)
        + len(result.behavioral_questions)
        + len(result.scenario_questions),
    )
    return result
