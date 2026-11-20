"""Auth: better-auth session cookie lookup, Gmail OAuth state and linking, token crypto,
invalid_grant."""

import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import pytest

from app.api.routes.auth import NEXT_COOKIE
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
    _, cookie = await _signed_in_user(
        session, "login@x.example", name="Rana Haddad", first_name="Rana", last_name="Haddad"
    )
    client.cookies.set(COOKIE, cookie)
    me = (await client.get("/api/v1/me")).json()
    assert me == {
        "email": "login@x.example",
        "name": "Rana Haddad",
        "first_name": "Rana",
        "last_name": "Haddad",
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
    assert q["access_type"] == ["offline"] and q["prompt"] == ["select_account consent"]
    assert "gmail.readonly" in q["scope"][0]
    assert STATE_COOKIE in resp.cookies


async def test_gmail_connection_belongs_to_one_account(session):
    tokens = google.TokenSet("access", "refresh", datetime.now(UTC) + timedelta(hours=1))
    a, _ = await _signed_in_user(session, "a@x.example")
    b, _ = await _signed_in_user(session, "b@x.example")
    await google.link_gmail(session, a, "sub-1", "shared@gmail.com", tokens)
    assert google.gmail_connected(a) and not google.gmail_connected(b)
    assert b.gmail_email is None and b.refresh_token_enc is None
    # A second account may connect the same Gmail; each keeps its own row.
    await google.link_gmail(session, b, "sub-1", "shared@gmail.com", tokens)
    assert a.id != b.id and a.gmail_email == b.gmail_email == "shared@gmail.com"


async def test_disconnect_gmail_clears_only_this_account(client, session):
    tokens = google.TokenSet("access", "refresh", datetime.now(UTC) + timedelta(hours=1))
    a, cookie = await _signed_in_user(session, "a@x.example")
    b, _ = await _signed_in_user(session, "b@x.example")
    await google.link_gmail(session, a, "sub-1", "shared@gmail.com", tokens)
    await google.link_gmail(session, b, "sub-1", "shared@gmail.com", tokens)
    client.cookies.set(COOKIE, cookie)
    me = (await client.delete("/api/v1/me/gmail")).json()
    assert me["gmail_connected"] is False and me["gmail_email"] is None
    await session.refresh(a)
    await session.refresh(b)
    assert a.refresh_token_enc is None and a.access_token_enc is None and a.google_sub is None
    assert b.gmail_email == "shared@gmail.com" and google.gmail_connected(b)
    resp = await client.post("/api/v1/workspaces", json={"prompt": "Track my invoices"})
    assert resp.json()["error"]["code"] == "gmail_not_connected"


async def test_callback_rejects_bad_state(client):
    client.cookies.set(STATE_COOKIE, "nonce", path="/api/v1/auth")
    resp = await client.get(
        "/api/v1/auth/google/callback?code=c&state=bogus", follow_redirects=False
    )
    assert "error=bad_state" in resp.headers["location"]


@pytest.mark.parametrize(("next_", "kept"), [("profile", "profile"), ("https://evil", "new")])
async def test_gmail_login_remembers_only_known_return_pages(client, next_, kept):
    resp = await client.get(f"/api/v1/auth/google/login?next={next_}", follow_redirects=False)
    assert resp.cookies[NEXT_COOKIE] == kept


async def test_callback_returns_to_the_page_it_started_from(client):
    client.cookies.set(NEXT_COOKIE, "profile", path="/api/v1/auth")
    resp = await client.get("/api/v1/auth/google/callback?error=access_denied")
    assert resp.headers["location"].endswith("/profile?error=google_denied")


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
    assert resp.headers["location"].endswith("/workspaces/new?gmail=connected")
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


async def test_update_me_sets_first_and_last_name(client, session):
    user, cookie = await _signed_in_user(session, "login@x.example", name="login")
    client.cookies.set(COOKIE, cookie)
    resp = await client.patch("/api/v1/me", json={"first_name": " Rana ", "last_name": "Haddad"})
    assert resp.status_code == 200
    assert resp.json()["first_name"] == "Rana" and resp.json()["last_name"] == "Haddad"
    await session.refresh(user)
    assert user.name == "Rana Haddad"


@pytest.mark.parametrize(
    "body", [{"first_name": "  ", "last_name": "Haddad"}, {"first_name": "Rana"}]
)
async def test_update_me_needs_both_names(client, session, body):
    _, cookie = await _signed_in_user(session, "login@x.example")
    client.cookies.set(COOKIE, cookie)
    resp = await client.patch("/api/v1/me", json=body)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"
