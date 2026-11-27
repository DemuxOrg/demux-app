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
from app.agent.appcheck import check_app
from app.agent.context import RunContext
from app.agent.default_app import DEFAULT_APP
from app.agent.designer import Designer, designer_from_settings
from app.agent.llm import ChatModel, LLMError
from app.agent.loop import PhaseFailed, run_agent
from app.agent.tools import tools_for
from app.mail.base import MailboxError, ReconnectRequired, Thread
from app.mail.clean import clean_message

logger = logging.getLogger(__name__)

NEW_BODY_CHARS = 3000
OLD_BODY_CHARS = 400
THREAD_MAX_MESSAGES = 10


class CannotBuild(Exception):
    """The design phase decided the request cannot be served from email."""


@dataclass
class FlowConfig:
    llm: ChatModel
    build_model: str
    sync_model: str
    batch_threads: int = 6
    inline_max_chars: int = 120_000
    batch_max_chars: int = 45_000
    process_concurrency: int = 8
    # Designs and writes every interface (UI_MODEL); None: the same chat model as "ui".
    designer: Designer | None = None

    def __post_init__(self) -> None:
        if self.designer is None:
            self.designer = Designer(llm=self.llm, model="ui")

    @classmethod
    def from_settings(cls, llm: ChatModel) -> "FlowConfig":
        from app.core.config import settings

        return cls(
            llm=llm,
            build_model=settings.BUILD_MODEL,
            sync_model=settings.SYNC_MODEL,
            batch_threads=settings.BATCH_THREADS,
            inline_max_chars=settings.DATA_INLINE_MAX_CHARS,
            batch_max_chars=settings.BATCH_MAX_CHARS,
            process_concurrency=settings.PROCESS_CONCURRENCY,
            designer=designer_from_settings(llm),
        )


async def _event(ctx: RunContext, phase: str, label: str, **extra: int) -> None:
    """One progress event. `extra` carries structured progress (`done`, `total` threads)
    for the build screen; the label is what the activity log shows."""
    import time

    await ctx.persister.add_event(
        {"t": time.time(), "phase": phase, "tool": None, "label": label, **extra}
    )


def _count_label(data: dict) -> str:
    parts = [f"{len(recs)} {t.replace('_', ' ')}" for t, recs in data.items()]
    return ", ".join(parts) if parts else "no records"


# ------------------------------------------------------------------ mail collection


async def _thread_ids(ctx: RunContext, query: str, after, limit: int) -> list[str]:
    finder = getattr(ctx.mailbox, "search_ids", None)
    if finder is not None:
        return await finder(query, max_results=limit, after=after)
    return [s.thread_id for s in await ctx.mailbox.search(query, max_results=limit, after=after)]


async def _union_ids(ctx: RunContext, queries: list[str], after, limit: int) -> list[str]:
    """The newest `limit` threads matching any query. One combined Gmail search when the
    mailbox can do it (so only the kept threads are fetched), else one search per query."""
    union = getattr(ctx.mailbox, "search_ids_any", None)
    if union is not None and len(queries) > 1:
        try:
            return await union(queries, max_results=limit, after=after)
        except MailboxError:
            logger.info("combined search rejected, searching each query run=%s", ctx.run_id)
    found = await asyncio.gather(*(_thread_ids(ctx, q, after, limit) for q in queries))
    return list(dict.fromkeys(tid for group in found for tid in group))


async def collect_threads(ctx: RunContext, queries: list[str], after, limit: int) -> list[Thread]:
    ids = await _union_ids(ctx, queries, after, limit)

    async def get(tid: str) -> Thread | None:
        try:
            return await ctx.mailbox.get_thread(tid)
        except ReconnectRequired:
            raise
        except MailboxError:
            return None

    threads = [t for t in await asyncio.gather(*(get(t) for t in ids)) if t and t.messages]
    return threads


def _thread_block(ctx: RunContext, t: Thread, new_ids: set[str]) -> str:
    """One <thread> element. Registers its messages as seen (citable) by the agent."""
    ctx.known_threads.add(t.thread_id)
    shown = t.messages
    if len(shown) > THREAD_MAX_MESSAGES:  # very long threads: first + most recent
        shown = [shown[0], *shown[-(THREAD_MAX_MESSAGES - 1) :]]
    lines = [f'  <thread id="{t.thread_id}">']
    for m in shown:
        ctx.seen_messages[m.message_id] = t.thread_id
        ctx.message_dates[m.message_id] = m.date
        is_new = m.message_id in new_ids
        body = clean_message(m).body[: NEW_BODY_CHARS if is_new else OLD_BODY_CHARS]
        att = f" attachments: {', '.join(m.attachments)}" if m.attachments else ""
        lines.append(
            f'    <message id="{m.message_id}" date="{m.date:%Y-%m-%dT%H:%M:%SZ}" '
            f'from="{html.escape(m.sender, quote=True)}" new="{str(is_new).lower()}">'
            f"Subject: {m.subject}\n{body}{att}</message>"
        )
    lines.append("  </thread>")
    return "\n".join(lines)


