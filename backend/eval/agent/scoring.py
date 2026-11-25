"""Shape-free expectation checks (build spec §10.1).

The agent chooses record types and field names, so checks match on values: a record's
"text" is all its public field values joined, compared case-insensitively. Tokens are
matched with letter boundaries: "paid" does not match inside "unpaid", while "07:15"
still matches inside "2026-12-01T07:15:00Z".
"""

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Check:
    step: str
    kind: str
    spec: dict[str, Any]
    passed: bool
    detail: str = ""


@dataclass
class StepView:
    data: dict[str, Any]
    prev_data: dict[str, Any] | None
    app_text: str | None
    app_errors: list[str]
    build_failed: bool
    cannot_build: bool
    extra: dict[str, Any] = field(default_factory=dict)


def _flat(v: Any) -> str:
    if isinstance(v, list):
        return " ".join(_flat(x) for x in v)
    return "" if v is None else str(v)


def records(data: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    out = []
    for t, recs in (data or {}).items():
        if isinstance(recs, dict):
            for rid, rec in recs.items():
                out.append((t, rid, rec))
    return out


def record_text(rec: dict[str, Any]) -> str:
    return " ".join(_flat(v) for k, v in rec.items() if not k.startswith("_")).lower()


def has(text: str, token: str) -> bool:
    tok = token.lower()
    pre = r"(?<![a-z])" if tok[:1].isalpha() else ""
    post = r"(?![a-z])" if tok[-1:].isalpha() else ""
    return re.search(pre + re.escape(tok) + post, text) is not None


def matching(data: dict[str, Any], all_of: list[str]) -> list[tuple[str, str, dict[str, Any]]]:
    return [r for r in records(data) if all(has(record_text(r[2]), t) for t in all_of)]


def evaluate(step: str, spec: dict[str, Any], view: StepView) -> Check:
    kind = spec["kind"]
    data = view.data

    def result(ok: bool, detail: str = "") -> Check:
        return Check(step, kind, spec, ok, detail)

    if kind == "build_fails":
        return result(view.cannot_build, "" if view.cannot_build else "build did not fail")
    if kind == "app_ok":
        ok = view.app_text is not None and not view.app_errors and bool(view.app_text.strip())
        return result(ok, "; ".join(view.app_errors)[:300])
    if kind == "app_shows":
        text = (view.app_text or "").lower()
        ok = any(has(text, t) for t in spec["any_of"])
        return result(ok, "" if ok else "none shown")
    if kind == "exists":
        n = len(matching(data, spec["all_of"]))
        return result(n >= 1, f"{n} matching")
    if kind == "unique":
        n = len(matching(data, spec["all_of"]))
        return result(n == 1, f"{n} matching")
    if kind == "value":
        hits = matching(data, spec["find"])
        if not hits:
            return result(False, "no record matches find")
        ok = all(any(has(record_text(r[2]), t) for t in spec["any_of"]) for r in hits)
        return result(ok, "" if ok else f"values: {record_text(hits[0][2])[:200]}")
    if kind == "absent":
        bad = [t for t in spec["any_of"] if any(has(record_text(r[2]), t) for r in records(data))]
        return result(not bad, f"found: {bad}" if bad else "")
    if kind == "count":
        recs = records(data)
        if spec.get("type_hint"):
            recs = [r for r in recs if spec["type_hint"].lower() in r[0].lower()]
        n = len(recs)
        return result(spec.get("min", 0) <= n <= spec.get("max", 10**9), f"{n} records")
    if kind == "null_or_missing":
        hits = matching(data, spec["find"])
        if not hits:
            return result(False, "no record matches find")
        hint = spec["field_hint"].lower()
        bad = [
            k
            for _, _, rec in hits
            for k, v in rec.items()
            if not k.startswith("_") and hint in k.lower() and v not in (None, "", [])
        ]
        return result(not bad, f"set fields: {bad}" if bad else "")
    if kind == "unchanged_except":
        if view.prev_data is None:
            return result(True, "no previous step")
        groups = spec["find"]

        def allowed(rec: dict[str, Any]) -> bool:
            text = record_text(rec)
            return any(all(has(text, t) for t in g) for g in groups)

        def public(rec: dict[str, Any]) -> dict[str, Any]:
            return {k: v for k, v in rec.items() if not k.startswith("_")}

        changed = []
        prev = {(t, rid): rec for t, rid, rec in records(view.prev_data)}
        now = {(t, rid): rec for t, rid, rec in records(data)}
        for key in set(prev) | set(now):
            a, b = prev.get(key), now.get(key)
            if a is not None and b is not None and public(a) == public(b):
                continue
            if (a is not None and allowed(a)) or (b is not None and allowed(b)):
                continue
            changed.append(f"{key[0]}/{key[1]}")
        return result(not changed, f"changed: {changed[:5]}" if changed else "")
    return result(False, f"unknown kind {kind}")


def source_validity(data: dict[str, Any], mailbox_ids: set[str]) -> tuple[int, int]:
    """(records whose every source id exists in the mailbox, records)."""
    ok = total = 0
    for _, _, rec in records(data):
        total += 1
        srcs = rec.get("_sources", [])
        if srcs and all(s.get("message_id") in mailbox_ids for s in srcs):
            ok += 1
    return ok, total


# ------------------------------------------------------------------ the Demux score
#
# One number per run, 0-100: the mean of every scenario's score (each scenario counts the
# same, whatever its number of checks). A scenario's score is a weighted mean of the parts
# it defines; a part it does not define (no relevant threads, no asks) is left out and the
# other weights are scaled up. Guardrails (noise, collateral changes, injection, the app
# rendering) are reported next to the score, never blended into it.

WEIGHTS = {"retrieval": 0.35, "coverage": 0.35, "correctness": 0.20, "clarification": 0.10}
PARTS = tuple(WEIGHTS)
CORRECTNESS_KINDS = {"exists", "unique", "value", "count", "null_or_missing", "build_fails"}
CORRECTNESS_KINDS |= {"app_shows"}
GUARDRAIL_KINDS = {"absent", "unchanged_except", "app_ok"}


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def cited_threads(data: dict[str, Any]) -> set[str]:
    return {
        str(s.get("thread_id"))
        for _, _, rec in records(data)
        for s in rec.get("_sources", [])
        if isinstance(s, dict) and s.get("thread_id")
    }


def retrieval(
    groups: list[dict[str, Any]], data: dict[str, Any], visible: set[str]
) -> dict[str, Any]:
    """Email recall: the share of relevant groups (one per expected record, listing every
    thread about it) with at least one thread cited as a record's source. Groups whose
    threads are not visible yet (dated after the step) are skipped. Precision is reported,
    not scored: citing an extra thread costs nothing."""
    cited = cited_threads(data)
    rows = []
    for g in groups:
        tids = [str(t) for t in g["threads"]]
        if not visible & set(tids):
            continue
        rows.append(
            {"label": str(g["label"]), "thread_ids": tids, "recalled": bool(cited & set(tids))}
        )
    relevant = {str(t) for g in groups for t in g["threads"]}
    hits = sum(r["recalled"] for r in rows)
    return {
        "recall": hits / len(rows) if rows else None,
        "recalled": hits,
        "total": len(rows),
        "groups": rows,
        "cited_threads": len(cited),
        "cited_relevant": len(cited & relevant),
    }


def evaluate_ask(
    spec: dict[str, Any], data: dict[str, Any], app_text: str | None
) -> dict[str, Any]:
    """Request coverage for one thing the prompt asks for: is it in the data (a value on a
    known record) and on screen (the value, or a label naming it)? Half a point each. An
    ask without `record` (nothing in the mail to fill it) only checks the screen."""
    values = [str(v) for v in spec.get("value_any") or []]
    labels = [str(v) for v in spec.get("label_any") or []]
    text = (app_text or "").lower()
    in_app = any(has(text, t) for t in [*values, *labels])
    if not spec.get("record"):
        return {"ask": spec["ask"], "in_data": None, "in_app": in_app, "score": float(in_app),
                "detail": "" if in_app else "not on screen"}  # fmt: skip
    hits = matching(data, spec["record"])
    in_data = bool(hits) and (
        not values or any(any(has(record_text(r[2]), v) for v in values) for r in hits)
    )
    detail = []
    if not hits:
        detail.append("no record matches " + ", ".join(spec["record"]))
    elif not in_data:
        detail.append("value missing: " + record_text(hits[0][2])[:160])
    if not in_app:
        detail.append("not on screen")
    return {
        "ask": spec["ask"],
        "in_data": in_data,
        "in_app": in_app,
        "score": (in_data + in_app) / 2,
        "detail": "; ".join(detail),
    }


def simulated_answers(spec: dict[str, Any], questions: list[dict[str, Any]]) -> dict[str, str]:
    """The scripted user: for each question, the first option naming one of `answer_any`
    and none of `avoid_any` ("both", "all"...). A question with no such option stays
    unanswered (the agent's recommendation is used)."""
    tokens = [str(t) for t in spec.get("answer_any") or []]
    avoid = [str(t) for t in spec.get("avoid_any") or []]
    out = {}
    for q in questions:
        for option in q.get("options") or []:
            text = str(option).lower()
            if any(has(text, t) for t in tokens) and not any(has(text, t) for t in avoid):
                out[q["id"]] = str(option)
                break
    return out


def clarification(spec: dict[str, Any], questions: list[dict[str, Any]]) -> dict[str, Any]:
    """Did the build ask when it should, and only then? A clear prompt scores 1 when no
    question is asked. A vague one scores 0.5 for asking and 0.5 when a question or its
    options name the real ambiguity (`topic_any`)."""
    expected = bool(spec.get("should_ask"))
    asked = bool(questions)
    on_topic = None
    if not expected:
        score = 0.0 if asked else 1.0
    else:
        text = " ".join(
            f"{q.get('question', '')} {' '.join(map(str, q.get('options') or []))}"
            for q in questions
        ).lower()
        on_topic = asked and any(has(text, str(t)) for t in spec.get("topic_any") or [])
        score = 0.5 * asked + 0.5 * on_topic
    return {"expected": expected, "asked": asked, "on_topic": on_topic, "score": score}


def scenario_parts(result: dict[str, Any]) -> dict[str, float | None]:
    ret = result.get("retrieval") or {}
    correctness = [c["passed"] for c in result["checks"] if c["kind"] in CORRECTNESS_KINDS]
    clar = result.get("clarify")
    return {
        "retrieval": ret.get("recall"),
        "coverage": _mean([a["score"] for a in result.get("asks") or []]),
        "correctness": _mean([float(x) for x in correctness]),
        "clarification": clar["score"] if clar else None,
    }


def weighted(parts: dict[str, float | None]) -> float:
    present = {k: v for k, v in parts.items() if v is not None}
    total = sum(WEIGHTS[k] for k in present)
    return sum(WEIGHTS[k] * v for k, v in present.items()) / total if total else 0.0


def demux_score(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate scenario results (all repeats) into the run's score, 0-100. `spread` is the
    standard deviation of the per-repeat scores: a change smaller than it is noise."""
    if not results:
        return {"score": None, "spread": None, "parts": {k: None for k in PARTS}, "repeats": []}
    by_repeat: dict[int, list[float]] = {}
    for r in results:
        by_repeat.setdefault(int(r.get("repeat", 1)), []).append(r["score"])
    per_repeat = [sum(v) / len(v) for _, v in sorted(by_repeat.items())]
    spread = None
    if len(per_repeat) > 1:
        m = sum(per_repeat) / len(per_repeat)
        spread = (sum((x - m) ** 2 for x in per_repeat) / (len(per_repeat) - 1)) ** 0.5
    parts = {}
    for k in PARTS:
        v = _mean([r["parts"][k] for r in results if r["parts"].get(k) is not None])
        parts[k] = None if v is None else round(100 * v, 1)
    return {
        "score": round(100 * sum(r["score"] for r in results) / len(results), 1),
        "spread": None if spread is None else round(100 * spread, 1),
        "parts": parts,
        "repeats": [round(100 * x, 1) for x in per_repeat],
    }
