"""Run flows from the terminal against a fake or real mailbox, without the DB workspace.

    uv run python -m app.agent.cli build --prompt "..." --mailbox fake:path/to/mailbox.json \
        --out .runs/cli/demo [--now 2026-10-20T09:00:00Z]
    uv run python -m app.agent.cli sync --out .runs/cli/demo --mailbox fake:... [--now ...]
    uv run python -m app.agent.cli edit --out .runs/cli/demo --mailbox ... --message "..."

`--mailbox gmail:<email>` uses that signed-in user's Gmail tokens from the database.
State (data, guide, queries, processed ids) is kept in `--out`; the app is written to
`<out>/app.html` and `<out>/preview.html` (shell + app + data, opens in a browser).
Prints counts and cost only.
"""

import argparse
import asyncio
import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

from app.agent import flows
from app.agent.context import MemoryPersister, RunContext, WorkspaceState
from app.agent.llm import OpenAICompatibleLLM
from app.agent.shell import build_srcdoc
from app.core.config import settings


async def _mailbox(spec: str, now: datetime | None):
    kind, _, arg = spec.partition(":")
    if kind == "fake":
        from app.mail.fake import FakeMailbox

        return FakeMailbox.from_file(arg, now=now)
    if kind == "gmail":
        from sqlalchemy import select

        from app.auth.google import UserTokenProvider
        from app.db.session import SessionLocal
        from app.mail.fake import TimeBoxedMailbox
        from app.mail.gmail import GmailMailbox
        from app.models.user import User

        async with SessionLocal() as s:
            user = await s.scalar(select(User).where(User.email == arg))
        if user is None:
            sys.exit(f"no signed-in user {arg!r}")
        box = GmailMailbox(UserTokenProvider(SessionLocal, user.id))
        return TimeBoxedMailbox(box, now) if now else box
    sys.exit("--mailbox must be fake:<path> or gmail:<email>")


def write_preview(out: Path, state: WorkspaceState) -> None:
    if not state.app_html:
        return
    page = build_srcdoc(state.app_html).replace(
        "</body>",
        "<script>window.postMessage({type:'demux:data',data:"
        + json.dumps(state.data).replace("</", "<\\/")
        + "},'*');</script></body>",
    )
    (out / "preview.html").write_text(page)


async def main() -> None:
    ap = argparse.ArgumentParser(prog="app.agent.cli")
    ap.add_argument("command", choices=["build", "sync", "edit"])
    ap.add_argument("--prompt")
    ap.add_argument("--message")
    ap.add_argument("--mailbox", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--now", help="ISO time; hides mail after it (default: real now)")
    args = ap.parse_args()

    now = datetime.fromisoformat(args.now.replace("Z", "+00:00")) if args.now else None
    out = Path(args.out)
    mailbox = await _mailbox(args.mailbox, now)

    if args.command == "build":
        if not args.prompt:
            sys.exit("--prompt is required for build")
        persister = MemoryPersister(out, max_usd=settings.MAX_USD_PER_RUN)
        state = WorkspaceState(prompt=args.prompt)
        persister.state = state
    else:
        persister, state = MemoryPersister.load(out)
        persister.max_usd = settings.MAX_USD_PER_RUN

    ctx = RunContext(
        state=state,
        mailbox=mailbox,
        persister=persister,
        run_id=f"cli-{uuid.uuid4().hex[:8]}",
        now=now or datetime.now(UTC),
        lookback_days=settings.LOOKBACK_DAYS,
        max_build_threads=settings.BUILD_MAX_THREADS,
        inline_max_chars=settings.DATA_INLINE_MAX_CHARS,
    )
    cfg = flows.FlowConfig(
        llm=OpenAICompatibleLLM(),
        build_model=settings.BUILD_MODEL,
        sync_model=settings.SYNC_MODEL,
        batch_threads=settings.BATCH_THREADS,
        inline_max_chars=settings.DATA_INLINE_MAX_CHARS,
    )
    status = "done"
    try:
        if args.command == "build":
            summary = await flows.build(ctx, cfg)
        elif args.command == "sync":
            summary = await flows.sync(ctx, cfg)
        else:
            summary = await flows.edit(ctx, cfg, args.message or "", [])
    except flows.CannotBuild as e:
        status, summary = "cannot_build", str(e)
    persister._dump(state)
    write_preview(out, state)
    for ev in persister.events:
        print(f"  [{ev['phase']}] {ev['label']}")
    counts = {t: len(r) for t, r in state.data.items()}
    print(f"\n{status}: {summary}")
    print(f"records: {counts}  changes: {len(persister.changes)}")
    print(
        f"tokens in={persister.input_tokens} out={persister.output_tokens} "
        f"cost=${persister.cost:.4f}"
    )
    print(f"files: {out}/app.html  {out}/preview.html  {out}/guide.md  {out}/state.json")


if __name__ == "__main__":
    asyncio.run(main())
