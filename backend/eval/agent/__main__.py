"""Agent eval entry point (costs money; not run in CI).

make eval-agent ARGS="--repeats 3"
make eval-agent ARGS="--scenario 01 07 --concurrency 2"
make eval-agent ARGS="--replay --workspace <id> --days 14"

`--job <eval_run_id>` runs an eval queued from /admin/evals and records it in the
database; the worker starts it as its own process, so it always runs the code on disk.
"""

import argparse
import asyncio
import logging

from app.core.config import settings
from app.core.logging import setup_logging


def main() -> None:
    ap = argparse.ArgumentParser(prog="eval.agent")
    ap.add_argument("--scenario", nargs="*", help="scenario id prefixes (default: all)")
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--concurrency", type=int, default=1, help="scenarios run at once")
    ap.add_argument("--replay", action="store_true")
    ap.add_argument("--workspace")
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--job", help="eval_runs id queued from /admin/evals")
    args = ap.parse_args()
    setup_logging(settings.ENV, "WARNING")
    logging.getLogger("app").setLevel(logging.WARNING)

    if args.job:
        import uuid

        from app.db.session import SessionLocal
        from app.services.evals import execute_eval

        logging.getLogger("app.services.evals").setLevel(logging.INFO)
        asyncio.run(execute_eval(uuid.UUID(args.job), session_factory=SessionLocal))
        return

    if args.replay:
        from eval.agent.replay import replay

        if not args.workspace:
            raise SystemExit("--workspace is required with --replay")
        out = asyncio.run(replay(args.workspace, args.days))
        print(f"replay report: {out}/replay.md")
        return

    from eval.agent.runner import run_all

    out = asyncio.run(run_all(args.scenario, args.repeats, args.concurrency))
    print(f"report: {out}/report.md")


if __name__ == "__main__":
    main()
