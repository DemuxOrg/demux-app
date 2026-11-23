"""Replay on real Gmail (build spec §10.2).

1. Build a throwaway copy of a workspace (same prompt) with mail visible up to
   today − N days, then advance one day at a time running sync each day.
2. Build a second copy from scratch with now = today (the reference).
3. Pair records with an LLM matcher at temperature 0 (pairing only); scoring in code.
4. Write runs/<ts>/replay.md (git-ignored: it contains email-derived values).

Nothing is written to the database; both copies live in memory.
"""

import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI
from sqlalchemy import select

from app.agent import flows
from app.agent.context import MemoryPersister, RunContext, WorkspaceState
from app.agent.llm import OpenAICompatibleLLM
from app.auth.google import UserTokenProvider
from app.core.config import settings
from app.db.session import SessionLocal
from app.mail.fake import TimeBoxedMailbox
from app.mail.gmail import GmailMailbox
from app.models.workspace import Workspace
from eval.agent.runner import RUNS
from eval.agent.scoring import records

MATCH_PROMPT = """You pair records from two lists that describe the same real-world thing.
Return JSON: {"pairs": [{"a": "<type>/<id>", "b": "<type>/<id>"}]}. Pair a record at most
once. Only pair when you are confident they are the same thing. Do not judge values."""


def _cfg(llm) -> flows.FlowConfig:
    return flows.FlowConfig.from_settings(llm)


def _ctx(state, mailbox, persister, now) -> RunContext:
    return RunContext(
        state=state,
        mailbox=mailbox,
        persister=persister,
        run_id=f"replay-{uuid.uuid4().hex[:8]}",
        now=now,
        lookback_days=settings.LOOKBACK_DAYS,
        max_build_threads=settings.BUILD_MAX_THREADS,
        inline_max_chars=settings.DATA_INLINE_MAX_CHARS,
    )


async def _match(a: dict[str, Any], b: dict[str, Any]) -> list[tuple[str, str]]:
    def compact(data):
        return {
            f"{t}/{rid}": {k: v for k, v in rec.items() if not k.startswith("_")}
            for t, rid, rec in records(data)
        }

    client = AsyncOpenAI(base_url=settings.LLM_BASE_URL, api_key=settings.llm_api_key)
    resp = await client.chat.completions.create(
        model=settings.BUILD_MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": MATCH_PROMPT},
            {
                "role": "user",
                "content": (
                    f"List A:\n{json.dumps(compact(a))}\n\nList B:\n{json.dumps(compact(b))}"
                ),
            },
        ],
    )
    try:
        pairs = json.loads(resp.choices[0].message.content or "{}").get("pairs", [])
    except json.JSONDecodeError:
        pairs = []
    return [(p["a"], p["b"]) for p in pairs if "a" in p and "b" in p]


async def replay(workspace_id: str, days: int) -> Path:
    async with SessionLocal() as s:
        ws = await s.scalar(select(Workspace).where(Workspace.id == uuid.UUID(workspace_id)))
        if ws is None:
            raise SystemExit("workspace not found")
        prompt, user_id = ws.prompt, ws.user_id
    gmail = GmailMailbox(UserTokenProvider(SessionLocal, user_id))
    llm = OpenAICompatibleLLM()
    today = datetime.now(UTC)
    log: list[dict[str, Any]] = []

    # incremental copy
    inc_p = MemoryPersister()
    inc = WorkspaceState(prompt=prompt)
    inc_p.state = inc
    start = today - timedelta(days=days)
    box = TimeBoxedMailbox(gmail, start)
    await flows.build(_ctx(inc, box, inc_p, start), _cfg(llm))
    log.append({"day": "build", "cost": round(inc_p.cost, 4)})
    for d in range(1, days + 1):
        now = start + timedelta(days=d)
        box.now = now
        c0 = inc_p.cost
        t0 = datetime.now(UTC)
        summary = await flows.sync(_ctx(inc, box, inc_p, now), _cfg(llm))
        log.append(
            {
                "day": f"{now:%Y-%m-%d}",
                "summary": summary,
                "cost": round(inc_p.cost - c0, 4),
                "latency_s": round((datetime.now(UTC) - t0).total_seconds(), 1),
            }
        )

    # reference copy
    ref_p = MemoryPersister()
    ref = WorkspaceState(prompt=prompt)
    ref_p.state = ref
    await flows.build(_ctx(ref, gmail, ref_p, today), _cfg(llm))
    await gmail.aclose()

    pairs = await _match(inc.data, ref.data)
    inc_recs = {f"{t}/{rid}": rec for t, rid, rec in records(inc.data)}
    ref_recs = {f"{t}/{rid}": rec for t, rid, rec in records(ref.data)}
    paired_a = {a for a, _ in pairs}
    paired_b = {b for _, b in pairs}
    identical, differing = 0, []
    for a, b in pairs:
        ra = {k: v for k, v in inc_recs.get(a, {}).items() if not k.startswith("_")}
        rb = {k: v for k, v in ref_recs.get(b, {}).items() if not k.startswith("_")}
        if ra == rb:
            identical += 1
        else:
            differing.append((a, ra, b, rb))

    out = RUNS / f"replay-{today:%Y%m%d-%H%M%S}"
    out.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Replay — workspace {workspace_id}, {days} days",
        "",
        f"- incremental records: {len(inc_recs)}; reference records: {len(ref_recs)}",
        f"- paired: {len(pairs)}; identical values: {identical}",
        f"- only in incremental: {len(set(inc_recs) - paired_a)}; "
        f"only in reference: {len(set(ref_recs) - paired_b)}",
        f"- replay agreement (identical / reference): {identical / len(ref_recs):.2f}"
        if ref_recs
        else "- replay agreement: n/a",
        f"- cost: incremental ${inc_p.cost:.3f}, reference ${ref_p.cost:.3f}",
        "",
        "## Per day",
        "",
        *[f"- {e}" for e in log],
        "",
        "## Only in incremental",
        *[f"- {k}: {json.dumps(inc_recs[k], default=str)[:400]}" for k in set(inc_recs) - paired_a],
        "",
        "## Only in reference",
        *[f"- {k}: {json.dumps(ref_recs[k], default=str)[:400]}" for k in set(ref_recs) - paired_b],
        "",
        "## Paired with different values",
        *[
            f"- {a} vs {b}\n  - inc: {json.dumps(ra)}\n  - ref: {json.dumps(rb)}"
            for a, ra, b, rb in differing
        ],
    ]
    (out / "replay.md").write_text("\n".join(lines))
    return out
