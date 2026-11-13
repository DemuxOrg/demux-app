"""Test helpers: a scripted fake LLM and small builders."""

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.agent.llm import LLMReply, ToolCall

FIXTURES = Path(__file__).parent / "fixtures"
SMALL_MAILBOX = FIXTURES / "mailbox_small.json"

Step = list[tuple[str, dict[str, Any]]] | Callable[[list[dict[str, Any]]], Any] | str


class ScriptedLLM:
    """Replays a list of turns. Each turn is a list of (tool, args), a plain string
    (assistant text without tool calls), or a callable(messages) returning either."""

    def __init__(self, turns: list[Step]):
        self.turns = list(turns)
        self.calls: list[list[dict[str, Any]]] = []

    async def chat(self, model, messages, tools) -> LLMReply:
        self.calls.append(json.loads(json.dumps(messages)))
        if not self.turns:
            raise AssertionError("ScriptedLLM ran out of turns")
        turn = self.turns.pop(0)
        if callable(turn):
            turn = turn(messages)
        if isinstance(turn, str):
            return LLMReply(turn, [], 100, 10, 1, {"role": "assistant", "content": turn})
        n = len(self.calls)
        calls = [
            ToolCall(id=f"c{n}-{i}", name=name, arguments=json.dumps(args))
            for i, (name, args) in enumerate(turn)
        ]
        raw = {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": c.arguments}}
                for c in calls
            ],
        }
        return LLMReply(None, calls, 100, 10, 1, raw)


def tool_results(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [json.loads(m["content"]) for m in messages if m["role"] == "tool"]


def dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(UTC)


GOOD_APP = """
<div id="root"></div>
<script>
function render(data) {
  var root = document.getElementById('root');
  root.textContent = '';
  var types = Object.keys(data || {});
  if (!types.length) { root.textContent = 'Nothing yet'; return; }
  types.forEach(function (t) {
    Object.keys(data[t]).forEach(function (id) {
      var p = document.createElement('p');
      var r = data[t][id];
      p.textContent = Object.keys(r).filter(function (k) { return k[0] !== '_'; })
        .map(function (k) { return String(r[k]); }).join(' | ');
      root.appendChild(p);
    });
  });
}
</script>
"""
