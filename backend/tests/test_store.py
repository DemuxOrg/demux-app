"""Data store rules (pure) and snapshot / undo / change rows (DB)."""

import pytest
from sqlalchemy import func, select

from app.models import Change, Snapshot, Workspace
from app.services import store
from app.services.store import DataError, apply_delete, apply_save

SEEN = {"m1": "t1", "m2": "t2"}


def save(data, records, rtype="loan"):
    return apply_save(data, rtype, records, seen_messages=SEEN)


def rec(rid="a-1", fields=None, sources=("m1",)):
    return {"id": rid, "fields": fields or {"title": "Dune"}, "source_message_ids": list(sources)}


def test_create_then_merge_update_and_null_clear():
    data, results, changes = save({}, [rec(fields={"title": "Dune", "due": "2026-01-01"})])
    assert results == [{"id": "a-1", "status": "created"}]
    assert changes[0].op == "create" and changes[0].before is None
    r = data["loan"]["a-1"]
    assert r["_sources"] == [{"message_id": "m1", "thread_id": "t1"}] and r["_updated_at"]

    data2, results, changes = save(data, [rec(fields={"due": None}, sources=["m2"])])
    assert results[0]["status"] == "updated" and results[0]["fields"] == ["due"]
    assert data2["loan"]["a-1"]["title"] == "Dune" and data2["loan"]["a-1"]["due"] is None
    assert changes[0].before == {"title": "Dune", "due": "2026-01-01"}
    assert changes[0].after == {"title": "Dune", "due": None}
    assert [s["message_id"] for s in data2["loan"]["a-1"]["_sources"]] == ["m1", "m2"]
    # input not mutated
    assert data["loan"]["a-1"]["due"] == "2026-01-01"


def test_unchanged_save_records_no_change_row():
    data, _, _ = save({}, [rec()])
    _, results, changes = save(data, [rec()])
    assert results[0]["status"] == "unchanged" and changes == []


@pytest.mark.parametrize(
    "record,msg",
    [
        (rec(rid="Bad Id"), "id must match"),
        (rec(sources=[]), "at least one"),
        (rec(sources=["nope"]), "received in this run"),
        (rec(fields={"_secret": 1}), "reserved"),
        (rec(fields={"Title": "x"}), "snake_case"),
        (rec(fields={"x": {"a": 1}}), "string, number"),
        (rec(fields={"x": [[1]]}), "flat"),
        (rec(fields={"x": "a" * 2001}), "longer than"),
        (rec(fields={f"f{i}": i for i in range(21)}), "at most 20 fields"),
    ],
)
def test_validation_rejects(record, msg):
    with pytest.raises(DataError, match=msg):
        save({}, [record])


def test_one_bad_record_rejects_the_whole_call():
    with pytest.raises(DataError):
        save({}, [rec(rid="ok-1"), rec(rid="BAD")])


def test_caps_on_types_and_records():
    data = {f"t{i}": {} for i in range(5)}
    with pytest.raises(DataError, match="5 record types"):
        apply_save(data, "t9", [rec()], seen_messages=SEEN)
    many = {"loan": {f"r-{i}": {"title": "x"} for i in range(500)}}
    with pytest.raises(DataError, match="500 records"):
        save(many, [rec(rid="new-one")])
    with pytest.raises(DataError, match="snake_case"):
        apply_save({}, "Bad-Type", [rec()], seen_messages=SEEN)


def test_sources_capped_at_ten():
    seen = {f"m{i}": "t" for i in range(15)}
    data = {}
    for i in range(15):
        data, _, _ = apply_save(
            data, "loan", [rec(fields={"n": i}, sources=[f"m{i}"])], seen_messages=seen
        )
    assert len(data["loan"]["a-1"]["_sources"]) == 10
    assert data["loan"]["a-1"]["_sources"][-1]["message_id"] == "m14"


