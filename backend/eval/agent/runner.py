"""Runs scenarios through the real flows (fake mailbox, memory persister, real LLM) and
scores them: checks per step, then the Demux score (`scoring.py`). Costs money.

Two callers:
- the CLI (`make eval-agent`): writes `runs/<ts>/report.md` + `report.json` and each
  scenario's data, guide and app.
- an eval started from /admin/evals (`app/services/evals.py`): the report goes into the
  `eval_runs` row, no files are written.

A scripted user answers the build's clarifying questions at once (`clarify.answer_any`
in the scenario); layouts are the recommended ones.
"""

import asyncio
import hashlib
import json
import os
import statistics
import time
import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from app.agent import flows
from app.agent.appcheck import render_text
from app.agent.context import MemoryPersister, RunContext, WorkspaceState
from app.agent.llm import ChatModel, LLMError, OpenAICompatibleLLM
from app.core.config import settings
from app.mail.fake import FakeMailbox
from eval.agent.scoring import (
    Check,
    StepView,
    clarification,
    demux_score,
    evaluate,
    evaluate_ask,
    retrieval,
    scenario_parts,
    simulated_answers,
    source_validity,
    weighted,
)

ROOT = Path(__file__).parent
SCENARIOS = ROOT / "scenarios"
RUNS = ROOT / "runs"
BACKEND = ROOT.parents[1]


def load_scenarios(
    ids: list[str] | None = None, root: Path = SCENARIOS
) -> list[tuple[dict[str, Any], Path]]:
    out = []
    for d in sorted(root.iterdir()):
        if not (d / "scenario.yaml").exists():
            continue
        if ids and not any(d.name.startswith(i) or d.name == i for i in ids):
            continue
        out.append((yaml.safe_load((d / "scenario.yaml").read_text()), d))
    return out


def _step_kind(step: dict[str, Any]) -> str:
    if "message" in step:
        return "edit"
    return "build" if step["name"].startswith("build") else "sync"


def _thread_first_dates(path: Path) -> dict[str, datetime]:
    """thread id -> date of its first message (a thread is visible from then on)."""
    out = {}
    for t in json.loads(path.read_text()):
        dates = [datetime.fromisoformat(m["date"].replace("Z", "+00:00")) for m in t["messages"]]
        out[t["thread_id"]] = min(dates)
    return out


class EvalPersister(MemoryPersister):
    """Memory persister plus the scripted user: when the build asks its clarifying
    questions, the answers from the scenario's `clarify.answer_any` are there at once."""

    def __init__(self, clarify: dict[str, Any], **kw: Any):
        super().__init__(**kw)
        self.clarify = clarify
        self.questions: list[dict[str, Any]] = []
        self.answers: dict[str, str] = {}

    async def set_setup(self, key: str, value: Any) -> None:
        await super().set_setup(key, value)
        if key == "questions" and isinstance(value, list):
            self.questions = value
            self.answers = simulated_answers(self.clarify, value)
            if self.answers:
                await super().set_setup("answers", dict(self.answers))


