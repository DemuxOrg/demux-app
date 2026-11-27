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

    async def chat(self, model, messages, tools, options=None) -> LLMReply:
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
                {
                    "id": c.id,
                    "type": "function",
                    "function": {"name": c.name, "arguments": c.arguments},
                }
                for c in calls
            ],
        }
        return LLMReply(None, calls, 100, 10, 1, raw)


def tool_results(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for m in messages:
        if m["role"] == "tool" and m["content"].startswith(("{", "[{")):
            out.append(json.loads(m["content"]))
    return out


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


# A studio (v3) app, as the interface designer writes it (the JSX of one ```jsx block).
GOOD_STUDIO_JSX = """
function App({ data }) {
  const names = types(data);
  if (!names.length) return <p className="p-6 text-slate-500">Nothing yet</p>;
  return (
    <div className="p-6 font-sans">
      {names.map((t) => (
        <ul key={t}>
          {records(data, t).map((r) => (
            <li key={r.id}>
              {Object.keys(r).filter((k) => !k.startsWith("_")).map((k) => String(r[k])).join(" | ")}
            </li>
          ))}
        </ul>
      ))}
    </div>
  );
}
"""
GOOD_STUDIO_ANSWER = f"Here is the app.\n\n```jsx\n{GOOD_STUDIO_JSX.strip()}\n```\n"


class PhaseLLM:
    """Scripted LLM for concurrent flows: one queue of turns per phase, chosen from the
    system prompt. A phase's last turn repeats when `repeat_last` is set for it."""

    MARKS = {
        "You design": "design",
        "You keep": "process",
        "You are a senior product designer": "app",
        "You change": "edit",
    }

    def __init__(self, repeat_last: tuple[str, ...] = ("process",), **turns: list[Step]):
        self.turns = {k: list(v) for k, v in turns.items()}
        self.repeat_last = repeat_last
        self.calls: list[list[dict[str, Any]]] = []
        self.phases: list[str] = []
        self._n = 0

    def calls_for(self, phase: str) -> list[list[dict[str, Any]]]:
        return [c for c, p in zip(self.calls, self.phases, strict=True) if p == phase]

    async def chat(self, model, messages, tools, options=None) -> LLMReply:
        system = messages[0]["content"]
        phase = next(v for k, v in self.MARKS.items() if system.startswith(k))
        self.calls.append(json.loads(json.dumps(messages)))
        self.phases.append(phase)
        queue = self.turns.get(phase) or []
        if not queue:
            raise AssertionError(f"PhaseLLM has no turn left for phase {phase}")
        turn = queue[0] if (len(queue) == 1 and phase in self.repeat_last) else queue.pop(0)
        if callable(turn):
            turn = turn(messages)
        if isinstance(turn, str):
            return LLMReply(turn, [], 100, 10, 1, {"role": "assistant", "content": turn})
        self._n += 1
        calls = [
            ToolCall(id=f"c{self._n}-{i}", name=name, arguments=json.dumps(args))
            for i, (name, args) in enumerate(turn)
        ]
        raw = {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": c.id,
                    "type": "function",
                    "function": {"name": c.name, "arguments": c.arguments},
                }
                for c in calls
            ],
        }
        return LLMReply(None, calls, 100, 10, 1, raw)
