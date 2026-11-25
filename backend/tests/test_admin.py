"""Admin: LLM call metering, access control, the privacy allowlist, the stats, the mailbox
counter and the demo inbox."""

import json
import random
import time
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import func, select

from app.agent.llm import LLMError, LLMReply, MeteredLLM, usage_scope
from app.core.config import Env, settings
from app.mail.demo_inbox import DEMO_HEADER, build_threads
from app.mail.fake import FakeMailbox
from app.main import app
from app.models import (
    AdminAudit,
    DemoSeed,
    DemoSeedStatus,
    LLMCall,
    MailboxDailyStat,
    ProcessedMessage,
    Run,
    RunKind,
    RunStatus,
    User,
    Workspace,
)
from app.services import demo, runs
from app.services.workspaces import create_workspace
from app.worker import count_mailboxes, execute_run
from tests.conftest import _make_user
from tests.helpers import SMALL_MAILBOX, dt
from tests.test_flows import build_llm

# Every field name an admin response may contain. A new field must be reviewed against
# the privacy rule (no email content, subjects, senders, record values, guide, app HTML)
# before it is added here.
ALLOWED_FIELDS = {
    # overview
    "days", "start", "end", "active_users", "total_users", "workspaces", "new_workspaces",
    "builds", "syncs", "edits", "input_tokens", "output_tokens", "cost_usd", "failed_runs",
    "finished_runs", "cost_by_phase", "cost_by_model", "tokens", "cost_per_user", "failures",
    "date", "key", "p50_usd", "p95_usd", "finished", "failed",
    # users
    "id", "email", "name", "created_at", "last_active_at", "emails_processed",
    "emails_received_per_day", "cost_7d", "cost_30d", "cost_total", "gmail_connected",
    "needs_reconnect", "user", "mailbox_daily", "count",
    # workspaces and runs
    "user_id", "prompt", "status", "last_synced_at", "record_count", "emails_per_day", "runs",
    "kind", "duration_s", "error_code", "run_id", "text", "workspace", "owner_email",
    "daily", "emails",
    # demo inbox (synthetic data written by admins; `error` is our own failure message)
    "configured", "inbox_email", "model", "seeds", "thread_count", "threads_created",
    "messages_created", "error", "finished_at", "removed",
    # evals: scores, statuses, versions, costs, and text from the committed synthetic
    # fixtures in backend/eval/agent/scenarios (labels, check specs and details, the
    # agent's questions on fixture mail), never a user's inbox
    "scenarios", "steps", "vague", "scenario_ids", "repeats", "progress_done",
    "progress_total", "commit", "branch", "agent_hash", "suite_hash", "build_model",
    "sync_model", "score", "spread", "parts", "retrieval", "coverage", "correctness",
    "clarification", "guardrails", "label", "value", "target", "op", "met", "started_at",
    "repeat", "asks", "ask", "in_data", "in_app", "detail", "step", "passed", "expected",
    "recall", "recalled", "total", "cited_threads", "cited_relevant", "groups",
    "thread_ids", "clarify", "asked", "on_topic", "questions", "question", "options",
    "answer", "latency_s", "app_renders", "checks",
}  # fmt: skip

# Never allowed, whatever the schema says.
FORBIDDEN_FIELDS = {
    "subject", "sender", "senders", "snippet", "body", "from", "to", "data", "guide",
    "app_html", "summary", "config", "events", "record", "records", "queries",
}  # fmt: skip

SECRET = "SECRET-FROM-THE-INBOX"


@pytest.fixture
def admin_env(monkeypatch):
    """The dev user (the `client` fixture) becomes an admin through ADMIN_EMAILS."""
    monkeypatch.setattr(settings, "ADMIN_EMAILS", "Dev@Demux.local")


def admin_paths() -> list[tuple[str, str]]:
    """Every (method, path) under /api/v1/admin, path parameters filled with random ids."""
    out = []
    for path, ops in app.openapi()["paths"].items():
        if path.startswith("/api/v1/admin"):
            concrete = path.replace("{user_id}", str(uuid.uuid4()))
            concrete = concrete.replace("{workspace_id}", str(uuid.uuid4()))
            concrete = concrete.replace("{eval_id}", str(uuid.uuid4()))
            out += [(method.upper(), concrete) for method in ops]
    return out


