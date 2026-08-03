"""
router/chat_model.py
LangChain Custom BaseChatModel wrapper for the router graph.

Implements `with_structured_output` so agents can request Pydantic-parsed
responses routed transparently through the multi-provider router graph.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Type, Union

from langchain_core.callbacks.manager import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable, RunnableConfig
from pydantic import BaseModel, Field

from graph import run_graph_messages

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Structured-output wrapper Runnable
# ═══════════════════════════════════════════════════════════════════════════════

def _schema_to_instruction(schema_cls: Type[BaseModel]) -> str:
    """Build a concise JSON-schema instruction block for the system prompt."""
    schema = schema_cls.model_json_schema()
    # Remove verbose metadata to keep the prompt small
    schema.pop("title", None)
    schema.pop("description", None)
    schema_str = json.dumps(schema, indent=2)
    return (
        "You MUST respond with ONLY a valid JSON object (no markdown, no explanation, "
        "no code fences) that conforms to this JSON schema:\n"
        f"{schema_str}\n"
        "Respond with the JSON object ONLY."
    )


def _extract_json(text: str) -> str:
    """Extract JSON from LLM response, stripping markdown fences if present."""
    # Strip markdown ```json ... ``` fences
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    # Try to find raw JSON object
    # Find the first { and last }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text.strip()


class _StructuredOutputRunnable(Runnable):
    """
    Runnable that wraps a ChatRouter, injects JSON schema instructions,
    and parses the raw LLM text response into a Pydantic model.
    """

    def __init__(self, llm: ChatRouter, schema: Type[BaseModel]):
        self._llm = llm
        self._schema = schema
        self._instruction = _schema_to_instruction(schema)

    def _inject_schema(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """Prepend or amend system message with JSON schema instruction."""
        schema_msg = SystemMessage(content=self._instruction)
        if messages and isinstance(messages[0], SystemMessage):
            # Append instruction to existing system message
            combined = messages[0].content + "\n\n" + self._instruction
            return [SystemMessage(content=combined)] + list(messages[1:])
        return [schema_msg] + list(messages)

    def _parse(self, raw: str) -> BaseModel:
        """Parse raw text into the Pydantic schema, with lenient retry."""
        cleaned = _extract_json(raw)
        try:
            return self._schema.model_validate_json(cleaned)
        except Exception:
            # Try python json parse with strict=False (allows unescaped raw newlines/tabs inside strings)
            try:
                data = json.loads(cleaned, strict=False)
                return self._schema.model_validate(data)
            except Exception:
                # Fallback to json-repair for broken LLM syntax (unescaped quotes, missing commas)
                try:
                    from json_repair import repair_json
                    repaired = repair_json(cleaned)
                    data = json.loads(repaired, strict=False)
                    return self._schema.model_validate(data)
                except Exception as exc:
                    logger.error(
                        "Structured output parse failed for %s. raw=%s",
                        self._schema.__name__,
                        raw[:300],
                    )
                    raise ValueError(
                        f"Failed to parse LLM response into {self._schema.__name__}: {exc}"
                    ) from exc

    async def ainvoke(
        self,
        input: Any,
        config: Optional[RunnableConfig] = None,
        **kwargs: Any,
    ) -> BaseModel:
        # Input may be a list of messages or a dict (from a prompt template)
        if isinstance(input, list):
            messages = self._inject_schema(input)
        elif isinstance(input, dict):
            # LangChain prompt template will produce messages via the chain;
            # We need to invoke the prompt first if this is called standalone
            messages = self._inject_schema([])
        else:
            messages = self._inject_schema([])

        response: BaseMessage = await self._llm.ainvoke(messages, config, **kwargs)
        return self._parse(response.content)

    def invoke(
        self,
        input: Any,
        config: Optional[RunnableConfig] = None,
        **kwargs: Any,
    ) -> BaseModel:
        if isinstance(input, list):
            messages = self._inject_schema(input)
        else:
            messages = self._inject_schema([])

        response: BaseMessage = self._llm.invoke(messages, config, **kwargs)
        return self._parse(response.content)


# ═══════════════════════════════════════════════════════════════════════════════
# Structured chain builder: Prompt | StructuredLLM  →  Pydantic model
# ═══════════════════════════════════════════════════════════════════════════════

class _StructuredChainRunnable(Runnable):
    """
    When used in a LCEL chain like  `prompt | llm.with_structured_output(Schema)`,
    this Runnable receives the rendered PromptValue, injects the schema instruction,
    calls the router, and returns a parsed Pydantic model.
    """

    def __init__(self, llm: ChatRouter, schema: Type[BaseModel]):
        self._llm = llm
        self._schema = schema
        self._instruction = _schema_to_instruction(schema)

    def _inject_schema(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        schema_msg = SystemMessage(content=self._instruction)
        if messages and isinstance(messages[0], SystemMessage):
            combined = messages[0].content + "\n\n" + self._instruction
            return [SystemMessage(content=combined)] + list(messages[1:])
        return [schema_msg] + list(messages)

    def _parse(self, raw: str) -> BaseModel:
        cleaned = _extract_json(raw)
        try:
            return self._schema.model_validate_json(cleaned)
        except Exception:
            try:
                data = json.loads(cleaned, strict=False)
                return self._schema.model_validate(data)
            except Exception:
                try:
                    from json_repair import repair_json
                    repaired = repair_json(cleaned)
                    data = json.loads(repaired, strict=False)
                    return self._schema.model_validate(data)
                except Exception as exc:
                    logger.error(
                        "Structured output parse failed for %s. raw=%s",
                        self._schema.__name__,
                        raw[:300],
                    )
                    raise ValueError(
                        f"Failed to parse LLM response into {self._schema.__name__}: {exc}"
                    ) from exc

    async def ainvoke(
        self,
        input: Any,
        config: Optional[RunnableConfig] = None,
        **kwargs: Any,
    ) -> BaseModel:
        # Input can be PromptValue (from a prompt template in LCEL chain)
        from langchain_core.prompt_values import PromptValue
        if isinstance(input, PromptValue):
            messages = self._inject_schema(input.to_messages())
        elif isinstance(input, list):
            messages = self._inject_schema(input)
        else:
            messages = self._inject_schema([])

        response: BaseMessage = await self._llm.ainvoke(messages, config, **kwargs)
        return self._parse(response.content)

    def invoke(
        self,
        input: Any,
        config: Optional[RunnableConfig] = None,
        **kwargs: Any,
    ) -> BaseModel:
        from langchain_core.prompt_values import PromptValue
        if isinstance(input, PromptValue):
            messages = self._inject_schema(input.to_messages())
        elif isinstance(input, list):
            messages = self._inject_schema(input)
        else:
            messages = self._inject_schema([])

        response: BaseMessage = self._llm.invoke(messages, config, **kwargs)
        return self._parse(response.content)


# ═══════════════════════════════════════════════════════════════════════════════
# ChatRouter — main class
# ═══════════════════════════════════════════════════════════════════════════════

class ChatRouter(BaseChatModel):
    """
    Custom LangChain ChatModel that routes prompts dynamically across providers.
    Uses the underlying LangGraph router workflow (which handles database caching,
    health checks, quota verification, and automatic retries/failover).
    """

    default_task_type: str = Field(default="general")
    default_estimated_tokens: int = Field(default=500)
    default_required_tags: Optional[List[str]] = Field(default=None)

    @property
    def _llm_type(self) -> str:
        return "router-chat-model"

    # ── Structured output support ─────────────────────────────────────────────
    def with_structured_output(
        self,
        schema: Type[BaseModel],
        **kwargs: Any,
    ) -> Runnable:
        """
        Return a Runnable that routes through the router graph and parses
        the response into the given Pydantic schema.

        Works with LCEL chains:  prompt | llm.with_structured_output(Schema)
        """
        return _StructuredChainRunnable(self, schema)

    # ── invoke / ainvoke ──────────────────────────────────────────────────────

    async def ainvoke(
        self,
        input: Any,
        config: Optional[Any] = None,
        *,
        stop: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> BaseMessage:
        # Extract config parameter overrides if present in config["configurable"]
        configurable = config.get("configurable", {}) if config else {}
        task_type = configurable.get("task_type", self.default_task_type)
        estimated_tokens = configurable.get("estimated_tokens", self.default_estimated_tokens)
        required_tags = configurable.get("required_tags", self.default_required_tags)

        kwargs["task_type"] = task_type
        kwargs["estimated_tokens"] = estimated_tokens
        kwargs["required_tags"] = required_tags

        return await super().ainvoke(input, config, stop=stop, **kwargs)

    def invoke(
        self,
        input: Any,
        config: Optional[Any] = None,
        *,
        stop: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> BaseMessage:
        configurable = config.get("configurable", {}) if config else {}
        task_type = configurable.get("task_type", self.default_task_type)
        estimated_tokens = configurable.get("estimated_tokens", self.default_estimated_tokens)
        required_tags = configurable.get("required_tags", self.default_required_tags)

        kwargs["task_type"] = task_type
        kwargs["estimated_tokens"] = estimated_tokens
        kwargs["required_tags"] = required_tags

        return super().invoke(input, config, stop=stop, **kwargs)

    # ── Core generation ───────────────────────────────────────────────────────

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        task_type = kwargs.get("task_type", self.default_task_type)
        estimated_tokens = kwargs.get("estimated_tokens", self.default_estimated_tokens)
        required_tags = kwargs.get("required_tags", self.default_required_tags)

        # Execute routing graph with message list
        result = await run_graph_messages(
            messages=messages,
            task_type=task_type,
            estimated_tokens=estimated_tokens,
            required_tags=required_tags,
        )

        if result.get("error"):
            raise RuntimeError(f"ChatRouter failed to route request: {result['error']}")

        response_content = result.get("response") or ""

        # Populate response metadata
        token_usage = {}
        if result.get("prompt_tokens") is not None:
            token_usage["prompt_tokens"] = result["prompt_tokens"]
        if result.get("completion_tokens") is not None:
            token_usage["completion_tokens"] = result["completion_tokens"]

        ai_message = AIMessage(
            content=response_content,
            response_metadata={
                "model_name": result.get("selected_model"),
                "provider_name": result.get("selected_provider"),
                "latency_ms": result.get("latency_ms"),
                "token_usage": token_usage,
            },
        )

        return ChatResult(generations=[ChatGeneration(message=ai_message)])

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            # Already inside a running event loop, dispatch to thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                # Wrap agenerate call
                fut = pool.submit(
                    lambda: asyncio.run(
                        self._agenerate(messages, stop, **kwargs)
                    )
                )
                return fut.result()
        else:
            return loop.run_until_complete(
                self._agenerate(messages, stop, **kwargs)
            )
