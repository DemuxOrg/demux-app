"""Demo inbox: fill a test Gmail with synthetic threads for a prospect (/admin).

An admin describes a persona ("I'm a UGC creator; threads about brand deals"). The
worker then asks the LLM (DEMO_MODEL, default BUILD_MODEL: Qwen on the Hugging Face
router) for a plan of threads, writes each thread in parallel, and appends the messages
to the demo inbox over IMAP (`app/mail/demo_inbox.py`). The admin then connects that
inbox to Demux and builds workspaces on it.

Only counts and the admin's prompt are stored; the generated text lives in the demo
inbox alone. LLM calls are metered like any other (`llm_calls.phase = "seed"`), billed
to the admin who asked.
"""

import asyncio
import json
import logging
import random
import re
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.llm import ChatModel, LLMError, MeteredLLM, OpenAICompatibleLLM, usage_scope
from app.core.config import settings
from app.core.errors import AppError, ConflictError
from app.mail import demo_inbox
from app.mail.demo_inbox import DemoInboxError, DemoMessage
from app.models.admin import DemoSeed, DemoSeedStatus
from app.models.user import User

logger = logging.getLogger(__name__)

MIN_THREADS, MAX_THREADS = 3, 40
MAX_DAYS_AGO = 45  # well inside LOOKBACK_DAYS, so a build reads every thread
WRITE_CONCURRENCY = 4


class DemoNotConfiguredError(AppError):
    status_code = 503
    code = "demo_inbox_not_configured"


class GenerationError(Exception):
    pass


# ------------------------------------------------------------------ API side


async def create_seed(
    session: AsyncSession, admin: User, prompt: str, thread_count: int
) -> DemoSeed:
    if not settings.demo_inbox_configured:
        raise DemoNotConfiguredError(
            "The demo inbox is not configured: set TEST_GMAIL and "
            "TEST_GMAIL_PASSWORD in .env, then restart the backend and worker."
        )
    active = await session.scalar(
        select(func.count())
        .select_from(DemoSeed)
        .where(DemoSeed.status.in_((DemoSeedStatus.QUEUED, DemoSeedStatus.RUNNING)))
    )
    if active:
        raise ConflictError("Threads are already being written. Wait for them to finish.")
    seed = DemoSeed(
        created_by=admin.id,
        prompt=prompt.strip(),
        thread_count=thread_count,
        status=DemoSeedStatus.QUEUED,
    )
    session.add(seed)
    await session.flush()
    return seed


async def list_seeds(session: AsyncSession, limit: int = 20) -> list[DemoSeed]:
    return list(
        await session.scalars(select(DemoSeed).order_by(DemoSeed.created_at.desc()).limit(limit))
    )


async def remove_demo_threads() -> int:
    if not settings.demo_inbox_configured:
        raise DemoNotConfiguredError("The demo inbox is not configured.")
    try:
        return await asyncio.to_thread(
            demo_inbox.remove_demo_messages,
            settings.DEMO_IMAP_HOST,
            settings.TEST_GMAIL,
            settings.TEST_GMAIL_PASSWORD,
        )
    except DemoInboxError as e:
        raise AppError(str(e)) from e


# ------------------------------------------------------------------ worker side


