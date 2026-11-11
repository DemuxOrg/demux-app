"""Probe which Hugging Face Inference Providers serve the planner model.

Run: `cd backend && uv run python scripts/probe_planner_model.py`

Lists the providers serving `PLANNER_MODEL` on the router, then makes one tiny
structured-output call per provider (thinking off) and prints a comparison table.
Sends only a toy prompt: no user data.
"""

import json
import time

import httpx
from openai import OpenAI

from app.core.config import settings

ROUTER = "https://router.huggingface.co/v1"

TOY_SCHEMA = {
    "type": "object",
    "properties": {
        "city": {"type": "string"},
        "population_millions": {"type": "number"},
        "is_capital": {"type": "boolean"},
    },
    "required": ["city", "population_millions", "is_capital"],
    "additionalProperties": False,
}


def list_providers(model: str) -> list[dict]:
    resp = httpx.get(
        f"{ROUTER}/models/{model}",
        headers={"Authorization": f"Bearer {settings.HF_TOKEN}"},
        timeout=30,
    )
    if resp.status_code == 404:
        resp = httpx.get(
            f"{ROUTER}/models", headers={"Authorization": f"Bearer {settings.HF_TOKEN}"}, timeout=30
        )
        resp.raise_for_status()
        entry = next((m for m in resp.json()["data"] if m["id"] == model), None)
        return (entry or {}).get("providers", [])
    resp.raise_for_status()
    return resp.json().get("data", {}).get("providers", [])


def probe(client: OpenAI, model: str, provider: str) -> dict:
    row = {"provider": provider, "ok": False, "json_schema_honoured": False, "error": ""}
    start = time.perf_counter()
    try:
        resp = client.chat.completions.create(
            model=f"{model}:{provider}",
            messages=[{"role": "user", "content": "Give facts about Paris."}],
            max_tokens=200,
            temperature=0,
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "Toy", "strict": True, "schema": TOY_SCHEMA},
            },
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )
        row["latency_ms"] = int((time.perf_counter() - start) * 1000)
        row["ok"] = True
        row["input_tokens"] = resp.usage.prompt_tokens if resp.usage else None
        row["output_tokens"] = resp.usage.completion_tokens if resp.usage else None
        content = resp.choices[0].message.content or ""
        try:
            data = json.loads(content)
            row["json_schema_honoured"] = set(data) == set(TOY_SCHEMA["properties"]) and isinstance(
                data.get("is_capital"), bool
            )
        except json.JSONDecodeError:
            pass
    except Exception as exc:  # noqa: BLE001 - probe reports any failure
        row["latency_ms"] = int((time.perf_counter() - start) * 1000)
        row["error"] = str(exc)[:80]
    return row


def main() -> None:
    if not settings.HF_TOKEN:
        raise SystemExit("HF_TOKEN is not set in the repo-root .env")
    model = settings.PLANNER_MODEL
    providers = list_providers(model)
    print(f"Model: {model}\nProviders listed by router: {[p.get('provider') for p in providers]}\n")
    meta = {p.get("provider"): p for p in providers}
    client = OpenAI(base_url=ROUTER, api_key=settings.HF_TOKEN)
    rows = [probe(client, model, name) for name in meta]
    print(
        f"{'provider':<16}{'ok':<6}{'schema':<8}{'ms':<8}{'in/out':<10}{'$in/$out per M':<16}error"
    )
    for r in rows:
        p = meta[r["provider"]].get("pricing") or {}
        print(
            f"{r['provider']:<16}{'yes' if r['ok'] else 'NO':<6}"
            f"{'yes' if r['json_schema_honoured'] else 'no':<8}{r['latency_ms']:<8}"
            f"{str(r.get('input_tokens')) + '/' + str(r.get('output_tokens')):<10}"
            f"{str(p.get('input')) + '/' + str(p.get('output')):<16}{r['error']}"
        )


if __name__ == "__main__":
    main()
