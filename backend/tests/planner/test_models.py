import json

import pytest
from pydantic import ValidationError

from app.pipeline.planner.models import (
    FieldType,
    Origin,
    PlanResult,
    Schema,
    Source,
    Support,
    Thread,
    Usage,
)

SCHEMA_DICT = {
    "version": 1,
    "outcome": "ok",
    "user_message": None,
    "scope": "unpaid invoices",
    "record_types": [
        {
            "name": "invoice",
            "label": "Invoices",
            "description": "One invoice",
            "source": "extracted",
            "identity": "same invoice number",
            "fields": [
                {
                    "name": "status",
                    "label": "Status",
                    "description": "Payment status",
                    "type": "enum",
                    "allowed_values": ["paid", "unpaid"],
                    "origin": "observed",
                    "support": "found",
                    "justification": "shows paid state",
                }
            ],
        }
    ],
    "unresolved": [],
}

THREAD_DICT = {
    "thread_id": "t1",
    "messages": [
        {
            "message_id": "m1",
            "sender": "Ana <ana@acme.example>",
            "to": ["me@example.com"],
            "date": "2026-03-04T09:15:00+00:00",
            "subject": "Invoice",
            "body": "hello",
        }
    ],
}


def test_enum_values():
    assert {t.value for t in FieldType} == {
        "string",
        "number",
        "money",
        "date",
        "boolean",
        "enum",
    }
    assert {o.value for o in Origin} == {"explicit", "inferred", "observed"}
    assert {s.value for s in Support} == {"found", "not_found"}
    assert {s.value for s in Source} == {"thread", "extracted"}


def test_schema_parses_and_coerces_enums():
    s = Schema.model_validate(SCHEMA_DICT)
    f = s.record_types[0].fields[0]
    assert f.type is FieldType.enum and f.origin is Origin.observed
    assert s.record_types[0].source is Source.extracted


def test_schema_json_round_trip():
    s = Schema.model_validate(SCHEMA_DICT)
    again = Schema.model_validate_json(s.model_dump_json())
    assert again == s
    assert json.loads(s.model_dump_json())["record_types"][0]["fields"][0]["type"] == "enum"


def test_schema_version_defaults_to_1():
    d = {k: v for k, v in SCHEMA_DICT.items() if k != "version"}
    assert Schema.model_validate(d).version == 1


def test_schema_rejects_bad_outcome_and_type():
    with pytest.raises(ValidationError):
        Schema.model_validate({**SCHEMA_DICT, "outcome": "maybe"})
    bad = json.loads(json.dumps(SCHEMA_DICT))
    bad["record_types"][0]["fields"][0]["type"] = "float"
    with pytest.raises(ValidationError):
        Schema.model_validate(bad)


def test_thread_parse_and_round_trip():
    t = Thread.model_validate(THREAD_DICT)
    assert t.messages[0].date.tzinfo is not None
    assert t.messages[0].attachments == []
    assert Thread.model_validate_json(t.model_dump_json()) == t


def test_plan_result_and_usage_defaults():
    u = Usage()
    assert (u.input_tokens, u.output_tokens) == (0, 0)
    r = PlanResult(None, False, 2, ["e"], u, 10, ["raw"])
    assert r.schema is None and r.attempts == 2