# ------------------------------------------------------------------ metering


async def test_llm_calls_match_run_costs(session, session_factory, dev_user):
    box = FakeMailbox.from_file(SMALL_MAILBOX, now=dt("2026-10-16T00:00:00Z"))
    ws = await create_workspace(session, dev_user.id, "track orders")
    run = await runs.claim_next(session)
    llm = build_llm()
    await execute_run(
        run.id,
        llm=llm,
        mailbox_factory=lambda _uid: box,
        session_factory=session_factory,
        now=dt("2026-10-16T00:00:00Z"),
    )
    await session.refresh(run)
    assert run.status == RunStatus.DONE, run.error

    calls = list(await session.scalars(select(LLMCall).where(LLMCall.run_id == run.id)))
    assert len(calls) == len(llm.calls)
    assert {c.phase for c in calls} >= {"design", "batch", "app"}
    assert all(c.user_id == dev_user.id and c.workspace_id == ws.id for c in calls)
    assert all(c.status == "ok" and c.input_price > 0 and c.provider for c in calls)
    assert sum(c.input_tokens for c in calls) == run.input_tokens
    assert abs(sum(c.cost_usd for c in calls) - run.cost_usd) <= Decimal("0.01")


async def test_cost_totals_match_for_every_range(session, dev_user):
    """For any date range, llm_calls and runs agree on what users cost (±$0.01)."""
    await seed_history(session, users=3, days=90, rng=random.Random(7))
    today = datetime.now(UTC).date()
    for days in (1, 2, 7, 30, 45, 90):
        start = datetime.combine(today - timedelta(days=days - 1), datetime.min.time(), UTC)
        calls = await session.scalar(
            select(func.coalesce(func.sum(LLMCall.cost_usd), 0)).where(
                LLMCall.created_at >= start, LLMCall.run_id.is_not(None)
            )
        )
        run_total = await session.scalar(
            select(func.coalesce(func.sum(Run.cost_usd), 0)).where(Run.created_at >= start)
        )
        assert abs(calls - run_total) <= Decimal("0.01"), days


async def test_metered_llm_records_errors_and_prices(session, session_factory, dev_user):
    class Failing:
        async def chat(self, model, messages, tools):
            raise LLMError("down", "http_503")

    class Cached:
        async def chat(self, model, messages, tools):
            return LLMReply("hi", [], 1_000_000, 0, 5, {}, model, cached_input_tokens=400_000)

    model = "Qwen/Qwen3.8-27B:nebius"  # 0.45 in / 3.0 out per million
    with usage_scope(session_factory=session_factory, user_id=dev_user.id, phase="seed"):
        with pytest.raises(LLMError):
            await MeteredLLM(Failing()).chat(model, [], [])
        reply = await MeteredLLM(Cached()).chat(model, [], [])
    assert reply.cost_usd == pytest.approx(0.45)  # cached input billed at input price
    rows = list(await session.scalars(select(LLMCall).order_by(LLMCall.status)))
    assert [(r.status, r.error_code, r.provider) for r in rows] == [
        ("error", "http_503", "nebius"),
        ("ok", None, "nebius"),
    ]
    assert rows[1].cached_input_tokens == 400_000 and rows[1].input_price == Decimal("0.45")


async def test_no_scope_records_nothing(session):
    class Ok:
        async def chat(self, model, messages, tools):
            return LLMReply("hi", [], 10, 1, 1, {}, model)

    await MeteredLLM(Ok()).chat("x", [], [])
    assert await session.scalar(select(func.count()).select_from(LLMCall)) == 0


# ------------------------------------------------------------------ access


