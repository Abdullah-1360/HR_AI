"""
app/api/v1/candidates.py
REST endpoints for candidate management — including resume upload.
"""
import logging

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Query, UploadFile

from app.deps import PoolDep, LLMDep, TenantDep
from app.models.schemas import CandidateResponse, CandidateListResponse
from app.services.candidate_service import ingest_candidate, get_candidate, list_all_candidates
from app.services.tasks import create_task_record, get_task_status, async_parse_and_ingest_resume

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/candidates", tags=["Candidates"])

ALLOWED_CONTENT_TYPES = {"application/pdf", "application/octet-stream"}
MAX_FILE_SIZE_MB = 10


@router.post(
    "/",
    response_model=CandidateResponse,
    status_code=201,
    summary="Upload a resume PDF and ingest candidate",
)
async def upload_candidate_endpoint(
    pool: PoolDep,
    llm: LLMDep,
    tenant_id: TenantDep,
    file: UploadFile = File(..., description="Resume PDF file"),
) -> CandidateResponse:
    """
    Upload a resume PDF. The AI pipeline will automatically:
    - Extract text from the PDF
    - Parse structured profile (name, skills, experience, education, etc.)
    - Generate a semantic embedding for matching
    - Store the PDF in MinIO object storage
    - Persist the candidate profile to PostgreSQL
    """
    # Validate file type
    if file.content_type not in ALLOWED_CONTENT_TYPES and not (
        file.filename or ""
    ).lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are accepted",
        )

    pdf_bytes = await file.read()

    # Validate file size
    if len(pdf_bytes) > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File too large — maximum size is {MAX_FILE_SIZE_MB}MB",
        )

    try:
        candidate_row = await ingest_candidate(
            pool,
            pdf_bytes=pdf_bytes,
            filename=file.filename or "resume.pdf",
            tenant_id=tenant_id,
            llm=llm,
        )
        return CandidateResponse(**candidate_row)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.error("POST /candidates error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/async",
    status_code=202,
    summary="Enqueue resume upload for background parsing",
)
async def upload_candidate_async_endpoint(
    background_tasks: BackgroundTasks,
    tenant_id: TenantDep,
    file: UploadFile = File(..., description="Resume PDF file"),
):
    pdf_bytes = await file.read()
    if len(pdf_bytes) > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large")

    task_id = create_task_record(task_type="resume_ingestion", tenant_id=tenant_id)
    background_tasks.add_task(
        async_parse_and_ingest_resume,
        task_id=task_id,
        file_bytes=pdf_bytes,
        filename=file.filename or "resume.pdf",
        tenant_id=tenant_id,
    )
    return {"task_id": task_id, "status": "pending", "status_url": f"/api/v1/candidates/tasks/{task_id}"}


@router.get(
    "/tasks/{task_id}",
    summary="Get status of an async background resume processing task",
)
async def get_task_status_endpoint(task_id: str):
    task = get_task_status(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/{candidate_id}", response_model=CandidateResponse, summary="Get a candidate by ID")
async def get_candidate_endpoint(
    candidate_id: str,
    pool: PoolDep,
) -> CandidateResponse:
    candidate_row = await get_candidate(pool, candidate_id)
    if not candidate_row:
        raise HTTPException(status_code=404, detail=f"Candidate {candidate_id} not found")
    return CandidateResponse(**candidate_row)


@router.get("/", response_model=CandidateListResponse, summary="List all candidates")
async def list_candidates_endpoint(
    pool: PoolDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> CandidateListResponse:
    rows = await list_all_candidates(pool, limit=limit, offset=offset)
    return CandidateListResponse(
        items=[CandidateResponse(**r) for r in rows],
        total=len(rows),
    )

