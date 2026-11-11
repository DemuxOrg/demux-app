from types import SimpleNamespace

from app.pipeline.planner.models import Field, RecordType, Schema, Usage
from eval.planner.scoring import aggregate, normalise, score_case, stability


def fld(name, type_="string", support="found", origin="explicit"):
    return Field(
        name=name,
        label=name,
        description=name,
        type=type_,
        allowed_values=None,
        origin=origin,
        support=support,
        justification=None,
    )


def rt(name, fields, source="extracted"):
    return RecordType(
        name=name,
        label=name,
        description=name,
        source=source,
        identity="same number" if source == "extracted" else None,
        fields=fields,
    )


def schema(rts, outcome="ok"):
    return Schema(
        outcome=outcome,
        user_message=None if outcome == "ok" else "msg",
        scope="s",
        record_types=rts if outcome == "ok" else [],
        unresolved=[],
    )


EXPECTED = {
    "outcome": "ok",
    "record_types": [
        {
            "name": "invoice",
            "synonyms": ["bill"],
            "source": "extracted",
            "required_fields": [
                {"name": "amount", "synonyms": ["total"], "type": "money", "support": "found"},
                {"name": "due_date", "synonyms": ["due"], "type": "date", "support": "found"},
            ],
            "optional_fields": ["status"],
            "forbidden_fields": ["signature"],
        }
    ],
    "forbidden_record_types": ["vendor_contact"],
}


def perfect():
    return schema(
        [
            rt(
                "invoice",
                [fld("amount", "money"), fld("due_date", "date"), fld("status")],
            )
        ]
    )


def test_normalise():
    assert normalise("Due_Date") == normalise("due-dates") == "duedate"
    assert normalise("invoices") == "invoice"


def test_perfect_case():
    s = score_case(perfect(), EXPECTED)
    assert s.outcome_correct and s.full
    assert (s.rt_labelled, s.rt_produced, s.rt_matched, s.source_correct) == (1, 1, 1, 1)
    assert (s.req_total, s.req_found) == (2, 2)
    assert (s.fields_matched, s.type_correct, s.support_correct) == (2, 2, 2)
    assert (s.overgen_weighted, s.overgen_rts) == (0, 1)
    assert not (s.missing_fields or s.extra_fields or s.wrong_type or s.missing_record_types)


def test_synonyms_match_names_and_fields():
    sc = schema([rt("Bills", [fld("Total", "money"), fld("due", "date")])])
    s = score_case(sc, EXPECTED)
    assert s.rt_matched == 1 and s.req_found == 2 and s.overgen_weighted == 0


def test_missing_and_extra_record_types():
    sc = schema([rt("vendor_contact", [fld("name")]), rt("reminder", [fld("x")])])
    s = score_case(sc, EXPECTED)
    assert s.rt_matched == 0 and s.rt_produced == 2
    assert s.missing_record_types == ["invoice"]
    assert sorted(s.extra_record_types) == ["reminder", "vendor_contact"]
    assert s.forbidden_record_types_hit == ["vendor_contact"]
    assert s.missing_fields == ["invoice.amount", "invoice.due_date"]
    assert s.overgen_rts == 0


def test_wrong_source_type_support():
    sc = schema(
        [
            rt(
                "invoice",
                [fld("amount", "number"), fld("due_date", "date", support="not_found")],
                source="thread",
            )
        ]
    )
    s = score_case(sc, EXPECTED)
    assert s.source_correct == 0 and len(s.wrong_source) == 1
    assert s.type_correct == 1 and len(s.wrong_type) == 1
    assert s.support_correct == 1 and len(s.wrong_support) == 1


def test_missing_required_field():
    s = score_case(schema([rt("invoice", [fld("amount", "money")])]), EXPECTED)
    assert (s.req_found, s.req_total) == (1, 2)
    assert s.missing_fields == ["invoice.due_date"]


def test_overgeneration_forbidden_counts_double():
    fields = [fld("amount", "money"), fld("due_date", "date"), fld("color"), fld("signature")]
    s = score_case(schema([rt("invoice", fields)]), EXPECTED)
    assert s.overgen_weighted == 3  # color 1 + signature 2
    assert sorted(s.extra_fields) == ["invoice.color", "invoice.signature"]
    assert s.forbidden_fields_hit == ["invoice.signature"]


def test_optional_fields_not_overgeneration():
    s = score_case(perfect(), EXPECTED)
    assert s.overgen_weighted == 0


def test_none_schema():
    s = score_case(None, EXPECTED)
    assert not s.outcome_correct
    assert s.rt_matched == 0 and s.rt_produced == 0 and s.rt_labelled == 1
    assert s.req_total == 2 and s.req_found == 0
    assert s.missing_record_types == ["invoice"]