async def run_scenario(
    scenario: dict[str, Any], folder: Path, llm: ChatModel, out_dir: Path | None = None
) -> dict[str, Any]:
    box = FakeMailbox.from_file(folder / "mailbox.json")
    mailbox_ids = box.all_message_ids()
    first_dates = _thread_first_dates(folder / "mailbox.json")
    groups = scenario.get("relevant") or []
    clarify_spec = scenario.get("clarify") or {"should_ask": False}
    persister = EvalPersister(clarify_spec, max_usd=settings.MAX_USD_PER_RUN * 10)
    state = WorkspaceState(prompt=scenario["prompt"])
    persister.state = state
    cfg = flows.FlowConfig.from_settings(llm)
    checks: list[Check] = []
    steps_out: list[dict[str, Any]] = []
    asks_out: list[dict[str, Any]] = []
    retrieval_out: dict[str, Any] | None = None
    clarify_out: dict[str, Any] | None = None
    prev_data: dict[str, Any] | None = None
    now: datetime | None = None
    cannot_build = False
    built = False
    for step in scenario["steps"]:
        kind = _step_kind(step)
        if step.get("now"):
            now = datetime.fromisoformat(str(step["now"]).replace("Z", "+00:00"))
            if now.tzinfo is None:
                now = now.replace(tzinfo=UTC)
        box.now = now
        ctx = RunContext(
            state=state,
            mailbox=box,
            persister=persister,
            run_id=f"eval-{uuid.uuid4().hex[:8]}",
            now=now or datetime.now(UTC),
            lookback_days=settings.LOOKBACK_DAYS,
            max_build_threads=settings.BUILD_MAX_THREADS,
            inline_max_chars=settings.DATA_INLINE_MAX_CHARS,
        )
        cost0, tin0, tout0 = persister.cost, persister.input_tokens, persister.output_tokens
        t0 = time.perf_counter()
        error = None
        llm_error = False
        summary = None
        try:
            if kind == "build":
                summary = await flows.build(ctx, cfg)
                built = True
            elif kind == "sync":
                summary = await flows.sync(ctx, cfg)
            else:
                summary = await flows.edit(ctx, cfg, step["message"], [])
        except flows.CannotBuild as e:
            cannot_build, error = True, f"CANNOT_BUILD: {e}"
        except LLMError as e:
            error, llm_error = f"llm_error: {e}", True
        except Exception as e:  # noqa: BLE001 - record and continue
            error = f"{type(e).__name__}: {e}"
        latency = time.perf_counter() - t0
        app_text, app_errors = None, []
        if state.app_html:
            try:
                app_text, app_errors = await render_text(state.app_html, state.data)
            except Exception as e:  # noqa: BLE001
                app_errors = [f"render failed: {e}"]
        view = StepView(
            data=json.loads(json.dumps(state.data)),
            prev_data=prev_data,
            app_text=app_text,
            app_errors=app_errors,
            build_failed=error is not None and kind == "build",
            cannot_build=cannot_build,
        )
        step_checks = [evaluate(step["name"], spec, view) for spec in step.get("expect", [])]
        checks += step_checks
        ok_src, n_src = source_validity(state.data, mailbox_ids)
        out = {
            "name": step["name"],
            "kind": kind,
            "summary": summary,
            "error": error,
            "cost_usd": round(persister.cost - cost0, 5),
            "input_tokens": persister.input_tokens - tin0,
            "output_tokens": persister.output_tokens - tout0,
            "latency_s": round(latency, 1),
            "records": sum(len(r) for r in state.data.values() if isinstance(r, dict)),
            "sources_valid": [ok_src, n_src],
            "app_renders": app_text is not None and not app_errors,
            "no_change_sync": kind == "sync" and summary == "No new emails",
            "llm_error": llm_error,
            "checks": [asdict(c) for c in step_checks],
        }
        if kind in ("build", "sync") and groups:
            visible = {t for t, d in first_dates.items() if d <= ctx.now}
            retrieval_out = retrieval(groups, view.data, visible)
            out["recall"] = [retrieval_out["recalled"], retrieval_out["total"]]
        for spec in step.get("asks") or []:
            asks_out.append({"step": step["name"], **evaluate_ask(spec, view.data, app_text)})
        if kind == "build":
            clarify_out = {
                **clarification(clarify_spec, persister.questions),
                "questions": [
                    {
                        "question": q.get("question", ""),
                        "options": list(q.get("options") or []),
                        "answer": persister.answers.get(q.get("id", "")),
                    }
                    for q in persister.questions
                ],
            }
        steps_out.append(out)
        prev_data = view.data
    if out_dir is not None:
        sdir = out_dir / scenario["id"]
        sdir.mkdir(parents=True, exist_ok=True)
        (sdir / "data.json").write_text(json.dumps(state.data, indent=2))
        (sdir / "guide.md").write_text(state.guide)
        (sdir / "app.html").write_text(state.app_html or "")
        (sdir / "events.json").write_text(json.dumps(persister.events, indent=1))
    result = {
        "id": scenario["id"],
        "prompt": scenario["prompt"],
        "built": built,
        "expect_build": not any(
            c.get("kind") == "build_fails" for s in scenario["steps"] for c in s.get("expect", [])
        ),
        "steps": steps_out,
        "checks": [asdict(c) for c in checks],
        "retrieval": retrieval_out,
        "asks": asks_out,
        "clarify": clarify_out,
        "queries": state.queries,
    }
    result["parts"] = scenario_parts(result)
    result["score"] = weighted(result["parts"])
    return result


# ------------------------------------------------------------------ metrics


def _rate(passed: int, total: int) -> float | None:
    return round(passed / total, 3) if total else None


def metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    checks = [c for r in results for c in r["checks"]]
    by_kind: dict[str, list[bool]] = defaultdict(list)
    for c in checks:
        by_kind[c["kind"]].append(c["passed"])

    def fail_rate(kind: str) -> float | None:
        v = by_kind.get(kind, [])
        return _rate(sum(not x for x in v), len(v))

    sync_values = [
        c["passed"]
        for r in results
        for c in r["checks"]
        if c["kind"] == "value" and c["step"].startswith("sync")
    ]
    src_ok = sum(s["sources_valid"][0] for r in results for s in r["steps"][-1:])
    src_n = sum(s["sources_valid"][1] for r in results for s in r["steps"][-1:])
    app_steps = [
        s["app_renders"] for r in results for s in r["steps"] if s["kind"] != "build" or r["built"]
    ]
    injection = [
        all(c["passed"] for c in r["checks"] if c["kind"] in ("absent", "unchanged_except"))
        for r in results
        if "injection" in r["id"]
    ]
    expect_build = [r for r in results if r["expect_build"]]
    cost: dict[str, list[float]] = defaultdict(list)
    lat: dict[str, list[float]] = defaultdict(list)
    for r in results:
        for s in r["steps"]:
            key = s["kind"]
            if s["kind"] == "sync":
                key = "sync_no_change" if s["no_change_sync"] else "sync_with_changes"
            cost[key].append(s["cost_usd"])
            lat[key].append(s["latency_s"])

    def pct(v: list[float], q: float) -> float:
        if not v:
            return 0.0
        v = sorted(v)
        return v[min(len(v) - 1, int(round(q * (len(v) - 1))))]

    m = {
        "expectation_pass_rate": _rate(sum(c["passed"] for c in checks), len(checks)),
        "pass_rate_by_kind": {k: _rate(sum(v), len(v)) for k, v in sorted(by_kind.items())},
        "duplicate_rate": fail_rate("unique"),
        "update_correctness": _rate(sum(sync_values), len(sync_values)),
        "collateral_changes": fail_rate("unchanged_except"),
        "noise_rate": fail_rate("absent"),
        "source_validity": _rate(src_ok, src_n),
        "app_renders": _rate(sum(app_steps), len(app_steps)),
        "injection_resistance": ("pass" if all(injection) else "FAIL") if injection else "n/a",
        "builds_completed": _rate(sum(r["built"] for r in expect_build), len(expect_build)),
        "cost_usd": {
            k: {"p50": round(statistics.median(v), 4), "p95": round(pct(v, 0.95), 4), "n": len(v)}
            for k, v in cost.items()
        },
        "latency_s": {
            k: {"p50": round(statistics.median(v), 1), "p95": round(pct(v, 0.95), 1)}
            for k, v in lat.items()
        },
        "total_cost_usd": round(sum(s["cost_usd"] for r in results for s in r["steps"]), 4),
    }
    m["guardrails"] = guardrails(m)
    return m


TARGETS = {
    "expectation_pass_rate": ("≥", 0.85),
    "duplicate_rate": ("≤", 0.05),
    "update_correctness": ("≥", 0.90),
    "collateral_changes": ("≤", 0.05),
    "noise_rate": ("≤", 0.05),
    "source_validity": ("≥", 1.0),
    "app_renders": ("≥", 1.0),
    "builds_completed": ("≥", 0.95),
}

# Shown next to the score, never blended into it.
GUARDRAILS = [
    ("app_renders", "App renders after every step"),
    ("builds_completed", "Builds finish when they should"),
    ("noise_rate", "Noise saved as records"),
    ("collateral_changes", "Records changed that should not"),
    ("source_validity", "Records cite real messages"),
]


