"""LLM name normaliser for the planner benchmark.

Maps the planner's record type and field *names* onto the labelled names when they mean the same
thing (`deposit_info` -> `deposit`), so harmless renames do not count as misses. It never judges
correctness: a different, broader or extra item maps to null and is scored as before.

Only names that the deterministic matcher (names + synonyms) could not match are sent. The model
sees names, types and descriptions: no thread content. Verdicts are cached per case variant in
`<run>/normalization.json`, keyed by a hash of the input, so `--rescore` repeats them exactly.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

from app.pipeline.planner.llm import LLMConfig, _client
from app.pipeline.planner.models import Schema
from eval.planner.scoring import _names, normalise

SYSTEM = """\
You normalise names for a benchmark. A planner produced a schema (record types with fields); an \
answer key lists labelled record types and fields. Some names differ only in wording. For each \
unmatched planner name, say which unmatched labelled name it is, or null.

Map a name only when both describe the same information, ignoring wording, suffixes, word order \
and singular/plural. Ignore types: type mistakes are scored separately, so a planner field whose \
type differs from the label's still maps when it holds the same information. Return null \
when the planner item is different information, broader or narrower, or simply an additional \
item. Never map a record type to a \
labelled one whose rows would be a different kind of thing (a list of people is not a list of \
subscriptions). Use each labelled name at most once. Do not judge whether the planner is right."""

THINKING = True  # non-thinking mode was too conservative on clear renames

VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "record_types": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "produced": {"type": "string"},
                    "label": {"type": ["string", "null"]},
                },
                "required": ["produced", "label"],
                "additionalProperties": False,
            },
        },
        "fields": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "produced_record_type": {"type": "string"},
                    "produced": {"type": "string"},
                    "label": {"type": ["string", "null"]},
                },
                "required": ["produced_record_type", "produced", "label"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["record_types", "fields"],
    "additionalProperties": False,
}


def _field_entries(lab: dict) -> list[dict]:
    out = []
    for kind in ("required_fields", "optional_fields", "forbidden_fields"):
        for f in lab.get(kind) or []:
            name = f if isinstance(f, str) else f["name"]
            typ = None if isinstance(f, str) else f.get("type")
            out.append({"name": name, "kind": kind.split("_")[0], "type": typ})
    return out


def _unmatched(schema: Schema, expected: dict) -> dict[str, Any]:
    """The names the deterministic matcher could not match, as the model's input."""
    labelled = list(expected.get("record_types") or [])
    taken: set[int] = set()
    produced = []
    for rt in schema.record_types:
        hit = next(
            (
                i
                for i, lab in enumerate(labelled)
                if i not in taken and normalise(rt.name) in _names(lab)
            ),
            None,
        )
        if hit is not None:
            taken.add(hit)
        produced.append((rt, hit))

    free_labels = [lab["name"] for i, lab in enumerate(labelled) if i not in taken]
    prod_rts = [
        {"name": rt.name, "description": rt.description, "source": rt.source.value}
        for rt, hit in produced
        if hit is None
    ]
    fields = []
    for rt, hit in produced:
        entries = _field_entries(labelled[hit]) if hit is not None else []
        label_fields = [
            e for e in entries if not any(normalise(f.name) in _names(e["name"]) for f in rt.fields)
        ]
        known = {n for e in entries for n in _names({"name": e["name"], **_syn(labelled[hit], e)})}
        prod_fields = [
            {"name": f.name, "type": f.type.value, "description": f.description}
            for f in rt.fields
            if normalise(f.name) not in known
        ]
        if hit is not None and prod_fields and label_fields:
            fields.append(
                {
                    "produced_record_type": rt.name,
                    "label_record_type": labelled[hit]["name"],
                    "produced_fields": prod_fields,
                    "unmatched_label_fields": label_fields,
                }
            )
    return {
        "unmatched_label_record_types": free_labels,
        "unmatched_produced_record_types": prod_rts,
        "field_groups": fields,
    }


