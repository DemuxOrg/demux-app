"""Probe candidate models for the agent's tool-calling needs (build spec §5.1).

Toy task: look up two cities' stock of books (parallel calls in one turn), convert a
number with a second tool, then call `finish`. Records success, steps, latency, tokens,
whether every tool-call argument string was valid JSON, and whether a turn had ≥2
parallel calls. Prints a table. Costs a few cents.

    cd backend && uv run python scripts/probe_agent_model.py model1 model2 ...
"""

import asyncio
import json
import sys
import time

from app.agent.llm import LLMError, OpenAICompatibleLLM, cost_usd

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "count_books",
            "description": "Number of books a library branch holds.",
            "parameters": {
                "type": "object",
                "properties": {"branch": {"type": "string"}},
                "required": ["branch"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "to_shelves",
            "description": "Convert a number of books into a number of shelves.",
            "parameters": {
                "type": "object",
                "properties": {"books": {"type": "integer"}},
                "required": ["books"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": "End the task with a short summary.",
            "parameters": {
                "type": "object",
                "properties": {"summary": {"type": "string"}},
                "required": ["summary"],
            },
        },
    },
]

COUNTS = {"north": 1200, "south": 800}

SYSTEM = (
    "You solve tasks only by calling tools. When you need several independent lookups, "
    "call the tools in parallel in a single turn. Call finish when done."
)
USER = (
    "Find how many books the North and South branches hold (look both up at once), "
    "convert the total into shelves, then finish with the number of shelves."
)


async def probe(llm: OpenAICompatibleLLM, model: str) -> dict:
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": USER},
    ]
    row = {
        "model": model,
        "ok": False,
        "steps": 0,
        "ms": 0,
        "in": 0,
        "out": 0,
        "json_ok": True,
        "parallel": False,
        "tools_used": set(),
        "note": "",
    }
    for _ in range(8):
        row["steps"] += 1
        t = time.perf_counter()
        try:
            reply = await llm.chat(model, messages, TOOLS)
        except LLMError as e:
            row["note"] = str(e)[:60]
            return row
        row["ms"] += int((time.perf_counter() - t) * 1000)
        row["in"] += reply.input_tokens
        row["out"] += reply.output_tokens
        messages.append(reply.raw_message)
        if not reply.tool_calls:
            messages.append({"role": "user", "content": "Use the tools. Call finish when done."})
            continue
        if len(reply.tool_calls) >= 2:
            row["parallel"] = True
        for call in reply.tool_calls:
            row["tools_used"].add(call.name)
            try:
                args = json.loads(call.arguments or "{}")
            except json.JSONDecodeError:
                row["json_ok"] = False
                args = {}
            if call.name == "finish":
                row["ok"] = "5" in str(args.get("summary", "")) or "shelves" in str(args)
                row["note"] = str(args.get("summary", ""))[:40]
                return row
            if call.name == "count_books":
                result = {"books": COUNTS.get(str(args.get("branch", "")).lower().split()[0], 0)}
            else:
                result = {"shelves": int(args.get("books", 0)) // 400}
            messages.append(
                {"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)}
            )
    row["note"] = "no finish"
    return row


async def main(models: list[str]) -> None:
    llm = OpenAICompatibleLLM()
    rows = await asyncio.gather(*(probe(llm, m) for m in models))
    print(f"{'model':48} ok   steps  latency_s  in_tok  out_tok  json  parallel  cost$   note")
    for r in rows:
        ok = r["ok"] and len(r["tools_used"] - {"finish"}) >= 2
        print(
            f"{r['model'][:48]:48} {'yes' if ok else 'NO ':4} {r['steps']:5}  {r['ms'] / 1000:9.1f}"
            f"  {r['in']:6}  {r['out']:7}  {'ok' if r['json_ok'] else 'BAD':4}  "
            f"{'yes' if r['parallel'] else 'no':8}  {cost_usd(r['model'], r['in'], r['out']):.4f}"
            f"  {r['note']}"
        )
    print(
        "\nRecommendation: run the first trial with the strongest model that passes, for both "
        "BUILD_MODEL and SYNC_MODEL. A weak model would confound the result. Compare cheaper "
        "models (e.g. Qwen/Qwen3.6-35B-A3B) afterwards with the eval, on SYNC_MODEL first."
    )


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
