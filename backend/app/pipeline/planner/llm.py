"""Thin LLM client for the planner: OpenAI SDK against the Hugging Face router.

Never logs prompts or responses (CLAUDE.md): callers get them back in `LLMResponse`.
"""

import copy
import json
import time
from dataclasses import dataclass
from typing import Any

from openai import BadRequestError, OpenAI

from app.core.config import settings
from app.pipeline.planner.models import Schema, Usage

ROUTER_URL = "https://router.huggingface.co/v1"


@dataclass
class LLMConfig:
    model: str
    provider: str
    thinking: bool
    temperature: float
    max_tokens: int

    @classmethod
    def from_settings(cls) -> "LLMConfig":
        return cls(
            model=settings.PLANNER_MODEL,
            provider=settings.PLANNER_PROVIDER,
            thinking=settings.PLANNER_THINKING,
            temperature=settings.PLANNER_TEMPERATURE,
            max_tokens=settings.PLANNER_MAX_TOKENS,
        )


@dataclass
class LLMResponse:
    content: str
    usage: Usage
    latency_ms: int
    mode: str  # "json_schema" or "json_object" (fallback)


def strict_json_schema(model: type[Schema] = Schema) -> dict[str, Any]:
    """JSON schema for strict structured output: refs inlined, every property required,
    `additionalProperties: false` everywhere (optionals are nullable instead)."""
    raw = model.model_json_schema()
    defs = raw.pop("$defs", {})

    def walk(node: Any) -> Any:
        if isinstance(node, list):
            return [walk(n) for n in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            return walk(copy.deepcopy(defs[node["$ref"].rsplit("/", 1)[-1]]))
        out = {k: walk(v) for k, v in node.items() if k not in ("title", "default")}
        if out.get("type") == "object" and "properties" in out:
            out["required"] = list(out["properties"])
            out["additionalProperties"] = False
        return out

    return walk(raw)


def _client() -> OpenAI:
    return OpenAI(base_url=ROUTER_URL, api_key=settings.HF_TOKEN, timeout=900, max_retries=4)


def complete(messages: list[dict[str, str]], config: LLMConfig) -> LLMResponse:
    """One chat completion that should return a JSON `Schema`.

    `messages[0]` is the system prompt. Tries `json_schema` structured output; if the
    provider rejects it, falls back to `json_object` with the JSON schema appended to the
    system prompt, and records the mode used.
    """
    schema = strict_json_schema()
    kwargs: dict[str, Any] = {
        "model": f"{config.model}:{config.provider}",
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "extra_body": {"chat_template_kwargs": {"enable_thinking": config.thinking}},
    }
    client = _client()
    start = time.perf_counter()
    mode = "json_schema"
    try:
        resp = client.chat.completions.create(
            messages=messages,
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "Schema", "strict": True, "schema": schema},
            },
            **kwargs,
        )
    except BadRequestError:
        mode = "json_object"
        fallback = [dict(m) for m in messages]
        fallback[0]["content"] += (
            "\n\nRespond with a single JSON object matching this JSON schema:\n"
            + json.dumps(schema)
        )
        resp = client.chat.completions.create(
            messages=fallback, response_format={"type": "json_object"}, **kwargs
        )
    latency_ms = int((time.perf_counter() - start) * 1000)
    usage = Usage(
        input_tokens=resp.usage.prompt_tokens if resp.usage else 0,
        output_tokens=resp.usage.completion_tokens if resp.usage else 0,
    )
    return LLMResponse(
        content=resp.choices[0].message.content or "",
        usage=usage,
        latency_ms=latency_ms,
        mode=mode,
    )
