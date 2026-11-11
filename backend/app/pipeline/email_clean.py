"""Cleaning of thread text before it goes to the planner. No PII work."""

from app.pipeline.planner.models import Thread


def clean_thread(thread: Thread) -> Thread:
    """Return a copy of `thread` with noise removed from each message body.

    Drops quoted replies (lines starting with `>` and "On ... wrote:" blocks) and
    signatures after a `-- ` line, then collapses whitespace. Ids, senders, dates,
    subjects and attachments are unchanged.
    """
    raise NotImplementedError
