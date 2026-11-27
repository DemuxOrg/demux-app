"""OpenAI-compatible chat client with tool calling, plus usage and cost accounting.

Works with any endpoint that speaks `/chat/completions` with `tools` (default: the
Hugging Face router). Never logs prompts or responses; callers get them back.

Metering: `MeteredLLM` wraps any chat model, prices every call from `prices.yaml` and
writes one `llm_calls` row per call (tokens, the unit prices used, cost, latency,
status) into the scope set with `usage_scope()` (run, workspace, user, DB session
factory) and `usage_phase()` (design, batch, app, edit, seed). Without a scope (CLI,
eval) nothing is written. The cost on the reply is the exact amount stored on the row,
so run totals added from it always equal the sum of their calls.
"""

import asyncio
import contextlib
import functools
import logging
import time
import uuid
from collections.abc import Iterator
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse

import yaml
from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)

PRICES_FILE = Path(__file__).with_name("prices.yaml")


@functools.cache
def _prices() -> dict[str, Any]:
    return yaml.safe_load(PRICES_FILE.read_text())


@dataclass(frozen=True)
class Price:
    """USD per million tokens. `cached_input` defaults to `input` when not listed."""

    input: Decimal
    cached_input: Decimal
    output: Decimal


def price_for(model: str) -> Price:
    table = _prices()
    p = table["models"].get(model) or table["default"]
    inp = Decimal(str(p["input"]))
    return Price(inp, Decimal(str(p.get("cached_input", p["input"]))), Decimal(str(p["output"])))


def priced_cost(
    price: Price, input_tokens: int, cached_input_tokens: int, output_tokens: int
) -> Decimal:
    """Cost of one call in USD, rounded to the 6 decimals stored in the database."""
    cached = min(max(cached_input_tokens, 0), input_tokens)
    total = (
        (input_tokens - cached) * price.input
        + cached * price.cached_input
        + output_tokens * price.output
    ) / 1_000_000
    return total.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def cost_usd(
    model: str, input_tokens: int, output_tokens: int, cached_input_tokens: int = 0
) -> float:
    return float(priced_cost(price_for(model), input_tokens, cached_input_tokens, output_tokens))


def provider_of(model: str) -> str:
    """`Qwen/Qwen3.8-27B:nebius` -> `nebius`; no suffix -> the endpoint's host."""
    if ":" in model:
        return model.rsplit(":", 1)[1]
    return urlparse(settings.LLM_BASE_URL).hostname or "unknown"


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
    cached_input_tokens: int = 0  # part of input_tokens served from the provider's cache
    cost_usd: float | None = None  # set by MeteredLLM: exactly what was recorded
    truncated: bool = False  # the answer stopped at the max_tokens limit


@dataclass(frozen=True)
class CallOptions:
    """Per-call overrides of the LLM_* settings (the interface designer writes long
    answers, slowly). `None` keeps the setting; `fallback_model=""` means no fallback."""

    max_tokens: int | None = None
    timeout_s: float | None = None
    temperature: float | None = None
    reasoning_effort: str | None = None
    fallback_model: str | None = None


class LLMError(Exception):
    def __init__(self, message: str, code: str = "llm_error"):
        super().__init__(message)
        self.code = code


class ChatModel(Protocol):
    async def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        options: CallOptions | None = None,
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
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        opts: CallOptions,
    ) -> LLMReply:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": settings.LLM_TEMPERATURE
            if opts.temperature is None
            else opts.temperature,
            "max_tokens": opts.max_tokens or settings.LLM_MAX_TOKENS,
        }
        if opts.timeout_s:
            kwargs["timeout"] = opts.timeout_s
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        effort = (
            settings.LLM_REASONING_EFFORT
            if opts.reasoning_effort is None
            else opts.reasoning_effort
        )
        if effort and model not in self._no_effort:
            kwargs["reasoning_effort"] = effort
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
            raise LLMError("The AI model returned an empty answer.", "empty_answer")
        choice = resp.choices[0]
        msg = choice.message
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
        details = getattr(usage, "prompt_tokens_details", None) if usage else None
        return LLMReply(
            content=msg.content,
            tool_calls=calls,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            latency_ms=latency,
            raw_message=raw,
            model=model,
            cached_input_tokens=(getattr(details, "cached_tokens", None) or 0) if details else 0,
            truncated=choice.finish_reason == "length",
        )

    async def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        options: CallOptions | None = None,
    ) -> LLMReply:
        opts = options or CallOptions()
        fallback = (
            settings.LLM_FALLBACK_MODEL if opts.fallback_model is None else opts.fallback_model
        )
        plan = [(model, 3)]
        if fallback and fallback != model:
            plan.append((fallback, 2))
        last = "unknown error"
        for candidate, attempts in plan:
            for attempt in range(attempts):
                try:
                    return await self._once(candidate, messages, tools, opts)
                except (APITimeoutError, APIConnectionError) as e:
                    last = "timeout" if isinstance(e, APITimeoutError) else "connection"
                except APIStatusError as e:
                    code = e.status_code
                    if code == 401:
                        raise LLMError(
                            "The AI provider rejected the API key (401). Set a valid "
                            "LLM_API_KEY (or HF_TOKEN) in .env and restart the worker.",
                            "http_401",
                        ) from e
                    if code == 402:
                        raise LLMError(
                            "The AI provider account is out of credits (402). Add credits "
                            "or switch provider in .env.",
                            "http_402",
                        ) from e
                    if code == 403:
                        raise LLMError(
                            "The AI provider refused the request (403): the key lacks "
                            "permission for this model.",
                            "http_403",
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
            "Nothing was lost; try again in a minute.",
            last.replace("HTTP ", "http_"),
        )


