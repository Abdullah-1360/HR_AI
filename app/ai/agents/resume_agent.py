"""
app/ai/agents/resume_agent.py
Resume Parsing Agent — extracts structured candidate profile from raw resume text.
Uses ChatRouter with required_tags=['large-context'] for handling lengthy resumes.
"""
import logging
from typing import Optional

from router.chat_model import ChatRouter
from app.ai.prompts.resume_prompts import RESUME_PARSE_PROMPT
from app.ai.schemas.resume_schemas import ParsedResume

logger = logging.getLogger(__name__)


async def parse_resume(
    resume_text: str,
    llm: Optional[ChatRouter] = None,
) -> ParsedResume:
    """
    Parse raw resume text into a structured candidate profile.

    Args:
        resume_text: Plain text content extracted from a resume PDF.
        llm: ChatRouter instance. Creates one if not provided.

    Returns:
        ParsedResume structured output.
    """
    if llm is None:
        llm = ChatRouter(
            default_required_tags=["large-context"],
            default_estimated_tokens=2000,
        )

    structured_llm = llm.with_structured_output(ParsedResume)
    chain = RESUME_PARSE_PROMPT | structured_llm

    logger.info("resume_agent.parse text_len=%d", len(resume_text))
    result: ParsedResume = await chain.ainvoke({"resume_text": resume_text})
    logger.info(
        "resume_agent.done name=%r skills=%d exp_years=%d",
        result.name,
        len(result.skills),
        result.experience_years,
    )
    return result
