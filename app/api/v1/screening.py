"""
app/api/v1/screening.py
REST API endpoints for AI Audio Pre-Screening.
Uses OpenAI Whisper API or free browser Web Speech API for zero extra cost dependencies.
"""
import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.deps import PoolDep, LLMDep, TenantDep
from app.repositories.job_repository import get_job_by_id
from app.ai.schemas.job_schemas import ParsedJob
from app.ai.agents.audio_agent import generate_audio_screening_session, evaluate_screening_transcript

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/screening", tags=["AI Audio Screening"])


class ScreeningSessionRequest(BaseModel):
    job_id: str = Field(..., description="Target Job UUID")
    candidate_id: Optional[str] = Field(default=None, description="Optional Candidate UUID")


class ScreeningSessionResponse(BaseModel):
    job_id: str
    job_title: str
    questions: List[str]


class ScreeningEvaluationRequest(BaseModel):
    job_id: str
    transcript: str = Field(..., min_length=10, description="Full interview transcript text")


@router.post(
    "/session",
    response_model=ScreeningSessionResponse,
    summary="Generate AI Audio Screening Session for a job",
)
async def create_screening_session_endpoint(
    body: ScreeningSessionRequest,
    pool: PoolDep,
    llm: LLMDep,
):
    job_row = await get_job_by_id(pool, body.job_id)
    if not job_row:
        raise HTTPException(status_code=404, detail="Job not found")

    parsed_job = ParsedJob(**job_row["parsed_requirements"])
    questions = await generate_audio_screening_session(parsed_job, llm=llm)

    return ScreeningSessionResponse(
        job_id=body.job_id,
        job_title=job_row.get("title", "Position"),
        questions=questions,
    )


@router.post(
    "/transcribe",
    summary="Transcribe audio response using OpenAI Whisper API",
)
async def transcribe_audio_endpoint(
    file: UploadFile = File(..., description="Audio recording file (mp3/wav/webm/m4a)"),
):
    """
    Transcribe candidate audio recording using OpenAI Whisper API (`whisper-1`).
    """
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    try:
        import os
        import openai
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise HTTPException(status_code=400, detail="OPENAI_API_KEY required for Whisper transcription")

        client = openai.AsyncOpenAI(api_key=api_key)
        # Wrap bytes in tuple for OpenAI audio API
        response = await client.audio.transcriptions.create(
            model="whisper-1",
            file=(file.filename or "audio.webm", audio_bytes, file.content_type or "audio/webm"),
        )
        return {"text": response.text, "filename": file.filename}
    except Exception as exc:
        logger.error("screening.transcribe_failed error=%s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/evaluate",
    summary="Evaluate candidate screening transcript against job rubric",
)
async def evaluate_screening_endpoint(
    body: ScreeningEvaluationRequest,
    pool: PoolDep,
    llm: LLMDep,
):
    job_row = await get_job_by_id(pool, body.job_id)
    if not job_row:
        raise HTTPException(status_code=404, detail="Job not found")

    parsed_job = ParsedJob(**job_row["parsed_requirements"])
    evaluation = await evaluate_screening_transcript(
        job_title=job_row.get("title", "Position"),
        required_skills=parsed_job.required_skills,
        transcript=body.transcript,
        llm=llm,
    )
    return evaluation
