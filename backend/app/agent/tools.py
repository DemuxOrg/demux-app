"""Agent tools: JSON schemas + implementations (build spec §5.3).

Each tool returns a `ToolOutput`: the result sent back to the model and a short, safe
event label (counts and record type names only, never email content or values).
`ToolError` is reported to the model as `{"error": ...}` so it can correct itself.
"""

import asyncio
import json
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.agent.appcheck import check_app
from app.agent.context import RunContext
from app.mail.base import MailboxError, ReconnectRequired
from app.mail.clean import clean_message
from app.services.store import DataError, apply_delete, apply_save, public_fields

MAX_GUIDE_CHARS = 6000
MAX_BODY_CHARS = 4000
# Design phase: a sample is enough. Small bodies and a hard cap keep it fast and cheap.
DESIGN_BODY_CHARS = 1200
DESIGN_MAX_MESSAGES = 4
DESIGN_MAX_READS = 10
DESIGN_MAX_SEARCHES = 8
EDIT_MAX_MESSAGES = 12
MAX_SUMMARY_CHARS = 300
SETUP_POLL_SECONDS = 1.5
MAX_QUESTIONS = 5
# Questions are about what the workspace tracks, never about its look (frontend/theme.md
# §7.10): those are the fixed, generic questions users found useless.
_LOOK_QUESTION = re.compile(
    r"\b(colou?rs?|palettes?|themes?|fonts?|dark mode|light mode|visual style)\b", re.I
)


class ToolError(Exception):
    pass


@dataclass
class ToolOutput:
    result: Any
    label: str | None = None


Handler = Callable[[RunContext, dict[str, Any]], Awaitable[ToolOutput]]


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Handler

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


def _plural(n: int, word: str) -> str:
    if n == 1:
        return f"{n} {word}"
    return f"{n} {word}{'es' if word.endswith(('s', 'sh', 'ch', 'x')) else 's'}"


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------------ mail


async def _search_mail(ctx: RunContext, args: dict[str, Any]) -> ToolOutput:
    query = str(args.get("query", "")).strip()
    if not query:
        raise ToolError("query is required")
    max_results = max(1, min(int(args.get("max_results", 25) or 25), 50))
    if ctx.phase == "design":
        ctx.design_searches += 1
        if ctx.design_searches > DESIGN_MAX_SEARCHES:
            raise ToolError("search budget used up: now call write_guide, set_queries and finish")
        max_results = min(max_results, 15)
    try:
        hits = await ctx.mailbox.search(
            query, max_results=max_results, after=ctx.window_start, before=None
        )
    except ReconnectRequired:
        raise
    except MailboxError as e:
        raise ToolError(f"search failed: {e}") from e
    for h in hits:
        ctx.known_threads.add(h.thread_id)
    return ToolOutput(
        {
            "count": len(hits),
            "threads": [
                {
                    "thread_id": h.thread_id,
                    "subject": h.subject,
                    "senders": h.senders,
                    "last_date": _iso(h.last_date),
                    "messages": h.message_count,
                    "snippet": h.snippet[:200],
                }
                for h in hits
            ],
        },
        "Searching mail",
    )


async def _read_thread(ctx: RunContext, args: dict[str, Any]) -> ToolOutput:
    thread_id = str(args.get("thread_id", ""))
    if thread_id not in ctx.known_threads:
        raise ToolError("unknown thread_id: only ids returned by search_mail or given in the input")
    try:
        thread = await ctx.mailbox.get_thread(thread_id)
    except ReconnectRequired:
        raise
    except MailboxError as e:
        raise ToolError(f"could not read thread: {e}") from e
    design = ctx.phase == "design"
    if design:
        ctx.design_reads += 1
        if ctx.design_reads > DESIGN_MAX_READS:
            raise ToolError(
                "read budget used up: you have a sample; now call write_guide, set_queries "
                "and finish"
            )
    body_cap = DESIGN_BODY_CHARS if design else MAX_BODY_CHARS
    shown = thread.messages
    limit = DESIGN_MAX_MESSAGES if design else EDIT_MAX_MESSAGES
    if len(shown) > limit:  # first message + the most recent ones
        shown = [shown[0], *shown[-(limit - 1) :]]
    messages = []
    for m in shown:
        c = clean_message(m)
        ctx.seen_messages[m.message_id] = thread_id
        ctx.message_dates[m.message_id] = m.date
        messages.append(
            {
                "message_id": m.message_id,
                "date": _iso(m.date),
                "from": m.sender,
                "to": m.to[:5],
                "subject": m.subject,
                "body": c.body[:body_cap],
                "attachments": m.attachments,
            }
        )
    result: dict[str, Any] = {"thread_id": thread_id, "messages": messages}
    if len(shown) < len(thread.messages):
        result["omitted_messages"] = len(thread.messages) - len(shown)
    return ToolOutput(result, "Reading a thread")


