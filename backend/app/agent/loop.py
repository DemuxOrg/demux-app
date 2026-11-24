"""The agent loop (build spec §5.2).

Chat completions with tools; every tool call in an assistant message is executed in
order and its result appended; repeat until `finish` or `max_steps`. Tool errors go back
to the model; three consecutive errors from the same tool fail the phase. Older
`read_thread` results are trimmed (8 most recent kept in full). Usage is added to the run
after every call (the persister enforces budgets). One event per tool call.
"""

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.agent.context import BudgetExceeded, RunContext
from app.agent.llm import ChatModel, cost_usd, usage_phase
from app.agent.tools import Tool, ToolError, parse_args
from app.core.config import Env, settings
from app.mail.base import ReconnectRequired

logger = logging.getLogger(__name__)

KEEP_THREADS = 8
TRANSCRIPT_DIR = Path(__file__).resolve().parents[2] / ".runs"


class PhaseFailed(Exception):
    pass


@dataclass
class AgentResult:
    finished: bool
    summary: str | None
    steps: int
    error: str | None = None


def _trim_threads(messages: list[dict[str, Any]], thread_msg_idx: list[int]) -> None:
    for idx in thread_msg_idx[:-KEEP_THREADS]:
        msg = messages[idx]
        if not msg.get("_trimmed"):
            tid = msg.get("_thread_id", "?")
            msg["content"] = f"[thread {tid} already read, content dropped]"
            msg["_trimmed"] = True


def _text_summary(content: str | None) -> str | None:
    """A text-only final answer; some models write the finish arguments as JSON text."""
    text = (content or "").strip()
    if text.startswith("{"):
        try:
            value = json.loads(text).get("summary")
            if isinstance(value, str):
                return value
        except (ValueError, AttributeError):
            pass
    return text or None


def _wire(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{k: v for k, v in m.items() if not k.startswith("_")} for m in messages]


def _transcript(ctx: RunContext, record: dict[str, Any]) -> None:
    if not (settings.AGENT_DEBUG_TRANSCRIPTS and settings.ENV == Env.DEV):
        return
    TRANSCRIPT_DIR.mkdir(exist_ok=True)
    with (TRANSCRIPT_DIR / f"{ctx.run_id}.jsonl").open("a") as f:
        f.write(json.dumps(record, default=str) + "\n")


async def run_agent(
    *,
    llm: ChatModel,
    model: str,
    system: str,
    user: str,
    tools: list[Tool],
    ctx: RunContext,
    max_steps: int,
    done_when: Callable[[RunContext], bool] | None = None,
    text_ends_after: int | None = None,
) -> AgentResult:
    """Some models answer in plain text instead of calling `finish`.

    `done_when`: the phase's real goal. If it holds when the model stops calling tools
    or runs out of steps, the phase counts as finished.
    `text_ends_after`: after this many "call tools" reminders, another text-only reply
    ends the phase (for phases where doing nothing is a valid outcome).
    """
    by_name = {t.name: t for t in tools}
    schemas = [t.schema() for t in tools]
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    _transcript(ctx, {"phase": ctx.phase, "messages": messages})
    thread_idx: list[int] = []
    last_error_tool: str | None = None
    error_streak = 0
    ctx.finish_summary = None
    out_of_steps_sent = False
    reminders = 0
    step = 0

    while True:
        if step >= max_steps:
            if done_when is not None and done_when(ctx):
                return AgentResult(finished=True, summary=ctx.finish_summary, steps=step)
            if out_of_steps_sent:
                raise PhaseFailed(f"{ctx.phase}: ran out of steps without calling finish")
            out_of_steps_sent = True
            messages.append({"role": "user", "content": "You are out of steps. Call finish now."})
        step += 1
        with usage_phase(ctx.phase):
            reply = await llm.chat(model, _wire(messages), schemas)
        cost = (
            reply.cost_usd
            if reply.cost_usd is not None
            else cost_usd(
                reply.model or model,
                reply.input_tokens,
                reply.output_tokens,
                reply.cached_input_tokens,
            )
        )
        logger.info(
            "llm call run=%s phase=%s step=%s in=%s out=%s calls=%s ms=%s",
            ctx.run_id,
            ctx.phase,
            step,
            reply.input_tokens,
            reply.output_tokens,
            len(reply.tool_calls),
            reply.latency_ms,
        )
        await ctx.persister.add_usage(reply.input_tokens, reply.output_tokens, cost)
        messages.append(dict(reply.raw_message))
        _transcript(ctx, {"step": step, "assistant": reply.raw_message})

        if not reply.tool_calls:
            if done_when is not None and done_when(ctx):
                return AgentResult(finished=True, summary=_text_summary(reply.content), steps=step)
            if text_ends_after is not None and reminders >= text_ends_after:
                return AgentResult(finished=True, summary=ctx.finish_summary, steps=step)
            reminders += 1
            messages.append(
                {
                    "role": "user",
                    "content": "Continue by calling tools. When you are done, call finish.",
                }
            )
            continue

        finished = False
        for call in reply.tool_calls:
            if finished:
                # Calls after finish are not executed but need a result for well-formed history.
                messages.append(
                    {"role": "tool", "tool_call_id": call.id, "content": '{"skipped": true}'}
                )
                continue
            tool = by_name.get(call.name)
            label: str | None = None
            try:
                if tool is None:
                    raise ToolError(f"unknown tool '{call.name}'; available: {', '.join(by_name)}")
                args = parse_args(call.arguments)
                output = await tool.handler(ctx, args)
                # A failed app check is feedback, not a tool error: max_steps bounds it.
                result, label, failed = output.result, output.label, False
            except (ReconnectRequired, BudgetExceeded):
                raise
            except ToolError as e:
                result, failed = {"error": str(e)}, True
            if failed:
                error_streak = error_streak + 1 if last_error_tool == call.name else 1
                last_error_tool = call.name
                if error_streak >= 3:
                    raise PhaseFailed(f"{ctx.phase}: tool {call.name} failed 3 times in a row")
            else:
                error_streak, last_error_tool = 0, None

            content = json.dumps(result, ensure_ascii=False, default=str)
            tool_msg: dict[str, Any] = {"role": "tool", "tool_call_id": call.id, "content": content}
            if call.name == "read_thread" and not failed:
                tool_msg["_thread_id"] = result.get("thread_id")
                thread_idx.append(len(messages))
            messages.append(tool_msg)
            _transcript(ctx, {"tool": call.name, "result": content[:20000]})
            if label:
                await ctx.persister.add_event(
                    {"t": time.time(), "phase": ctx.phase, "tool": call.name, "label": label}
                )
            if call.name == "finish" and not failed:
                finished = True
        _trim_threads(messages, thread_idx)
        if finished:
            return AgentResult(finished=True, summary=ctx.finish_summary, steps=step)
