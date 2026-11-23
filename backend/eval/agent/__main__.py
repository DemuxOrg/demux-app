"""Agent eval entry point (costs money; not run in CI).

make eval-agent ARGS="--repeats 3"
make eval-agent ARGS="--scenario 01 07"
make eval-agent ARGS="--replay --workspace <id> --days 14"
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
    ap.add_argument("--replay", action="store_true")
    ap.add_argument("--workspace")
    ap.add_argument("--days", type=int, default=14)
    args = ap.parse_args()
    setup_logging(settings.ENV, "WARNING")
    logging.getLogger("app").setLevel(logging.WARNING)

    if args.replay:
        from eval.agent.replay import replay

        if not args.workspace:
            raise SystemExit("--workspace is required with --replay")
        out = asyncio.run(replay(args.workspace, args.days))
        print(f"replay report: {out}/replay.md")
        return

    from eval.agent.runner import run_all

    out = asyncio.run(run_all(args.scenario, args.repeats))
    print(f"report: {out}/report.md")


if __name__ == "__main__":
    main()
