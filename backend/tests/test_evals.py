"""/admin/evals: queue, run (scripted LLM, tiny fixture scenario), score, read, cancel."""

import re
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select

from app.agent import tools
from app.agent.context import RunContext, WorkspaceState
from app.core.config import settings
from app.mail.fake import FakeMailbox
from app.models.eval import EvalRun, EvalRunStatus
from app.models.usage import LLMCall
from app.services import evals
from eval.agent.runner import EvalPersister, code_version, git_head
from tests.helpers import FIXTURES, GOOD_APP, SMALL_MAILBOX, PhaseLLM, dt

ROOT = FIXTURES / "eval_scenarios"

GUIDE = "# Purpose\nOrders.\n\n# Record types\n## order\n\n# What to ignore\n\n# Learned\n"
DESIGN = [
    [("search_mail", {"query": "order"})],
    [
        ("write_guide", {"text": GUIDE}),
        (
            "propose_views",
            {
                "options": [
                    {
                        "block": "DataTable",
                        "title": "Orders",
                        "description": "all",
                        "recommended": True,
                    },
                    {
                        "block": "Board",
                        "title": "By status",
                        "description": "status",
                        "recommended": False,
                    },
                ],
                "primary": 0,
            },
        ),
        ("set_queries", {"queries": ["order"]}),
    ],
    [("finish", {"summary": "Tracks orders."})],
]


def save_orders(messages):
    """Process turn: one record per order number, with the item, total and status."""
    records = []
    for block in re.findall(r'<thread id="\w+">(.*?)</thread>', messages[1]["content"], re.S):
        mids = re.findall(r'<message id="(\w+)"[^>]*new="true"', block)
        num = re.search(r"#?\b([A-Z]-\d{4}|\d{2}-\d{3})\b", block)
        if not mids or not num or "sale" in block.lower() or "digest" in block.lower():
            continue
        fields = {"number": num.group(1)}
        if m := re.search(r"Item: ([^\n<]+)", block):
            fields["item"] = m.group(1).strip()
        if m := re.search(r"Total(?: paid)?: ([\d.]+)", block):
            fields["total"] = m.group(1)
        fields["status"] = "delivered" if "delivered" in block else "ordered"
        records.append({"id": num.group(1).lower(), "fields": fields, "source_message_ids": mids})
    if not records:
        return [("finish", {"summary": "No changes"})]
    return [
        ("save_records", {"record_type": "order", "records": records}),
        ("finish", {"summary": f"{len(records)} orders"}),
    ]


def llm():
    app = [[("write_app", {"html": GOOD_APP})], [("finish", {"summary": "table"})]]
    return PhaseLLM(design=DESIGN, process=[save_orders], app=app)


