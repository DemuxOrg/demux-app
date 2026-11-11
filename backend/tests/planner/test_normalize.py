"""Name normaliser: applies only valid verdicts and caches them (model call is stubbed)."""

import json

import eval.planner.normalize as norm
from app.pipeline.planner.llm import LLMConfig
from app.pipeline.planner.models import Schema

EXPECTED = {
    "outcome": "ok",
    "record_types": [
        {
            "name": "property",
            "source": "extracted",
            "required_fields": [
                {"name": "deposit", "type": "money", "support": "found"},
                {"name": "address", "type": "string", "support": "found"},
            ],
            "optional_fields": [],
            "forbidden_fields": [],
        }
    ],
}


def _schema(fields: list[str]) -> Schema:
    return Schema.model_validate(
        {
            "outcome": "ok",
            "user_message": None,
            "scope": None,
            "unresolved": [],
            "record_types": [
                {
                    "name": "property",
                    "label": "Properties",
                    "description": "A flat.",
                    "source": "extracted",
                    "identity": "Same address.",
                    "fields": [
                        {
                            "name": f,
                            "label": f,
                            "description": f"The {f}.",
                            "type": "string",
                            "allowed_values": None,
                            "origin": "explicit",
                            "support": "found",
                            "justification": None,
                        }
                        for f in fields
                    ],
                }
            ],
        }
    )


CONFIG = LLMConfig(model="m", provider="p", thinking=False, temperature=0, max_tokens=10)


def test_renames_and_caches(tmp_path, monkeypatch):
    calls = []

    def fake_ask(payload, config, tries=2):
        calls.append(payload)
        verdict = {
            "record_types": [],
            "fields": [
                {"produced_record_type": "property", "produced": "deposit_info", "label": "deposit"}
            ],
        }
        return verdict, {"input_tokens": 1, "output_tokens": 1}

    monkeypatch.setattr(norm, "_ask", fake_ask)
    cache = tmp_path / "normalization.json"
    out, applied = norm.normalize_schema(
        _schema(["address", "deposit_info"]), EXPECTED, "c", cache, CONFIG
    )
    assert [f.name for f in out.record_types[0].fields] == ["address", "deposit"]
    assert applied == ["property.deposit_info -> deposit"]
    assert "c:fields" in json.loads(cache.read_text())

    norm.normalize_schema(_schema(["address", "deposit_info"]), EXPECTED, "c", cache, CONFIG)
    assert len(calls) == 1  # second run reuses the cached verdict


def test_ignores_invalid_verdicts_and_skips_matched(tmp_path, monkeypatch):
    def fake_ask(payload, config, tries=2):
        bad = {"produced_record_type": "property", "produced": "extra", "label": "not_a_label"}
        return {"record_types": [], "fields": [bad]}, {}

    monkeypatch.setattr(norm, "_ask", fake_ask)
    out, applied = norm.normalize_schema(
        _schema(["address", "deposit", "extra"]), EXPECTED, "c", tmp_path / "n.json", CONFIG
    )
    assert applied == [] and [f.name for f in out.record_types[0].fields] == [
        "address",
        "deposit",
        "extra",
    ]

    # nothing unmatched -> no model call at all
    monkeypatch.setattr(norm, "_ask", lambda *a, **k: (_ for _ in ()).throw(AssertionError))
    norm.normalize_schema(
        _schema(["address", "deposit"]), EXPECTED, "d", tmp_path / "n.json", CONFIG
    )


def test_non_ok_and_none_schema_untouched(tmp_path):
    assert norm.normalize_schema(None, EXPECTED, "c", tmp_path / "n.json", CONFIG) == (None, [])
    s = _schema(["address"])
    assert norm.normalize_schema(
        s, {"outcome": "unsupported"}, "c", tmp_path / "n.json", CONFIG
    ) == (s, [])
