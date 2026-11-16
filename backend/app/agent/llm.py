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
    model: str = ""  # the model that actually answered (may be the fallback)


class LLMError(Exception):
    pass


class ChatModel(Protocol):
    async def chat(
        self, model: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> LLMReply: ...


class OpenAICompatibleLLM:
    """Chat client with retries and an optional fallback model.

    Per call: up to 3 attempts on the main model (timeouts, connection errors, 429, 5xx),
    then, if LLM_FALLBACK_MODEL is set, up to 2 on the fallback. 401/402/403 are not
    retried: they need the user (bad key, no credits).
    """

    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        self._client = AsyncOpenAI(
            base_url=base_url or settings.LLM_BASE_URL,
            api_key=api_key or settings.llm_api_key or "missing",
            timeout=settings.LLM_CALL_TIMEOUT_S,
            max_retries=0,
        )
        # Models that rejected `reasoning_effort`; we stop sending it to them.
        self._no_effort: set[str] = set()

    async def _once(
        self, model: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> LLMReply:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": settings.LLM_TEMPERATURE,
            "max_tokens": settings.LLM_MAX_TOKENS,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        if settings.LLM_REASONING_EFFORT and model not in self._no_effort:
            kwargs["reasoning_effort"] = settings.LLM_REASONING_EFFORT
        start = time.perf_counter()
        try:
            resp = await self._client.chat.completions.create(**kwargs)
        except APIStatusError as e:
            if e.status_code in (400, 422) and "reasoning_effort" in kwargs:
                self._no_effort.add(model)
                kwargs.pop("reasoning_effort")
                resp = await self._client.chat.completions.create(**kwargs)
            else:
                raise
        latency = int((time.perf_counter() - start) * 1000)
        if not resp.choices:
            raise LLMError("The AI model returned an empty answer.")
        msg = resp.choices[0].message
        calls = [
            ToolCall(id=c.id, name=c.function.name, arguments=c.function.arguments or "{}")
            for c in (msg.tool_calls or [])
            if getattr(c, "function", None) is not None
        ]
        raw: dict[str, Any] = {"role": "assistant", "content": msg.content or ""}
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
            model=model,
        )

    async def chat(
        self, model: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> LLMReply:
        plan = [(model, 3)]
        if settings.LLM_FALLBACK_MODEL and settings.LLM_FALLBACK_MODEL != model:
            plan.append((settings.LLM_FALLBACK_MODEL, 2))
        last = "unknown error"
        for candidate, attempts in plan:
            for attempt in range(attempts):
                try:
                    return await self._once(candidate, messages, tools)
                except (APITimeoutError, APIConnectionError) as e:
                    last = f"{type(e).__name__}"
                except APIStatusError as e:
                    code = e.status_code
                    if code == 401:
                        raise LLMError(
                            "The AI provider rejected the API key (401). Set a valid "
                            "LLM_API_KEY (or HF_TOKEN) in .env and restart the worker."
                        ) from e
                    if code == 402:
                        raise LLMError(
                            "The AI provider account is out of credits (402). Add credits "
                            "or switch provider in .env."
                        ) from e
                    if code == 403:
                        raise LLMError(
                            "The AI provider refused the request (403): the key lacks "
                            "permission for this model."
                        ) from e
                    if code == 429 or code >= 500:
                        last = f"HTTP {code}"
                    else:
                        # 400/404/413...: retrying the same request cannot help, but the
                        # fallback model might accept it (e.g. a larger context window).
                        last = f"HTTP {code}"
                        logger.warning("llm rejected request model=%s status=%s", candidate, code)
                        break
                logger.warning(
                    "llm call failed model=%s attempt=%s (%s)", candidate, attempt + 1, last
                )
                await asyncio.sleep(min(8.0, 1.5 * (attempt + 1)))
        raise LLMError(
            f"The AI provider kept failing ({last}) after several retries. "
            "Nothing was lost; try again in a minute."
        )