async def test_every_admin_route_is_404_for_non_admins(client):
    paths = admin_paths()
    assert len(paths) >= 7
    unknown = await client.get("/api/v1/admin/does-not-exist")
    for method, path in paths:
        r = await client.request(method, path, json={})
        assert r.status_code == 404, (method, path, r.text)
        assert r.json() == unknown.json()  # indistinguishable from an unknown URL


async def test_every_admin_route_is_401_without_a_session(client, monkeypatch):
    monkeypatch.setattr(settings, "ENV", Env.DEV)  # no test-user fallback
    for method, path in admin_paths():
        r = await client.request(method, path, json={})
        assert r.status_code == 401, (method, path)
    r = await client.get("/api/v1/admin/users", headers={"Cookie": "demux.session_token=nope.sig"})
    assert r.status_code == 401


async def test_admin_by_flag_and_audit(client, session, dev_user):
    assert (await client.get("/api/v1/me")).json()["is_admin"] is False
    dev_user.is_admin = True
    await session.flush()
    assert (await client.get("/api/v1/me")).json()["is_admin"] is True
    uid = str(dev_user.id)
    assert (await client.get(f"/api/v1/admin/users/{uid}")).status_code == 200
    assert (await client.get("/api/v1/admin/overview?days=7")).status_code == 200
    audit = list(await session.scalars(select(AdminAudit).order_by(AdminAudit.created_at)))
    assert [(a.admin_email, a.method, a.action) for a in audit] == [
        ("dev@demux.local", "GET", "/admin/users/{user_id}"),
        ("dev@demux.local", "GET", "/admin/overview"),
    ]
    assert audit[0].target == {"user_id": uid} and audit[1].target == {"days": "7"}


async def test_bad_range_is_422(client, admin_env):
    r = await client.get("/api/v1/admin/overview?days=12")
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


# ------------------------------------------------------------------ privacy


def _schema_fields(schema: dict[str, Any], components: dict[str, Any], seen: set[str]) -> set:
    if "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[1]
        if name in seen:
            return set()
        seen.add(name)
        return _schema_fields(components[name], components, seen)
    out: set[str] = set()
    for key in ("items", "additionalProperties"):
        if isinstance(schema.get(key), dict):
            out |= _schema_fields(schema[key], components, seen)
    for key in ("anyOf", "oneOf", "allOf"):
        for sub in schema.get(key, []):
            out |= _schema_fields(sub, components, seen)
    for name, sub in (schema.get("properties") or {}).items():
        out.add(name)
        out |= _schema_fields(sub, components, seen)
    return out


def test_admin_response_schemas_use_allowed_fields_only():
    spec = app.openapi()
    components = spec["components"]["schemas"]
    fields: set[str] = set()
    for path, ops in spec["paths"].items():
        if not path.startswith("/api/v1/admin"):
            continue
        for op in ops.values():
            for code, resp in op.get("responses", {}).items():
                if not code.startswith("2"):
                    continue  # FastAPI's own validation-error shape
                for content in resp.get("content", {}).values():
                    fields |= _schema_fields(content["schema"], components, set())
    assert fields, "no admin response schema found"
    assert not fields & FORBIDDEN_FIELDS, fields & FORBIDDEN_FIELDS
    assert fields <= ALLOWED_FIELDS, f"review these fields first: {fields - ALLOWED_FIELDS}"


def _keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {k for v in value.values() for k in _keys(v)}
    if isinstance(value, list):
        return {k for v in value for k in _keys(v)}
    return set()