def _batch_input(ctx: RunContext, blocks: list[str], note: str = "") -> str:
    block, compacted = prompts.data_block(ctx.state.data, ctx.inline_max_chars)
    parts = [f"<guide>\n{ctx.state.guide}\n</guide>"]
    data_note = (
        "\n(The data was compacted to ids + first 4 fields; use read_records for details.)"
        if compacted
        else ""
    )
    parts.append(f"<data>\n{block}\n</data>{data_note}")
    parts.append("<threads>\n" + "\n".join(blocks) + "\n</threads>")
    if note:
        parts.append(note)
    return "\n\n".join(parts)


def _make_batches(
    ctx: RunContext, cfg: FlowConfig, threads: list[Thread], new_ids: set[str]
) -> list[tuple[list[Thread], list[str]]]:
    """Split into batches bounded by thread count and by text size (context safety)."""
    batches: list[tuple[list[Thread], list[str]]] = []
    cur_threads: list[Thread] = []
    cur_blocks: list[str] = []
    size = 0
    for t in threads:
        block = _thread_block(ctx, t, new_ids)
        if cur_threads and (
            len(cur_threads) >= max(1, cfg.batch_threads) or size + len(block) > cfg.batch_max_chars
        ):
            batches.append((cur_threads, cur_blocks))
            cur_threads, cur_blocks, size = [], [], 0
        cur_threads.append(t)
        cur_blocks.append(block)
        size += len(block)
    if cur_threads:
        batches.append((cur_threads, cur_blocks))
    return batches


async def process_threads(
    ctx: RunContext,
    cfg: FlowConfig,
    threads: list[Thread],
    new_ids: set[str],
    *,
    phase_label: str,
    note: str = "",
    concurrency: int = 1,
) -> list[str]:
    """Run the process-batch phase over `threads`, oldest → newest.

    `concurrency=1` (sync): batches run in order, each seeing the data left by the
    previous one. `concurrency>1` (build backfill): batches run in parallel for speed;
    stable record ids make saves to the same record merge, and the store's
    older-fill-only guard keeps "newer messages win" true whatever the finishing order.
    """
    threads = sorted(threads, key=lambda t: t.messages[-1].date)
    batches = _make_batches(ctx, cfg, threads, new_ids)
    parallel = concurrency > 1 and len(batches) > 1
    gate = asyncio.Semaphore(max(1, concurrency))
    done = 0
    threads_done = 0

    async def one(i: int, batch: list[Thread], blocks: list[str]) -> str | None:
        nonlocal done, threads_done
        summary = None
        async with gate:
            ok = False
            for attempt in range(2):
                child = ctx.child("process", older_fill_only=parallel)
                try:
                    result = await run_agent(
                        llm=cfg.llm,
                        model=cfg.sync_model,
                        system=prompts.PROCESS,
                        user=_batch_input(ctx, blocks, note),
                        tools=tools_for("process"),
                        ctx=child,
                        max_steps=8,
                        text_ends_after=1,
                    )
                    if result.summary and result.summary.strip().lower() != "no changes":
                        summary = result.summary
                    ok = True
                    break
                except PhaseFailed as e:
                    logger.warning("batch %s failed (attempt %s): %s", i, attempt + 1, e)
            if not ok:
                await _event(ctx, "process", f"Skipped batch {i} after two failures")
            pairs = [(m.message_id, t.thread_id) for t in batch for m in t.messages]
            await ctx.persister.mark_processed(pairs)
            done += 1
            threads_done += len(batch)
            await _event(
                ctx,
                "process",
                f"{phase_label} ({done} of {len(batches)} batches)",
                done=threads_done,
                total=len(threads),
            )
        return summary

    if not batches:
        return []
    await _event(
        ctx, "process", f"{phase_label} ({len(threads)} threads)", done=0, total=len(threads)
    )
    tasks = [asyncio.create_task(one(i, b, blocks)) for i, (b, blocks) in enumerate(batches, 1)]
    try:
        results = await asyncio.gather(*tasks)
    except BaseException:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
    return [r for r in results if r]


# ------------------------------------------------------------------ build


