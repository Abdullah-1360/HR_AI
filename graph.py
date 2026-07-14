"""
graph.py
LangGraph multi-provider routing graph.

Graph structure:
    START → router_node → llm_node → [conditional] → update_node → END
                 ↑                        |
                 └── handle_failure_node ←┘ (on llm failure, up to MAX_RETRIES)
                              ↓
                           fail_node → END (all retries exhausted)

RouterState carries the full context of a single request through the graph.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional, Annotated
from uuid import uuid4

from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict

from router import RouterNode
from router.db import get_pool, close_pool

logger = logging.getLogger(__name__)

MAX_RETRIES = 5


# =============================================================================
# State Definition
# =============================================================================

class RouterState(TypedDict):
    # --- Input ---
    messages: list[BaseMessage]          # conversation messages
    estimated_tokens: int                # pre-computed prompt token estimate
    task_type: str                       # "general" | "coding" | "reasoning"

    # --- Routing ---
    request_uuid: Optional[str]          # unique ID for this request
    selected_model: Optional[str]        # model_name chosen by router
    selected_provider: Optional[str]     # provider_name
    selected_model_id: Optional[str]     # UUID string
    selected_provider_id: Optional[str]  # UUID string
    selected_base_url: Optional[str]     # provider base URL
    selected_tier: Optional[str]         # tier of selected model
    reservation_id: Optional[str]        # quota reservation UUID
    failed_models: list[str]             # exclusion list for retry (UUIDs as str)
    attempt: int                         # current attempt number

    # --- Response ---
    response: Optional[str]             # final LLM response content
    prompt_tokens: Optional[int]
    completion_tokens: Optional[int]
    latency_ms: Optional[int]

    # --- Errors ---
    llm_error: Optional[str]            # error from LLM call
    error: Optional[str]                # fatal routing error


# =============================================================================
# Routing logic (conditional edges)
# =============================================================================

def after_llm(state: RouterState) -> str:
    """
    Conditional edge after llm_node:
      - LLM succeeded → 'update_node'
      - LLM failed + retries remaining → 'handle_failure_node'
      - LLM failed + retries exhausted → 'fail_node'
    """
    if state.get("llm_error") is None and state.get("response") is not None:
        return "update_node"
    elif state.get("attempt", 1) < MAX_RETRIES:
        return "handle_failure_node"
    else:
        return "fail_node"


def after_failure(state: RouterState) -> str:
    """
    Conditional edge after handle_failure_node:
      - Go back to router_node to try next model
      - Unless routing-level error (all tiers exhausted already)
    """
    if state.get("error"):
        return "fail_node"
    return "router_node"


def after_select(state: RouterState) -> str:
    """
    Conditional edge after router_node:
      - Fatal error (all tiers exhausted) → 'fail_node'
      - No reservation yet (SKIP LOCKED race) → 'router_node' (immediate retry)
      - Model selected successfully → 'llm_node'
    """
    if state.get("error"):
        return "fail_node"
    if not state.get("reservation_id"):
        return "router_node"   # quota race, try again
    return "llm_node"


# =============================================================================
# Graph assembly
# =============================================================================

def build_graph() -> tuple[any, RouterNode]:
    """Build and compile the LangGraph routing graph."""
    router = RouterNode()

    # Sync wrappers for LangGraph (which calls nodes synchronously in some modes)
    # We use async nodes here since LangGraph supports async natively
    workflow = StateGraph(RouterState)

    workflow.add_node("router_node",         router.select)
    workflow.add_node("llm_node",            router.call_llm)
    workflow.add_node("update_node",         router.update)
    workflow.add_node("handle_failure_node", router.handle_failure)
    workflow.add_node("fail_node",           _fail_node)

    # Edges
    workflow.add_edge(START, "router_node")
    workflow.add_conditional_edges("router_node", after_select, {
        "llm_node":     "llm_node",
        "router_node":  "router_node",
        "fail_node":    "fail_node",
    })
    workflow.add_conditional_edges("llm_node", after_llm, {
        "update_node":         "update_node",
        "handle_failure_node": "handle_failure_node",
        "fail_node":           "fail_node",
    })
    workflow.add_edge("update_node", END)
    workflow.add_conditional_edges("handle_failure_node", after_failure, {
        "router_node": "router_node",
        "fail_node":   "fail_node",
    })
    workflow.add_edge("fail_node", END)

    app = workflow.compile()
    return app, router


async def _fail_node(state: RouterState) -> RouterState:
    """Terminal failure node — logs and surfaces the error."""
    error = state.get("llm_error") or state.get("error") or "Unknown routing failure"
    logger.error(
        "Request FAILED after %d attempts. Last error: %s",
        state.get("attempt", 1),
        error,
    )
    return {**state, "error": error, "response": None}


# =============================================================================
# Public helper: run_graph
# =============================================================================

async def run_graph(
    user_message: str,
    task_type: str = "general",
    estimated_tokens: int = 500,
) -> dict:
    """
    High-level helper to run the routing graph with a single user message.
    Returns the final RouterState dict.
    """
    app, _ = build_graph()

    initial_state: RouterState = {
        "messages": [HumanMessage(content=user_message)],
        "estimated_tokens": estimated_tokens,
        "task_type": task_type,
        "request_uuid": str(uuid4()),
        "selected_model": None,
        "selected_provider": None,
        "selected_model_id": None,
        "selected_provider_id": None,
        "selected_base_url": None,
        "selected_tier": None,
        "reservation_id": None,
        "failed_models": [],
        "attempt": 1,
        "response": None,
        "prompt_tokens": None,
        "completion_tokens": None,
        "latency_ms": None,
        "llm_error": None,
        "error": None,
    }

    result = await app.ainvoke(initial_state)
    return result


# =============================================================================
# CLI entry point for quick testing
# =============================================================================

if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    load_dotenv()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    message = sys.argv[1] if len(sys.argv) > 1 else "Hello! What can you do?"

    async def main():
        result = await run_graph(message)
        if result.get("response"):
            print(f"\n✅ Response from {result['selected_provider']}/{result['selected_model']}:")
            print(result["response"])
        else:
            print(f"\n❌ Failed: {result.get('error')}")

    asyncio.run(main())
