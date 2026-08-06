"""
app/api/router.py
Aggregate all API v1 routers under a single include.
"""
from fastapi import APIRouter

from app.api.v1.jobs import router as jobs_router
from app.api.v1.candidates import router as candidates_router
from app.api.v1.hiring import router as hiring_router
from app.api.v1.copilot import router as copilot_router
from app.api.v1.webhooks import router as webhooks_router
from app.api.v1.screening import router as screening_router

api_router = APIRouter()

api_router.include_router(jobs_router)
api_router.include_router(candidates_router)
api_router.include_router(hiring_router)
api_router.include_router(copilot_router)
api_router.include_router(webhooks_router)
api_router.include_router(screening_router)



