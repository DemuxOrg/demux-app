"""Auth: better-auth session cookie lookup, Gmail OAuth state and linking, token crypto,
invalid_grant."""

import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import pytest

from app.auth import google
from app.auth.crypto import decrypt, encrypt
from app.auth.session import STATE_COOKIE, check_state, make_state
from app.core.config import Env, settings
from app.mail.base import ReconnectRequired
from app.models.auth import AuthSession
from app.models.user import User

COOKIE = "demux.session_token"


async def _signed_in_user(session, email, *, verified=True, expires_in=timedelta(days=1), **kw):
    user = User(email=email, email_verified=verified, **kw)
    session.add(user)
    await session.flush()
    token = uuid.uuid4().hex
    session.add(
        AuthSession(user_id=user.id, token=token, expires_at=datetime.now(UTC) + expires_in)
    )
    await session.flush()
    return user, f"{token}.c2lnbmF0dXJl"


def test_token_encryption_roundtrip():
    enc = encrypt("ya29.secret")
    assert enc != "ya29.secret" and decrypt(enc) == "ya29.secret"


def test_state_tokens():
    nonce, state = make_state()
    assert check_state(state, nonce)
    assert not check_state(state, "other")
    assert not check_state(state + "x", nonce)
    assert not check_state(state, None)


async def test_session_cookie_resolves_user(client, session):
    _, cookie = await _signed_in_user(session, "login@x.example", name="Rana")
    client.cookies.set(COOKIE, cookie)
    me = (await client.get("/api/v1/me")).json()
    assert me == {
        "email": "login@x.example",
        "name": "Rana",
        "gmail_email": None,
        "gmail_connected": False,
        "needs_reconnect": False,
    }


@pytest.mark.parametrize("kw", [{"verified": False}, {"expires_in": timedelta(seconds=-1)}])
async def test_unverified_or_expired_session_is_401(client, session, kw):
    _, cookie = await _signed_in_user(session, "late@x.example", **kw)
    client.cookies.set(COOKIE, cookie)
    assert (await client.get("/api/v1/me")).status_code == 401


async def test_workspace_needs_gmail(client, session):
    _, cookie = await _signed_in_user(session, "nogmail@x.example")
    client.cookies.set(COOKIE, cookie)
    resp = await client.post("/api/v1/workspaces", json={"prompt": "Track my invoices"})
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "gmail_not_connected"


async def test_gmail_login_sends_signed_out_users_to_login(client, monkeypatch):
    monkeypatch.setattr(settings, "ENV", Env.DEV)
    resp = await client.get("/api/v1/auth/google/login", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"].endswith("/login")


async def test_gmail_login_redirects_to_google_with_offline_access(client):
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


async def test_callback_links_gmail_to_signed_in_user(client, session, monkeypatch):
    """The Gmail address can differ from the login email; login email is kept."""
    user, cookie = await _signed_in_user(session, "login@x.example")

    async def fake_exchange(code):
        tokens = google.TokenSet("acc", "ref", datetime.now(UTC) + timedelta(hours=1))
        return tokens, "sub-123", "inbox@gmail.example", "openid " + google.SCOPES.split()[-1]

    monkeypatch.setattr(google, "exchange_code", fake_exchange)
    nonce, state = make_state()
    client.cookies.set(COOKIE, cookie)
    client.cookies.set(STATE_COOKIE, nonce, path="/api/v1/auth")
    resp = await client.get(
        f"/api/v1/auth/google/callback?code=c&state={state}", follow_redirects=False
    )
    assert resp.headers["location"].endswith("/workspaces?gmail=connected")
    me = (await client.get("/api/v1/me")).json()
    assert me["email"] == "login@x.example"
    assert me["gmail_email"] == "inbox@gmail.example" and me["gmail_connected"] is True
    await session.refresh(user)
    assert user.access_token_enc and decrypt(user.access_token_enc) == "acc"


async def test_401_without_session_outside_test_env(client, monkeypatch):
    monkeypatch.setattr(settings, "ENV", Env.DEV)
    resp = await client.get("/api/v1/me")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"
    client.cookies.set(COOKIE, "garbage.sig")
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
