"""
app/api/v1/webhooks.py
Self-Hosted Open-Source ATS & HRIS Webhook Receivers for Greenhouse, Lever, and custom ATS systems.
Zero paid middleware dependencies (Merge.dev/Finch).
"""
import hmac
import hashlib
import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from app.deps import PoolDep
from app.services.tasks import create_task_record, async_parse_and_ingest_resume

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["ATS Webhooks"])


def verify_hmac_signature(payload: bytes, secret: str, signature_header: Optional[str]) -> bool:
    """Verify HMAC SHA-256 signature for webhook security."""
    if not secret or not signature_header:
        return True  # Dev mode fallback
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)


@router.post(
    "/greenhouse",
    status_code=202,
    summary="Inbound webhook for Greenhouse ATS applicant submissions",
)
async def greenhouse_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_greenhouse_signature: Optional[str] = Header(default=None, alias="X-Greenhouse-Signature"),
):
    """
    Receive candidate submission webhooks from Greenhouse ATS.
    Extracts candidate information and automatically queues resume ingestion.
    """
    body_bytes = await request.body()
    try:
        payload: Dict[str, Any] = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    logger.info("webhooks.greenhouse_received payload_action=%s", payload.get("action"))

    application = payload.get("payload", {}).get("application", {})
    candidate_data = application.get("candidate", {})

    name = f"{candidate_data.get('first_name', '')} {candidate_data.get('last_name', '')}".strip() or "Greenhouse Applicant"
    email_addresses = candidate_data.get("email_addresses", [])
    email = email_addresses[0].get("value") if email_addresses else None

    # Dummy resume payload representation for webhook ingest
    dummy_resume_text = f"Name: {name}\nEmail: {email}\nExtracted from Greenhouse Application ID: {application.get('id')}"

    task_id = create_task_record(task_type="ats_greenhouse_ingestion", tenant_id="greenhouse_sync")
    background_tasks.add_task(
        async_parse_and_ingest_resume,
        task_id=task_id,
        file_bytes=dummy_resume_text.encode('utf-8'),
        filename=f"greenhouse_{application.get('id', 'app')}.pdf",
        tenant_id="default",
    )

    return {
        "status": "accepted",
        "task_id": task_id,
        "ats_source": "greenhouse",
        "candidate_name": name,
    }


@router.post(
    "/lever",
    status_code=202,
    summary="Inbound webhook for Lever ATS application submissions",
)
async def lever_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_lever_signature: Optional[str] = Header(default=None, alias="X-Lever-Signature"),
):
    """
    Receive candidate application webhooks from Lever ATS.
    """
    try:
        payload: Dict[str, Any] = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    logger.info("webhooks.lever_received event=%s", payload.get("event"))

    candidate_id = payload.get("data", {}).get("candidateId")
    name = payload.get("data", {}).get("name", "Lever Applicant")

    dummy_resume_text = f"Name: {name}\nExtracted from Lever Candidate ID: {candidate_id}"
    task_id = create_task_record(task_type="ats_lever_ingestion", tenant_id="lever_sync")

    background_tasks.add_task(
        async_parse_and_ingest_resume,
        task_id=task_id,
        file_bytes=dummy_resume_text.encode('utf-8'),
        filename=f"lever_{candidate_id or 'cand'}.pdf",
        tenant_id="default",
    )

    return {
        "status": "accepted",
        "task_id": task_id,
        "ats_source": "lever",
        "candidate_name": name,
    }
