"""Planner benchmark runner. Costs money (LLM calls); not run in CI.

    cd backend && uv run python -m eval.planner [--all] [--real] [--stability]
        [--case ID] [--thinking on|off] [--provider P] [--rescore runs/<run_id>]

Writes `runs/<UTC-timestamp>_<model>_<provider>/{responses/*.json, report.json, report.md}`
and exits 1 if any threshold fails. `--rescore` re-scores saved responses without LLM calls.
"""

import argparse
import dataclasses
import hashlib
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import yaml
from pydantic import TypeAdapter

from app.pipeline.email_clean import clean_thread
from app.pipeline.planner.llm import LLMConfig
from app.pipeline.planner.models import Schema, Thread
from app.pipeline.planner.plan import plan
from app.pipeline.planner.prompts import SYSTEM_PROMPT, render_user_prompt
from app.pipeline.sampling import sample_threads
from eval.planner.normalize import normalize_schema
from eval.planner.scoring import aggregate, load_expected, score_case, stability

ROOT = Path(__file__).parent
RUNS = ROOT / "runs"
THREADS = TypeAdapter(list[Thread])


def load_cases(args: argparse.Namespace) -> list[Path]:
    dirs = sorted(p.parent for p in (ROOT / "cases").glob("*/request.yaml"))
    if args.real:
        dirs += sorted(p.parent for p in (ROOT / "real").glob("*/request.yaml"))
    if args.case:
        return [d for d in dirs if d.name == args.case]
    if args.all:
        return dirs
    return [d for d in dirs if not yaml.safe_load((d / "request.yaml").read_text()).get("holdout")]


def git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def run_one(case_dir: Path, prompt: str, config: LLMConfig, out: Path, suffix: str) -> dict:
    threads = THREADS.validate_json((case_dir / "threads.json").read_text())
    sampled = sample_threads([clean_thread(t) for t in threads])
    result = plan(prompt, threads, config)
    record = {
        "case": case_dir.name,
        "variant": suffix or "main",
        "prompt_sent": {"system": SYSTEM_PROMPT, "user": render_user_prompt(prompt, sampled)},
        "raw_responses": result.raw_responses,
        "schema": result.schema.model_dump(mode="json") if result.schema else None,
        "errors": result.errors,
        "valid_first_try": result.valid_first_try,
        "attempts": result.attempts,
        "usage": dataclasses.asdict(result.usage),
        "latency_ms": result.latency_ms,
    }
    (out / "responses" / f"{case_dir.name}{suffix}.json").write_text(json.dumps(record, indent=2))
    return record


def load_record(path: Path) -> tuple[Schema | None, SimpleNamespace]:
    rec = json.loads(path.read_text())
    schema = Schema.model_validate(rec["schema"]) if rec["schema"] else None
    result = SimpleNamespace(
        valid_first_try=rec["valid_first_try"],
        latency_ms=rec["latency_ms"],
        usage=SimpleNamespace(**rec["usage"]),
    )
    return schema, result


def score_run(
    run_dir: Path,
    case_dirs: list[Path],
    with_stability: bool,
    prices: dict,
    config: LLMConfig,
    normalize: bool = True,
) -> dict:
    scores, stabs, per_case, renames = [], [], {}, {}
    cache = run_dir / "normalization.json"

    def norm(schema, expected, key):
        if not normalize:
            return schema
        out, applied = normalize_schema(schema, expected, key, cache, config)
        if applied:
            renames[key] = applied
        return out

    for d in case_dirs:
        main = run_dir / "responses" / f"{d.name}.json"
        if not main.exists():
            continue
        expected = load_expected(str(d / "expected.yaml"))
        schema, result = load_record(main)
        schema = norm(schema, expected, d.name)
        cs = score_case(schema, expected, result, d.name)
        scores.append(cs)
        per_case[d.name] = dataclasses.asdict(cs)
        variants = [run_dir / "responses" / f"{d.name}__p{i}.json" for i in (1, 2)]
        if with_stability and all(v.exists() for v in variants):
            others = [norm(load_record(v)[0], expected, v.stem) for v in variants]
            stabs.append(stability([schema] + others, expected))
    return {
        "aggregate": aggregate(scores, stabs or None, prices),
        "cases": per_case,
        "normalization": renames,
    }


def outcomes(run_dir: Path, case_dirs: list[Path]) -> dict[str, str]:
    out = {}
    for d in case_dirs:
        f = run_dir / "responses" / f"{d.name}.json"
        if f.exists():
            schema = json.loads(f.read_text())["schema"]
            out[d.name] = schema["outcome"] if schema else "none (invalid)"
    return out


