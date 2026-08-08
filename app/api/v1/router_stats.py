"""
app/api/v1/router_stats.py
REST endpoints for Real-Time Router Intelligence & Monitoring.
All metrics are queried directly from live PostgreSQL router tables.
"""
from typing import Any, Dict, List, Optional
from datetime import datetime
from uuid import UUID
import logging

from fastapi import APIRouter, Query
from app.deps import PoolDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/router", tags=["Router Intelligence"])


@router.get("/overview")
async def get_router_overview(pool: PoolDep) -> Dict[str, Any]:
    """
    Returns real-time dashboard overview metrics queried from the router tables.
    """
    async with pool.acquire() as conn:
        # Request and token stats
        stats_row = await conn.fetchrow("""
            SELECT 
                COUNT(*) AS total_requests,
                COALESCE(SUM(total_tokens), 0) AS total_tokens,
                COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
                COALESCE(SUM(completion_tokens), 0) AS completion_tokens,
                COALESCE(AVG(CASE WHEN status = 'success' THEN latency_ms END), 0) AS avg_latency_ms,
                COUNT(CASE WHEN status = 'success' THEN 1 END) AS success_count,
                COUNT(CASE WHEN status = 'failure' THEN 1 END) AS failure_count
            FROM request_log;
        """)

        # Provider and model counts
        counts_row = await conn.fetchrow("""
            SELECT 
                (SELECT COUNT(*) FROM providers WHERE enabled = true) AS active_providers,
                (SELECT COUNT(*) FROM providers) AS total_providers,
                (SELECT COUNT(*) FROM models WHERE enabled = true) AS active_models,
                (SELECT COUNT(*) FROM models) AS total_models,
                (SELECT COUNT(*) FROM model_health WHERE healthy = true) AS healthy_models;
        """)

        # Active reservations right now
        res_row = await conn.fetchrow("""
            SELECT 
                COUNT(*) AS active_reservations,
                COALESCE(SUM(reserved_amount), 0) AS active_reserved_tokens
            FROM reservations
            WHERE state = 'pending' AND expires_at > NOW();
        """)

        # Tokens breakdown by provider
        provider_tokens = await conn.fetch("""
            SELECT 
                COALESCE(p.display_name, p.name, 'Unknown') AS provider_name,
                p.name AS provider_key,
                COALESCE(SUM(rl.total_tokens), 0) AS tokens,
                COUNT(rl.id) AS requests
            FROM request_log rl
            LEFT JOIN providers p ON p.id = rl.provider_id
            GROUP BY p.name, p.display_name
            ORDER BY tokens DESC;
        """)

        # Recent 24h hourly request velocity
        hourly_stats = await conn.fetch("""
            SELECT 
                date_trunc('hour', created_at) AS hour_bucket,
                COUNT(*) AS requests,
                COALESCE(SUM(total_tokens), 0) AS tokens,
                COALESCE(AVG(latency_ms), 0) AS avg_latency
            FROM request_log
            WHERE created_at >= NOW() - INTERVAL '24 hours'
            GROUP BY hour_bucket
            ORDER BY hour_bucket ASC;
        """)

    total_req = stats_row["total_requests"] or 0
    succ_cnt = stats_row["success_count"] or 0
    success_rate = round((succ_cnt / total_req * 100), 2) if total_req > 0 else 100.0

    return {
        "overview": {
            "total_requests": total_req,
            "total_tokens": stats_row["total_tokens"],
            "prompt_tokens": stats_row["prompt_tokens"],
            "completion_tokens": stats_row["completion_tokens"],
            "avg_latency_ms": round(float(stats_row["avg_latency_ms"]), 1),
            "success_count": succ_cnt,
            "failure_count": stats_row["failure_count"] or 0,
            "success_rate": success_rate,
            "active_providers": counts_row["active_providers"],
            "total_providers": counts_row["total_providers"],
            "active_models": counts_row["active_models"],
            "total_models": counts_row["total_models"],
            "healthy_models": counts_row["healthy_models"],
            "active_reservations": res_row["active_reservations"],
            "active_reserved_tokens": res_row["active_reserved_tokens"],
        },
        "by_provider": [
            {
                "provider_name": r["provider_name"],
                "provider_key": r["provider_key"],
                "tokens": int(r["tokens"]),
                "requests": int(r["requests"]),
            }
            for r in provider_tokens
        ],
        "hourly_velocity": [
            {
                "timestamp": r["hour_bucket"].isoformat() if r["hour_bucket"] else None,
                "requests": int(r["requests"]),
                "tokens": int(r["tokens"]),
                "avg_latency_ms": round(float(r["avg_latency"]), 1),
            }
            for r in hourly_stats
        ],
    }


