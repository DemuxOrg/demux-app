"""Tests for GET /api/v1/health."""


async def test_health_ok(client):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok"}
    assert "x-request-id" in response.headers
