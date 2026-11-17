"""Auth: state check, session cookie, 401 without session, token crypto, invalid_grant."""

from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import pytest

from app.auth import google
from app.auth.crypto import decrypt, encrypt
from app.auth.session import (
    SESSION_COOKIE,
    STATE_COOKIE,
    check_state,
    make_session_token,
    make_state,
    read_session_token,
)
from app.core.config import Env, settings
from app.mail.base import ReconnectRequired
from app.models.user import User


def test_token_encryption_roundtrip():
    enc = encrypt("ya29.secret")
    assert enc != "ya29.secret" and decrypt(enc) == "ya29.secret"


def test_state_and_session_tokens():
    nonce, state = make_state()
    assert check_state(state, nonce)
    assert not check_state(state, "other")
    assert not check_state(state + "x", nonce)
    assert not check_state(state, None)
    import uuid

    uid = uuid.uuid4()
    assert read_session_token(make_session_token(uid)) == uid
    assert read_session_token("forged.token") is None


async def test_login_redirects_to_google_with_offline_access(client):
    resp = await client.get("/api/v1/auth/google/login", follow_redirects=False)
    assert resp.status_code == 302
    q = parse_qs(urlparse(resp.headers["location"]).query)
    assert q["access_type"] == ["offline"] and q["prompt"] == ["consent"]
    assert "gmail.readonly" in q["scope"][0]
    assert STATE_COOKIE in resp.cookies


async def test_callback_rejects_bad_state(client):
    client.cookies.set(STATE_COOKIE, "nonce", path="/api/v1/auth")
    resp = await client.get(
        "/api/v1/auth/google/callback?code=c&state=bogus", follow_redirects=False
    )
    assert "error=bad_state" in resp.headers["location"]


async def test_callback_signs_in(client, session, monkeypatch):
    async def fake_exchange(code):
        tokens = google.TokenSet("acc", "ref", datetime.now(UTC) + timedelta(hours=1))
        return tokens, "sub-123", "me@x.example", "openid " + google.SCOPES.split()[-1]

    monkeypatch.setattr(google, "exchange_code", fake_exchange)
    nonce, state = make_state()
    client.cookies.set(STATE_COOKIE, nonce, path="/api/v1/auth")
    resp = await client.get(
        f"/api/v1/auth/google/callback?code=c&state={state}", follow_redirects=False
    )
    assert resp.headers["location"].endswith("/workspaces")
    cookie = resp.cookies[SESSION_COOKIE]
    client.cookies.clear()
    client.cookies.set(SESSION_COOKIE, cookie)
    me = await client.get("/api/v1/me")
    assert me.json() == {"email": "me@x.example", "needs_reconnect": False}
    user = await session.get(User, read_session_token(cookie))
    assert user.access_token_enc and decrypt(user.access_token_enc) == "acc"


async def test_401_without_session_outside_test_env(client, monkeypatch):
    monkeypatch.setattr(settings, "ENV", Env.DEV)
    resp = await client.get("/api/v1/me")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"
    client.cookies.set(SESSION_COOKIE, "garbage")
    assert (await client.get("/api/v1/workspaces")).status_code == 401


async def test_invalid_grant_marks_needs_reconnect(session, session_factory, monkeypatch):
    user = User(
        email="r@x.example",
        refresh_token_enc=encrypt("ref"),
        access_token_enc=encrypt("old"),
        token_expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    session.add(user)
    await session.flush()

    async def boom(refresh_token):
        raise ReconnectRequired("invalid_grant")

    monkeypatch.setattr(google, "refresh_access_token", boom)
    provider = google.UserTokenProvider(session_factory, user.id)
    with pytest.raises(ReconnectRequired):
        await provider.get()
    await session.refresh(user)
    assert user.needs_reconnect is True