async def test_admin_responses_never_contain_inbox_content(client, session, admin_env, dev_user):
    ws = Workspace(
        user_id=dev_user.id,
        name="Orders",
        prompt="track my orders",
        data={"order": {"o1": {"title": SECRET}, "o2": {"title": "x"}}, "_meta": {"a": 1}},
        guide=f"guide {SECRET}",
        app_html=f"<p>{SECRET}</p>",
        config={"queries": [SECRET]},
    )
    session.add(ws)
    await session.flush()
    session.add_all(
        [
            Run(
                workspace_id=ws.id,
                kind=RunKind.SYNC,
                status=RunStatus.DONE,
                summary=f"Added {SECRET}",
            ),
            Run(
                workspace_id=ws.id,
                kind=RunKind.BUILD,
                status=RunStatus.FAILED,
                error=f"No emails about {SECRET}",
            ),
            Run(
                workspace_id=ws.id,
                kind=RunKind.EDIT,
                status=RunStatus.DONE,
                input={"text": "add a column for the courier"},
            ),
            ProcessedMessage(workspace_id=ws.id, message_id="m1", thread_id="t1"),
        ]
    )
    await session.flush()
    bodies = []
    for path in (
        "/api/v1/admin/overview?days=90",
        "/api/v1/admin/users",
        f"/api/v1/admin/users/{dev_user.id}",
        f"/api/v1/admin/workspaces/{ws.id}?days=7",
        "/api/v1/admin/demo",
    ):
        r = await client.get(path)
        assert r.status_code == 200, (path, r.text)
        bodies.append(r.json())
        assert SECRET not in r.text, path
        assert _keys(r.json()) <= ALLOWED_FIELDS, _keys(r.json()) - ALLOWED_FIELDS

    detail = bodies[2]["workspaces"][0]
    assert detail["record_count"] == 2 and detail["emails_processed"] == 1
    assert [e["text"] for e in detail["edits"]] == ["add a column for the courier"]
    assert {r["error_code"] for r in detail["runs"]} == {None, "cannot_build"}


# ------------------------------------------------------------------ stats


async def test_overview_with_no_data(client, admin_env):
    for days in (7, 30, 90):
        body = (await client.get(f"/api/v1/admin/overview?days={days}")).json()
        assert body["cost_usd"] == 0 and body["active_users"] == 0
        assert len(body["tokens"]) == days and len(body["failures"]) == days
        assert len(body["cost_per_user"]) == days and body["cost_by_phase"] == []


async def test_overview_on_90_days_is_fast_and_consistent(client, session, admin_env):
    await seed_history(session, users=25, days=90, rng=random.Random(1))
    start = time.perf_counter()
    o = (await client.get("/api/v1/admin/overview?days=90")).json()
    users = (await client.get("/api/v1/admin/users")).json()
    top = users[0]
    detail = (await client.get(f"/api/v1/admin/users/{top['id']}")).json()
    ws = detail["workspaces"][0]
    (await client.get(f"/api/v1/admin/workspaces/{ws['id']}?days=90")).json()
    elapsed = time.perf_counter() - start
    assert elapsed < 2.0, f"admin pages took {elapsed:.2f}s"

    assert o["cost_usd"] == pytest.approx(sum(r["cost_usd"] for r in o["cost_by_phase"]), abs=1e-4)
    assert o["cost_usd"] == pytest.approx(sum(r["cost_usd"] for r in o["cost_by_model"]), abs=1e-4)
    assert o["input_tokens"] == sum(r["input_tokens"] for r in o["tokens"])
    assert o["builds"] + o["syncs"] + o["edits"] > 0 and o["active_users"] == 25
    assert all(d["p95_usd"] >= d["p50_usd"] for d in o["cost_per_user"])
    assert [u["cost_30d"] for u in users] == sorted((u["cost_30d"] for u in users), reverse=True)
    assert top["emails_received_per_day"] is not None


# ------------------------------------------------------------------ mailbox counter


async def test_count_mailboxes_backfills_seven_days(session, session_factory, dev_user):
    today = datetime.now(UTC).date()
    yesterday_noon = datetime.combine(today - timedelta(days=1), datetime.min.time(), UTC)
    yesterday_noon += timedelta(hours=12)

    class Box:
        async def count_received(self, after, before):
            return 5 if after <= yesterday_noon < before else 1

    stored = await count_mailboxes(lambda _u: Box(), session_factory)
    assert stored == 7
    rows = dict(
        (
            await session.execute(select(MailboxDailyStat.date, MailboxDailyStat.messages_received))
        ).all()
    )
    assert rows[today - timedelta(days=1)] == 5 and len(rows) == 7
    assert today not in rows  # only finished days
    assert await count_mailboxes(lambda _u: Box(), session_factory) == 0  # idempotent


