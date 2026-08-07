"""
app/deps.py
FastAPI dependency injection — pool, LLM, settings.
"""
from typing import Annotated

import asyncpg
from fastapi import Depends, Header


from app.core.config import Settings, get_settings
from app.db.pool import get_pool as _get_pool
from router.chat_model import ChatRouter

# ── Singleton ChatRouter ───────────────────────────────────────────────────────
_llm: ChatRouter | None = None


def get_llm() -> ChatRouter:
    """Return a module-level singleton ChatRouter instance."""
    global _llm
    if _llm is None:
        _llm = ChatRouter()
    return _llm


# ── FastAPI dependency aliases ─────────────────────────────────────────────────
async def pool_dep() -> asyncpg.Pool:
    return await _get_pool()


def get_current_tenant(
    x_tenant_id: Annotated[str | None, Header(alias="X-Tenant-ID")] = None,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> str:
    """
    Extract tenant_id from request headers.
    Supports X-Tenant-ID header and JWT authorization fallback.
    Default to 'default' if not present in dev mode.
    """
    if x_tenant_id:
        return x_tenant_id.strip()

    # JWT inspection fallback
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        try:
            import jwt
            payload = jwt.decode(token, options={"verify_signature": False})
            if "tenant_id" in payload:
                return str(payload["tenant_id"])
        except Exception:
            pass

    return "default"


PoolDep = Annotated[asyncpg.Pool, Depends(pool_dep)]
LLMDep = Annotated[ChatRouter, Depends(get_llm)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
TenantDep = Annotated[str, Depends(get_current_tenant)]

