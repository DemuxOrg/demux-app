"""Login session (owned by better-auth) and the Gmail OAuth state.

Login is handled by better-auth in the Next.js app. It sets an httpOnly cookie named
`demux.session_token` (`__Secure-demux.session_token` over HTTPS) whose value is
`<token>.<signature>`. Frontend and backend share one site (localhost, or subdomains of
one domain with AUTH_COOKIE_DOMAIN set in the frontend), so the browser sends the
cookie to this API too. We resolve it by looking the token up in `auth_sessions`: the
token is 32 random characters, unguessable, and the row is deleted on sign-out.

OAuth `state` for the Gmail connection is a signed, short-lived nonce that is also set in
a cookie so the callback can check that the same browser started the flow.
"""

import secrets
from datetime import UTC, datetime

from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Env, settings
from app.models.auth import AuthSession
from app.models.user import User

# Must match `advanced.cookiePrefix` in frontend/src/lib/auth.ts.
SESSION_COOKIES = ("__Secure-demux.session_token", "demux.session_token")
STATE_COOKIE = "demux_oauth_state"
STATE_MAX_AGE_S = 600


def session_token_from_cookies(cookies: dict[str, str]) -> str | None:
    for name in SESSION_COOKIES:
        value = cookies.get(name)
        if value:
            # "<token>.<signature>": the token never contains a dot.
            return value.split(".", 1)[0] or None
    return None


async def user_for_session_token(session: AsyncSession, token: str) -> User | None:
    """The verified user behind a live better-auth session, or None."""
    return await session.scalar(
        select(User)
        .join(AuthSession, AuthSession.user_id == User.id)
        .where(
            AuthSession.token == token,
            AuthSession.expires_at > datetime.now(UTC),
            User.email_verified.is_(True),
        )
    )


def _serializer(salt: str) -> URLSafeTimedSerializer:
    if not settings.SECRET_KEY:
        raise RuntimeError("SECRET_KEY is not set (run `make setup`).")
    return URLSafeTimedSerializer(settings.SECRET_KEY, salt=salt)


def make_state() -> tuple[str, str]:
    """Return (nonce, signed_state). The nonce goes in a cookie, the state to Google."""
    nonce = secrets.token_urlsafe(24)
    return nonce, _serializer("oauth-state").dumps(nonce)


def check_state(state: str, nonce_cookie: str | None) -> bool:
    if not nonce_cookie:
        return False
    try:
        nonce = _serializer("oauth-state").loads(state, max_age=STATE_MAX_AGE_S)
    except BadSignature:
        return False
    return secrets.compare_digest(str(nonce), nonce_cookie)


def cookie_secure() -> bool:
    return settings.ENV == Env.PROD
