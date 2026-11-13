"""Build / sync / edit orchestration (build spec §6).

Flows only use the `RunContext` (state, mailbox, persister) and a chat model, so the
same code runs in the worker (Postgres), the CLI and the eval (memory).
"""

import asyncio
import html
import logging
from dataclasses import dataclass
from datetime import timedelta

from app.agent import prompts
from app.agent.context import RunContext
from app.agent.default_app import DEFAULT_APP
from app.agent.llm import ChatModel
from app.agent.loop import PhaseFailed, run_agent
from app.agent.tools import tools_for
from app.mail.base import MailboxError, ReconnectRequired, Thread
from app.mail.clean import clean_message

logger = logging.getLogger(__name__)

NEW_BODY_CHARS = 4000
OLD_BODY_CHARS = 500


class CannotBuild(Exception):
    """The design phase decided the request cannot be served from email."""


@dataclass
class FlowConfig:
    llm: ChatModel
    build_model: str
    sync_model: str
    batch_threads: int = 8
    inline_max_chars: int = 120_000


async def _event(ctx: RunContext, phase: str, label: str) -> None:
    import time

    await ctx.persister.add_event({"t": time.time(), "phase": phase, "tool": None, "label": label})


def _count_label(data: dict) -> str:
    parts = [f"{len(recs)} {t.replace('_', ' ')}" for t, recs in data.items()]
    return ", ".join(parts) if parts else "no records"


# ------------------------------------------------------------------ mail collection


async def _thread_ids(ctx: RunContext, query: str, after, limit: int) -> list[str]:
    finder = getattr(ctx.mailbox, "search_ids", None)
    if finder is not None:
        return await finder(query, max_results=limit, after=after)
    return [s.thread_id for s in await ctx.mailbox.search(query, max_results=limit, after=after)]


async def collect_threads(ctx: RunContext, queries: list[str], after, limit: int) -> list[Thread]:
    ids: list[str] = []
    for q in queries:
        for tid in await _thread_ids(ctx, q, after, limit):
            if tid not in ids:
                ids.append(tid)

    async def get(tid: str) -> Thread | None:
        try:
            return await ctx.mailbox.get_thread(tid)
        except ReconnectRequired:
            raise
        except MailboxError:
            return None

    threads = [t for t in await asyncio.gather(*(get(t) for t in ids)) if t and t.messages]
    return threads


def _batch_input(ctx: RunContext, threads: list[Thread], new_ids: set[str], note: str = "") -> str:
    block, compacted = prompts.data_block(ctx.state.data, ctx_inline_max(ctx))
    parts = [f"<guide>\n{ctx.state.guide}\n</guide>"]
    data_note = (
        "\n(The data was compacted to ids + first 4 fields; use read_records for details.)"
        if compacted
        else ""
    )
    parts.append(f"<data>\n{block}\n</data>{data_note}")
    lines = ["<threads>"]
    for t in threads:
        ctx.known_threads.add(t.thread_id)
        lines.append(f'  <thread id="{t.thread_id}">')
        for m in t.messages:
            ctx.seen_messages[m.message_id] = t.thread_id
            is_new = m.message_id in new_ids
            body = clean_message(m).body[: NEW_BODY_CHARS if is_new else OLD_BODY_CHARS]
            att = f" attachments: {', '.join(m.attachments)}" if m.attachments else ""
            lines.append(
                f'    <message id="{m.message_id}" date="{m.date:%Y-%m-%dT%H:%M:%SZ}" '
                f'from="{html.escape(m.sender, quote=True)}" new="{str(is_new).lower()}">'
                f"Subject: {m.subject}\n{body}{att}</message>"
            )
        lines.append("  </thread>")
    lines.append("</threads>")
    parts.append("\n".join(lines))
    if note:
        parts.append(note)
    return "\n\n".join(parts)


def ctx_inline_max(ctx: RunContext) -> int:
    return ctx.inline_max_chars


