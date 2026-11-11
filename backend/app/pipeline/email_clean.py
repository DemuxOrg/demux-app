"""Cleaning of thread text before it goes to the planner. No PII work."""

import re

from app.pipeline.planner.models import Message, Thread

_WROTE_START = re.compile(r"^\s*On\b.*", re.IGNORECASE)
_WROTE_END = re.compile(r"\bwrote:\s*$", re.IGNORECASE)
_SIGNATURE = re.compile(r"^--\s*$")


def _clean_body(body: str) -> str:
    kept: list[str] = []
    lines = body.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if _SIGNATURE.match(line):
            break  # signature: drop everything after
        if line.lstrip().startswith(">"):
            i += 1
            continue
        if _WROTE_START.match(line):
            # "On ... wrote:" header, possibly wrapped over up to 3 lines
            for j in range(i, min(i + 3, len(lines))):
                if _WROTE_END.search(lines[j]):
                    i = j + 1
                    break
            else:
                kept.append(line)
                i += 1
            continue
        kept.append(line)
        i += 1
    return re.sub(r"\s+", " ", " ".join(kept)).strip()


def clean_thread(thread: Thread) -> Thread:
    """Return a copy of `thread` with noise removed from each message body.

    Drops quoted replies (lines starting with `>` and "On ... wrote:" blocks) and
    signatures after a `-- ` line, then collapses whitespace. Ids, senders, dates,
    subjects and attachments are unchanged.
    """
    messages: list[Message] = [
        m.model_copy(update={"body": _clean_body(m.body)}) for m in thread.messages
    ]
    return thread.model_copy(update={"messages": messages})
