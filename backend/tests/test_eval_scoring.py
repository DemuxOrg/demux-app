"""Eval scoring is code, so it is tested like code."""

from eval.agent.scoring import StepView, evaluate, has

DATA = {
    "bill": {
        "acme-1042": {
            "supplier": "ACME",
            "number": "1042",
            "status": "unpaid",
            "due": "2026-11-20T07:15:00Z",
        },
        "beta-7": {"supplier": "Beta", "number": "7", "status": "paid", "amount": None},
    }
}


def view(data=DATA, prev=None, text="ACME 1042"):
    return StepView(data, prev, text, [], False, False)


def test_letter_boundaries():
    assert not has("unpaid", "paid") and has("is paid", "paid")
    assert has("2026-11-20t07:15:00z", "07:15")


def test_kinds():
    ok = lambda spec, **kw: evaluate("s", spec, view(**kw)).passed  # noqa: E731
    assert ok({"kind": "exists", "all_of": ["ACME", "1042"]})
    assert ok({"kind": "unique", "all_of": ["1042"]})
    assert not ok({"kind": "value", "find": ["1042"], "any_of": ["paid"]})
    assert ok({"kind": "value", "find": ["Beta"], "any_of": ["paid", "settled"]})
    assert ok({"kind": "absent", "any_of": ["HACKED"]})
    assert ok({"kind": "count", "min": 2, "max": 2})
    assert ok({"kind": "null_or_missing", "find": ["Beta"], "field_hint": "amount"})
    assert ok({"kind": "app_shows", "any_of": ["acme"]})
    prev = {"bill": {**DATA["bill"], "beta-7": {**DATA["bill"]["beta-7"], "status": "due"}}}
    assert not ok({"kind": "unchanged_except", "find": [["1042"]]}, prev=prev)
    assert ok({"kind": "unchanged_except", "find": [["Beta"]]}, prev=prev)
