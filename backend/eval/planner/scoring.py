"""Deterministic scoring for the planner benchmark. Pure functions: no LLM, no I/O
(except the optional `load_expected` helper).

Public API
----------
load_expected(path) -> dict
    Parse an expected.yaml (see FORMAT.md) into a dict.

normalise(name) -> str
    Lowercase, strip `_`, `-` and spaces, strip one trailing `s`. Used for all name matching.

score_case(schema, expected, result=None, case_id="") -> CaseScore
    Score one planner output against one label. `schema` is a `Schema` or None (invalid after
    retry: outcome wrong, nothing matched). `expected` is the parsed expected.yaml dict.
    `result` is optional and PlanResult-like (attributes `valid_first_try`, `latency_ms`,
    `usage.input_tokens`, `usage.output_tokens`); it fills the run fields of the score.
    Record types are matched first (name or synonyms, one-to-one); fields are matched only
    inside matched record types. A produced record type matching `forbidden_record_types`
    counts as produced-but-wrong. Cases whose expected outcome is not `ok` only contribute
    to outcome accuracy, valid-first-try and latency (`CaseScore.full` is False).

CaseScore (dataclass): raw counts per metric
    outcome_correct; rt_labelled, rt_produced, rt_matched, source_correct;
    req_total, req_found; fields_matched, type_correct, support_correct;
    overgen_weighted (non-allowed fields, forbidden counted double), overgen_rts (matched
    record types, the denominator); valid_first_try, latency_ms, input_tokens, output_tokens
    (None when no `result`).
    Diff lists: missing_record_types, extra_record_types, missing_fields, extra_fields
    ("rt.field"), wrong_source ("rt: expected thread, got extracted"), wrong_type,
    wrong_support (same style), forbidden_record_types_hit, forbidden_fields_hit.

stability(schemas, expected) -> StabilityResult
    `schemas`: the outputs for the prompt and its 2 paraphrases (Schema | None each).
    Stable iff no schema is None, all outcomes are equal, the sets of matched labelled
    record types are equal, and the required fields found agree >= 0.8, measured as
    |intersection| / |union| of the sets of found (record type, required field) over runs
    (1.0 when the union is empty). For non-ok expected cases only the outcome is compared.
    StabilityResult: stable, same_outcome, same_record_types, field_agreement.

aggregate(case_scores, stability_results=None, prices=None, thresholds=None) -> dict
    Micro-averaged metrics over `case_scores` (list[CaseScore]).
    `stability_results`: list[StabilityResult] (one per case that was run with paraphrases).
    `prices`: {"input_per_mtok": float, "output_per_mtok": float}; enables cost.
    `thresholds`: overrides of THRESHOLDS by metric name.
    Returns {"metrics": {name: {"value", "threshold", "direction", "passed", "n"}},
             "reported": {"latency_p50_ms", "latency_p95_ms", "cost_per_call", "cost_total"},
             "passed": bool}
    Metric names: outcome_accuracy, record_type_recall, record_type_precision,
    source_accuracy, required_field_recall, over_generation, type_accuracy,
    support_accuracy, valid_first_try, stability. A metric without data has value None and
    passed None (ignored by the overall `passed`). Latency percentiles use nearest rank.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import yaml

THRESHOLDS: dict[str, tuple[str, float]] = {
    "outcome_accuracy": (">=", 0.90),
    "record_type_recall": (">=", 0.90),
    "record_type_precision": (">=", 0.85),
    "source_accuracy": (">=", 0.90),
    "required_field_recall": (">=", 0.85),
    "over_generation": ("<=", 1.0),
    "type_accuracy": (">=", 0.90),
    "support_accuracy": (">=", 0.85),
    "valid_first_try": (">=", 0.90),
    "stability": (">=", 0.80),
}

FIELD_AGREEMENT_MIN = 0.80


def load_expected(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def normalise(name: str) -> str:
    n = name.lower().replace("_", "").replace("-", "").replace(" ", "")
    return n[:-1] if n.endswith("s") else n


def _names(entry: dict | str) -> set[str]:
    if isinstance(entry, str):
        return {normalise(entry)}
    return {normalise(n) for n in [entry["name"], *(entry.get("synonyms") or [])]}


@dataclass
class CaseScore:
    case_id: str = ""
    full: bool = False  # expected outcome is ok: structure metrics apply
    outcome_expected: str = ""
    outcome_actual: str | None = None
    outcome_correct: bool = False

    rt_labelled: int = 0
    rt_produced: int = 0
    rt_matched: int = 0
    source_correct: int = 0
    req_total: int = 0
    req_found: int = 0
    fields_matched: int = 0
    type_correct: int = 0
    support_correct: int = 0
    overgen_weighted: int = 0
    overgen_rts: int = 0

    valid_first_try: bool | None = None
    latency_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None

    missing_record_types: list[str] = field(default_factory=list)
    extra_record_types: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    extra_fields: list[str] = field(default_factory=list)
    wrong_source: list[str] = field(default_factory=list)
    wrong_type: list[str] = field(default_factory=list)
    wrong_support: list[str] = field(default_factory=list)
    forbidden_record_types_hit: list[str] = field(default_factory=list)
    forbidden_fields_hit: list[str] = field(default_factory=list)


def _match_record_types(schema: Any, expected: dict) -> list[tuple[Any, dict]]:
    """One-to-one matches (produced record type, labelled record type), in produced order."""
    labelled = list(expected.get("record_types") or [])
    taken: set[int] = set()
    pairs = []
    for rt in schema.record_types:
        n = normalise(rt.name)
        for i, lab in enumerate(labelled):
            if i not in taken and n in _names(lab):
                taken.add(i)
                pairs.append((rt, lab))
                break
    return pairs


def _val(x: Any) -> str:
    return str(getattr(x, "value", x))


def score_case(
    schema: Any | None, expected: dict, result: Any | None = None, case_id: str = ""
) -> CaseScore:
    exp_outcome = expected.get("outcome", "ok")
    s = CaseScore(
        case_id=case_id,
        full=exp_outcome == "ok",
        outcome_expected=exp_outcome,
        outcome_actual=None if schema is None else schema.outcome,
    )
    s.outcome_correct = schema is not None and schema.outcome == exp_outcome
    if result is not None:
        s.valid_first_try = result.valid_first_try
        s.latency_ms = result.latency_ms
        s.input_tokens = result.usage.input_tokens
        s.output_tokens = result.usage.output_tokens
    if not s.full:
        return s

    labelled = list(expected.get("record_types") or [])
    forbidden_rts = {normalise(n) for n in expected.get("forbidden_record_types") or []}
    s.rt_labelled = len(labelled)
    s.req_total = sum(len(lab.get("required_fields") or []) for lab in labelled)

    if schema is None:
        s.missing_record_types = [lab["name"] for lab in labelled]
        s.missing_fields = [
            f"{lab['name']}.{f['name']}"
            for lab in labelled
            for f in lab.get("required_fields") or []
        ]
        return s

    s.rt_produced = len(schema.record_types)
    pairs = _match_record_types(schema, expected)
    matched_ids = {id(rt) for rt, _ in pairs}
    s.rt_matched = len(pairs)
    matched_labels = {id(lab) for _, lab in pairs}
    s.missing_record_types = [lab["name"] for lab in labelled if id(lab) not in matched_labels]
    for rt in schema.record_types:
        if id(rt) not in matched_ids:
            s.extra_record_types.append(rt.name)
            if normalise(rt.name) in forbidden_rts:
                s.forbidden_record_types_hit.append(rt.name)

    for rt, lab in pairs:
        if _val(rt.source) == lab.get("source"):
            s.source_correct += 1
        else:
            s.wrong_source.append(
                f"{lab['name']}: expected {lab.get('source')}, got {_val(rt.source)}"
            )

        required = list(lab.get("required_fields") or [])
        optional = {normalise(n) for n in lab.get("optional_fields") or []}
        forbidden_fields = {normalise(n) for n in lab.get("forbidden_fields") or []}
        found_req: set[int] = set()
        overgen = 0
        for f in rt.fields:
            n = normalise(f.name)
            hit = next((i for i, r in enumerate(required) if n in _names(r)), None)
            if hit is not None:
                if hit in found_req:
                    continue  # duplicate of an already matched field: neither gain nor penalty
                found_req.add(hit)
                r = required[hit]
                s.fields_matched += 1
                tag = f"{lab['name']}.{r['name']}"
                if _val(f.type) == r.get("type"):
                    s.type_correct += 1
                else:
                    s.wrong_type.append(f"{tag}: expected {r.get('type')}, got {_val(f.type)}")
                if _val(f.support) == r.get("support"):
                    s.support_correct += 1
                else:
                    s.wrong_support.append(
                        f"{tag}: expected {r.get('support')}, got {_val(f.support)}"
                    )
            elif n in optional:
                continue
            else:
                tag = f"{lab['name']}.{f.name}"
                s.extra_fields.append(tag)
                overgen += 1
                if n in forbidden_fields:
                    overgen += 1
                    s.forbidden_fields_hit.append(tag)
        s.req_found += len(found_req)
        s.missing_fields += [
            f"{lab['name']}.{r['name']}" for i, r in enumerate(required) if i not in found_req
        ]
        s.overgen_weighted += overgen
        s.overgen_rts += 1

    # required fields of unmatched labelled record types are missing too
    for lab in labelled:
        if id(lab) not in matched_labels:
            s.missing_fields += [
                f"{lab['name']}.{f['name']}" for f in lab.get("required_fields") or []
            ]
    return s


@dataclass
class StabilityResult:
    stable: bool
    same_outcome: bool
    same_record_types: bool
    field_agreement: float


def _found_sets(schema: Any, expected: dict) -> tuple[frozenset[str], frozenset[str]]:
    rts = set()
    fields_found = set()
    for rt, lab in _match_record_types(schema, expected):
        rts.add(lab["name"])
        for r in lab.get("required_fields") or []:
            if any(normalise(f.name) in _names(r) for f in rt.fields):
                fields_found.add(f"{lab['name']}.{r['name']}")
    return frozenset(rts), frozenset(fields_found)


def stability(schemas: list[Any | None], expected: dict) -> StabilityResult:
    if not schemas or any(s is None for s in schemas):
        return StabilityResult(False, False, False, 0.0)
    same_outcome = len({s.outcome for s in schemas}) == 1
    if expected.get("outcome", "ok") != "ok" or schemas[0].outcome != "ok":
        return StabilityResult(
            same_outcome, same_outcome, same_outcome, 1.0 if same_outcome else 0.0
        )
    sets = [_found_sets(s, expected) for s in schemas]
    same_rts = len({rts for rts, _ in sets}) == 1
    inter = frozenset.intersection(*(f for _, f in sets))
    union = frozenset.union(*(f for _, f in sets))
    agreement = 1.0 if not union else len(inter) / len(union)
    stable = same_outcome and same_rts and agreement >= FIELD_AGREEMENT_MIN
    return StabilityResult(stable, same_outcome, same_rts, agreement)


def _ratio(num: float, den: float) -> float | None:
    return None if den == 0 else num / den


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(p / 100 * len(ordered)))
    return ordered[rank - 1]


def aggregate(
    case_scores: list[CaseScore],
    stability_results: list[StabilityResult] | None = None,
    prices: dict[str, float] | None = None,
    thresholds: dict[str, tuple[str, float]] | None = None,
) -> dict:
    th = {**THRESHOLDS, **(thresholds or {})}
    full = [c for c in case_scores if c.full]
    vft = [c.valid_first_try for c in case_scores if c.valid_first_try is not None]
    og_den = sum(c.overgen_rts for c in full)

    values: dict[str, tuple[float | None, int]] = {
        "outcome_accuracy": (
            _ratio(sum(c.outcome_correct for c in case_scores), len(case_scores)),
            len(case_scores),
        ),
        "record_type_recall": (
            _ratio(sum(c.rt_matched for c in full), sum(c.rt_labelled for c in full)),
            sum(c.rt_labelled for c in full),
        ),
        "record_type_precision": (
            _ratio(sum(c.rt_matched for c in full), sum(c.rt_produced for c in full)),
            sum(c.rt_produced for c in full),
        ),
        "source_accuracy": (
            _ratio(sum(c.source_correct for c in full), sum(c.rt_matched for c in full)),
            sum(c.rt_matched for c in full),
        ),
        "required_field_recall": (
            _ratio(sum(c.req_found for c in full), sum(c.req_total for c in full)),
            sum(c.req_total for c in full),
        ),
        "over_generation": (_ratio(sum(c.overgen_weighted for c in full), og_den), og_den),
        "type_accuracy": (
            _ratio(sum(c.type_correct for c in full), sum(c.fields_matched for c in full)),
            sum(c.fields_matched for c in full),
        ),
        "support_accuracy": (
            _ratio(sum(c.support_correct for c in full), sum(c.fields_matched for c in full)),
            sum(c.fields_matched for c in full),
        ),
        "valid_first_try": (_ratio(sum(vft), len(vft)), len(vft)),
        "stability": (
            _ratio(sum(r.stable for r in stability_results or []), len(stability_results or [])),
            len(stability_results or []),
        ),
    }

    metrics = {}
    for name, (value, n) in values.items():
        direction, threshold = th[name]
        passed = None
        if value is not None:
            passed = value >= threshold if direction == ">=" else value <= threshold
        metrics[name] = {
            "value": value,
            "threshold": threshold,
            "direction": direction,
            "passed": passed,
            "n": n,
        }

    lat = [c.latency_ms for c in case_scores if c.latency_ms is not None]
    costs = None
    with_usage = [c for c in case_scores if c.input_tokens is not None]
    if prices is not None and with_usage:
        costs = [
            (c.input_tokens or 0) * prices["input_per_mtok"] / 1e6
            + (c.output_tokens or 0) * prices["output_per_mtok"] / 1e6
            for c in with_usage
        ]
    return {
        "metrics": metrics,
        "reported": {
            "latency_p50_ms": _percentile(lat, 50),
            "latency_p95_ms": _percentile(lat, 95),
            "cost_per_call": None if costs is None else sum(costs) / len(costs),
            "cost_total": None if costs is None else sum(costs),
        },
        "passed": all(m["passed"] is not False for m in metrics.values()),
    }