def render_md(report: dict, baseline: dict | None) -> str:
    cfg = report["config"]
    lines = [
        f"# Planner benchmark — {cfg['model']} via {cfg['provider']}",
        f"git `{cfg['git_sha']}` · thinking={cfg['thinking']} · temp={cfg['temperature']} · "
        f"prompt hash `{cfg['prompt_hash']}`",
        "",
        "| Metric | Value | Threshold | | Δ baseline |",
        "|---|---|---|---|---|",
    ]
    base_metrics = (baseline or {}).get("aggregate", {}).get("metrics", {})
    for name, m in report["aggregate"]["metrics"].items():
        v = m["value"]
        mark = "—" if m["passed"] is None else ("✅" if m["passed"] else "❌")
        sign = m["direction"].replace(">=", "≥").replace("<=", "≤")
        delta = ""
        if v is not None and base_metrics.get(name, {}).get("value") is not None:
            delta = f"{v - base_metrics[name]['value']:+.3f}"
        shown = "n/a" if v is None else f"{v:.3f}"
        lines.append(f"| {name} | {shown} | {sign} {m['threshold']} | {mark} | {delta} |")
    rep = report["aggregate"]["reported"]
    lines += [
        "",
        f"Latency p50/p95: {rep['latency_p50_ms']} / {rep['latency_p95_ms']} ms · "
        f"cost per call: {rep['cost_per_call']} · total: {rep['cost_total']}",
        "",
        "## Per case",
    ]
    keys = [
        "missing_record_types",
        "extra_record_types",
        "missing_fields",
        "extra_fields",
        "wrong_source",
        "wrong_type",
        "wrong_support",
        "forbidden_record_types_hit",
        "forbidden_fields_hit",
    ]
    for case, cs in report["cases"].items():
        got = report.get("outcomes", {}).get(case, "none (invalid)")
        lines.append(
            f"\n### {case} — outcome {'✅' if cs['outcome_correct'] else f'❌ (got {got})'}"
        )
        diffs = [f"- {k}: {cs[k]}" for k in keys if cs.get(k)]
        lines += diffs or ["- no differences"]
    if report.get("normalization"):
        lines += ["", "## Name normalisation applied (planner -> label)"]
        for key, items in report["normalization"].items():
            lines.append(f"- {key}: " + "; ".join(items))
    return "\n".join(lines) + "\n"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--all", action="store_true", help="include holdout cases")
    p.add_argument("--real", action="store_true", help="add real cases")
    p.add_argument("--stability", action="store_true", help="also run the 2 paraphrases")
    p.add_argument("--case")
    p.add_argument("--thinking", choices=["on", "off"])
    p.add_argument("--provider")
    p.add_argument("--rescore", type=Path)
    p.add_argument("--resume", type=Path, help="continue a run: skip responses already saved")
    p.add_argument("--workers", type=int, default=4, help="parallel LLM calls")
    p.add_argument("--max-tokens", type=int, help="output budget (default 12000 with thinking)")
    p.add_argument("--no-normalize", action="store_true", help="strict name matching only")
    args = p.parse_args()

    config = LLMConfig.from_settings()
    if args.thinking:
        config.thinking = args.thinking == "on"
    if args.provider:
        config.provider = args.provider
    if args.max_tokens:
        config.max_tokens = args.max_tokens
    elif config.thinking:
        config.max_tokens = max(config.max_tokens, 12000)  # thinking tokens share the budget
    prices_all = yaml.safe_load((ROOT / "prices.yaml").read_text())
    prices = prices_all.get(config.provider, prices_all["default"])
    case_dirs = load_cases(args)

    if args.rescore:
        run_dir = args.rescore if args.rescore.is_absolute() else ROOT / args.rescore
        base_cfg = json.loads((run_dir / "report.json").read_text())["config"]
        with_stability = args.stability or base_cfg.get("stability", False)
        config_dict = base_cfg
    else:
        if args.resume:
            run_dir = args.resume if args.resume.is_absolute() else ROOT / args.resume
        else:
            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            model = config.model.replace("/", "-")
            run_dir = RUNS / f"{stamp}_{model}_{config.provider}"
        (run_dir / "responses").mkdir(parents=True, exist_ok=True)
        jobs = []
        for d in case_dirs:
            req = yaml.safe_load((d / "request.yaml").read_text())
            jobs.append((d, req["prompt"], ""))
            if args.stability:
                jobs += [(d, para, f"__p{i}") for i, para in enumerate(req["paraphrases"], 1)]
        jobs = [j for j in jobs if not (run_dir / "responses" / f"{j[0].name}{j[2]}.json").exists()]

        def work(job):
            d, prompt, suffix = job
            try:
                run_one(d, prompt, config, run_dir, suffix)
                print(f"done {d.name}{suffix}", file=sys.stderr, flush=True)
            except Exception as exc:  # noqa: BLE001 - one failed call must not lose the run
                print(f"FAILED {d.name}{suffix}: {type(exc).__name__}", file=sys.stderr, flush=True)

        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            list(pool.map(work, jobs))
        with_stability = args.stability
        config_dict = {
            "model": config.model,
            "provider": config.provider,
            "thinking": config.thinking,
            "temperature": config.temperature,
            "git_sha": git_sha(),
            "stability": with_stability,
            "prompt_hash": hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()[:10],
        }

    scored = score_run(
        run_dir, case_dirs, with_stability, prices, config, normalize=not args.no_normalize
    )
    report = {"config": config_dict, **scored, "outcomes": outcomes(run_dir, case_dirs)}
    baseline = None
    pointer = RUNS / "BASELINE"
    if pointer.exists():
        bp = RUNS / pointer.read_text().strip() / "report.json"
        baseline = json.loads(bp.read_text()) if bp.exists() else None
    (run_dir / "report.json").write_text(json.dumps(report, indent=2))
    (run_dir / "report.md").write_text(render_md(report, baseline))
    print(f"report: {run_dir / 'report.md'}")
    sys.exit(0 if report["aggregate"]["passed"] else 1)


if __name__ == "__main__":
    main()
