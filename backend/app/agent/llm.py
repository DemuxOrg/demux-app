"""OpenAI-compatible chat client with tool calling, plus usage and cost accounting.

Works with any endpoint that speaks `/chat/completions` with `tools` (default: the
Hugging Face router). Never logs prompts or responses; callers get them back.
"""

import asyncio
import functools
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import yaml
from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)

PRICES_FILE = Path(__file__).with_name("prices.yaml")


@functools.cache
def _prices() -> dict[str, Any]:
    return yaml.safe_load(PRICES_FILE.read_text())


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    table = _prices()
    price = table["models"].get(model) or table["default"]
    return (input_tokens * price["input"] + output_tokens * price["output"]) / 1_000_000


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str  # raw JSON text from the model


@dataclass
class LLMReply:
    content: str | None
    tool_calls: list[ToolCall]
    input_tokens: int
    output_tokens: int
    latency_ms: int
    raw_message: dict[str, Any] = field(default_factory=dict)  # to append to the history


class LLMError(Exception):
    pass


class ChatModel(Protocol):
    async def chat(
        self, model: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> LLMReply: ...


class OpenAICompatibleLLM:
    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        self._client = AsyncOpenAI(
            base_url=base_url or settings.LLM_BASE_URL,
            api_key=api_key or settings.llm_api_key or "missing",
            timeout=settings.LLM_CALL_TIMEOUT_S,
            max_retries=0,
        )

    async def chat(
        self, model: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> LLMReply:
        last_exc: Exception | None = None
        for attempt in range(2):  # one retry on timeout / 5xx / connection error
            start = time.perf_counter()
            try:
                resp = await self._client.chat.completions.create(
                    model=model,
                    messages=messages,  # type: ignore[arg-type]
                    tools=tools or None,  # type: ignore[arg-type]
                    tool_choice="auto" if tools else None,  # type: ignore[arg-type]
                    temperature=settings.LLM_TEMPERATURE,
                    max_tokens=settings.LLM_MAX_TOKENS,
                )
            except (APITimeoutError, APIConnectionError) as e:
                last_exc = e
            except APIStatusError as e:
                if e.status_code >= 500 or e.status_code == 429:
                    last_exc = e
                    await asyncio.sleep(3 if e.status_code == 429 else 1)
                else:
                    raise LLMError(f"LLM request rejected ({e.status_code})") from e
            else:
                latency = int((time.perf_counter() - start) * 1000)
                if not resp.choices:
                    raise LLMError("LLM returned no choices")
                msg = resp.choices[0].message
                calls = [
                    ToolCall(id=c.id, name=c.function.name, arguments=c.function.arguments or "{}")
                    for c in (msg.tool_calls or [])
                    if getattr(c, "function", None) is not None
                ]
                raw: dict[str, Any] = {"role": "assistant", "content": msg.content or ""}
                reasoning = getattr(msg, "reasoning_content", None)
                if reasoning:
                    raw["reasoning_content"] = reasoning
                if calls:
                    raw["tool_calls"] = [
                        {
                            "id": c.id,
                            "type": "function",
                            "function": {"name": c.name, "arguments": c.arguments},
                        }
                        for c in calls
                    ]
                usage = resp.usage
                return LLMReply(
                    content=msg.content,
                    tool_calls=calls,
                    input_tokens=usage.prompt_tokens if usage else 0,
                    output_tokens=usage.completion_tokens if usage else 0,
                    latency_ms=latency,
                    raw_message=raw,
                )
            logger.warning("llm call failed (attempt %s), retrying", attempt + 1)
        raise LLMError(f"LLM call failed after retry: {type(last_exc).__name__}")
