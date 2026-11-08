"""Tests for the workspaces API: CRUD, the 2-workspace limit, and user isolation."""

URL = "/api/v1/workspaces"
BODY = {"name": "Invoices", "prompt": "Track invoices from my email"}


async def test_create_list_get_delete(client):
    created = await client.post(URL, json=BODY)
    assert created.status_code == 201
    workspace = created.json()
    assert workspace["name"] == "Invoices"
    assert workspace["status"] == "draft"

    listed = await client.get(URL)
    assert [w["id"] for w in listed.json()] == [workspace["id"]]

    fetched = await client.get(f"{URL}/{workspace['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["prompt"] == BODY["prompt"]

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


async def test_user_cannot_read_other_users_workspace(client, other_client):
    created = await client.post(URL, json=BODY)
    workspace_id = created.json()["id"]

    assert (await other_client.get(f"{URL}/{workspace_id}")).status_code == 404
    assert (await other_client.delete(f"{URL}/{workspace_id}")).status_code == 404
    assert (await other_client.get(URL)).json() == []


async def test_validation_error_uses_error_format(client):
    response = await client.post(URL, json={"name": ""})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
