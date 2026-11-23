"""Cost and latency benchmark for the agent (real LLM calls, synthetic mail).

    uv run python -m eval.agent.bench [--repeats 3] [--only builds|syncs|scenarios]

Experiments, all written as one JSON line each to `eval/agent/runs/bench-<ts>/results.jsonl`:
  * build     3 personas x 3 email volumes (low / mid / high) x repeats
  * sync      from a finished build of every persona x volume, with k new messages
  * scenario  every step (build, sync, edit) of the eval scenarios, once per repeat

Runs are sequential so that wall-clock times are not distorted by our own concurrency.
Each line has wall time, tokens, cost, thread and record counts, and a per-phase
breakdown (design / process / app / edit) of calls, tokens, cost and LLM time.
"""

import argparse
import asyncio
import json
import logging
import shutil
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from app.agent import flows, prompts
from app.agent.context import MemoryPersister, RunContext, WorkspaceState
from app.agent.default_app import DEFAULT_APP
from app.agent.llm import LLMReply, OpenAICompatibleLLM, cost_usd
from app.core.config import settings
from app.mail.fake import FakeMailbox
from eval.agent.bench.mailgen import PROMPTS, generate

ROOT = Path(__file__).resolve().parents[1]
T0 = datetime(2026, 10, 20, 9, 0, tzinfo=UTC)
# volume tier -> (threads to track, noise threads) in the 90-day window
TIERS = {"low": (10, 15), "mid": (40, 60), "high": (160, 120)}
SYNC_KS = [1, 3, 10, 30]


class RecordingLLM:
    """Wraps the real client and records every call with the phase it belongs to."""

    def __init__(self) -> None:
        self.inner = OpenAICompatibleLLM()
        self.calls: list[dict[str, Any]] = []

    @staticmethod
    def _phase(messages: list[dict[str, Any]]) -> str:
        system = messages[0]["content"]
        if system == prompts.PROCESS:
            return "process"
        if system == prompts.APP:
            return "app"
        if system == prompts.EDIT:
            return "edit"
        return "design"

    async def chat(self, model: str, messages: list[dict[str, Any]], tools: list[dict]) -> LLMReply:
        t = time.perf_counter()
        reply = await self.inner.chat(model, messages, tools)
        self.calls.append(
            {
                "phase": self._phase(messages),
                "model": reply.model or model,
                "in": reply.input_tokens,
                "out": reply.output_tokens,
                "s": round(time.perf_counter() - t, 3),
                "cost": cost_usd(reply.model or model, reply.input_tokens, reply.output_tokens),
            }
        )
        return reply