@router.get("/providers")
async def get_router_providers(pool: PoolDep) -> List[Dict[str, Any]]:
    """
    Returns the real-time status of all LLM providers, including model count,
    average latency, error rates, and capability flags.
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT 
                p.id,
                p.name,
                p.display_name,
                p.provider_type,
                p.tier,
                p.priority,
                p.enabled,
                p.base_url,
                p.supports_streaming,
                p.supports_tools,
                p.supports_images,
                p.supports_reasoning,
                p.created_at,
                COUNT(DISTINCT m.id) AS total_models,
                COUNT(DISTINCT CASE WHEN m.enabled = true THEN m.id END) AS active_models,
                COALESCE(AVG(mh.average_latency), 0) AS avg_latency_ms,
                COALESCE(AVG(mh.error_rate), 0) AS avg_error_rate,
                COALESCE(BOOL_AND(mh.healthy), true) AS is_healthy,
                COALESCE(SUM(rl.total_tokens), 0) AS tokens_consumed,
                COUNT(rl.id) AS total_requests
            FROM providers p
            LEFT JOIN models m ON m.provider_id = p.id
            LEFT JOIN model_health mh ON mh.model_id = m.id
            LEFT JOIN request_log rl ON rl.provider_id = p.id
            GROUP BY 
                p.id, p.name, p.display_name, p.provider_type, p.tier, p.priority,
                p.enabled, p.base_url, p.supports_streaming, p.supports_tools,
                p.supports_images, p.supports_reasoning, p.created_at
            ORDER BY p.priority ASC, p.name ASC;
        """)

    return [
        {
            "id": str(r["id"]),
            "name": r["name"],
            "display_name": r["display_name"],
            "provider_type": str(r["provider_type"]),
            "tier": str(r["tier"]),
            "priority": r["priority"],
            "enabled": r["enabled"],
            "base_url": r["base_url"],
            "capabilities": {
                "streaming": r["supports_streaming"],
                "tools": r["supports_tools"],
                "images": r["supports_images"],
                "reasoning": r["supports_reasoning"],
            },
            "metrics": {
                "total_models": r["total_models"],
                "active_models": r["active_models"],
                "avg_latency_ms": round(float(r["avg_latency_ms"]), 1),
                "error_rate": round(float(r["avg_error_rate"]) * 100, 2),
                "healthy": r["is_healthy"],
                "tokens_consumed": int(r["tokens_consumed"]),
                "total_requests": int(r["total_requests"]),
            },
        }
        for r in rows
    ]