async def process_threads(
    ctx: RunContext,
    cfg: FlowConfig,
    threads: list[Thread],
    new_ids: set[str],
    *,
    phase_label: str,
    note: str = "",
) -> list[str]:
    """Run the process-batch phase over `threads` (sorted oldest → newest), sequentially."""
    threads = sorted(threads, key=lambda t: t.messages[-1].date)
    size = max(1, cfg.batch_threads)
    batches = [threads[i : i + size] for i in range(0, len(threads), size)]
    summaries: list[str] = []
    for i, batch in enumerate(batches, 1):
        await _event(ctx, "process", f"{phase_label} (batch {i} of {len(batches)})")
        ok = False
        for attempt in range(2):
            ctx.phase = "process"
            try:
                result = await run_agent(
                    llm=cfg.llm,
                    model=cfg.sync_model,
                    system=prompts.PROCESS,
                    user=_batch_input(ctx, batch, new_ids, note),
                    tools=tools_for("process"),
                    ctx=ctx,
                    max_steps=15,
                )
                if result.summary and result.summary.strip().lower() != "no changes":
                    summaries.append(result.summary)
                ok = True
                break
            except PhaseFailed as e:
                logger.warning("batch %s failed (attempt %s): %s", i, attempt + 1, e)
        if not ok:
            await _event(ctx, "process", f"Skipped batch {i} after two failures")
        pairs = [(m.message_id, t.thread_id) for t in batch for m in t.messages]
        await ctx.persister.mark_processed(pairs)
    return summaries


# ------------------------------------------------------------------ build


async def build(ctx: RunContext, cfg: FlowConfig) -> str:
    await ctx.persister.snapshot()

    # 1. design
    ctx.phase = "design"
    await _event(ctx, "design", "Understanding your request")
    system = prompts.DESIGN.replace("{max_threads}", str(ctx.max_build_threads))
    result = await run_agent(
        llm=cfg.llm,
        model=cfg.build_model,
        system=system,
        user=prompts.design_input(ctx.state.prompt, ctx.now, ctx.lookback_days),
        tools=tools_for("design"),
        ctx=ctx,
        max_steps=30,
    )
    summary = (result.summary or "").strip()
    if summary.upper().startswith("CANNOT_BUILD"):
        raise CannotBuild(summary.split(":", 1)[-1].strip() or "This can't be built from email.")
    if not ctx.state.guide.strip():
        raise PhaseFailed("design ended without a guide")
    if not ctx.state.queries:
        raise PhaseFailed("design ended without searches")

    # 2. backfill
    await _event(ctx, "process", "Collecting matching emails")
    threads = await collect_threads(ctx, ctx.state.queries, ctx.window_start, ctx.max_build_threads)
    threads.sort(key=lambda t: t.messages[-1].date, reverse=True)
    dropped = max(0, len(threads) - ctx.max_build_threads)
    threads = threads[: ctx.max_build_threads]
    if dropped:
        await _event(
            ctx, "process", f"Kept the newest {len(threads)} threads, {dropped} older dropped"
        )
    await _event(ctx, "process", f"Found {len(threads)} matching threads")
    new_ids = {m.message_id for t in threads for m in t.messages}
    await process_threads(ctx, cfg, threads, new_ids, phase_label="Reading your emails")

    # 3. app
    await build_app(ctx, cfg)

    ctx.state.last_synced_at = ctx.now
    await ctx.persister.save_synced(ctx.state)
    counts = f"Built from {len(threads)} threads: {_count_label(ctx.state.data)}."
    return f"{counts} {summary}"[:300]


async def build_app(ctx: RunContext, cfg: FlowConfig) -> None:
    ctx.phase = "app"
    ctx.app_written = False
    await _event(ctx, "app", "Building the interface")
    try:
        await run_agent(
            llm=cfg.llm,
            model=cfg.build_model,
            system=prompts.APP,
            user=prompts.app_input(
                ctx.state.prompt, ctx.state.guide, ctx.state.data, ctx_inline_max(ctx)
            ),
            tools=tools_for("app"),
            ctx=ctx,
            max_steps=12,
        )
    except PhaseFailed as e:
        logger.warning("app phase failed: %s", e)
    if not ctx.app_written:
        ctx.state.app_html = DEFAULT_APP
        await ctx.persister.save_app(ctx.state)
        await _event(ctx, "app", "Used the default table view (ask in chat to change it)")