async def build(ctx: RunContext, cfg: FlowConfig) -> str:
    await ctx.persister.snapshot()

    # 1. design: a few turns, small sample (budgets enforced in the tools)
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
        max_steps=16,
        done_when=lambda c: bool(c.state.guide.strip() and c.state.queries),
    )
    summary = (result.summary or "").strip()
    if summary.upper().startswith("CANNOT_BUILD"):
        raise CannotBuild(summary.split(":", 1)[-1].strip() or "This can't be built from email.")
    if not ctx.state.guide.strip():
        raise PhaseFailed("design ended without a guide")
    if not ctx.state.queries:
        raise PhaseFailed("design ended without searches")

    # No questions were needed: mark it, so the build screen moves on.
    setup = await ctx.persister.get_setup()
    if "questions_state" not in setup:
        await ctx.persister.set_setup("questions_state", "none")

    # 2. the interface designer writes the app from the guide (and the user's answers)
    # while the emails are being read
    app_task = asyncio.create_task(build_app(ctx, cfg))
    try:
        await _event(ctx, "process", "Collecting matching emails")
        threads = await collect_threads(
            ctx, ctx.state.queries, ctx.window_start, ctx.max_build_threads
        )
        threads.sort(key=lambda t: t.messages[-1].date, reverse=True)
        dropped = max(0, len(threads) - ctx.max_build_threads)
        threads = threads[: ctx.max_build_threads]
        if dropped:
            await _event(
                ctx, "process", f"Kept the newest {len(threads)} threads, {dropped} older dropped"
            )
        new_ids = {m.message_id for t in threads for m in t.messages}
        await process_threads(
            ctx,
            cfg,
            threads,
            new_ids,
            phase_label="Reading your emails",
            concurrency=cfg.process_concurrency,
        )
    except BaseException:
        app_task.cancel()
        await asyncio.gather(app_task, return_exceptions=True)
        raise
    await app_task

    # 3. the app was checked before the data existed: check it against the real records
    if ctx.state.data and ctx.state.app_html and ctx.state.app_html != DEFAULT_APP:
        problems = await check_app(ctx.state.app_html, ctx.state.data)
        if problems:
            await _event(ctx, "app", "Adjusting the interface to your data")
            await build_app(ctx, cfg, problems=problems)

    ctx.state.last_synced_at = ctx.now
    await ctx.persister.save_synced(ctx.state)
    counts = f"Built from {len(threads)} threads: {_count_label(ctx.state.data)}."
    return f"{counts} {summary}"[:300]


async def build_app(ctx: RunContext, cfg: FlowConfig, problems: list[str] | None = None) -> None:
    """The interface designer designs the app (or, with `problems`, fixes the current one
    against the real data). If it cannot, the build still ends with the default app."""
    child = ctx.child("app")
    assert cfg.designer is not None
    try:
        left = await cfg.designer.design(child, problems)
    except LLMError as e:
        logger.warning("interface designer failed: %s", e.code)
        left = ["the interface designer is unavailable"]
    if left:
        logger.warning("interface not designed run=%s problems=%s", ctx.run_id, len(left))
    if not child.app_written and (problems or not ctx.state.app_html):
        ctx.state.app_html = DEFAULT_APP
        await ctx.persister.save_app(ctx.state)
        await _event(ctx, "app", "Used a simple list view (ask in chat to change it)")
    ctx.app_written = ctx.app_written or child.app_written


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
        ctx.designer = cfg.designer
        ctx.user_message = message
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
                ctx.inline_max_chars,
                config=ctx.state.config,
            ),
            tools=tools_for("edit"),
            ctx=ctx,
            max_steps=30,
        )
        summary = result.summary or "Done."
        if ctx.backfill_requested:
            thread_ids = await ctx.persister.processed_thread_ids()
            await _event(ctx, "process", f"Re-reading {len(thread_ids)} threads")

            async def get(tid: str) -> Thread | None:
                try:
                    return await ctx.mailbox.get_thread(tid)
                except ReconnectRequired:
                    raise
                except MailboxError:
                    return None

            fetched = await asyncio.gather(*(get(t) for t in thread_ids))
            threads = [t for t in fetched if t and t.messages]
            # New queries may match threads not processed yet: include them too.
            extra = await collect_threads(
                ctx, ctx.state.queries, ctx.window_start, ctx.max_build_threads
            )
            known = {t.thread_id for t in threads}
            threads += [t for t in extra if t.thread_id not in known]
            all_ids = {m.message_id for t in threads for m in t.messages}
            await process_threads(
                ctx,
                cfg,
                threads,
                all_ids,
                phase_label="Re-reading emails",
                note=BACKFILL_NOTE,
                concurrency=cfg.process_concurrency,
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