@router.get("/models")
async def get_router_models(pool: PoolDep) -> List[Dict[str, Any]]:
    """
    Returns all models with their live quota consumption (used vs limit),
    latency scores, health metrics, and capabilities.
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT 
                m.id AS model_id,
                m.model_name,
                COALESCE(m.display_name, m.model_name) AS display_name,
                m.tier,
                m.enabled,
                m.context_window,
                m.max_output_tokens,
                m.vision,
                m.tools,
                m.reasoning,
                m.coding,
                m.last_selected_at,
                p.id AS provider_id,
                p.name AS provider_name,
                p.display_name AS provider_display_name,
                COALESCE(mh.healthy, true) AS healthy,
                mh.average_latency AS avg_latency_ms,
                mh.average_ttft AS avg_ttft_ms,
                COALESCE(mh.error_rate, 0.0) AS error_rate,
                COALESCE(mh.consecutive_failures, 0) AS consecutive_failures,
                mh.disabled_until,
                COALESCE(rs.overall_score, 50.0) AS overall_score,
                COALESCE(rs.quality_score, 50.0) AS quality_score,
                COALESCE(rs.speed_score, 50.0) AS speed_score,
                COALESCE(rs.availability_score, 50.0) AS availability_score,
                COALESCE(rs.cost_score, 50.0) AS cost_score,
                qd.id AS quota_id,
                qd.quota_type,
                qd.quota_window,
                qd.limit_value AS quota_limit,
                COALESCE(qu.used, 0) AS quota_used,
                COALESCE(qu.reserved, 0) AS quota_reserved,
                qu.window_start,
                qu.window_end
            FROM models m
            JOIN providers p ON p.id = m.provider_id
            LEFT JOIN model_health mh ON mh.model_id = m.id
            LEFT JOIN routing_scores rs ON rs.model_id = m.id
            LEFT JOIN quota_definitions qd ON qd.model_id = m.id AND qd.active = true
            LEFT JOIN quota_usage qu ON qu.quota_definition_id = qd.id AND qu.window_end > NOW()
            ORDER BY 
                CASE m.tier
                    WHEN 'PRIMARY_FREE' THEN 1
                    WHEN 'SECONDARY_FREE' THEN 2
                    WHEN 'LIMITED_FREE' THEN 3
                    WHEN 'PAID' THEN 4
                    WHEN 'LOCAL' THEN 5
                    ELSE 6
                END,
                p.name,
                m.model_name;
        """)

    # Group quotas by model
    models_dict: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        mid = str(r["model_id"])
        if mid not in models_dict:
            disabled_until_iso = r["disabled_until"].isoformat() if r["disabled_until"] else None
            last_selected_iso = r["last_selected_at"].isoformat() if r["last_selected_at"] else None
            
            models_dict[mid] = {
                "id": mid,
                "model_name": r["model_name"],
                "display_name": r["display_name"],
                "tier": str(r["tier"]),
                "enabled": r["enabled"],
                "context_window": r["context_window"],
                "max_output_tokens": r["max_output_tokens"],
                "capabilities": {
                    "vision": r["vision"],
                    "tools": r["tools"],
                    "reasoning": r["reasoning"],
                    "coding": r["coding"],
                },
                "provider": {
                    "id": str(r["provider_id"]),
                    "name": r["provider_name"],
                    "display_name": r["provider_display_name"],
                },
                "health": {
                    "healthy": r["healthy"],
                    "avg_latency_ms": round(float(r["avg_latency_ms"]), 1) if r["avg_latency_ms"] else None,
                    "avg_ttft_ms": round(float(r["avg_ttft_ms"]), 1) if r["avg_ttft_ms"] else None,
                    "error_rate": round(float(r["error_rate"]) * 100, 2),
                    "consecutive_failures": r["consecutive_failures"],
                    "disabled_until": disabled_until_iso,
                },
                "scores": {
                    "overall": round(float(r["overall_score"]), 1),
                    "quality": round(float(r["quality_score"]), 1),
                    "speed": round(float(r["speed_score"]), 1),
                    "availability": round(float(r["availability_score"]), 1),
                    "cost": round(float(r["cost_score"]), 1),
                },
                "last_selected_at": last_selected_iso,
                "quotas": [],
            }

        # Add quota definition if present
        if r["quota_id"]:
            limit = r["quota_limit"] or 1
            used = r["quota_used"] or 0
            reserved = r["quota_reserved"] or 0
            usage_pct = round(((used + reserved) / limit) * 100, 1) if limit > 0 else 0.0

            models_dict[mid]["quotas"].append({
                "type": str(r["quota_type"]),
                "window": str(r["quota_window"]),
                "limit": limit,
                "used": used,
                "reserved": reserved,
                "usage_percentage": min(usage_pct, 100.0),
                "window_start": r["window_start"].isoformat() if r["window_start"] else None,
                "window_end": r["window_end"].isoformat() if r["window_end"] else None,
            })

    return list(models_dict.values())


