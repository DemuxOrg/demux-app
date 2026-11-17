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
