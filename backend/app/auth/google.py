"""Gmail connection: Google OAuth (authorization code flow, backend-owned), token refresh.

This is not login (better-auth handles that). Each Demux account owns at most one Gmail
connection, stored on its own `users` row: a new account starts with none, and connecting
one never touches another account. Two Demux accounts may connect the same Gmail; each
then holds its own tokens. The Gmail address may differ from the login email.

Endpoints from Google's OAuth 2.0 for web server apps documentation:
- authorization: https://accounts.google.com/o/oauth2/v2/auth
- token exchange / refresh: https://oauth2.googleapis.com/token
- identity: the `id_token` returned with the code exchange (we only read `sub` and
  `email` from the userinfo endpoint, which avoids verifying the JWT ourselves).

Tokens are stored encrypted on the user row. `invalid_grant` on refresh (revoked, or the
~7-day expiry for apps in *Testing*) marks the user `needs_reconnect`.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.crypto import decrypt, encrypt
from app.core.config import settings
from app.mail.base import ReconnectRequired
from app.models.user import User

logger = logging.getLogger(__name__)

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
SCOPES = "openid email https://www.googleapis.com/auth/gmail.readonly"


class OAuthError(Exception):
    pass


@dataclass
class TokenSet:
    access_token: str
    refresh_token: str | None
    expires_at: datetime


def authorization_url(state: str) -> str:
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        # select_account: always show Google's account chooser. With "consent" alone,
        # Google silently reuses the Google account the browser is signed in to, so every
        # Demux account in that browser ended up connected to the same Gmail.
        # consent: always return a refresh token.
        "prompt": "select_account consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    return f"{AUTH_URL}?{urlencode(params)}"


def _token_set(body: dict) -> TokenSet:
    return TokenSet(
        access_token=body["access_token"],
        refresh_token=body.get("refresh_token"),
        expires_at=datetime.now(UTC) + timedelta(seconds=int(body.get("expires_in", 3600)) - 60),
    )


async def exchange_code(code: str) -> tuple[TokenSet, str, str, str]:
    """Exchange an authorization code. Returns (tokens, google_sub, email, granted_scope)."""
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        if resp.status_code != 200:
            logger.warning("google code exchange failed: status=%s", resp.status_code)
            raise OAuthError("Google sign-in failed.")
        body = resp.json()
        tokens = _token_set(body)
        info = await client.get(
            USERINFO_URL, headers={"Authorization": f"Bearer {tokens.access_token}"}
        )
        if info.status_code != 200:
            raise OAuthError("Could not read the Google account.")
        user = info.json()
    return tokens, user["sub"], user["email"], body.get("scope", "")


async def link_gmail(
    session: AsyncSession, user: User, google_sub: str, gmail_email: str, tokens: TokenSet
) -> User:
    """Attach a Gmail account to a signed-in Demux user (replacing any previous one)."""
    user.google_sub = google_sub
    user.gmail_email = gmail_email
    user.access_token_enc = encrypt(tokens.access_token)
    if tokens.refresh_token:
        user.refresh_token_enc = encrypt(tokens.refresh_token)
    user.token_expires_at = tokens.expires_at
    user.needs_reconnect = False
    await session.flush()
    return user


async def unlink_gmail(session: AsyncSession, user: User) -> User:
    """Forget the signed-in user's Gmail connection: the address and every stored token.

    Only this Demux account's row changes. The grant is not revoked at Google: another
    Demux account may have connected the same Gmail, and revoking would cut it off too.
    The user can remove Demux at myaccount.google.com/permissions.
    """
    user.google_sub = None
    user.gmail_email = None
    user.access_token_enc = None
    user.refresh_token_enc = None
    user.token_expires_at = None
    user.needs_reconnect = False
    await session.flush()
    return user


def gmail_connected(user: User) -> bool:
    """True when the worker can read this user's mail (or reads the dev fake mailbox)."""
    return bool(user.refresh_token_enc) or settings.uses_fake_mailbox


async def refresh_access_token(refresh_token: str) -> TokenSet:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            TOKEN_URL,
            data={
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
    if resp.status_code in (400, 401):
        err = ""
        try:
            err = resp.json().get("error", "")
        except ValueError:
            pass
        if (
            err in ("invalid_grant", "unauthorized_client", "invalid_client")
            or resp.status_code == 401
        ):
            raise ReconnectRequired(err or "token refresh rejected")
    resp.raise_for_status()
    return _token_set(resp.json())


class UserTokenProvider:
    """Gives GmailMailbox a valid access token for one user, refreshing and persisting it.

    Uses its own DB sessions (the worker holds no long-lived session).
    """

    def __init__(self, session_factory, user_id):
        self._session_factory = session_factory
        self._user_id = user_id
        self._cached: tuple[str, datetime] | None = None

    async def get(self, force_refresh: bool = False) -> str:
        now = datetime.now(UTC)
        if self._cached and not force_refresh and self._cached[1] > now:
            return self._cached[0]
        async with self._session_factory() as session:
            user = await session.get(User, self._user_id)
            if user is None or user.needs_reconnect:
                raise ReconnectRequired("reconnect required")
            if (
                not force_refresh
                and user.access_token_enc
                and user.token_expires_at
                and user.token_expires_at > now
            ):
                token = decrypt(user.access_token_enc)
                self._cached = (token, user.token_expires_at)
                return token
            if not user.refresh_token_enc:
                user.needs_reconnect = True
                await session.commit()
                raise ReconnectRequired("no refresh token")
            try:
                tokens = await refresh_access_token(decrypt(user.refresh_token_enc))
            except ReconnectRequired:
                user.needs_reconnect = True
                await session.commit()
                raise
            user.access_token_enc = encrypt(tokens.access_token)
            if tokens.refresh_token:
                user.refresh_token_enc = encrypt(tokens.refresh_token)
            user.token_expires_at = tokens.expires_at
            await session.commit()
            self._cached = (tokens.access_token, tokens.expires_at)
            return tokens.access_token