# ------------------------------------------------------------------ data


async def _read_records(ctx: RunContext, args: dict[str, Any]) -> ToolOutput:
    rtype = args.get("record_type")
    ids = args.get("ids")
    data = ctx.state.data
    types = [rtype] if rtype else list(data)
    out: dict[str, Any] = {}
    n = 0
    for t in types:
        if t not in data:
            raise ToolError(f"unknown record type '{t}'; existing: {', '.join(data) or 'none'}")
        for rid, rec in data[t].items():
            if ids and rid not in ids:
                continue
            if n >= 200:
                break
            item = public_fields(rec)
            item["_sources"] = len(rec.get("_sources", []))
            out.setdefault(t, {})[rid] = item
            n += 1
    return ToolOutput({"records": out, "returned": n}, "Reading records")


async def _save_records(ctx: RunContext, args: dict[str, Any]) -> ToolOutput:
    rtype = args.get("record_type")
    records = args.get("records")
    try:
        new, results, changes = apply_save(
            ctx.state.data,
            rtype,
            records,
            seen_messages=ctx.seen_messages,
            now=ctx.now,  # type: ignore[arg-type]
            message_dates=ctx.message_dates,
            older_fill_only=ctx.older_fill_only,
        )
    except DataError as e:
        raise ToolError(str(e)) from e
    ctx.state.data = new
    if changes:
        ctx.data_changed = True
    await ctx.persister.save_data(ctx.state, changes)
    created = sum(1 for r in results if r["status"] == "created")
    updated = sum(1 for r in results if r["status"] == "updated")
    parts = []
    if created:
        parts.append(f"{created} new")
    if updated:
        parts.append(f"{updated} updated")
    label = f"Saved {_plural(len(results), str(rtype) + ' record')}"
    if parts:
        label += f" ({', '.join(parts)})"
    return ToolOutput({"results": results}, label)


async def _delete_records(ctx: RunContext, args: dict[str, Any]) -> ToolOutput:
    rtype = str(args.get("record_type", ""))
    ids = args.get("ids")
    if not str(args.get("reason", "")).strip():
        raise ToolError("reason is required")
    try:
        new, deleted, changes = apply_delete(ctx.state.data, rtype, ids)  # type: ignore[arg-type]
    except DataError as e:
        raise ToolError(str(e)) from e
    ctx.state.data = new
    ctx.data_changed = True
    await ctx.persister.save_data(ctx.state, changes)
    return ToolOutput({"deleted": deleted}, f"Deleted {_plural(len(deleted), 'record')}")


# ------------------------------------------------------------------ guide / queries / app


def _above_learned(text: str) -> str:
    idx = re.search(r"^#\s*Learned\b", text, re.M)
    return (text[: idx.start()] if idx else text).strip()


async def _write_guide(ctx: RunContext, args: dict[str, Any]) -> ToolOutput:
    text = str(args.get("text", "")).strip()
    if not text:
        raise ToolError("text is required")
    if len(text) > MAX_GUIDE_CHARS:
        raise ToolError(f"guide is {len(text)} chars; the limit is {MAX_GUIDE_CHARS}")
    if ctx.phase == "process" and ctx.state.guide:
        if _above_learned(text) != _above_learned(ctx.state.guide):
            raise ToolError(
                "during sync you may only change the '# Learned' section; keep everything "
                "above it exactly as it is"
            )
    ctx.state.guide = text
    ctx.guide_changed = True
    await ctx.persister.save_guide(ctx.state)
    return ToolOutput({"ok": True}, "Updated the guide")


NAME_MAX_WORDS = 3
NAME_MAX_CHARS = 40


