"""Run the planner on one prompt and a threads file.

uv run python -m app.pipeline.planner.cli --prompt "..." --threads path/to/threads.json
"""

import argparse
import json
import sys
from pathlib import Path

from pydantic import TypeAdapter

from app.pipeline.planner.models import Thread
from app.pipeline.planner.plan import plan


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--threads", required=True, type=Path)
    args = parser.parse_args()

    threads = TypeAdapter(list[Thread]).validate_json(args.threads.read_text())
    result = plan(args.prompt, threads)
    if result.schema is None:
        print(json.dumps({"errors": result.errors}, indent=2), file=sys.stderr)
        raise SystemExit(1)
    print(result.schema.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