def test_delete():
    data, _, _ = save({}, [rec(rid="a-1"), rec(rid="a-2")])
    new, deleted, changes = apply_delete(data, "loan", ["a-1"])
    assert deleted == ["a-1"] and list(new["loan"]) == ["a-2"]
    assert changes[0].op == "delete" and changes[0].after is None
    with pytest.raises(DataError, match="unknown ids"):
        apply_delete(new, "loan", ["zzz"])
    gone, _, _ = apply_delete(new, "loan", ["a-2"])
    assert gone == {}


async def _workspace(session, dev_user, **kw):
    ws = Workspace(user_id=dev_user.id, name="w", prompt="p", **kw)
    session.add(ws)
    await session.flush()
    return ws


async def test_persist_bumps_version_and_writes_changes(session, dev_user):
    ws = await _workspace(session, dev_user)
    data, _, changes = save({}, [rec()])
    v = await store.persist_data(session, ws.id, None, data, changes)
    assert v == 1
    n = await session.scalar(
        select(func.count()).select_from(Change).where(Change.workspace_id == ws.id)
    )
    assert n == 1


async def test_snapshot_undo_roundtrip_and_retention(session, dev_user):
    ws = await _workspace(session, dev_user, data={"loan": {"a": {"x": 1}}}, guide="g1")
    await store.take_snapshot(session, ws.id, None)
    ws.data = {"loan": {"a": {"x": 2}}}
    ws.guide = "g2"
    await session.flush()
    restored = await store.undo(session, dev_user.id, ws.id)
    assert restored.data == {"loan": {"a": {"x": 1}}} and restored.guide == "g1"
    undo_rows = await session.scalar(
        select(func.count()).select_from(Change).where(Change.record_type == "_workspace")
    )
    assert undo_rows == 1
    for _ in range(12):
        await store.take_snapshot(session, ws.id, None)
    n = await session.scalar(
        select(func.count()).select_from(Snapshot).where(Snapshot.workspace_id == ws.id)
    )
    assert n == 10


async def test_processed_messages_dedupe(session, dev_user):
    ws = await _workspace(session, dev_user)
    await store.mark_processed(session, ws.id, None, [("m1", "t1"), ("m2", "t1")])
    await store.mark_processed(session, ws.id, None, [("m1", "t1")])
    assert await store.processed_message_ids(session, ws.id) == {"m1", "m2"}
    assert await store.processed_thread_ids(session, ws.id) == ["t1"]


async def test_undo_never_restores_the_pre_build_snapshot(session, dev_user):
    from app.core.errors import ConflictError
    from app.models import Run, RunKind, RunStatus

    ws = await _workspace(session, dev_user, data={"t": {"a": {"x": 1}}})
    build = Run(workspace_id=ws.id, kind=RunKind.BUILD, status=RunStatus.DONE)
    session.add(build)
    await session.flush()
    session.add(Snapshot(workspace_id=ws.id, run_id=build.id, data={}, guide="", config={}))
    await session.flush()
    with pytest.raises(ConflictError, match="Nothing to undo"):
        await store.undo(session, dev_user.id, ws.id)


def test_older_sources_only_fill_empty_fields_in_parallel_backfill():
    from datetime import UTC, datetime

    dates = {"m1": datetime(2026, 10, 1, tzinfo=UTC), "m2": datetime(2026, 10, 9, tzinfo=UTC)}

    def go(data, fields, src):
        return apply_save(
            data,
            "bill",
            [rec(fields=fields, sources=[src])],
            seen_messages=SEEN,
            message_dates=dates,
            older_fill_only=True,
        )[0]

    # The newer email (paid) is saved first, the older one (unpaid, amount) arrives later.
    data = go({}, {"status": "paid", "amount": None}, "m2")
    data = go(data, {"status": "unpaid", "amount": 40}, "m1")
    r = data["bill"]["a-1"]
    assert r["status"] == "paid" and r["amount"] == 40
    assert r["_latest"] == "2026-10-09T00:00:00Z"
    # In the normal order the newer email still wins.
    data = go(go({}, {"status": "unpaid"}, "m1"), {"status": "paid"}, "m2")
    assert data["bill"]["a-1"]["status"] == "paid"