async def _set_name(ctx: RunContext, args: dict[str, Any]) -> ToolOutput:
    name = " ".join(str(args.get("name", "")).split()).strip(" \"'.,;:!?")
    if not name:
        raise ToolError("name is required")
    if len(name.split()) > NAME_MAX_WORDS or len(name) > NAME_MAX_CHARS:
        raise ToolError(
            f"use at most {NAME_MAX_WORDS} words and {NAME_MAX_CHARS} characters, "
            "e.g. 'Online Orders' or 'Job Applications'"
        )
    ctx.state.name = name
    await ctx.persister.save_name(ctx.state)
    return ToolOutput({"ok": True}, f"Named the workspace {name}")


async def _count(ctx: RunContext, query: str, limit: int) -> int:
    counter = getattr(ctx.mailbox, "search_ids", None)
    if counter is not None:
        return len(await counter(query, max_results=limit, after=ctx.window_start))
    return len(await ctx.mailbox.search(query, max_results=limit, after=ctx.window_start))


async def _set_queries(ctx: RunContext, args: dict[str, Any]) -> ToolOutput:
    queries = args.get("queries")
    if not isinstance(queries, list) or not 1 <= len(queries) <= 8:
        raise ToolError("queries must be a list of 1 to 8 Gmail search strings")
    queries = [str(q).strip() for q in queries if str(q).strip()]
    if not queries:
        raise ToolError("queries must not be empty")
    limit = ctx.max_build_threads + 1
    try:
        numbers = await asyncio.gather(*(_count(ctx, q, limit) for q in queries))
    except ReconnectRequired:
        raise
    except MailboxError as e:
        raise ToolError(f"a query failed: {e}") from e
    counts = [
        {"query": q, "threads": n if n < limit else f">{limit - 1}"}
        for q, n in zip(queries, numbers, strict=True)
    ]
    total = sum(c["threads"] if isinstance(c["threads"], int) else limit for c in counts)
    if total == 0 and ctx.phase == "design":
        raise ToolError(
            "these queries match no email, so nothing was saved. Reuse the terms of a "
            "search_mail query that returned threads; keep each query simple "
            "(a few words joined with OR, or from:<sender domain>)."
        )
    ctx.state.config = {**ctx.state.config, "queries": queries}
    await ctx.persister.save_config(ctx.state)
    return ToolOutput(
        {
            "saved": True,
            "counts": counts,
            "note": f"threads per query in the last {ctx.lookback_days} days "
            f"(overlaps not removed); target ≤ {ctx.max_build_threads} in total"
            + (
                ". Very few threads match: if the user probably has more relevant mail, "
                "call set_queries again with broader queries (plain words joined with OR)."
                if total < 5 and ctx.phase == "design"
                else ""
            ),
        },
        f"Watching {_plural(len(queries), 'search')} ({total} threads)",
    )


async def _write_app(ctx: RunContext, args: dict[str, Any]) -> ToolOutput:
    html = str(args.get("html", ""))
    if not html.strip():
        raise ToolError("html is required")
    problems = await check_app(html, ctx.state.data)
    if problems:
        return ToolOutput(
            {"ok": False, "problems": problems, "note": "The app was NOT saved. Fix and retry."},
            "App check failed, fixing",
        )
    ctx.state.app_html = html
    ctx.app_written = True
    await ctx.persister.save_app(ctx.state)
    return ToolOutput({"ok": True}, "Wrote the app")


async def wait_setup(ctx: RunContext, key: str) -> Any:
    """The user's answer under `key` (written by the setup API), or None after the wait."""
    deadline = time.monotonic() + max(0.0, ctx.setup_wait)
    while True:
        value = (await ctx.persister.get_setup()).get(key)
        if value or time.monotonic() >= deadline:
            return value
        await asyncio.sleep(SETUP_POLL_SECONDS)


def _clip(v: Any, n: int) -> str:
    return " ".join(str(v or "").split())[:n]