async def claim_next(session: AsyncSession) -> DemoSeed | None:
    seed = await session.scalar(
        select(DemoSeed)
        .where(DemoSeed.status == DemoSeedStatus.QUEUED)
        .order_by(DemoSeed.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if seed is None:
        return None
    seed.status = DemoSeedStatus.RUNNING
    seed.started_at = datetime.now(UTC)
    await session.flush()
    return seed


async def fail_stale(session: AsyncSession) -> None:
    await session.execute(
        update(DemoSeed)
        .where(DemoSeed.status == DemoSeedStatus.RUNNING)
        .values(
            status=DemoSeedStatus.FAILED,
            error="Interrupted (worker restarted).",
            finished_at=func.now(),
        )
    )


PLAN_SYSTEM = """You design realistic, fictional email inboxes for product demos of Demux, \
an app that turns a Gmail inbox into structured workspaces (tables, boards, timelines).
Reply with one JSON object and nothing else."""

PLAN_USER = """The inbox owner: {persona}

Plan {n} email threads for this person's inbox, received over the last {max_days} days.
Make them the kind of threads this person really gets, with enough concrete detail that \
someone could track them in a table: names, companies, amounts, dates, statuses, \
deliverables. Vary the counterparts, stages and outcomes (new requests, negotiations, \
confirmed, paid, late, declined). Include 2 or 3 unrelated everyday threads (a receipt, \
a newsletter, a personal note) so the inbox feels real.

Use fictional people and companies with plausible email domains. Never use real brands \
or real people.

JSON shape:
{{"owner_name": "first and last name of the inbox owner",
  "threads": [{{"counterpart_name": "...", "counterpart_email": "name@company-domain.com",
               "company": "...", "topic": "one sentence: what happens in this thread",
               "messages": 1-5, "owner_replies": true|false, "days_ago": 1-{max_days}}}]}}"""

THREAD_SYSTEM = """You write one realistic email thread for a product demo. Plain text \
emails, natural tone, signatures where natural, concrete amounts, dates and deliverables. \
No markdown. Reply with one JSON object and nothing else."""

THREAD_USER = """Inbox owner: {owner_name} <{owner_email}> ({persona})
Counterpart: {counterpart_name} <{counterpart_email}> at {company}
What happens: {topic}
Messages in the thread: {messages} (the first one is from the counterpart{replies})
The thread starts {days_ago} days before today ({today}); write dates in the text \
consistent with that.

JSON shape:
{{"subject": "...",
  "messages": [{{"from": "counterpart" | "owner", "hours_after_previous": number,
                "body": "the full email text"}}]}}"""


def _json(text: str | None) -> dict[str, Any]:
    raw = (text or "").strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        raise GenerationError("The model did not return JSON.")
    try:
        value = json.loads(raw[start : end + 1])
    except json.JSONDecodeError as e:
        raise GenerationError("The model returned invalid JSON.") from e
    if not isinstance(value, dict):
        raise GenerationError("The model did not return a JSON object.")
    return value


async def _ask(llm: ChatModel, model: str, system: str, user: str) -> tuple[dict, float]:
    """One JSON answer; asks once more if the first one does not parse."""
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    cost = 0.0
    for attempt in range(2):
        reply = await llm.chat(model, messages, [])
        cost += reply.cost_usd or 0.0
        try:
            return _json(reply.content), cost
        except GenerationError:
            if attempt == 1:
                raise
            messages += [
                {"role": "assistant", "content": reply.content or ""},
                {"role": "user", "content": "That was not valid JSON. Reply with the JSON only."},
            ]
    raise GenerationError("unreachable")


def _clamp(value: Any, lo: float, hi: float, default: float) -> float:
    try:
        return max(lo, min(hi, float(value)))
    except (TypeError, ValueError):
        return default


def thread_messages(
    plan: dict[str, Any],
    written: dict[str, Any],
    owner_name: str,
    owner_email: str,
    now: datetime,
    rng: random.Random,
) -> list[DemoMessage]:
    """Turn one written thread into dated messages, oldest first, all before `now`."""
    subject = str(written.get("subject") or plan.get("topic") or "Hello")[:200]
    cp_name = str(plan.get("counterpart_name") or "Alex Morgan")
    cp_email = str(plan.get("counterpart_email") or "alex@example.com")
    if "@" not in cp_email:
        cp_email = "contact@example.com"
    days_ago = _clamp(plan.get("days_ago"), 1, MAX_DAYS_AGO, 7)
    date = (now - timedelta(days=days_ago)).replace(
        hour=rng.randint(8, 18), minute=rng.randint(0, 59), second=0, microsecond=0
    )
    out: list[DemoMessage] = []
    for i, m in enumerate(written.get("messages") or []):
        body = str((m or {}).get("body") or "").strip()
        if not body:
            continue
        if i:
            date += timedelta(hours=_clamp(m.get("hours_after_previous"), 0.2, 96, 20))
        if date > now - timedelta(minutes=5):
            break  # never in the future
        outgoing = i > 0 and str(m.get("from", "")).lower() == "owner"
        out.append(
            DemoMessage(
                from_name=owner_name if outgoing else cp_name,
                from_email=owner_email if outgoing else cp_email,
                to_name=cp_name if outgoing else owner_name,
                to_email=cp_email if outgoing else owner_email,
                subject=subject,
                body=body,
                date=date,
                outgoing=outgoing,
            )
        )
    # The newest incoming message of a recent thread stays unread, like a real inbox.
    if out and not out[-1].outgoing and now - out[-1].date < timedelta(days=2):
        out[-1].seen = False
    return out


async def generate_threads(
    llm: ChatModel,
    model: str,
    persona: str,
    n: int,
    owner_email: str,
    now: datetime,
    rng: random.Random | None = None,
) -> tuple[list[list[DemoMessage]], float]:
    rng = rng or random.Random()
    plan, cost = await _ask(
        llm, model, PLAN_SYSTEM, PLAN_USER.format(persona=persona, n=n, max_days=MAX_DAYS_AGO)
    )
    owner_name = str(plan.get("owner_name") or "Sam Taylor")
    plans = [p for p in (plan.get("threads") or []) if isinstance(p, dict)][:n]
    if not plans:
        raise GenerationError("The model planned no threads.")
    sem = asyncio.Semaphore(WRITE_CONCURRENCY)

    async def write(p: dict[str, Any]) -> tuple[list[DemoMessage], float]:
        async with sem:
            try:
                written, c = await _ask(
                    llm,
                    model,
                    THREAD_SYSTEM,
                    THREAD_USER.format(
                        owner_name=owner_name,
                        owner_email=owner_email,
                        persona=persona,
                        counterpart_name=p.get("counterpart_name", ""),
                        counterpart_email=p.get("counterpart_email", ""),
                        company=p.get("company", ""),
                        topic=p.get("topic", ""),
                        messages=int(_clamp(p.get("messages"), 1, 5, 2)),
                        replies=", then the owner replies" if p.get("owner_replies") else "",
                        days_ago=int(_clamp(p.get("days_ago"), 1, MAX_DAYS_AGO, 7)),
                        today=now.date().isoformat(),
                    ),
                )
            except GenerationError:
                return [], 0.0  # one bad thread does not sink the batch
            return thread_messages(p, written, owner_name, owner_email, now, rng), c

    results = await asyncio.gather(*(write(p) for p in plans))
    threads = [t for t, _ in results if t]
    cost += sum(c for _, c in results)
    if not threads:
        raise GenerationError("No thread could be written.")
    return threads, cost


async def execute_seed(
    seed_id: uuid.UUID,
    *,
    session_factory,
    llm: ChatModel | None = None,
    append=demo_inbox.append_threads,
    now: datetime | None = None,
) -> None:
    async with session_factory() as s:
        seed = await s.get(DemoSeed, seed_id)
        assert seed is not None
        prompt, n, admin_id = seed.prompt, seed.thread_count, seed.created_by

    metered = MeteredLLM(llm or OpenAICompatibleLLM())
    model = settings.DEMO_MODEL or settings.BUILD_MODEL
    status, error, threads_n, messages_n, cost = DemoSeedStatus.DONE, None, 0, 0, 0.0
    try:
        with usage_scope(session_factory=session_factory, user_id=admin_id, phase="seed"):
            threads, cost = await generate_threads(
                metered, model, prompt, n, settings.TEST_GMAIL, now or datetime.now(UTC)
            )
        messages_n = await asyncio.to_thread(
            append,
            settings.DEMO_IMAP_HOST,
            settings.TEST_GMAIL,
            settings.TEST_GMAIL_PASSWORD,
            threads,
            str(seed_id),
        )
        threads_n = len(threads)
    except (GenerationError, LLMError, DemoInboxError) as e:
        status, error = DemoSeedStatus.FAILED, str(e)
    except Exception as e:  # noqa: BLE001 - the worker must survive
        logger.exception("demo seed %s crashed", seed_id)
        status, error = DemoSeedStatus.FAILED, f"internal_error: {type(e).__name__}"

    async with session_factory() as s:
        await s.execute(
            update(DemoSeed)
            .where(DemoSeed.id == seed_id)
            .values(
                status=status,
                error=error,
                threads_created=threads_n,
                messages_created=messages_n,
                cost_usd=Decimal(str(round(cost, 6))),
                finished_at=datetime.now(UTC),
            )
        )
        await s.commit()
    logger.info(
        "demo seed %s status=%s threads=%s messages=%s cost=%.4f",
        seed_id,
        status.value,
        threads_n,
        messages_n,
        cost,
    )