# ------------------------------------------------------------------ demo inbox


class DemoLLM:
    def __init__(self, n: int):
        self.n = n
        self.calls = 0

    async def chat(self, model, messages, tools):
        self.calls += 1
        system = messages[0]["content"]
        if system.startswith("You design"):
            content = json.dumps(
                {
                    "owner_name": "Maya Chen",
                    "threads": [
                        {
                            "counterpart_name": f"Brand Lead {i}",
                            "counterpart_email": f"lead{i}@brand{i}.com",
                            "company": f"Brand {i}",
                            "topic": "A paid UGC video for a skincare launch",
                            "messages": 3,
                            "owner_replies": True,
                            "days_ago": 3 + i,
                        }
                        for i in range(self.n)
                    ],
                }
            )
        else:
            content = (
                "```json\n"
                + json.dumps(
                    {
                        "subject": "Paid UGC video for our launch",
                        "messages": [
                            {"from": "counterpart", "hours_after_previous": 0, "body": "Hi Maya,"},
                            {"from": "owner", "hours_after_previous": 5, "body": "Rate is $900."},
                            {"from": "counterpart", "hours_after_previous": 20, "body": "Deal."},
                        ],
                    }
                )
                + "\n```"
            )
        return LLMReply(content, [], 1000, 500, 3, {}, model)


async def test_generate_threads_dates_and_directions():
    now = datetime(2026, 11, 23, 12, tzinfo=UTC)
    threads, cost = await demo.generate_threads(
        MeteredLLM(DemoLLM(4)), "Qwen/Qwen3.8-27B:nebius", "UGC creator", 4, "demo@x.com", now
    )
    assert len(threads) == 4 and cost > 0
    for t in threads:
        assert [m.outgoing for m in t] == [False, True, False]
        assert [m.date for m in t] == sorted(m.date for m in t)
        assert all(m.date < now for m in t)
        assert t[1].from_email == "demo@x.com" and t[0].to_email == "demo@x.com"
    mime = build_threads(threads[:1], "seed-1")
    first, second = mime[0][0], mime[1][0]
    assert second["In-Reply-To"] == first["Message-ID"]
    assert second["Subject"] == "Re: Paid UGC video for our launch"
    assert first[DEMO_HEADER] == "seed-1"


async def test_demo_seed_end_to_end(client, session, session_factory, admin_env, monkeypatch):
    monkeypatch.setattr(settings, "TEST_GMAIL", "")
    r = await client.post("/api/v1/admin/demo/seeds", json={"prompt": "I am a UGC creator"})
    assert r.status_code == 503 and r.json()["error"]["code"] == "demo_inbox_not_configured"

    monkeypatch.setattr(settings, "TEST_GMAIL", "demo@demux.test")
    monkeypatch.setattr(settings, "TEST_GMAIL_PASSWORD", "app-password")
    r = await client.post(
        "/api/v1/admin/demo/seeds",
        json={"prompt": "I am a UGC creator; brand deals", "thread_count": 3},
    )
    assert r.status_code == 202 and r.json()["status"] == "queued"
    again = await client.post("/api/v1/admin/demo/seeds", json={"prompt": "another persona"})
    assert again.status_code == 409

    seed = await demo.claim_next(session)
    appended: list[Any] = []

    def fake_append(host, email, password, threads, seed_id):
        appended.append((email, password, threads, seed_id))
        return sum(len(t) for t in threads)

    await demo.execute_seed(
        seed.id, session_factory=session_factory, llm=DemoLLM(3), append=fake_append
    )
    await session.refresh(seed)
    assert seed.status == DemoSeedStatus.DONE, seed.error
    assert (seed.threads_created, seed.messages_created) == (3, 9)
    assert appended[0][:2] == ("demo@demux.test", "app-password")
    calls = list(await session.scalars(select(LLMCall).where(LLMCall.phase == "seed")))
    assert len(calls) == 4 and all(c.run_id is None for c in calls)
    assert float(seed.cost_usd) == pytest.approx(float(sum(c.cost_usd for c in calls)))

    state = (await client.get("/api/v1/admin/demo")).json()
    assert state["configured"] and state["seeds"][0]["threads_created"] == 3