async def _ask_user(ctx: RunContext, args: dict[str, Any]) -> ToolOutput:
    if ctx.asked_user:
        raise ToolError("you already asked: ask_user can be called once")
    raw = args.get("questions")
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_QUESTIONS:
        raise ToolError(f"questions must be a list of 1 to {MAX_QUESTIONS} questions")
    items = []
    for i, q in enumerate(raw, 1):
        if not isinstance(q, dict):
            raise ToolError("each question is an object with question, options, recommended")
        options = [_clip(o, 80) for o in q.get("options") or [] if _clip(o, 80)]
        if not _clip(q.get("question"), 300) or not 2 <= len(options) <= 4:
            raise ToolError("each question needs text and 2 to 4 short options")
        if _LOOK_QUESTION.search(" ".join([str(q.get("question")), *options])):
            raise ToolError(
                "ask only about what the workspace should track or show first, never about "
                "colours, themes or visual style: drop that question"
            )
        rec = q.get("recommended", 0)
        rec = rec if isinstance(rec, int) and 0 <= rec < len(options) else 0
        items.append(
            {
                "id": f"q{i}",
                "question": _clip(q["question"], 300),
                "options": options,
                "recommended": rec,
            }
        )
    ctx.asked_user = True
    await ctx.persister.set_setup("questions", items)
    await ctx.persister.set_setup("questions_state", "asking")
    await ctx.persister.add_event(
        {"t": time.time(), "phase": "design", "tool": "ask_user",
         "label": f"Asked you {_plural(len(items), 'question')}"}
    )  # fmt: skip
    answers = await wait_setup(ctx, "answers")
    answered = isinstance(answers, dict) and bool(answers)
    pairs = []
    for it in items:
        given = _clip(answers.get(it["id"]), 300) if answered else ""
        pairs.append(
            {
                "question": it["question"],
                "answer": given or it["options"][it["recommended"]],
                "from": "user" if given else "recommended (no answer)",
            }
        )
    await ctx.persister.set_setup("questions_state", "answered" if answered else "timed_out")
    ctx.state.config["clarifications"] = [
        {"question": p["question"], "answer": p["answer"]} for p in pairs
    ]
    await ctx.persister.save_config(ctx.state)
    return ToolOutput(
        {
            "answers": pairs,
            "note": "Follow these answers and write them into the guide (Purpose, fields or "
            "What to ignore).",
        },
        "Got your answers" if answered else "Used the recommended answers",
    )


async def _request_backfill(ctx: RunContext, args: dict[str, Any]) -> ToolOutput:
    ctx.backfill_requested = True
    return ToolOutput({"ok": True}, "Scheduled a re-read of all emails")


async def _finish(ctx: RunContext, args: dict[str, Any]) -> ToolOutput:
    summary = str(args.get("summary", "")).strip()
    if not summary:
        raise ToolError("summary is required")
    if ctx.phase == "design" and not summary.upper().startswith("CANNOT_BUILD"):
        missing = [
            n
            for n, ok in (
                ("write_guide", ctx.state.guide.strip()),
                ("set_queries", ctx.state.queries),
            )
            if not ok
        ]
        if missing:
            raise ToolError(
                f"not done yet: call {' and '.join(missing)} before finish "
                "(or finish with 'CANNOT_BUILD: <reason>' if the request cannot be served)"
            )
    if ctx.phase == "app" and not ctx.app_written:
        raise ToolError("the app is not saved yet: call write_app until it returns ok")
    ctx.finish_summary = summary[:MAX_SUMMARY_CHARS]
    return ToolOutput({"ok": True}, None)


# ------------------------------------------------------------------ registry

_RECORD_ITEM = {
    "type": "object",
    "properties": {
        "id": {
            "type": "string",
            "description": "Stable lowercase slug [a-z0-9-], per the id rule.",
        },
        "fields": {
            "type": "object",
            "description": "Field values to set (shallow merge). null clears a field.",
            "additionalProperties": True,
        },
        "source_message_ids": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Ids of the messages these values come from (at least one).",
        },
    },
    "required": ["id", "fields", "source_message_ids"],
}

