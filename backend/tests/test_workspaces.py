"""Workspaces API: CRUD, the 2-workspace limit, active-run 409, undo, and user isolation."""

import asyncio
import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.auth.crypto import encrypt
from app.core.errors import ConflictError
from app.models import Run, RunStatus, Snapshot, User, Workspace
from app.services.workspaces import MAX_WORKSPACES_PER_USER, create_workspace

URL = "/api/v1/workspaces"
BODY = {"prompt": "Track invoices from my email"}


async def test_create_list_get_rename_delete(client):
    created = await client.post(URL, json=BODY)
    assert created.status_code == 201
    workspace = created.json()
    assert workspace["name"] == BODY["prompt"][:60]
    assert workspace["status"] == "building"

    listed = await client.get(URL)
    assert [w["id"] for w in listed.json()] == [workspace["id"]]

    fetched = (await client.get(f"{URL}/{workspace['id']}")).json()
    assert fetched["prompt"] == BODY["prompt"]
    assert fetched["active_run"]["kind"] == "build"
    assert fetched["active_run"]["status"] == "queued"

    renamed = await client.patch(f"{URL}/{workspace['id']}", json={"name": "Bills"})
    assert renamed.json()["name"] == "Bills"

    deleted = await client.delete(f"{URL}/{workspace['id']}")
    assert deleted.status_code == 204
    assert (await client.get(f"{URL}/{workspace['id']}")).status_code == 404


async def test_workspace_limit_returns_409(client):
    assert (await client.post(URL, json=BODY)).status_code == 201
    assert (await client.post(URL, json=BODY)).status_code == 201
    third = await client.post(URL, json=BODY)
    assert third.status_code == 409
    assert third.json()["error"]["code"] == "conflict"
    assert "limit" in third.json()["error"]["message"].lower()


async def test_message_409_while_run_active_and_sync_is_noop(client):
    ws = (await client.post(URL, json=BODY)).json()
    resp = await client.post(f"{URL}/{ws['id']}/messages", json={"text": "make it blue"})
    assert resp.status_code == 409
    first = await client.post(f"{URL}/{ws['id']}/sync")
    runs = (await client.get(f"{URL}/{ws['id']}/runs")).json()
    assert first.status_code == 202 and len(runs) == 1  # the queued build, no new sync


async def test_undo_restores_snapshot(client, session):
    ws = (await client.post(URL, json=BODY)).json()
    w = await session.get(Workspace, ws["id"])
    await session.execute(Run.__table__.update().values(status=RunStatus.DONE.value))
    session.add(Snapshot(workspace_id=w.id, data={"a": {"x": {"v": 1}}}, guide="g", config={}))
    w.data = {"a": {"x": {"v": 2}}}
    await session.flush()
    resp = await client.post(f"{URL}/{ws['id']}/undo")
    assert resp.status_code == 200
    assert resp.json()["data"] == {"a": {"x": {"v": 1}}}
    assert (await client.post(f"{URL}/{ws['id']}/undo")).status_code == 409


async def test_user_isolation_everywhere(client, other_client):
    ws_id = (await client.post(URL, json=BODY)).json()["id"]
    for path in ["", "/app", "/data", "/runs", "/changes", "/guide"]:
        assert (await other_client.get(f"{URL}/{ws_id}{path}")).status_code == 404, path
    for path in ["/sync", "/undo", "/rebuild"]:
        assert (await other_client.post(f"{URL}/{ws_id}{path}")).status_code == 404, path
    msg = await other_client.post(f"{URL}/{ws_id}/messages", json={"text": "x"})
    assert msg.status_code == 404
    assert (await other_client.patch(f"{URL}/{ws_id}", json={"name": "x"})).status_code == 404
    assert (await other_client.delete(f"{URL}/{ws_id}")).status_code == 404
    assert (await other_client.get(URL)).json() == []


async def test_validation_error_uses_error_format(client):
    response = await client.post(URL, json={"prompt": ""})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_app_shell_has_csp(client):
    head = (await client.get("/api/v1/app-shell")).json()["head"]
    assert "Content-Security-Policy" in head and "default-src 'none'" in head


async def test_palette_defaults_to_violet_and_undo_keeps_it(client, session):
    ws = (await client.post(URL, json=BODY)).json()
    assert (await client.get(f"{URL}/{ws['id']}")).json()["palette"] == "violet"
    # No endpoint changes it after setup.
    put = await client.put(f"{URL}/{ws['id']}/palette", json={"palette": "teal"})
    assert put.status_code in (404, 405)

    # Chosen during the build, the palette is not part of what Undo restores.
    w = await session.get(Workspace, ws["id"])
    w.palette = "teal"
    await session.execute(Run.__table__.update().values(status=RunStatus.DONE.value))
    session.add(Snapshot(workspace_id=w.id, data={}, guide="g", config={}))
    await session.flush()
    assert (await client.post(f"{URL}/{ws['id']}/undo")).status_code == 200
    assert (await client.get(f"{URL}/{ws['id']}")).json()["palette"] == "teal"


async def test_app_shell_lists_palettes(client):
    shell = (await client.get("/api/v1/app-shell")).json()
    ids = [p["id"] for p in shell["palettes"]]
    assert ids == ["violet", "ocean", "teal", "rose", "graphite"]
    for p in shell["palettes"]:
        assert len(p["series"]) == 5 and p["series"][0] == p["accent"]
        assert f':root[data-palette="{p["id"]}"]' in shell["head"]


async def test_concurrent_creates_respect_the_limit(engine):
    """Parallel requests each in their own transaction (committed data, cleaned up)."""
    factory = async_sessionmaker(engine, expire_on_commit=False)
    email = f"race-{uuid.uuid4().hex[:8]}@demux.local"
    async with factory() as s:
        user = User(
            email=email, email_verified=True, gmail_email=email, refresh_token_enc=encrypt("t")
        )
        s.add(user)
        await s.commit()
    go = asyncio.Event()

    async def attempt(i: int) -> None:
        async with factory() as s:
            await go.wait()
            try:
                await create_workspace(s, user.id, f"prompt {i}")
                await asyncio.sleep(0.2)  # a slow request keeps its transaction open
                await s.commit()
            except ConflictError:
                await s.rollback()

    try:
        tasks = [asyncio.create_task(attempt(i)) for i in range(5)]
        await asyncio.sleep(0.05)
        go.set()
        await asyncio.gather(*tasks)
        async with factory() as s:
            n = await s.scalar(
                select(func.count()).select_from(Workspace).where(Workspace.user_id == user.id)
            )
        assert n == MAX_WORKSPACES_PER_USER
    finally:
        async with factory() as s:
            await s.execute(delete(User).where(User.id == user.id))
            await s.commit()
