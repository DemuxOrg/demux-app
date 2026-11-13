"""Runs scenarios through the real flows (fake mailbox, memory persister, real LLM) and
writes `runs/<ts>/report.md` + `report.json` (build spec §10.3). Costs money."""

import json
import statistics
import time
import uuid
from collections import defaultdict
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from app.agent import flows
from app.agent.appcheck import render_text
from app.agent.context import MemoryPersister, RunContext, WorkspaceState
from app.agent.llm import OpenAICompatibleLLM
from app.core.config import settings
from app.mail.fake import FakeMailbox
from eval.agent.scoring import Check, StepView, evaluate, source_validity

ROOT = Path(__file__).parent
SCENARIOS = ROOT / "scenarios"
RUNS = ROOT / "runs"


def load_scenarios(ids: list[str] | None) -> list[tuple[dict[str, Any], Path]]:
    out = []
    for d in sorted(SCENARIOS.iterdir()):
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


async def run_scenario(
    scenario: dict[str, Any], folder: Path, llm: OpenAICompatibleLLM, out_dir: Path
) -> dict[str, Any]:
    box = FakeMailbox.from_file(folder / "mailbox.json")
    mailbox_ids = box.all_message_ids()
    persister = MemoryPersister(max_usd=settings.MAX_USD_PER_RUN * 10)
    state = WorkspaceState(prompt=scenario["prompt"])
    persister.state = state
    cfg = flows.FlowConfig(
        llm=llm,
        build_model=settings.BUILD_MODEL,
        sync_model=settings.SYNC_MODEL,
        batch_threads=settings.BATCH_THREADS,
        inline_max_chars=settings.DATA_INLINE_MAX_CHARS,
    )
    checks: list[Check] = []
    steps_out: list[dict[str, Any]] = []
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
        steps_out.append(
            {
                "name": step["name"],
                "kind": kind,
                "summary": summary,
                "error": error,
                "cost_usd": round(persister.cost - cost0, 5),
                "input_tokens": persister.input_tokens - tin0,
                "output_tokens": persister.output_tokens - tout0,
                "latency_s": round(latency, 1),
                "records": sum(len(r) for r in state.data.values()),
                "sources_valid": [ok_src, n_src],
                "app_renders": app_text is not None and not app_errors,
                "no_change_sync": kind == "sync" and summary == "No new emails",
            }
        )
        prev_data = view.data
    sdir = out_dir / scenario["id"]
    sdir.mkdir(parents=True, exist_ok=True)
    (sdir / "data.json").write_text(json.dumps(state.data, indent=2))
    (sdir / "guide.md").write_text(state.guide)
    (sdir / "app.html").write_text(state.app_html or "")
    (sdir / "events.json").write_text(json.dumps(persister.events, indent=1))
    return {
        "id": scenario["id"],
        "built": built,
        "expect_build": not any(
            c.get("kind") == "build_fails" for s in scenario["steps"] for c in s.get("expect", [])
        ),
        "steps": steps_out,
        "checks": [asdict(c) for c in checks],
        "queries": state.queries,
    }


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

    return {
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


def report_md(m: dict[str, Any], results: list[dict[str, Any]], repeats: int) -> str:
    lines = [
        f"# Agent eval — {datetime.now(UTC):%Y-%m-%d %H:%M} UTC",
        "",
        f"Models: build `{settings.BUILD_MODEL}`, sync `{settings.SYNC_MODEL}`. "
        f"Repeats: {repeats}. Total cost: ${m['total_cost_usd']}.",
        "",
        "| Metric | Value | Target | Met |",
        "|---|---|---|---|",
    ]
    for key, (op, target) in TARGETS.items():
        v = m[key]
        met = "—" if v is None else ("✅" if (v >= target if op == "≥" else v <= target) else "❌")
        lines.append(f"| {key} | {v} | {op} {target} | {met} |")
    lines.append(f"| injection_resistance | {m['injection_resistance']} | pass | |")
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
        passed = sum(c["passed"] for c in r["checks"])
        lines.append(f"### {r['id']} — {passed}/{len(r['checks'])} checks")
        for s in r["steps"]:
            lines.append(
                f"- **{s['name']}** ({s['kind']}): {s['records']} records, ${s['cost_usd']}, "
                f"{s['latency_s']}s{' — ERROR ' + s['error'] if s['error'] else ''}"
            )
        for c in r["checks"]:
            if not c["passed"]:
                lines.append(f"  - ❌ {c['step']} `{json.dumps(c['spec'])}` {c['detail']}")
        lines.append("")
    return "\n".join(lines)


async def run_all(ids: list[str] | None, repeats: int) -> Path:
    llm = OpenAICompatibleLLM()
    out = RUNS / datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    results = []
    for rep in range(repeats):
        for scenario, folder in load_scenarios(ids):
            print(f"[{rep + 1}/{repeats}] {scenario['id']} …", flush=True)
            r = await run_scenario(scenario, folder, llm, out / f"rep{rep + 1}")
            r["repeat"] = rep + 1
            passed = sum(c["passed"] for c in r["checks"])
            cost = sum(s["cost_usd"] for s in r["steps"])
            print(f"    {passed}/{len(r['checks'])} checks, ${cost:.3f}", flush=True)
            results.append(r)
            (out / "report.json").write_text(
                json.dumps({"metrics": metrics(results), "results": results}, indent=1)
            )
    m = metrics(results)
    (out / "report.json").write_text(json.dumps({"metrics": m, "results": results}, indent=1))
    (out / "report.md").write_text(report_md(m, results, repeats))
    return out
