"""In-memory mailboxes for tests, the CLI and eval scenarios.

`FakeMailbox` loads a list of `Thread` and implements a small subset of Gmail search:
plain terms, quoted phrases, `from:`, `to:`, `subject:`, `OR` (and `{a b}`), parentheses,
`-term` negation, `after:`/`before:` (YYYY/MM/DD or Unix seconds) and `newer_than:Nd`.
Other operators (`label:`, `category:`, `in:`, `is:`, `has:`) are accepted and ignored.
Matching is per message, case-insensitive; a thread matches when one of its visible
messages matches every clause.

`now` hides every message dated after it, so scenarios can reveal mail step by step.
`TimeBoxedMailbox(inner, now)` does the same for any mailbox (used by replay).
"""

import json
import re
import shlex
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.mail.base import Mailbox, MailboxError, Message, Thread, ThreadSummary

_IGNORED_OPS = ("label", "category", "in", "is", "has", "larger", "smaller", "filename")


def _to_dt(value: str) -> datetime | None:
    value = value.strip()
    if value.isdigit():
        return datetime.fromtimestamp(int(value), tz=UTC)
    for fmt in ("%Y/%m/%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def _tokenize(query: str) -> list[str]:
    query = query.replace("(", " ( ").replace(")", " ) ").replace("{", " { ").replace("}", " } ")
    # Re-glue `op:"quoted phrase"` that the spacing above did not split.
    try:
        lexer = shlex.shlex(query, posix=True)
        lexer.whitespace_split = True
        lexer.quotes = '"'
        lexer.commenters = ""
        return list(lexer)
    except ValueError:
        return query.replace('"', " ").split()


Predicate = Callable[[Message, datetime], bool]


def _term(token: str) -> Predicate:
    negate = token.startswith("-") and len(token) > 1
    if negate:
        token = token[1:]
    op, _, val = token.partition(":")
    op_l = op.lower()
    pred: Predicate
    if val and op_l in ("from", "to", "subject"):
        needle = val.lower()

        def field_pred(m: Message, _now: datetime, op_l=op_l, needle=needle) -> bool:
            if op_l == "from":
                return needle in m.sender.lower()
            if op_l == "to":
                return any(needle in t.lower() for t in m.to)
            return needle in m.subject.lower()

        pred = field_pred
    elif val and op_l in ("after", "before"):
        when = _to_dt(val)

        def date_pred(m: Message, _now: datetime, op_l=op_l, when=when) -> bool:
            if when is None:
                return True
            return m.date >= when if op_l == "after" else m.date < when

        pred = date_pred
    elif val and op_l in ("newer_than", "older_than"):
        match = re.fullmatch(r"(\d+)([dmy])", val.lower())
        days = 0
        if match:
            n, unit = int(match.group(1)), match.group(2)
            days = n * {"d": 1, "m": 30, "y": 365}[unit]

        def rel_pred(m: Message, now: datetime, op_l=op_l, days=days) -> bool:
            cutoff = now - timedelta(days=days)
            return m.date >= cutoff if op_l == "newer_than" else m.date < cutoff

        pred = rel_pred
    elif val and op_l in _IGNORED_OPS:

        def always(_m: Message, _now: datetime) -> bool:
            return True

        return always
    else:
        needle = token.lower()

        def text_pred(m: Message, _now: datetime, needle=needle) -> bool:
            hay = f"{m.subject}\n{m.body}\n{m.sender}\n{' '.join(m.attachments)}".lower()
            return needle in hay

        pred = text_pred
    if negate:
        inner = pred
        return lambda m, now: not inner(m, now)
    return pred


def compile_query(query: str) -> list[list[Predicate]]:
    """Return clauses (AND) of alternatives (OR)."""
    tokens = _tokenize(query)
    clauses: list[list[Predicate]] = []
    i = 0
    pending_or = False
    while i < len(tokens):
        tok = tokens[i]
        if tok in ("(", "{"):
            close = ")" if tok == "(" else "}"
            depth, j = 1, i + 1
            inner: list[str] = []
            while j < len(tokens) and depth:
                if tokens[j] == tok:
                    depth += 1
                elif tokens[j] == close:
                    depth -= 1
                    if depth == 0:
                        break
                inner.append(tokens[j])
                j += 1
            terms = [t for t in inner if t not in ("(", ")", "{", "}", "OR", "AND")]
            is_or = tok == "{" or "OR" in inner
            if is_or:
                group = [_term(t) for t in terms]
                if group:
                    if pending_or and clauses:
                        clauses[-1].extend(group)
                    else:
                        clauses.append(group)
            else:
                for t in terms:
                    clauses.append([_term(t)])
            pending_or = False
            i = j + 1
            continue
        if tok in (")", "}", "AND"):
            i += 1
            continue
        if tok == "OR":
            pending_or = True
            i += 1
            continue
        pred = _term(tok)
        if pending_or and clauses:
            clauses[-1].append(pred)
        else:
            clauses.append([pred])
        pending_or = False
        i += 1
    return clauses


def _summary(thread: Thread) -> ThreadSummary:
    senders: list[str] = []
    for m in thread.messages:
        if m.sender not in senders:
            senders.append(m.sender)
    last = thread.messages[-1]
    return ThreadSummary(
        thread_id=thread.thread_id,
        subject=thread.messages[0].subject,
        senders=senders[:5],
        last_date=last.date,
        message_count=len(thread.messages),
        snippet=last.body[:160],
    )


class FakeMailbox:
    def __init__(self, threads: list[Thread], now: datetime | None = None):
        self._threads = {
            t.thread_id: Thread(
                thread_id=t.thread_id, messages=sorted(t.messages, key=lambda m: m.date)
            )
            for t in threads
        }
        self.now = now

    @classmethod
    def from_file(cls, path: str | Path, now: datetime | None = None) -> "FakeMailbox":
        raw = json.loads(Path(path).read_text())
        return cls([Thread.model_validate(t) for t in raw], now=now)

    def _visible(self, thread: Thread) -> Thread | None:
        if self.now is None:
            return thread
        msgs = [m for m in thread.messages if m.date <= self.now]
        return Thread(thread_id=thread.thread_id, messages=msgs) if msgs else None

    async def search(
        self,
        query: str,
        max_results: int = 25,
        after: datetime | None = None,
        before: datetime | None = None,
    ) -> list[ThreadSummary]:
        clauses = compile_query(query)
        now = self.now or datetime.now(UTC)
        hits: list[Thread] = []
        for thread in self._threads.values():
            visible = self._visible(thread)
            if visible is None:
                continue
            for m in visible.messages:
                if after and m.date < after:
                    continue
                if before and m.date >= before:
                    continue
                if all(any(p(m, now) for p in clause) for clause in clauses):
                    hits.append(visible)
                    break
        hits.sort(key=lambda t: t.messages[-1].date, reverse=True)
        return [_summary(t) for t in hits[:max_results]]

    async def search_ids(
        self,
        query: str,
        max_results: int = 25,
        after: datetime | None = None,
        before: datetime | None = None,
    ) -> list[str]:
        return [s.thread_id for s in await self.search(query, max_results, after, before)]

    async def count_received(self, after: datetime, before: datetime) -> int:
        count = 0
        for thread in self._threads.values():
            visible = self._visible(thread)
            if visible is not None:
                count += sum(1 for m in visible.messages if after <= m.date < before)
        return count

    async def get_thread(self, thread_id: str) -> Thread:
        thread = self._threads.get(thread_id)
        visible = self._visible(thread) if thread else None
        if visible is None:
            raise MailboxError("thread not found")
        return visible

    def all_message_ids(self) -> set[str]:
        return {m.message_id for t in self._threads.values() for m in t.messages}


class TimeBoxedMailbox:
    """Wraps any mailbox and hides everything dated after `now`."""

    def __init__(self, inner: Mailbox, now: datetime):
        self.inner = inner
        self.now = now

    async def search(
        self,
        query: str,
        max_results: int = 25,
        after: datetime | None = None,
        before: datetime | None = None,
    ) -> list[ThreadSummary]:
        before = min(before, self.now) if before else self.now
        results = await self.inner.search(query, max_results, after=after, before=before)
        out = []
        for s in results:
            if s.last_date > self.now:
                thread = await self.get_thread(s.thread_id)
                s = _summary(thread)
            out.append(s)
        return out

    async def search_ids(
        self,
        query: str,
        max_results: int = 25,
        after: datetime | None = None,
        before: datetime | None = None,
    ) -> list[str]:
        before = min(before, self.now) if before else self.now
        finder = getattr(self.inner, "search_ids", None)
        if finder is not None:
            return await finder(query, max_results, after=after, before=before)
        return [s.thread_id for s in await self.inner.search(query, max_results, after, before)]

    async def get_thread(self, thread_id: str) -> Thread:
        thread = await self.inner.get_thread(thread_id)
        msgs = [m for m in thread.messages if m.date <= self.now]
        if not msgs:
            raise MailboxError("thread not found")
        return Thread(thread_id=thread_id, messages=msgs)