async def test_demo_seed_failure_is_recorded(session, session_factory, admin_env, dev_user):
    seed = DemoSeed(created_by=dev_user.id, prompt="persona text", thread_count=3)
    session.add(seed)
    await session.flush()

    class Broken:
        async def chat(self, model, messages, tools):
            return LLMReply("sorry, no JSON here", [], 10, 10, 1, {}, model)

    await demo.execute_seed(
        seed.id, session_factory=session_factory, llm=Broken(), append=lambda *a: 0
    )
    await session.refresh(seed)
    assert seed.status == DemoSeedStatus.FAILED and "JSON" in (seed.error or "")


# ------------------------------------------------------------------ seeding


async def seed_history(session, *, users: int, days: int, rng: random.Random) -> list[User]:
    """`users` users with a workspace each and runs + matching llm_calls every day."""
    today = datetime.now(UTC).date()
    out = []
    phases = {RunKind.BUILD: ("design", "batch", "app"), RunKind.SYNC: ("batch",)}
    phases[RunKind.EDIT] = ("edit", "app")
    models = ("Qwen/Qwen3.8-27B:nebius", "Qwen/Qwen3.8-27B:nscale")
    for u in range(users):
        user = await _make_user(session, f"seed{u}@demux.local")
        ws = Workspace(user_id=user.id, name=f"WS {u}", prompt=f"track thing {u}")
        session.add(ws)
        await session.flush()
        out.append(user)
        for d in range(days):
            day = today - timedelta(days=d)
            session.add(
                MailboxDailyStat(user_id=user.id, date=day, messages_received=rng.randint(5, 80))
            )
            for k in range(rng.randint(0, 3)):
                kind = (
                    RunKind.BUILD
                    if d == days - 1 and k == 0
                    else rng.choice((RunKind.SYNC, RunKind.SYNC, RunKind.EDIT))
                )
                at = datetime.combine(day, datetime.min.time(), UTC) + timedelta(
                    minutes=rng.randint(0, 1439)
                )
                at = min(at, datetime.now(UTC) - timedelta(seconds=1))
                run = Run(
                    workspace_id=ws.id,
                    kind=kind,
                    status=RunStatus.FAILED if rng.random() < 0.1 else RunStatus.DONE,
                    input={"text": "make it a board"} if kind == RunKind.EDIT else {},
                    created_at=at,
                    started_at=at,
                    finished_at=at + timedelta(seconds=rng.randint(5, 120)),
                )
                session.add(run)
                await session.flush()
                total, tin, tout = Decimal(0), 0, 0
                for phase in phases[kind]:
                    i, o = rng.randint(1000, 40000), rng.randint(100, 4000)
                    cost = (Decimal(i) * Decimal("0.45") + Decimal(o) * 3) / 1_000_000
                    cost = cost.quantize(Decimal("0.000001"))
                    session.add(
                        LLMCall(
                            run_id=run.id,
                            workspace_id=ws.id,
                            user_id=user.id,
                            phase=phase,
                            model=rng.choice(models),
                            provider="nebius",
                            input_tokens=i,
                            cached_input_tokens=0,
                            output_tokens=o,
                            input_price=Decimal("0.45"),
                            cached_input_price=Decimal("0.45"),
                            output_price=Decimal(3),
                            cost_usd=cost,
                            latency_ms=900,
                            status="ok",
                            created_at=at,
                        )
                    )
                    total, tin, tout = total + cost, tin + i, tout + o
                run.cost_usd, run.input_tokens, run.output_tokens = total, tin, tout
                session.add(
                    ProcessedMessage(
                        workspace_id=ws.id,
                        message_id=f"m-{run.id}",
                        thread_id="t",
                        created_at=at,
                    )
                )
        await session.flush()
    return out
