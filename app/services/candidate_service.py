"""
app/services/candidate_service.py
Business logic for candidate ingestion:
  PDF upload → text extraction → LLM parsing → embedding → MinIO storage → DB insert.
"""
import logging
from typing import Any, Dict, Optional

import asyncpg

from router.chat_model import ChatRouter
from app.ai.agents.resume_agent import parse_resume
from app.core.config import get_settings
from app.repositories.candidate_repository import (
    insert_candidate,
    get_candidate_by_id,
    list_candidates,
)
from app.utils.pdf_extractor import extract_text_from_bytes
from app.utils.embedder import embed_document
from app.utils.storage import upload_bytes

logger = logging.getLogger(__name__)


async def ingest_candidate(
    pool: asyncpg.Pool,
    *,
    pdf_bytes: bytes,
    filename: str,
    tenant_id: str = "default",
    llm: Optional[ChatRouter] = None,
) -> Dict[str, Any]:
    """
    Full candidate ingestion pipeline:
      1. Extract text from PDF bytes
      2. Parse resume → ParsedResume (Resume Parsing Agent)
      3. Generate semantic embedding
      4. Upload raw PDF to MinIO
      5. Persist candidate metadata to PostgreSQL
    """
    settings = get_settings()
    logger.info("candidate_service.ingest filename=%r tenant_id=%s", filename, tenant_id)

    # Step 1: Extract text
    resume_text = extract_text_from_bytes(pdf_bytes)

    # Step 2: LLM parse
    parsed = await parse_resume(resume_text=resume_text, llm=llm)

    # Step 3: Embedding
    embedding = await embed_document(resume_text)

    # Step 4: Upload to MinIO
    object_key = f"resumes/{parsed.name or 'unknown'}_{filename}"
    try:
        upload_bytes(
            bucket_name=settings.minio_bucket_resumes,
            object_name=object_key,
            data=pdf_bytes,
            content_type="application/pdf",
        )
        resume_url = f"minio://{settings.minio_bucket_resumes}/{object_key}"
    except Exception as exc:
        logger.warning("candidate_service.storage_failed: %s — continuing without URL", exc)
        resume_url = None

    # Step 5: Persist to DB
    candidate_row = await insert_candidate(
        pool,
        name=parsed.name,
        email=parsed.email,
        skills=parsed.skills,
        experience_years=parsed.experience_years,
        resume_url=resume_url,
        parsed_resume=parsed.model_dump(),
        embedding=embedding,
        tenant_id=tenant_id,
    )

    logger.info(
        "candidate_service.ingested candidate_id=%s name=%r tenant_id=%s",
        candidate_row["id"],
        parsed.name,
        tenant_id,
    )
    return candidate_row


class _CandidateObject:
    def __init__(self, data: dict):
        self.id = data["id"]
        self.name = data.get("name")


async def process_candidate_resume(
    pool: asyncpg.Pool,
    file_bytes: bytes,
    filename: str,
    tenant_id: str = "default",
):
    row = await ingest_candidate(pool, pdf_bytes=file_bytes, filename=filename, tenant_id=tenant_id)
    return _CandidateObject(row)



async def get_candidate(pool: asyncpg.Pool, candidate_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a candidate by ID."""
    return await get_candidate_by_id(pool, candidate_id)


async def list_all_candidates(
    pool: asyncpg.Pool,
    limit: int = 50,
    offset: int = 0,
) -> list[Dict[str, Any]]:
    """Return paginated candidate listing."""
    return await list_candidates(pool, limit=limit, offset=offset)