def _syn(lab: dict, entry: dict) -> dict:
    for f in lab.get("required_fields") or []:
        if not isinstance(f, str) and f["name"] == entry["name"]:
            return {"synonyms": f.get("synonyms") or []}
    return {}


def _ask(payload: dict[str, Any], config: LLMConfig, tries: int = 3) -> tuple[dict, dict]:
    resp = _client().chat.completions.create(
        model=f"{config.model}:{config.provider}",
        temperature=0,
        max_tokens=4000,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": json.dumps(payload, indent=1)},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "Verdict", "strict": True, "schema": VERDICT_SCHEMA},
        },
        extra_body={"chat_template_kwargs": {"enable_thinking": THINKING}},
    )
    usage = {
        "input_tokens": resp.usage.prompt_tokens if resp.usage else 0,
        "output_tokens": resp.usage.completion_tokens if resp.usage else 0,
    }
    try:
        return json.loads(resp.choices[0].message.content or ""), usage
    except json.JSONDecodeError:
        if tries <= 1:
            return {}, {"error": "unparseable verdict"}
        return _ask(payload, config, tries - 1)


def _cached_ask(
    payload: dict[str, Any], key: str, cache_path: Path, config: LLMConfig
) -> dict[str, Any]:
    digest = hashlib.sha256(
        (f"{SYSTEM}{THINKING}" + json.dumps(payload, sort_keys=True)).encode()
    ).hexdigest()[:16]
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    entry = cache.get(key)
    if not entry or entry["input_hash"] != digest:
        verdict, usage = _ask(payload, config)
        if "error" in usage:  # fail soft: score this schema strictly; retry on the next rescore
            return {"failed": True}
        entry = {"input_hash": digest, "verdict": verdict, "usage": usage}
        cache[key] = entry
        cache_path.write_text(json.dumps(cache, indent=2))
    return entry["verdict"]


def normalize_schema(
    schema: Schema | None, expected: dict, key: str, cache_path: Path, config: LLMConfig
) -> tuple[Schema | None, list[str]]:
    """Return (schema with renamed names, human-readable list of applied renames).

    Two stages, each at most one cached call: record types, then fields of matched record types.
    """
    if schema is None or expected.get("outcome") != "ok":
        return schema, []
    renamed = schema.model_copy(deep=True)
    applied: list[str] = []

    payload = _unmatched(renamed, expected)
    if payload["unmatched_label_record_types"] and payload["unmatched_produced_record_types"]:
        verdict = _cached_ask(
            {**payload, "field_groups": []}, f"{key}:record_types", cache_path, config
        )
        if verdict.get("failed"):
            applied.append("NORMALISER FAILED (record types): scored strictly")
        valid, used = set(payload["unmatched_label_record_types"]), set()
        for m in verdict.get("record_types", []):
            rt = next((r for r in renamed.record_types if r.name == m["produced"]), None)
            if rt and m["label"] in valid and m["label"] not in used:
                used.add(m["label"])
                applied.append(f"record type {rt.name} -> {m['label']}")
                rt.name = m["label"]

    payload = _unmatched(renamed, expected)
    if payload["field_groups"]:
        verdict = _cached_ask(
            {
                "unmatched_label_record_types": [],
                "unmatched_produced_record_types": [],
                "field_groups": payload["field_groups"],
            },
            f"{key}:fields",
            cache_path,
            config,
        )
        if verdict.get("failed"):
            applied.append("NORMALISER FAILED (fields): scored strictly")
        for group in payload["field_groups"]:
            valid = {e["name"] for e in group["unmatched_label_fields"]}
            rt = next(
                (r for r in renamed.record_types if r.name == group["produced_record_type"]), None
            )
            used = set()
            for m in verdict.get("fields", []):
                if m["produced_record_type"] != group["produced_record_type"]:
                    continue
                if m["label"] not in valid or m["label"] in used:
                    continue
                f = next((x for x in rt.fields if x.name == m["produced"]), None) if rt else None
                if f:
                    used.add(m["label"])
                    applied.append(f"{rt.name}.{f.name} -> {m['label']}")
                    f.name = m["label"]
    return renamed, applied
