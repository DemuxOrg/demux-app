import random
from datetime import UTC, datetime, timedelta

from app.pipeline.planner.models import Message, Thread
from app.pipeline.sampling import sample_threads

BASE = datetime(2026, 1, 1, tzinfo=UTC)


def thread(tid, day, domain="a.example", n_messages=1):
    msgs = [
        Message(
            message_id=f"{tid}-m{i}",
            sender=f"Someone <x@{domain}>" if i == 0 else "me@me.example",
            to=["me@me.example"],
            date=BASE + timedelta(days=day, minutes=i),
            subject="s",
            body="b",
        )
        for i in range(n_messages)
    ]
    return Thread(thread_id=tid, messages=msgs)


def ids(threads):
    return [t.thread_id for t in threads]


def test_empty_and_small_input():
    assert sample_threads([]) == []
    ts = [thread("a", 1, "a.example"), thread("b", 2, "b.example")]
    assert sorted(ids(sample_threads(ts))) == ["a", "b"]


def test_k_cap():
    ts = [thread(f"t{i}", i, f"d{i}.example") for i in range(30)]
    assert len(sample_threads(ts)) == 20
    assert len(sample_threads(ts, k=5)) == 5
    assert len(sample_threads(ts, k=100)) == 30


def test_newest_first():
    ts = [thread(f"t{i}", i, f"d{i}.example") for i in range(10)]
    random.Random(1).shuffle(ts)
    out = sample_threads(ts, k=10)
    assert ids(out) == [f"t{i}" for i in range(9, -1, -1)]


def test_ordering_uses_latest_message_date():
    old_first_msg_new_reply = thread("long", 0, "a.example", n_messages=1)
    old_first_msg_new_reply.messages.append(
        thread("x", 50, "a.example").messages[0].model_copy(update={"message_id": "long-late"})
    )
    mid = thread("mid", 10, "b.example")
    assert ids(sample_threads([mid, old_first_msg_new_reply], k=10)) == ["long", "mid"]


def test_deterministic_and_order_independent():
    ts = [thread(f"t{i}", i % 7, f"d{i % 4}.example", 1 + i % 3) for i in range(40)]
    first = ids(sample_threads(ts))
    assert ids(sample_threads(ts)) == first
    for seed in range(5):
        shuffled = ts[:]
        random.Random(seed).shuffle(shuffled)
        assert ids(sample_threads(shuffled)) == first


def test_at_most_3_per_domain_when_alternatives_exist():
    spam = [thread(f"s{i}", 100 + i, "spam.example", 2) for i in range(10)]
    others = [thread(f"o{i}", i, f"o{i}.example", 2) for i in range(10)]
    out = sample_threads(spam + others, k=10)
    assert len(out) == 10
    assert sum(t.thread_id.startswith("s") for t in out) == 3


def test_domain_taken_from_first_message_sender():
    # a reply from another domain must not change the thread's domain
    ts = []
    for i in range(5):
        t = thread(f"s{i}", 100 + i, "spam.example", 2)
        t.messages[1] = t.messages[1].model_copy(update={"sender": "y@other.example"})
        ts.append(t)
    others = [thread(f"o{i}", i, f"o{i}.example", 2) for i in range(10)]
    out = sample_threads(ts + others, k=10)
    assert sum(t.thread_id.startswith("s") for t in out) == 3


def test_prefers_multi_message_threads():
    singles = [thread(f"s{i}", 100 + i, f"s{i}.example", 1) for i in range(10)]
    multis = [thread(f"m{i}", i, f"m{i}.example", 2) for i in range(5)]
    out = sample_threads(singles + multis, k=8)
    assert {f"m{i}" for i in range(5)} <= set(ids(out))
    assert len(out) == 8


def test_fill_in_when_constraints_leave_gaps():
    # one domain only: cap of 3 would leave gaps, so remaining slots are filled by date
    ts = [thread(f"t{i}", i, "same.example", 1) for i in range(10)]
    out = sample_threads(ts, k=6)
    assert len(out) == 6
    assert ids(out) == [f"t{i}" for i in range(9, 3, -1)]


def test_fill_in_keeps_newest_first_output():
    ts = [thread(f"t{i}", i, "same.example", 2) for i in range(8)]
    out = sample_threads(ts, k=5)
    dates = [max(m.date for m in t.messages) for t in out]
    assert dates == sorted(dates, reverse=True)
