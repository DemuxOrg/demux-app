"""Deterministic thread sampling (stage: sampling)."""

from email.utils import parseaddr

from app.pipeline.planner.models import Thread

MAX_PER_DOMAIN = 3


def _latest(thread: Thread):
    return max(m.date for m in thread.messages)


def _domain(thread: Thread) -> str:
    sender = thread.messages[0].sender
    addr = parseaddr(sender)[1]
    return addr.rsplit("@", 1)[-1].lower() if "@" in addr else sender.lower()


def sample_threads(threads: list[Thread], k: int = 20) -> list[Thread]:
    """Pick at most `k` threads, deterministically (same input => same output).

    Order by latest message date, newest first. Prefer threads with >= 2 messages; take at
    most 3 threads per sender domain (domain of the first message's sender). If those
    constraints leave slots empty, fill the rest in date order. Returns <= k threads.
    """
    ordered = sorted(threads, key=lambda t: (_latest(t), t.thread_id), reverse=True)
    chosen: list[Thread] = []
    chosen_ids: set[str] = set()
    per_domain: dict[str, int] = {}

    def take(candidates: list[Thread], respect_cap: bool) -> None:
        for t in candidates:
            if len(chosen) >= k:
                return
            if t.thread_id in chosen_ids:
                continue
            d = _domain(t)
            if respect_cap and per_domain.get(d, 0) >= MAX_PER_DOMAIN:
                continue
            chosen.append(t)
            chosen_ids.add(t.thread_id)
            per_domain[d] = per_domain.get(d, 0) + 1

    take([t for t in ordered if len(t.messages) >= 2], respect_cap=True)
    take(ordered, respect_cap=True)
    take(ordered, respect_cap=False)  # constraints left gaps: fill in date order
    return sorted(chosen, key=lambda t: (_latest(t), t.thread_id), reverse=True)
