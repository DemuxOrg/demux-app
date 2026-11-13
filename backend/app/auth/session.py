"""Signed session cookie and OAuth state.

The session cookie holds only the user id, signed with SECRET_KEY (itsdangerous). It is
httpOnly and SameSite=Lax; the frontend never reads it. OAuth `state` is a signed,
short-lived nonce that is also set in a cookie so the callback can check that the same
browser started the flow.
"""

import secrets
import uuid

from itsdangerous import BadSignature, URLSafeTimedSerializer

from app.core.config import Env, settings

SESSION_COOKIE = "demux_session"
STATE_COOKIE = "demux_oauth_state"
STATE_MAX_AGE_S = 600


def _serializer(salt: str) -> URLSafeTimedSerializer:
    if not settings.SECRET_KEY:
        raise RuntimeError("SECRET_KEY is not set (run `make setup`).")
    return URLSafeTimedSerializer(settings.SECRET_KEY, salt=salt)


def session_max_age() -> int:
    return settings.SESSION_MAX_AGE_DAYS * 24 * 3600


def make_session_token(user_id: uuid.UUID) -> str:
    return _serializer("session").dumps({"uid": str(user_id)})


def read_session_token(token: str) -> uuid.UUID | None:
    try:
        payload = _serializer("session").loads(token, max_age=session_max_age())
        return uuid.UUID(payload["uid"])
    except (BadSignature, KeyError, ValueError, TypeError):
        return None


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
