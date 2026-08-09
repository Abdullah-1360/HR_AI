"""
router/router.py
RouterNode — the main class that ties together selector, reservation,
health tracking, and LangChain provider dispatch.

This is what the LangGraph router_node calls.
"""

from __future__ import annotations

import logging
import os
import time
from uuid import UUID, uuid4
from typing import Optional, Any

import asyncpg
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage

from .db import get_pool
from .selector import select_model_waterfall, ModelCandidate
from . import reservation as res_module
from . import health as health_module
from . import logger as log_module

logger = logging.getLogger(__name__)

MAX_RETRIES = 5


class NoModelAvailableError(Exception):
    """Raised when all tiers are exhausted and no model could be selected."""


class RouterNode:
    """
    RouterNode encapsulates all routing logic for use inside a LangGraph graph.

    Usage in graph:
        router = RouterNode()
        workflow.add_node("router", router.select)
        workflow.add_node("llm",    router.call_llm)
        workflow.add_node("update", router.update)
    """

    def __init__(self) -> None:
        self._pool: Optional[asyncpg.Pool] = None
        self._llm_cache: dict[str, BaseChatModel] = {}

    async def _get_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            self._pool = await get_pool()
        return self._pool

    # -------------------------------------------------------------------------
    # Node 1: select
    # Called by LangGraph as the "router_node".
    # Walks the tier waterfall and reserves quota for the winning model.
    # -------------------------------------------------------------------------
    async def select(self, state: dict) -> dict:
        """
        LangGraph node: select a model and reserve quota.
        Updates state with selected_model, selected_provider, reservation_id.
        """
        pool = await self._get_pool()
        request_uuid: UUID = state.get("request_uuid") or uuid4()
        estimated_tokens: int = state.get("estimated_tokens", 500)
        failed_models: list[UUID] = [
            UUID(mid) if isinstance(mid, str) else mid
            for mid in state.get("failed_models", [])
        ]

        required_tags: list[str] = state.get("required_tags") or []

        candidate: Optional[ModelCandidate] = await select_model_waterfall(
            pool, estimated_tokens, failed_models, required_tags
        )

        if candidate is None:
            logger.error("All tiers exhausted. No model available.")
            return {**state, "error": "NoModelAvailable — all tiers exhausted"}

        # Attempt quota reservation
        reservation_id = await res_module.reserve(
            pool, request_uuid, candidate.model_id, estimated_tokens
        )

        if reservation_id is None:
            # SKIP LOCKED claimed it — add to exclusion and retry same tier
            logger.warning(
                "Quota race on model=%s, adding to exclusion list",
                candidate.model_name,
            )
            failed_models.append(candidate.model_id)
            return {
                **state,
                "failed_models": [str(m) for m in failed_models],
                "request_uuid": str(request_uuid),
            }

        logger.info(
            "Router selected: provider=%s model=%s tier=%s reservation=%s",
            candidate.provider_name,
            candidate.model_name,
            candidate.tier,
            reservation_id,
        )

        return {
            **state,
            "request_uuid": str(request_uuid),
            "selected_model": candidate.model_name,
            "selected_provider": candidate.provider_name,
            "selected_model_id": str(candidate.model_id),
            "selected_provider_id": str(candidate.provider_id),
            "selected_base_url": candidate.base_url,
            "selected_tier": candidate.tier,
            "reservation_id": str(reservation_id),
            "failed_models": [str(m) for m in failed_models],
            "error": None,
        }

    # -------------------------------------------------------------------------
    # Node 2: call_llm
    # Called by LangGraph as the "llm_node".
    # Dispatches to the correct LangChain provider and measures latency.
    # -------------------------------------------------------------------------
    async def call_llm(self, state: dict) -> dict:
        """
        LangGraph node: invoke the selected LLM provider.
        Records latency and token counts into state.
        """
        if state.get("error"):
            return state  # propagate errors from select node

        model_name: str = state["selected_model"]
        provider_name: str = state["selected_provider"]
        base_url: str = state.get("selected_base_url", "")
        messages: list[BaseMessage] = state.get("messages", [])

        llm = self._get_llm_client(provider_name, model_name, base_url)

        start = time.monotonic()
        try:
            response = await llm.ainvoke(messages)
            latency_ms = int((time.monotonic() - start) * 1000)

            # Extract token usage if available
            usage = getattr(response, "usage_metadata", None) or {}
            prompt_tokens = usage.get("input_tokens") or usage.get("prompt_tokens")
            completion_tokens = usage.get("output_tokens") or usage.get("completion_tokens")

            return {
                **state,
                "response": response.content,
                "latency_ms": latency_ms,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "llm_error": None,
            }

        except Exception as exc:
            latency_ms = int((time.monotonic() - start) * 1000)
            logger.error(
                "LLM call failed: provider=%s model=%s error=%s",
                provider_name,
                model_name,
                exc,
            )
            return {
                **state,
                "latency_ms": latency_ms,
                "llm_error": str(exc),
                "response": None,
            }

    # -------------------------------------------------------------------------
    # Node 3: update
    # Called by LangGraph as the "update_node" on success path.
    # Confirms reservation, updates health, logs request.
    # -------------------------------------------------------------------------
    async def update(self, state: dict) -> dict:
        """
        LangGraph node: confirm quota reservation, update health, log request.
        Called only on the success path.
        """
        pool = await self._get_pool()
        reservation_id = UUID(state["reservation_id"])
        model_id = UUID(state["selected_model_id"])
        provider_id = UUID(state["selected_provider_id"])
        actual_tokens = (state.get("prompt_tokens") or 0) + (state.get("completion_tokens") or 0)
        if actual_tokens == 0:
            actual_tokens = state.get("estimated_tokens", 500)

        await res_module.confirm(pool, reservation_id, actual_tokens)
        await health_module.update_success(pool, model_id, state.get("latency_ms", 0))
        await log_module.log_request(
            pool,
            request_uuid=UUID(state["request_uuid"]),
            provider_id=provider_id,
            model_id=model_id,
            provider_name=state["selected_provider"],
            model_name=state["selected_model"],
            tier=state["selected_tier"],
            status="success",
            attempt=state.get("attempt", 1),
            prompt_tokens=state.get("prompt_tokens"),
            completion_tokens=state.get("completion_tokens"),
            latency_ms=state.get("latency_ms"),
            http_status=200,
        )
        return state

    # -------------------------------------------------------------------------
    # Node 4: handle_failure
    # Called by LangGraph on the failure path (conditional edge).
    # Releases reservation, updates health, logs failure, adds model to exclusion.
    # -------------------------------------------------------------------------
    async def handle_failure(self, state: dict) -> dict:
        """
        LangGraph node: release quota, mark health failure, log it, and
        add the failed model to the exclusion list for retry.
        """
        pool = await self._get_pool()

        if state.get("reservation_id"):
            await res_module.release(pool, UUID(state["reservation_id"]))

        if state.get("selected_model_id"):
            model_id = UUID(state["selected_model_id"])
            await health_module.update_failure(pool, model_id)
            await log_module.log_request(
                pool,
                request_uuid=UUID(state["request_uuid"]),
                provider_id=UUID(state["selected_provider_id"]),
                model_id=model_id,
                provider_name=state.get("selected_provider", "unknown"),
                model_name=state.get("selected_model", "unknown"),
                tier=state.get("selected_tier", "unknown"),
                status="failure",
                attempt=state.get("attempt", 1),
                latency_ms=state.get("latency_ms"),
                error_message=state.get("llm_error"),
                http_status=500,
            )

        failed_models = list(state.get("failed_models", []))
        if state.get("selected_model_id") and state["selected_model_id"] not in failed_models:
            failed_models.append(state["selected_model_id"])

        return {
            **state,
            "failed_models": failed_models,
            "attempt": state.get("attempt", 1) + 1,
            "selected_model": None,
            "selected_provider": None,
            "selected_model_id": None,
            "selected_provider_id": None,
            "reservation_id": None,
        }

    # -------------------------------------------------------------------------
    # LLM client factory
    # Maps provider_name → LangChain BaseChatModel with the correct API key.
    # -------------------------------------------------------------------------
    def _get_llm_client(
        self,
        provider_name: str,
        model_name: str,
        base_url: str,
    ) -> BaseChatModel:
        """
        Return (and cache) the LangChain LLM client for a given provider/model.
        """
        cache_key = f"{provider_name}::{model_name}"
        if cache_key in self._llm_cache:
            return self._llm_cache[cache_key]

        llm = self._build_llm_client(provider_name, model_name, base_url)
        self._llm_cache[cache_key] = llm
        return llm

    def _build_llm_client(
        self,
        provider_name: str,
        model_name: str,
        base_url: str,
    ) -> BaseChatModel:
        """Build a fresh LangChain LLM client for the given provider."""

        if provider_name == "gemini":
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model=model_name,
                google_api_key=os.environ["GEMINI_API_KEY"],
            )

        elif provider_name == "groq":
            from langchain_groq import ChatGroq
            return ChatGroq(
                model=model_name,
                groq_api_key=os.environ["GROQ_API_KEY"],
            )

        elif provider_name == "openrouter":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=model_name,
                base_url="https://openrouter.ai/api/v1",
                api_key=os.environ["OPENROUTER_API_KEY"],
            )

        elif provider_name == "mistral":
            from langchain_mistralai import ChatMistralAI
            return ChatMistralAI(
                model=model_name,
                mistral_api_key=os.environ["MISTRAL_API_KEY"],
            )

        elif provider_name == "cerebras":
            from langchain_cerebras import ChatCerebras
            return ChatCerebras(
                model=model_name,
                cerebras_api_key=os.environ["CEREBRAS_API_KEY"],
            )

        elif provider_name == "openai":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=model_name,
                api_key=os.environ["OPENAI_API_KEY"],
            )

        elif provider_name == "cohere":
            from langchain_cohere import ChatCohere
            return ChatCohere(
                model=model_name,
                cohere_api_key=os.environ["COHERE_API_KEY"],
            )

        elif provider_name == "cloudflare":
            from langchain_openai import ChatOpenAI
            cf_account_id = os.environ["CF_ACCOUNT_ID"]
            cf_api_token = os.environ["CF_API_TOKEN"]
            return ChatOpenAI(
                model=model_name,
                base_url=f"https://api.cloudflare.com/client/v4/accounts/{cf_account_id}/ai/v1",
                api_key=cf_api_token,
            )

        elif provider_name == "local":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=model_name,
                base_url=base_url or "http://127.0.0.1:8080/v1",
                api_key="local",  # llama.cpp doesn't require a real key
            )

        else:
            raise ValueError(f"Unknown provider: {provider_name!r}")