@router.get("/requests")
async def get_router_requests(
    pool: PoolDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    """
    Returns the real-time request log stream for live telemetry and inspection.
    """
    async with pool.acquire() as conn:
        where_clause = ""
        params: List[Any] = [limit, offset]
        if status:
            where_clause = "WHERE rl.status = $3"
            params.append(status)

        count_query = f"SELECT COUNT(*) FROM request_log rl {where_clause}"
        total_count = await conn.fetchval(count_query, *params[2:]) if status else await conn.fetchval("SELECT COUNT(*) FROM request_log")

        query = f"""
            SELECT 
                rl.id,
                rl.request_uuid,
                rl.status,
                rl.prompt_tokens,
                rl.completion_tokens,
                rl.total_tokens,
                rl.latency_ms,
                rl.ttft_ms,
                rl.http_status,
                rl.error_message,
                rl.attempt,
                rl.created_at,
                p.name AS provider_name,
                COALESCE(p.display_name, p.name) AS provider_display_name,
                m.model_name,
                COALESCE(m.display_name, m.model_name) AS model_display_name,
                m.tier
            FROM request_log rl
            LEFT JOIN providers p ON p.id = rl.provider_id
            LEFT JOIN models m ON m.id = rl.model_id
            {where_clause}
            ORDER BY rl.created_at DESC
            LIMIT $1 OFFSET $2;
        """
        rows = await conn.fetch(query, *params)

    items = [
        {
            "id": str(r["id"]),
            "request_uuid": str(r["request_uuid"]),
            "status": r["status"],
            "prompt_tokens": r["prompt_tokens"],
            "completion_tokens": r["completion_tokens"],
            "total_tokens": r["total_tokens"],
            "latency_ms": r["latency_ms"],
            "ttft_ms": r["ttft_ms"],
            "http_status": r["http_status"],
            "error_message": r["error_message"],
            "attempt": r["attempt"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "provider_name": r["provider_name"] or "unknown",
            "provider_display_name": r["provider_display_name"] or "Unknown",
            "model_name": r["model_name"] or "unknown",
            "model_display_name": r["model_display_name"] or "Unknown",
            "tier": str(r["tier"]) if r["tier"] else "PRIMARY_FREE",
        }
        for r in rows
    ]

    return {
        "items": items,
        "total": total_count or 0,
        "limit": limit,
        "offset": offset,
    }


@router.get("/tier-waterfall")
async def get_tier_waterfall(pool: PoolDep) -> List[Dict[str, Any]]:
    """
    Returns request distribution across the 5 router tiers (PRIMARY_FREE -> LOCAL).
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT 
                COALESCE(m.tier, 'PRIMARY_FREE') AS tier,
                COUNT(rl.id) AS request_count,
                COALESCE(SUM(rl.total_tokens), 0) AS total_tokens,
                COALESCE(AVG(rl.latency_ms), 0) AS avg_latency_ms,
                COUNT(CASE WHEN rl.status = 'success' THEN 1 END) AS success_count,
                COUNT(CASE WHEN rl.status = 'failure' THEN 1 END) AS failure_count
            FROM request_log rl
            LEFT JOIN models m ON m.id = rl.model_id
            GROUP BY COALESCE(m.tier, 'PRIMARY_FREE')
            ORDER BY 
                CASE COALESCE(m.tier, 'PRIMARY_FREE')
                    WHEN 'PRIMARY_FREE' THEN 1
                    WHEN 'SECONDARY_FREE' THEN 2
                    WHEN 'LIMITED_FREE' THEN 3
                    WHEN 'PAID' THEN 4
                    WHEN 'LOCAL' THEN 5
                    ELSE 6
                END;
        """)

    tier_descriptions = {
        "PRIMARY_FREE": "High-throughput free tier (Gemini, Groq)",
        "SECONDARY_FREE": "Diverse backup models (OpenRouter, Mistral)",
        "LIMITED_FREE": "High-reasoning / low-RPS models (Cerebras)",
        "PAID": "Fallback commercial endpoints (OpenAI, Claude)",
        "LOCAL": "Self-hosted offline fallbacks (Ollama, vLLM)",
    }

    return [
        {
            "tier": str(r["tier"]),
            "description": tier_descriptions.get(str(r["tier"]), "Routing tier"),
            "request_count": int(r["request_count"]),
            "total_tokens": int(r["total_tokens"]),
            "avg_latency_ms": round(float(r["avg_latency_ms"]), 1),
            "success_count": int(r["success_count"]),
            "failure_count": int(r["failure_count"]),
        }
        for r in rows
    ]
