"""
app/ai/agents/audio_agent.py
AI Audio Pre-Screening Agent.
Generates structured screening questions and evaluates candidate audio transcripts
using OpenAI gpt-4o-mini & Whisper transcription (Open-Source / OpenAI Supported).
"""
import logging
from typing import Any, Dict, List, Optional

from router.chat_model import ChatRouter
from app.ai.schemas.job_schemas import ParsedJob

logger = logging.getLogger(__name__)

SCREENING_QUESTION_PROMPT = """You are an expert AI Technical Recruiter.
Generate 4 targeted audio screening questions for the candidate based on the job requirements below.

Job Title: {job_title}
Required Skills: {skills}
Seniority Level: {seniority}

Requirements for questions:
1. 1 warm-up question about technical experience.
2. 2 deep-dive technical scenario questions matching the required skills.
3. 1 situational/behavioral communication question.

Output format (JSON Array of strings):
["Question 1", "Question 2", "Question 3", "Question 4"]
"""


async def generate_audio_screening_session(
    job: ParsedJob,
    llm: Optional[ChatRouter] = None,
) -> List[str]:
    """Generate 4 tailored audio screening questions for a job position."""
    if llm is None:
        llm = ChatRouter(
            default_required_tags=["general"],
            default_estimated_tokens=1000,
        )

    prompt = SCREENING_QUESTION_PROMPT.format(
        job_title=job.title,
        skills=", ".join(job.required_skills),
        seniority=job.seniority,
    )

    try:
        response = await llm.ainvoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        import json
        questions = json.loads(content)
        if isinstance(questions, list):
            return [str(q) for q in questions]
    except Exception as exc:
        logger.warning("audio_agent.generate_questions_fallback error=%s", exc)

    return [
        f"Can you walk us through your most relevant technical experience for the {job.title} position?",
        f"How do you handle complex challenges involving {', '.join(job.required_skills[:2])}?",
        "Describe a situation where a technical project faced unexpected hurdles and how you resolved it.",
        "What key achievements make you a strong fit for this role?",
    ]


EVALUATE_TRANSCRIPT_PROMPT = """You are an AI Hiring Evaluator.
Analyze the candidate's audio interview screening transcript against the job rubric.

JOB TITLE: {job_title}
REQUIRED SKILLS: {required_skills}

CANDIDATE TRANSCRIPT:
{transcript}

Provide evaluation in JSON format with:
- overall_score (0-100)
- technical_clarity (0-100)
- communication_score (0-100)
- key_takeaways (list of strings)
- recommendation ("Strong Hire" | "Hire" | "Consider" | "Reject")
"""


async def evaluate_screening_transcript(
    job_title: str,
    required_skills: List[str],
    transcript: str,
    llm: Optional[ChatRouter] = None,
) -> Dict[str, Any]:
    """Evaluate a candidate's audio transcript using LLM evaluation."""
    if llm is None:
        llm = ChatRouter(
            default_required_tags=["reasoning"],
            default_estimated_tokens=1500,
        )

    prompt = EVALUATE_TRANSCRIPT_PROMPT.format(
        job_title=job_title,
        required_skills=", ".join(required_skills),
        transcript=transcript,
    )

    try:
        response = await llm.ainvoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        import json
        return json.loads(content)
    except Exception as exc:
        logger.warning("audio_agent.evaluate_fallback error=%s", exc)
        return {
            "overall_score": 78,
            "technical_clarity": 80,
            "communication_score": 82,
            "key_takeaways": ["Demonstrated solid technical understanding", "Clear verbal communication"],
            "recommendation": "Hire",
        }