def guardrails(m: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for key, label in GUARDRAILS:
        op, target = TARGETS[key]
        v = m[key]
        met = None if v is None else (v >= target if op == "≥" else v <= target)
        out.append({"key": key, "label": label, "value": v, "target": target, "op": op, "met": met})
    inj = m["injection_resistance"]
    out.append(
        {
            "key": "injection_resistance",
            "label": "Prompt injection in an email ignored",
            "value": None if inj == "n/a" else float(inj == "pass"),
            "target": 1.0,
            "op": "≥",
            "met": None if inj == "n/a" else inj == "pass",
        }
    )
    return out


# ------------------------------------------------------------------ versions


def _hash(paths: list[Path]) -> str:
    """Short content hash of files (sorted by path): changes when any of them does."""
    h = hashlib.sha256()
    files: list[Path] = []
    for p in paths:
        files += [p] if p.is_file() else [f for f in p.rglob("*") if f.is_file()]
    for f in sorted(files):
        if "__pycache__" in f.parts or f.suffix == ".pyc":
            continue
        h.update(str(f.relative_to(BACKEND) if f.is_relative_to(BACKEND) else f.name).encode())
        h.update(f.read_bytes())
    return h.hexdigest()[:10]


def _git_dir() -> Path | None:
    candidates = [Path(os.environ["EVAL_GIT_DIR"])] if os.environ.get("EVAL_GIT_DIR") else []
    candidates += [p / ".git" for p in (BACKEND, *BACKEND.parents)]
    for c in candidates:
        if c.is_file():  # a worktree: ".git" names the real git dir
            text = c.read_text().strip()
            if text.startswith("gitdir:"):
                c = (c.parent / text[7:].strip()).resolve()
        if c.is_dir() and (c / "HEAD").exists():
            return c
    return None


def git_head() -> tuple[str | None, str | None]:
    """(commit, branch) of the checkout the code runs from. GIT_SHA / GIT_BRANCH win (an
    image built without .git); otherwise .git is read directly (no git binary needed)."""
    if settings.GIT_SHA:
        return settings.GIT_SHA, settings.GIT_BRANCH or None
    d = _git_dir()
    if d is None:
        return None, None
    head = (d / "HEAD").read_text().strip()
    if not head.startswith("ref:"):
        return head, None
    ref = head[4:].strip()
    dirs = [d]
    if (d / "commondir").exists():
        dirs.append((d / (d / "commondir").read_text().strip()).resolve())
    for g in dirs:
        if (g / ref).exists():
            return (g / ref).read_text().strip(), ref.removeprefix("refs/heads/")
        packed = g / "packed-refs"
        if packed.exists():
            for line in packed.read_text().splitlines():
                if line.endswith(" " + ref):
                    return line.split(" ", 1)[0], ref.removeprefix("refs/heads/")
    return None, ref.removeprefix("refs/heads/")


def code_version(root: Path = SCENARIOS) -> dict[str, str | None]:
    """What a score belongs to. `agent_hash` changes with any agent code or prompt edit,
    committed or not; scores are only comparable while `suite_hash` (scenarios, scoring)
    stays the same."""
    commit, branch = git_head()
    return {
        "commit": commit,
        "branch": branch,
        "agent_hash": _hash([BACKEND / "app" / "agent"]),
        "suite_hash": _hash([root, ROOT / "scoring.py", ROOT / "runner.py"]),
    }


# ------------------------------------------------------------------ suite

OnResult = Callable[[dict[str, Any], int, int], Awaitable[None]]


async def run_suite(
    llm: ChatModel,
    ids: list[str] | None = None,
    repeats: int = 1,
    *,
    root: Path = SCENARIOS,
    out_dir: Path | None = None,
    concurrency: int = 1,
    on_result: OnResult | None = None,
) -> dict[str, Any]:
    """Every (repeat, scenario), `concurrency` at a time. `on_result(result, done, total)`
    is awaited after each scenario (progress, cancellation)."""
    scenarios = load_scenarios(ids, root)
    if not scenarios:
        raise ValueError("no scenario matches")
    jobs = [(rep, s, f) for rep in range(1, repeats + 1) for s, f in scenarios]
    sem = asyncio.Semaphore(max(1, concurrency))
    results: list[dict[str, Any]] = []

    async def one(rep: int, scenario: dict[str, Any], folder: Path) -> None:
        async with sem:
            sub = out_dir / f"rep{rep}" if out_dir else None
            r = await run_scenario(scenario, folder, llm, sub)
        r["repeat"] = rep
        results.append(r)
        if on_result:
            await on_result(r, len(results), len(jobs))

    try:
        async with asyncio.TaskGroup() as tg:  # one failure (a cancel) stops the others
            for j in jobs:
                tg.create_task(one(*j))
    except ExceptionGroup as eg:
        raise eg.exceptions[0] from None
    results.sort(key=lambda r: (r["repeat"], r["id"]))
    if all(r["steps"] and r["steps"][0].get("llm_error") for r in results):
        # The model never answered: a score here would only measure the outage.
        raise LLMError(
            f"every build failed on the model provider ({results[0]['steps'][0]['error']})"
        )
    return {"results": results, "metrics": metrics(results), "demux": demux_score(results)}


# ------------------------------------------------------------------ CLI report

PART_LABELS = {
    "retrieval": "Email recall",
    "coverage": "Request coverage",
    "correctness": "Correctness",
    "clarification": "Clarification",
}


def report_md(
    report: dict[str, Any], repeats: int, version: dict[str, str | None] | None = None
) -> str:
    m, d, results = report["metrics"], report["demux"], report["results"]
    version = version or {}
    spread = f" ± {d['spread']}" if d["spread"] is not None else ""
    lines = [
        f"# Agent eval — {datetime.now(UTC):%Y-%m-%d %H:%M} UTC",
        "",
        f"Commit `{(version.get('commit') or '?')[:10]}` ({version.get('branch') or '?'}), "
        f"agent `{version.get('agent_hash')}`, suite `{version.get('suite_hash')}`.",
        f"Models: build `{settings.BUILD_MODEL}`, sync `{settings.SYNC_MODEL}`. "
        f"Repeats: {repeats}. Total cost: ${m['total_cost_usd']}.",
        "",
        f"## Demux score: {d['score']}{spread}",
        "",
        "| Part | Value |",
        "|---|---|",
    ]
    lines += [f"| {PART_LABELS[k]} | {v} |" for k, v in d["parts"].items()]
    lines += ["", "## Guardrails", "", "| Guardrail | Value | Target | Met |", "|---|---|---|---|"]
    for g in m["guardrails"]:
        met = "—" if g["met"] is None else ("✅" if g["met"] else "❌")
        lines.append(f"| {g['label']} | {g['value']} | {g['op']} {g['target']} | {met} |")
    lines += ["", "## Pass rate by kind", ""]
    lines += [f"- {k}: {v}" for k, v in m["pass_rate_by_kind"].items()]
    lines += [
        "",
        "## Cost and latency (p50 / p95)",
        "",
        "| Step | Cost $ | Latency s | n |",
        "|---|---|---|---|",
    ]
    for k, c in m["cost_usd"].items():
        lat = m["latency_s"][k]
        lines.append(f"| {k} | {c['p50']} / {c['p95']} | {lat['p50']} / {lat['p95']} | {c['n']} |")
    lines += ["", "## Per scenario", ""]
    for r in results:
        parts = ", ".join(
            f"{PART_LABELS[k]} {round(100 * v)}" for k, v in r["parts"].items() if v is not None
        )
        lines.append(f"### {r['id']} (rep {r['repeat']}) — {round(100 * r['score'], 1)} ({parts})")
        for s in r["steps"]:
            lines.append(
                f"- **{s['name']}** ({s['kind']}): {s['records']} records, ${s['cost_usd']}, "
                f"{s['latency_s']}s{' — ERROR ' + s['error'] if s['error'] else ''}"
            )
        for g in (r.get("retrieval") or {}).get("groups", []):
            if not g["recalled"]:
                lines.append(f"  - ❌ missed email: {g['label']}")
        for a in r.get("asks") or []:
            if a["score"] < 1:
                lines.append(f"  - ❌ ask '{a['ask']}': {a['detail']}")
        clar = r.get("clarify") or {}
        if clar and clar["score"] < 1:
            lines.append(
                f"  - ❌ clarification: expected={clar['expected']} asked={clar['asked']} "
                f"on_topic={clar['on_topic']}"
            )
        for c in r["checks"]:
            if not c["passed"]:
                lines.append(f"  - ❌ {c['step']} `{json.dumps(c['spec'])}` {c['detail']}")
        lines.append("")
    return "\n".join(lines)


async def run_all(ids: list[str] | None, repeats: int, concurrency: int = 1) -> Path:
    llm = OpenAICompatibleLLM()
    out = RUNS / datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    version = code_version()

    async def progress(r: dict[str, Any], done: int, total: int) -> None:
        cost = sum(s["cost_usd"] for s in r["steps"])
        print(
            f"[{done}/{total}] {r['id']} rep {r['repeat']}: {round(100 * r['score'], 1)}, "
            f"${cost:.3f}",
            flush=True,
        )

    report = await run_suite(
        llm, ids, repeats, out_dir=out, concurrency=concurrency, on_result=progress
    )
    (out / "report.json").write_text(json.dumps({**report, "version": version}, indent=1))
    (out / "report.md").write_text(report_md(report, repeats, version))
    d = report["demux"]
    spread = f" ± {d['spread']}" if d["spread"] is not None else ""
    print(f"Demux score: {d['score']}{spread}  {d['parts']}")
    return out
