"""Auth endpoints: Google sign-in (backend-owned OAuth), logout, `/me`.

The browser is redirected to Google and back to `/auth/google/callback`, which stores
the tokens encrypted, sets the httpOnly session cookie and redirects to the frontend.
The frontend never sees Google tokens.
"""

import logging
from urllib.parse import urlencode

from fastapi import APIRouter, Request, Response
from fastapi.responses import RedirectResponse

from app.api.deps import CurrentUser, SessionDep
from app.auth import google
from app.auth.session import (
    SESSION_COOKIE,
    STATE_COOKIE,
    STATE_MAX_AGE_S,
    check_state,
    cookie_secure,
    make_session_token,
    make_state,
    session_max_age,
)
from app.core.config import settings
from app.core.errors import AppError
from app.schemas.workspace import Me

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])

GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"


class NotConfiguredError(AppError):
    status_code = 503
    code = "google_not_configured"


def _frontend(path: str, **params: str) -> RedirectResponse:
    query = f"?{urlencode(params)}" if params else ""
    return RedirectResponse(f"{settings.FRONTEND_URL}{path}{query}", status_code=302)


@router.get("/auth/google/login")
async def google_login() -> RedirectResponse:
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise NotConfiguredError(
            "Google sign-in is not configured: set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET."
        )
    nonce, state = make_state()
    resp = RedirectResponse(google.authorization_url(state), status_code=302)
    resp.set_cookie(
        STATE_COOKIE,
        nonce,
        max_age=STATE_MAX_AGE_S,
        httponly=True,
        samesite="lax",
        secure=cookie_secure(),
        path="/api/v1/auth",
    )
    return resp


@router.get("/auth/google/callback")
async def google_callback(
    request: Request,
    session: SessionDep,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    if error or not code or not state:
        return _frontend("/", error="google_denied")
    if not check_state(state, request.cookies.get(STATE_COOKIE)):
        return _frontend("/", error="bad_state")
    try:
        tokens, sub, email, scope = await google.exchange_code(code)
    except google.OAuthError:
        return _frontend("/", error="google_failed")
    if GMAIL_SCOPE not in scope.split():
        return _frontend("/", error="gmail_scope_missing")
    user = await google.upsert_user(session, sub, email, tokens)
    logger.info("user signed in: %s", user.id)
    resp = _frontend("/workspaces")
    resp.set_cookie(
        SESSION_COOKIE,
        make_session_token(user.id),
        max_age=session_max_age(),
        httponly=True,
        samesite="lax",
        secure=cookie_secure(),
        path="/",
    )
    resp.delete_cookie(STATE_COOKIE, path="/api/v1/auth")
    return resp


@router.post("/auth/logout", status_code=204)
async def logout() -> Response:
    resp = Response(status_code=204)
    resp.delete_cookie(SESSION_COOKIE, path="/")
    return resp


@router.get("/me", response_model=Me)
async def me(user: CurrentUser) -> Me:
    return Me(email=user.email, needs_reconnect=user.needs_reconnect)