class RetryCounter(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.n = 0

    def emit(self, record: logging.LogRecord) -> None:
        self.n += 1


def _phases(calls: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for c in calls:
        p = out.setdefault(c["phase"], {"calls": 0, "in": 0, "out": 0, "cost": 0.0, "llm_s": 0.0})
        p["calls"] += 1
        p["in"] += c["in"]
        p["out"] += c["out"]
        p["cost"] += c["cost"]
        p["llm_s"] += c["s"]
    return out


def _ctx(state: WorkspaceState, box: FakeMailbox, persister: MemoryPersister, now: datetime):
    box.now = now
    return RunContext(
        state=state,
        mailbox=box,
        persister=persister,
        run_id=f"bench-{uuid.uuid4().hex[:8]}",
        now=now,
        lookback_days=settings.LOOKBACK_DAYS,
        max_build_threads=settings.BUILD_MAX_THREADS,
        inline_max_chars=settings.DATA_INLINE_MAX_CHARS,
    )


async def measure(kind: str, ctx: RunContext, persister: MemoryPersister, message: str = ""):
    """Run one flow; return the measurements common to every experiment."""
    llm = RecordingLLM()
    cfg = flows.FlowConfig.from_settings(llm)
    retries = RetryCounter()
    logging.getLogger("app.agent.llm").addHandler(retries)
    n_events, n_processed = len(persister.events), len(persister.processed)
    threads_before = set(persister.processed.values())
    error = None
    t = time.perf_counter()
    started = time.time()
    try:
        if kind == "build":
            await flows.build(ctx, cfg)
        elif kind == "sync":
            await flows.sync(ctx, cfg)
        else:
            await flows.edit(ctx, cfg, message, [])
    except Exception as e:  # noqa: BLE001 - a failed run is a data point
        error = f"{type(e).__name__}: {str(e)[:160]}"
    wall = time.perf_counter() - t
    logging.getLogger("app.agent.llm").removeHandler(retries)
    events = persister.events[n_events:]
    first_process = next((e["t"] for e in events if e["phase"] == "process"), None)
    data = ctx.state.data
    return {
        "kind": kind,
        "wall_s": round(wall, 2),
        "design_s": round(first_process - started, 2)
        if first_process and kind == "build"
        else None,
        "error": error,
        "llm_calls": len(llm.calls),
        "llm_retries": retries.n,
        "fallback_calls": sum(1 for c in llm.calls if c["model"] != settings.BUILD_MODEL),
        "in": sum(c["in"] for c in llm.calls),
        "out": sum(c["out"] for c in llm.calls),
        "cost": round(sum(c["cost"] for c in llm.calls), 6),
        "phases": _phases(llm.calls),
        "messages_processed": len(persister.processed) - n_processed,
        "threads_processed": len(set(persister.processed.values()) - threads_before)
        if kind == "build"
        else len({e["label"] for e in events if "threads" in e["label"]}),
        "records": sum(len(r) for r in data.values()),
        "data_chars": len(json.dumps(data)),
        "guide_chars": len(ctx.state.guide),
        "app_chars": len(ctx.state.app_html or ""),
        "default_app": ctx.state.app_html == DEFAULT_APP,
        "queries": len(ctx.state.queries),
        "model": settings.BUILD_MODEL,
    }


def _write(out: Path, row: dict[str, Any]) -> None:
    with (out / "results.jsonl").open("a") as f:
        f.write(json.dumps(row) + "\n")
    tag = " ".join(str(row.get(k, "")) for k in ("exp", "persona", "tier", "scenario", "step", "k"))
    print(
        f"{tag:48s} {row['wall_s']:6.1f}s ${row['cost']:.4f} in={row['in']} out={row['out']} "
        f"threads={row['threads_processed']} recs={row['records']} "
        f"{'ERR ' + row['error'] if row['error'] else ''}",
        flush=True,
    )


def _mailbox(out: Path, persona: str, tier: str) -> Path:
    path = out / "mailboxes" / f"{persona}-{tier}.json"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        n_rel, n_noise = TIERS[tier]
        path.write_text(json.dumps(generate(persona, n_rel, n_noise, T0, n_future=40)))
    return path


async def run_builds(out: Path, repeats: int, tiers: list[str] | None = None) -> None:
    for rep in range(repeats):
        for tier in tiers or TIERS:
            for persona in PROMPTS:
                state_dir = out / "states" / f"{persona}-{tier}-{rep}"
                box = FakeMailbox.from_file(_mailbox(out, persona, tier))
                persister = MemoryPersister(state_dir, max_usd=settings.MAX_USD_PER_RUN)
                state = WorkspaceState(prompt=PROMPTS[persona])
                persister.state = state
                row = await measure("build", _ctx(state, box, persister, T0), persister)
                persister._dump(state)
                _write(out, {"exp": "build", "persona": persona, "tier": tier, "rep": rep, **row})


async def run_syncs(out: Path, repeats: int) -> None:
    for tier in TIERS:
        for persona in PROMPTS:
            base = out / "states" / f"{persona}-{tier}-0"
            if not (base / "state.json").exists():
                continue
            if not json.loads((base / "state.json").read_text())["data"]:
                continue
            for k in SYNC_KS:
                for rep in range(repeats):
                    work = out / "tmp-sync"
                    shutil.rmtree(work, ignore_errors=True)
                    shutil.copytree(base, work)
                    persister, state = MemoryPersister.load(work)
                    persister.max_usd = settings.MAX_USD_PER_RUN
                    box = FakeMailbox.from_file(_mailbox(out, persona, tier))
                    now = T0 + timedelta(minutes=10 * k + 1)
                    row = await measure("sync", _ctx(state, box, persister, now), persister)
                    _write(
                        out,
                        {
                            "exp": "sync",
                            "persona": persona,
                            "tier": tier,
                            "k": k,
                            "rep": rep,
                            **row,
                        },
                    )
            shutil.rmtree(out / "tmp-sync", ignore_errors=True)


async def run_scenarios(out: Path, repeats: int) -> None:
    for rep in range(repeats):
        for folder in sorted((ROOT / "scenarios").iterdir()):
            spec = folder / "scenario.yaml"
            if not spec.exists() or folder.name.startswith("08"):
                continue
            scenario = yaml.safe_load(spec.read_text())
            box = FakeMailbox.from_file(folder / "mailbox.json")
            persister = MemoryPersister(max_usd=settings.MAX_USD_PER_RUN * 10)
            state = WorkspaceState(prompt=scenario["prompt"])
            persister.state = state
            now = T0
            for step in scenario["steps"]:
                if step.get("now"):
                    now = datetime.fromisoformat(str(step["now"]).replace("Z", "+00:00"))
                    now = now if now.tzinfo else now.replace(tzinfo=UTC)
                kind = (
                    "edit"
                    if "message" in step
                    else "build"
                    if step["name"].startswith("build")
                    else "sync"
                )
                ctx = _ctx(state, box, persister, now)
                row = await measure(kind, ctx, persister, step.get("message", ""))
                _write(
                    out,
                    {
                        "exp": "scenario",
                        "scenario": folder.name[:2],
                        "step": step["name"],
                        "rep": rep,
                        **row,
                    },
                )
                if row["error"] and kind == "build":
                    break


async def main() -> None:
    ap = argparse.ArgumentParser(prog="eval.agent.bench")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--sync-repeats", type=int, default=2)
    ap.add_argument("--scenario-repeats", type=int, default=2)
    ap.add_argument("--only", choices=["builds", "syncs", "scenarios"])
    ap.add_argument("--out", help="continue in an existing run folder")
    ap.add_argument("--tiers", nargs="*", choices=list(TIERS), help="build volumes (default: all)")
    args = ap.parse_args()
    out = Path(args.out) if args.out else ROOT / "runs" / f"bench-{datetime.now():%Y%m%d-%H%M%S}"
    out.mkdir(parents=True, exist_ok=True)
    print(f"model={settings.BUILD_MODEL} effort={settings.LLM_REASONING_EFFORT!r} out={out}")
    if args.only in (None, "builds"):
        await run_builds(out, args.repeats, args.tiers)
    if args.only in (None, "syncs"):
        await run_syncs(out, args.sync_repeats)
    if args.only in (None, "scenarios"):
        await run_scenarios(out, args.scenario_repeats)
    print(f"results: {out / 'results.jsonl'}")


if __name__ == "__main__":
    asyncio.run(main())