# ------------------------------------------------------------------ metering


@dataclass(frozen=True)
class UsageScope:
    """Who an LLM call is billed to. `session_factory=None` records nothing."""

    session_factory: Any = None  # async_sessionmaker; opens its own short transaction
    user_id: uuid.UUID | None = None
    workspace_id: uuid.UUID | None = None
    run_id: uuid.UUID | None = None
    phase: str = ""


_scope: ContextVar[UsageScope | None] = ContextVar("llm_usage_scope", default=None)


def current_scope() -> UsageScope:
    return _scope.get() or UsageScope()


# Agent phase names -> llm_calls.phase.
_PHASES = {"process": "batch"}


@contextlib.contextmanager
def usage_scope(**values: Any) -> Iterator[None]:
    """Bill the LLM calls made inside this block (and tasks started in it) to `values`."""
    token = _scope.set(replace(current_scope(), **values))
    try:
        yield
    finally:
        _scope.reset(token)


@contextlib.contextmanager
def usage_phase(phase: str) -> Iterator[None]:
    with usage_scope(phase=_PHASES.get(phase, phase)):
        yield


async def _record(scope: UsageScope, **row: Any) -> None:
    if scope.session_factory is None:
        return
    from app.models.usage import LLMCall

    try:
        async with scope.session_factory() as s:
            s.add(
                LLMCall(
                    run_id=scope.run_id,
                    workspace_id=scope.workspace_id,
                    user_id=scope.user_id,
                    phase=scope.phase or "unknown",
                    **row,
                )
            )
            await s.commit()
    except Exception:  # noqa: BLE001 - accounting must never fail the run
        logger.exception("could not record llm call run=%s", scope.run_id)


class MeteredLLM:
    """Wraps a chat model: prices each call and records it in `llm_calls`."""

    def __init__(self, inner: ChatModel):
        self.inner = inner

    async def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        options: CallOptions | None = None,
    ) -> LLMReply:
        scope = current_scope()
        start = time.perf_counter()
        try:
            reply = (
                await self.inner.chat(model, messages, tools, options)
                if options is not None
                else await self.inner.chat(model, messages, tools)
            )
        except LLMError as e:
            price = price_for(model)
            await _record(
                scope,
                model=model,
                provider=provider_of(model),
                input_tokens=0,
                cached_input_tokens=0,
                output_tokens=0,
                input_price=price.input,
                cached_input_price=price.cached_input,
                output_price=price.output,
                cost_usd=Decimal(0),
                latency_ms=int((time.perf_counter() - start) * 1000),
                status="error",
                error_code=e.code,
            )
            raise
        used = reply.model or model
        price = price_for(used)
        cost = priced_cost(
            price, reply.input_tokens, reply.cached_input_tokens, reply.output_tokens
        )
        await _record(
            scope,
            model=used,
            provider=provider_of(used),
            input_tokens=reply.input_tokens,
            cached_input_tokens=reply.cached_input_tokens,
            output_tokens=reply.output_tokens,
            input_price=price.input,
            cached_input_price=price.cached_input,
            output_price=price.output,
            cost_usd=cost,
            latency_ms=reply.latency_ms,
            status="ok",
            error_code=None,
        )
        reply.cost_usd = float(cost)
        return reply