TOOLS: dict[str, Tool] = {
    t.name: t
    for t in [
        Tool(
            "search_mail",
            "Search the user's mailbox with Gmail search syntax. Limited to the lookback "
            "window. Returns thread summaries (id, subject, senders, date, snippet).",
            {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_results": {"type": "integer", "minimum": 1, "maximum": 50},
                },
                "required": ["query"],
            },
            _search_mail,
        ),
        Tool(
            "read_thread",
            "Read one thread: cleaned messages oldest first with ids, dates, senders, "
            "subject, body (≤4000 chars) and attachment names.",
            {
                "type": "object",
                "properties": {"thread_id": {"type": "string"}},
                "required": ["thread_id"],
            },
            _read_thread,
        ),
        Tool(
            "read_records",
            "Read existing records (all, one type, or specific ids).",
            {
                "type": "object",
                "properties": {
                    "record_type": {"type": "string"},
                    "ids": {"type": "array", "items": {"type": "string"}},
                },
            },
            _read_records,
        ),
        Tool(
            "save_records",
            "Create or update records of one type. Saving to an existing id updates it "
            "(shallow merge of fields). Every record must cite the messages it came from.",
            {
                "type": "object",
                "properties": {
                    "record_type": {"type": "string", "description": "snake_case type name"},
                    "records": {"type": "array", "items": _RECORD_ITEM},
                },
                "required": ["record_type", "records"],
            },
            _save_records,
        ),
        Tool(
            "delete_records",
            "Delete records (duplicates, or records created by mistake).",
            {
                "type": "object",
                "properties": {
                    "record_type": {"type": "string"},
                    "ids": {"type": "array", "items": {"type": "string"}},
                    "reason": {"type": "string"},
                },
                "required": ["record_type", "ids", "reason"],
            },
            _delete_records,
        ),
        Tool(
            "set_name",
            "Name the workspace: 1-3 words in Title Case, a noun phrase for what it tracks "
            "(e.g. 'Library Loans', 'Subscriptions', 'Travel Bookings'). No quotes or emoji.",
            {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
            _set_name,
        ),
        Tool(
            "write_guide",
            "Replace the guide (≤6000 chars). During sync, only the '# Learned' section may "
            "change.",
            {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
            _write_guide,
        ),
        Tool(
            "set_queries",
            "Set the 1-8 Gmail searches that define which mail belongs to this workspace. "
            "Returns how many threads each matches in the lookback window.",
            {
                "type": "object",
                "properties": {
                    "queries": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                        "maxItems": 8,
                    }
                },
                "required": ["queries"],
            },
            _set_queries,
        ),
        Tool(
            "write_app",
            "Write the app (one HTML fragment per the app contract). It is checked in a "
            "headless browser; problems are returned and the app is only saved when it passes.",
            {"type": "object", "properties": {"html": {"type": "string"}}, "required": ["html"]},
            _write_app,
        ),
        Tool(
            "ask_user",
            "Ask the user multiple-choice questions that fill the gaps in their request, "
            "once: one question per open point that changes the workspace (none for a "
            "precise request, up to 5 for a vague one). Waits for the answers (or uses your "
            "recommended options) and returns them.",
            {
                "type": "object",
                "properties": {
                    "questions": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": MAX_QUESTIONS,
                        "items": {
                            "type": "object",
                            "properties": {
                                "question": {
                                    "type": "string",
                                    "description": "Grounded in what you found, e.g. 'I found "
                                    "loans from three branches and two e-book apps. Should "
                                    "e-book loans count?'",
                                },
                                "options": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "minItems": 2,
                                    "maxItems": 4,
                                },
                                "recommended": {
                                    "type": "integer",
                                    "description": "Index of the option you recommend.",
                                },
                            },
                            "required": ["question", "options", "recommended"],
                        },
                    }
                },
                "required": ["questions"],
            },
            _ask_user,
        ),
        Tool(
            "request_backfill",
            "After this edit, re-process every email already in the workspace with the new "
            "guide (use when new information is needed for all records).",
            {"type": "object", "properties": {}},
            _request_backfill,
        ),
        Tool(
            "finish",
            "End this phase with a short, plain-language summary for the user (≤300 chars).",
            {
                "type": "object",
                "properties": {"summary": {"type": "string"}},
                "required": ["summary"],
            },
            _finish,
        ),
    ]
}

PHASE_TOOLS: dict[str, list[str]] = {
    "design": [
        "set_name",
        "search_mail",
        "ask_user",
        "read_thread",
        "write_guide",
        "set_queries",
        "finish",
    ],
    "process": [
        "read_thread",
        "read_records",
        "save_records",
        "delete_records",
        "write_guide",
        "finish",
    ],
    "app": ["read_records", "write_app", "finish"],
    "edit": [t for t in TOOLS if t != "ask_user"],
}


def tools_for(phase: str) -> list[Tool]:
    return [TOOLS[n] for n in PHASE_TOOLS[phase]]


def parse_args(raw: str) -> dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
    except json.JSONDecodeError as e:
        raise ToolError(f"arguments are not valid JSON: {e.msg}") from e
    if not isinstance(value, dict):
        raise ToolError("arguments must be a JSON object")
    return value
