"""
app/main.py
FastAPI application entry point.
Manages the asyncpg pool and MinIO bucket lifecycle via the lifespan context.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# Load environment variables into os.environ
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import get_settings
from app.db.pool import create_pool, close_pool
from app.models.schemas import HealthResponse
from app.utils.storage import ensure_bucket

logger = logging.getLogger(__name__)

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown resource management."""
    settings = get_settings()
    logger.info("startup: connecting to database")
    await create_pool()

    logger.info("startup: ensuring MinIO bucket '%s' exists", settings.minio_bucket_resumes)
    try:
        ensure_bucket(settings.minio_bucket_resumes)
    except Exception as exc:
        logger.warning("startup: MinIO bucket setup failed (non-fatal): %s", exc)

    logger.info("startup: HR AI Platform ready")
    yield

    logger.info("shutdown: closing database pool")
    await close_pool()


# ── Application ───────────────────────────────────────────────────────────────
def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_title,
        version=settings.app_version,
        description=(
            "AI-powered Hiring Platform API. "
            "Analyse job descriptions, parse resumes, match candidates semantically, "
            "and generate tailored interview packs — all routed through an intelligent "
            "multi-provider LLM router with automatic fallback and quota management."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS — allow all origins for development; restrict in production
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount API routes
    app.include_router(api_router, prefix=settings.api_prefix)

    # ── Health endpoint ────────────────────────────────────────────────────────
    @app.get("/health", response_model=HealthResponse, tags=["System"])
    async def health_check() -> HealthResponse:
        from app.db.pool import get_pool
        db_status = "ok"
        try:
            pool = await get_pool()
            await pool.fetchval("SELECT 1")
        except Exception as exc:
            db_status = f"error: {exc}"

        storage_status = "ok"
        try:
            from app.utils.storage import _get_minio_client
            _get_minio_client()  # will raise if misconfigured
        except Exception as exc:
            storage_status = f"error: {exc}"

        return HealthResponse(
            status="ok" if db_status == "ok" else "degraded",
            version=settings.app_version,
            db=db_status,
            storage=storage_status,
        )

    return app


app = create_app()