@pytest.fixture
def admin_env(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_EMAILS", "Dev@Demux.local")


@pytest.fixture
def fixture_suite(monkeypatch):
    real = evals.scenarios
    monkeypatch.setattr(evals, "scenarios", lambda root=None: real(root or ROOT))


async def test_queue_run_and_read_an_eval(
    client, session, session_factory, admin_env, fixture_suite, dev_user
):
    r = await client.post("/api/v1/admin/evals", json={"repeats": 1})
    assert r.status_code == 202, r.text
    row = r.json()
    assert row["status"] == "queued" and row["progress_total"] == 1
    again = await client.post("/api/v1/admin/evals", json={"repeats": 1})
    assert again.status_code == 409  # one eval at a time

    run = await evals.claim_next(session)
    assert run is not None and run.status == EvalRunStatus.RUNNING
    await evals.execute_eval(run.id, session_factory=session_factory, llm=llm(), root=ROOT)
    await session.refresh(run)
    assert run.status == EvalRunStatus.DONE, run.error
    assert run.progress_done == 1 and run.suite_hash and run.agent_hash
    # 3/3 groups cited, 3 asks fully covered (GOOD_APP shows every value), every
    # correctness check passes, no question asked on a clear prompt: 100.
    assert run.score == 100.0, run.report["results"][0]["parts"]
    assert run.parts == {
        "retrieval": 100.0,
        "coverage": 100.0,
        "correctness": 100.0,
        "clarification": 100.0,
    }
    assert {g["key"]: g["met"] for g in run.guardrails}["app_renders"] is True

    calls = list(await session.scalars(select(LLMCall).where(LLMCall.user_id == dev_user.id)))
    assert calls and {c.phase for c in calls} == {"eval"}  # billed as staff spending

    state = (await client.get("/api/v1/admin/evals")).json()
    assert [s["id"] for s in state["scenarios"]] == ["01-orders-small"]
    assert state["runs"][0]["score"] == 100.0
    detail = (await client.get(f"/api/v1/admin/evals/{run.id}")).json()
    sc = detail["scenarios"][0]
    assert sc["score"] == 100.0 and sc["retrieval"]["recalled"] == 3
    assert [a["ask"] for a in sc["asks"]] == ["the item", "the total", "whether it arrived"]
    assert sc["clarify"] == {
        "expected": False,
        "asked": False,
        "on_topic": None,
        "score": 1.0,
        "questions": [],
    }
    steps = {s["name"]: s for s in sc["steps"]}
    assert steps["build"]["record_count"] == 3 and all(
        c["passed"] for c in steps["build"]["checks"]
    )
    assert steps["build"]["checks"][1]["expected"] == 'unique {"all_of": ["A-1042"]}'


async def test_cancel_and_unknown_eval(client, session, admin_env, fixture_suite, dev_user):
    row = (
        await client.post("/api/v1/admin/evals", json={"scenario_ids": ["01-orders-small"]})
    ).json()
    r = await client.post(f"/api/v1/admin/evals/{row['id']}/cancel")
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    assert (await client.post(f"/api/v1/admin/evals/{row['id']}/cancel")).status_code == 409
    assert (await client.get(f"/api/v1/admin/evals/{uuid.uuid4()}")).status_code == 404
    bad = await client.post("/api/v1/admin/evals", json={"scenario_ids": ["99-nope"]})
    assert bad.status_code == 422


async def test_scripted_user_answers_the_build_questions():
    clarify = {"should_ask": True, "answer_any": ["paid"], "avoid_any": ["both"]}
    p = EvalPersister(clarify)
    box = FakeMailbox.from_file(SMALL_MAILBOX, now=dt("2026-10-16T00:00:00Z"))
    ctx = RunContext(
        state=WorkspaceState(prompt="x"), mailbox=box, persister=p, run_id="r", now=box.now
    )
    q = {"question": "Which orders?", "options": ["Both", "Paid ones only"], "recommended": 0}
    out = await tools._ask_user(ctx, {"questions": [q]})
    assert out.result["answers"][0] == {
        "question": "Which orders?",
        "answer": "Paid ones only",
        "from": "user",
    }
    assert p.questions[0]["id"] == "q1" and p.answers == {"q1": "Paid ones only"}


def test_code_version_reads_git_without_the_binary(tmp_path, monkeypatch):
    commit, branch = git_head()
    assert commit is None or re.fullmatch(r"[0-9a-f]{40}", commit)
    git = tmp_path / ".git"
    (git / "refs" / "heads").mkdir(parents=True)
    (git / "HEAD").write_text("ref: refs/heads/main\n")
    (git / "packed-refs").write_text("# pack-refs\n" + "a" * 40 + " refs/heads/main\n")
    monkeypatch.setenv("EVAL_GIT_DIR", str(git))
    assert git_head() == ("a" * 40, "main")
    monkeypatch.setattr(settings, "GIT_SHA", "b" * 40)
    assert git_head()[0] == "b" * 40
    v1 = code_version(ROOT)
    assert v1["suite_hash"] != code_version(Path(__file__).parent / "fixtures")["suite_hash"]


async def test_stale_running_evals_fail_on_worker_start(session):
    run = EvalRun(status=EvalRunStatus.RUNNING, repeats=1)
    session.add(run)
    await session.flush()
    await evals.fail_stale(session)
    await session.refresh(run)
    assert run.status == EvalRunStatus.FAILED and "Interrupted" in run.error


class DownLLM:
    async def chat(self, model, messages, tools):
        from app.agent.llm import LLMError

        raise LLMError("provider unreachable", code="connection")


async def test_an_unreachable_model_fails_the_run_instead_of_scoring_it(session, session_factory):
    run = EvalRun(status=EvalRunStatus.RUNNING, repeats=1, progress_total=1)
    session.add(run)
    await session.flush()
    await evals.execute_eval(run.id, session_factory=session_factory, llm=DownLLM(), root=ROOT)
    await session.refresh(run)
    assert run.status == EvalRunStatus.FAILED and run.score is None
    assert "model provider" in run.error
