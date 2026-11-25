"""The eval scenarios are test data: keep them well-formed (no LLM, no cost)."""

import json

import pytest

from eval.agent.runner import load_scenarios
from eval.agent.scoring import CORRECTNESS_KINDS, GUARDRAIL_KINDS

ALL = load_scenarios()


def test_there_are_clear_and_vague_scenarios():
    vague = [s for s, _ in ALL if (s.get("clarify") or {}).get("should_ask")]
    assert len(ALL) >= 11 and len(vague) >= 3


@pytest.mark.parametrize("scenario,folder", ALL, ids=[s["id"] for s, _ in ALL])
def test_scenario_is_well_formed(scenario, folder):
    assert scenario["id"] == folder.name
    threads = {t["thread_id"] for t in json.loads((folder / "mailbox.json").read_text())}
    for g in scenario.get("relevant") or []:
        assert g["label"] and g["threads"], g
        assert set(g["threads"]) <= threads, f"unknown threads in {g['label']}"
    clarify = scenario.get("clarify") or {}
    assert set(clarify) <= {"should_ask", "topic_any", "answer_any", "avoid_any"}
    if clarify.get("should_ask"):
        assert clarify.get("topic_any") and clarify.get("answer_any")
    for step in scenario["steps"]:
        for c in step.get("expect", []):
            assert c["kind"] in CORRECTNESS_KINDS | GUARDRAIL_KINDS, c
        for a in step.get("asks") or []:
            assert set(a) <= {"ask", "record", "value_any", "label_any"}, a
            assert a["ask"] and (a.get("record") or a.get("label_any")), a
