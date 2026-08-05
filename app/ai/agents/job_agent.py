"""
app/ai/agents/job_agent.py
Job Understanding Agent — analyses raw job descriptions and extracts structured requirements.
Uses ChatRouter with required_tags=['tool-calling'] to ensure structured output compatibility.
"""
import logging
from typing import Optional

from router.chat_model import ChatRouter
from app.ai.prompts.job_prompts import JOB_ANALYSIS_PROMPT
from app.ai.schemas.job_schemas import ParsedJob

logger = logging.getLogger(__name__)


async def analyze_job(
    raw_description: str,
    title: Optional[str] = None,
    llm: Optional[ChatRouter] = None,
) -> ParsedJob:
    """
    Analyse a raw job posting and extract structured requirements.

    Args:
        raw_description: Free-text job description.
        title: Optional job title (hint for the model).
        llm: ChatRouter instance. Creates one if not provided.

    Returns:
        ParsedJob structured output.
    """
    if llm is None:
        llm = ChatRouter(
            default_required_tags=["tool-calling"],
            default_estimated_tokens=1200,
        )

    # Build a structured-output chain
    structured_llm = llm.with_structured_output(ParsedJob)
    chain = JOB_ANALYSIS_PROMPT | structured_llm

    logger.info("job_agent.analyze title=%r", title or "unknown")
    result: ParsedJob = await chain.ainvoke({
        "title": title or "Not specified",
        "raw_description": raw_description,
    })
    logger.info("job_agent.done title=%r required_skills=%d", title, len(result.required_skills))
    return result
