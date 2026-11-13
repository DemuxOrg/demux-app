"""Cleaning of message bodies before they reach the agent: drop quoted replies and
signatures, strip HTML, collapse whitespace. No PII work. (Ported from the planner's
`email_clean.py`.)"""

import html
import re

from app.mail.base import Message, Thread

_WROTE_START = re.compile(r"^\s*On\b.*", re.IGNORECASE)
_WROTE_END = re.compile(r"\bwrote:\s*$", re.IGNORECASE)
_SIGNATURE = re.compile(r"^--\s*$")
_FORWARD_MARK = re.compile(r"^-{2,}\s*(Original Message|Forwarded message)\s*-{2,}", re.I)

_SCRIPT_STYLE = re.compile(r"<(script|style|head)\b.*?</\1\s*>", re.I | re.S)
_BLOCK_TAGS = re.compile(r"<\s*(br|/p|/div|/tr|/li|/h[1-6]|/table)\b[^>]*>", re.I)
_TAGS = re.compile(r"<[^>]+>")


def html_to_text(raw: str) -> str:
    text = _SCRIPT_STYLE.sub(" ", raw)
    text = _BLOCK_TAGS.sub("\n", text)
    text = _TAGS.sub(" ", text)
    text = html.unescape(text)
    lines = [re.sub(r"[ \t ]+", " ", ln).strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def clean_body(body: str) -> str:
    kept: list[str] = []
    lines = body.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if _SIGNATURE.match(line):
            break  # signature: drop everything after
        if _FORWARD_MARK.match(line.strip()):
            # Keep forwarded content: it is often the only copy of the facts.
            kept.append(line)
            i += 1
            continue
        if line.lstrip().startswith(">"):
            i += 1
            continue
        if _WROTE_START.match(line):
            # "On ... wrote:" header, possibly wrapped over up to 3 lines
            for j in range(i, min(i + 3, len(lines))):
                if _WROTE_END.search(lines[j]):
                    # Everything after a reply header is the quoted message: drop it.
                    i = len(lines)
                    break
            else:
                kept.append(line)
                i += 1
            continue
        kept.append(line)
        i += 1
    return re.sub(r"\s+", " ", " ".join(kept)).strip()


def clean_message(message: Message) -> Message:
    return message.model_copy(update={"body": clean_body(message.body)})


def clean_thread(thread: Thread) -> Thread:
    """Return a copy of `thread` with noise removed from each message body."""
    return thread.model_copy(update={"messages": [clean_message(m) for m in thread.messages]})
