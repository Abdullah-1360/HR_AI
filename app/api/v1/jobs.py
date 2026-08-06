"""
app/api/v1/jobs.py
REST endpoints for job management.
"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.deps import PoolDep, LLMDep
from app.models.schemas import JobCreateRequest, JobResponse, JobListResponse
from app.services.job_service import create_job, get_job, list_all_jobs

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.post("/", response_model=JobResponse, status_code=201, summary="Create and analyse a job posting")
async def create_job_endpoint(
    body: JobCreateRequest,
    pool: PoolDep,
    llm: LLMDep,
) -> JobResponse:
    """
    Create a new job posting. The AI will automatically:
    - Extract structured requirements (skills, seniority, responsibilities)
    - Generate a semantic embedding for candidate matching
    """
    try:
        job_row = await create_job(
            pool,
            title=body.title,
            raw_description=body.raw_description,
            llm=llm,
        )
        return JobResponse(**job_row)
    except Exception as exc:
        logger.error("POST /jobs error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{job_id}", response_model=JobResponse, summary="Get a job by ID")
async def get_job_endpoint(
    job_id: str,
    pool: PoolDep,
) -> JobResponse:
    job_row = await get_job(pool, job_id)
    if not job_row:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return JobResponse(**job_row)


@router.get("/", response_model=JobListResponse, summary="List all jobs")
async def list_jobs_endpoint(
    pool: PoolDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> JobListResponse:
    rows = await list_all_jobs(pool, limit=limit, offset=offset)
    return JobListResponse(items=[JobResponse(**r) for r in rows], total=len(rows))