# ------------------------------------------------------------------ sync


async def sync(ctx: RunContext, cfg: FlowConfig) -> str:
    queries = ctx.state.queries
    if not queries:
        return "No searches configured"
    after = (
        ctx.state.last_synced_at - timedelta(hours=1)
        if ctx.state.last_synced_at
        else ctx.window_start
    )
    after = max(after, ctx.window_start)
    threads = await collect_threads(ctx, queries, after, ctx.max_build_threads)
    processed = await ctx.persister.processed_ids()
    new_ids = {m.message_id for t in threads for m in t.messages if m.message_id not in processed}
    if not new_ids:
        ctx.state.last_synced_at = ctx.now
        await ctx.persister.save_synced(ctx.state)
        return "No new emails"
    await ctx.persister.snapshot()
    affected = [t for t in threads if any(m.message_id in new_ids for m in t.messages)]
    await _event(ctx, "process", f"{len(new_ids)} new emails in {len(affected)} threads")
    summaries = await process_threads(ctx, cfg, affected, new_ids, phase_label="Reading new emails")
    ctx.state.last_synced_at = ctx.now
    await ctx.persister.save_synced(ctx.state)
    return ("; ".join(summaries) or "No changes")[:300]


# ------------------------------------------------------------------ edit

BACKFILL_NOTE = (
    "Note: this is a re-read of emails already processed, because the guide changed. "
    "Fill in new fields and fix records according to the current guide. Update existing "
    "records (same ids) rather than creating duplicates."
)


async def edit(ctx: RunContext, cfg: FlowConfig, message: str, recent: list[str]) -> str:
    await ctx.persister.snapshot()
    try:
        ctx.phase = "edit"
        await _event(ctx, "edit", "Working on your request")
        for recs in ctx.state.data.values():
            for rec in recs.values():
                for s in rec.get("_sources", []):
                    ctx.known_threads.add(s["thread_id"])
        result = await run_agent(
            llm=cfg.llm,
            model=cfg.build_model,
            system=prompts.EDIT,
            user=prompts.edit_input(
                message,
                ctx.state.prompt,
                ctx.state.guide,
                ctx.state.queries,
                _with_thread_ids(ctx.state.data),
                ctx.state.app_html,
                recent,
                ctx_inline_max(ctx),
            ),
            tools=tools_for("edit"),
            ctx=ctx,
            max_steps=30,
        )
        summary = result.summary or "Done."
        if ctx.backfill_requested:
            thread_ids = await ctx.persister.processed_thread_ids()
            await _event(ctx, "process", f"Re-reading {len(thread_ids)} threads")
            threads = []
            for tid in thread_ids:
                try:
                    threads.append(await ctx.mailbox.get_thread(tid))
                except MailboxError:
                    continue
            # New queries may match threads not processed yet: include them too.
            extra = await collect_threads(
                ctx, ctx.state.queries, ctx.window_start, ctx.max_build_threads
            )
            known = {t.thread_id for t in threads}
            threads += [t for t in extra if t.thread_id not in known]
            all_ids = {m.message_id for t in threads for m in t.messages}
            await process_threads(
                ctx, cfg, threads, all_ids, phase_label="Re-reading emails", note=BACKFILL_NOTE
            )
        return summary
    except Exception:
        await ctx.persister.restore_snapshot()
        raise


def _with_thread_ids(data: dict) -> dict:
    """Data for the edit prompt: public fields plus `thread_ids` so the agent can re-read
    the source emails of a record it needs to fix."""
    out: dict = {}
    for t, recs in data.items():
        out[t] = {}
        for rid, rec in recs.items():
            item = {k: v for k, v in rec.items() if not k.startswith("_")}
            tids = list(dict.fromkeys(s["thread_id"] for s in rec.get("_sources", [])))
            if tids:
                item["source_thread_ids"] = tids
            out[t][rid] = item
    return out
