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


# ------------------------------------------------------------------ the Demux score

from eval.agent.scoring import (  # noqa: E402
    clarification,
    demux_score,
    evaluate_ask,
    retrieval,
    scenario_parts,
    simulated_answers,
    weighted,
)


def _rec(**fields):
    tids = fields.pop("tids", [])
    return {**fields, "_sources": [{"message_id": f"m-{t}", "thread_id": t} for t in tids]}


def test_retrieval_counts_groups_and_skips_unseen_ones():
    data = {"bill": {"a": _rec(n="1", tids=["t2"]), "b": _rec(n="2", tids=["t9"])}}
    groups = [
        {"label": "one", "threads": ["t1", "t2"]},  # cited through its second thread
        {"label": "two", "threads": ["t3"]},  # missed
        {"label": "later", "threads": ["t4"]},  # not visible yet: not counted
    ]
    r = retrieval(groups, data, visible={"t1", "t2", "t3", "t9"})
    assert (r["recalled"], r["total"], r["recall"]) == (1, 2, 0.5)
    assert [g["recalled"] for g in r["groups"]] == [True, False]
    assert (r["cited_threads"], r["cited_relevant"]) == (2, 1)  # t9 is extra: not scored


def test_ask_scores_half_for_data_and_half_for_screen():
    data = {"bill": {"a": {"number": "GP-2187", "amount": "EUR 980.00"}}}
    spec = {"ask": "how much", "record": ["GP-2187"], "value_any": ["980"], "label_any": ["amount"]}
    assert evaluate_ask(spec, data, "Supplier | Amount")["score"] == 1.0
    assert evaluate_ask(spec, data, "Supplier only")["score"] == 0.5
    missing = evaluate_ask({**spec, "record": ["NOPE"]}, data, "nothing")
    assert missing["score"] == 0 and "no record" in missing["detail"]
    screen_only = {"ask": "salary", "label_any": ["salary"]}
    assert evaluate_ask(screen_only, data, "Salary range")["score"] == 1.0
    assert evaluate_ask(screen_only, data, "Company")["in_data"] is None


def test_clarification_rewards_asking_only_when_vague():
    q = [
        {"id": "q1", "question": "Should free newsletters count?", "options": ["Paid only", "Both"]}
    ]
    assert clarification({"should_ask": False}, [])["score"] == 1.0
    assert clarification({"should_ask": False}, q)["score"] == 0.0
    vague = {"should_ask": True, "topic_any": ["newsletters"]}
    assert clarification(vague, [])["score"] == 0.0
    assert clarification(vague, q)["score"] == 1.0
    off_topic = [{"id": "q1", "question": "Include past months?", "options": ["Yes", "No"]}]
    assert clarification(vague, off_topic)["score"] == 0.5


def test_scripted_user_avoids_both_and_all():
    spec = {"answer_any": ["paid"], "avoid_any": ["both", "all"]}
    qs = [
        {"id": "q1", "question": "Which?", "options": ["Paid and free (both)", "Only paid ones"]},
        {"id": "q2", "question": "Since when?", "options": ["All time", "This year"]},
    ]
    assert simulated_answers(spec, qs) == {"q1": "Only paid ones"}  # q2: recommended


def test_scenario_score_rescales_missing_parts_and_run_score_has_spread():
    r = {
        "checks": [{"kind": "exists", "passed": True}, {"kind": "absent", "passed": False}],
        "retrieval": None,
        "asks": [],
        "clarify": {"score": 0.0},
    }
    parts = scenario_parts(r)
    assert parts == {"retrieval": None, "coverage": None, "correctness": 1.0, "clarification": 0.0}
    assert round(weighted(parts), 4) == round(0.2 / 0.3, 4)  # guardrail checks are left out
    results = [
        {"repeat": 1, "score": 0.8, "parts": {"retrieval": 1.0, "coverage": None}},
        {"repeat": 2, "score": 0.6, "parts": {"retrieval": 0.5, "coverage": None}},
    ]
    d = demux_score(results)
    assert d["score"] == 70.0 and d["repeats"] == [80.0, 60.0] and d["spread"] == 14.1
    assert d["parts"]["retrieval"] == 75.0 and d["parts"]["coverage"] is None