def test_non_ok_case_only_outcome():
    exp = {"outcome": "needs_clarification"}
    good = score_case(schema([], "needs_clarification"), exp)
    bad = score_case(perfect(), exp)
    assert good.outcome_correct and not bad.outcome_correct
    assert not good.full and good.rt_produced == 0 and bad.rt_produced == 0
    assert not score_case(None, exp).outcome_correct


def test_run_fields_from_result():
    res = SimpleNamespace(valid_first_try=True, latency_ms=100, usage=Usage(1000, 500))
    s = score_case(perfect(), EXPECTED, res, case_id="c1")
    assert s.case_id == "c1" and s.valid_first_try is True and s.latency_ms == 100
    assert (s.input_tokens, s.output_tokens) == (1000, 500)


def test_aggregate_micro_average_and_thresholds():
    res = SimpleNamespace(valid_first_try=True, latency_ms=100, usage=Usage(1_000_000, 0))
    good = score_case(perfect(), EXPECTED, res)
    bad_res = SimpleNamespace(valid_first_try=False, latency_ms=300, usage=Usage(0, 1_000_000))
    bad = score_case(schema([rt("invoice", [fld("amount", "money")])]), EXPECTED, bad_res)
    clar = score_case(schema([], "needs_clarification"), {"outcome": "needs_clarification"}, res)
    agg = aggregate([good, bad, clar], prices={"input_per_mtok": 3.0, "output_per_mtok": 15.0})
    m = agg["metrics"]
    assert m["outcome_accuracy"]["value"] == 1.0 and m["outcome_accuracy"]["passed"]
    assert m["record_type_recall"]["value"] == 1.0
    assert m["required_field_recall"]["value"] == 3 / 4
    assert m["required_field_recall"]["passed"] is False
    assert m["valid_first_try"]["value"] == 2 / 3
    assert m["over_generation"]["value"] == 0.0 and m["over_generation"]["passed"]
    assert m["type_accuracy"]["n"] == 3
    assert m["stability"]["value"] is None and m["stability"]["passed"] is None
    assert agg["passed"] is False
    rep = agg["reported"]
    assert rep["latency_p50_ms"] == 100 and rep["latency_p95_ms"] == 300
    assert rep["cost_total"] == 3.0 + 15.0 + 3.0
    assert rep["cost_per_call"] == rep["cost_total"] / 3


def test_aggregate_all_pass():
    agg = aggregate([score_case(perfect(), EXPECTED)])
    assert agg["passed"] is True
    assert agg["reported"]["cost_per_call"] is None


def test_aggregate_overgen_threshold_fails():
    fields = [fld("amount", "money"), fld("due_date", "date"), fld("a"), fld("b")]
    agg = aggregate([score_case(schema([rt("invoice", fields)]), EXPECTED)])
    assert agg["metrics"]["over_generation"]["value"] == 2.0
    assert agg["metrics"]["over_generation"]["passed"] is False


def test_aggregate_precision_counts_extras():
    sc = schema([rt("invoice", [fld("amount", "money")]), rt("junk", [fld("x")])])
    agg = aggregate([score_case(sc, EXPECTED)])
    assert agg["metrics"]["record_type_precision"]["value"] == 0.5
    assert agg["metrics"]["record_type_precision"]["passed"] is False


def test_stability_stable():
    a = perfect()
    b = schema([rt("bill", [fld("total", "money"), fld("due", "date")])])
    r = stability([a, b, a], EXPECTED)
    assert r.stable and r.same_outcome and r.same_record_types and r.field_agreement == 1.0


def test_stability_different_outcome():
    r = stability([perfect(), schema([], "unsupported"), perfect()], EXPECTED)
    assert not r.stable and not r.same_outcome


def test_stability_different_record_types():
    other = schema([rt("junk", [fld("x")])])
    r = stability([perfect(), other, perfect()], EXPECTED)
    assert not r.stable and not r.same_record_types


def test_stability_field_agreement_threshold():
    partial = schema([rt("invoice", [fld("amount", "money")])])
    r = stability([perfect(), partial, perfect()], EXPECTED)
    assert r.field_agreement == 0.5 and not r.stable


def test_stability_none_schema_unstable():
    assert not stability([perfect(), None, perfect()], EXPECTED).stable


def test_aggregate_stability_metric():
    ok = stability([perfect()] * 3, EXPECTED)
    bad = stability([perfect(), None, perfect()], EXPECTED)
    agg = aggregate([score_case(perfect(), EXPECTED)], stability_results=[ok, ok, ok, bad])
    assert agg["metrics"]["stability"]["value"] == 0.75
    assert agg["metrics"]["stability"]["passed"] is False
