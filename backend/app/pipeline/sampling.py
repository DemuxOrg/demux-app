"""Deterministic thread sampling (stage: sampling)."""

from app.pipeline.planner.models import Thread


def sample_threads(threads: list[Thread], k: int = 20) -> list[Thread]:
    """Pick at most `k` threads, deterministically (same input => same output).

    Order by latest message date, newest first. Prefer threads with >= 2 messages; take at
    most 3 threads per sender domain (domain of the first message's sender). If those
    constraints leave slots empty, fill the rest in date order. Returns <= k threads.
    """
    raise NotImplementedError
