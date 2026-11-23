"""Gmail connection (backend-owned Google OAuth) and `/me`.

Login itself (email + password, emailed code) is better-auth in the Next.js app. Here a
signed-in user connects Gmail: the browser goes to Google and back to
`/auth/google/callback`, which stores the tokens encrypted on the user and redirects to
the frontend page the flow started from (`?next=`, from a fixed list). The frontend never
sees Google tokens.

`/me` reads the signed-in user; `PATCH /me` edits their first and last name;
`DELETE /me/gmail` disconnects their Gmail.
"""

import logging
from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from app.api.deps import CurrentUser, SessionDep, get_current_user
from app.auth import google
from app.auth.session import (
    STATE_COOKIE,
    STATE_MAX_AGE_S,
    check_state,
    cookie_secure,
    make_state,
)
from app.core.config import settings
from app.core.errors import AppError, UnauthorizedError
from app.models.user import User
from app.schemas.workspace import Me, MeUpdate
from app.services import users

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])

GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"

# Where the frontend sends the user back after Google, by `?next=` key. A fixed list, so
# the parameter can never redirect anywhere else.
NEXT_PAGES = {"new": "/workspaces/new", "profile": "/profile"}
NEXT_COOKIE = "demux_oauth_next"


class NotConfiguredError(AppError):
    status_code = 503
    code = "google_not_configured"


def _frontend(path: str, **params: str) -> RedirectResponse:
    query = f"?{urlencode(params)}" if params else ""
    return RedirectResponse(f"{settings.FRONTEND_URL}{path}{query}", status_code=302)


async def _signed_in(request: Request, session: SessionDep) -> User | None:
    try:
        return await get_current_user(request, session)
    except UnauthorizedError:
        return None


@router.get("/auth/google/login")
async def google_login(
    request: Request, session: SessionDep, next: str = "new"
) -> RedirectResponse:
    """Start connecting Gmail. Needs a signed-in Demux user."""
    if await _signed_in(request, session) is None:
        return _frontend("/login")
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise NotConfiguredError(
            "Gmail connection is not configured: set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET."
        )
    nonce, state = make_state()
    resp = RedirectResponse(google.authorization_url(state), status_code=302)
    for name, value in (
        (STATE_COOKIE, nonce),
        (NEXT_COOKIE, next if next in NEXT_PAGES else "new"),
    ):
        resp.set_cookie(
            name,
            value,
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
    user = await _signed_in(request, session)
    if user is None:
        return _frontend("/login")
    back = NEXT_PAGES.get(request.cookies.get(NEXT_COOKIE, ""), NEXT_PAGES["new"])
    if error or not code or not state:
        return _frontend(back, error="google_denied")
    if not check_state(state, request.cookies.get(STATE_COOKIE)):
        return _frontend(back, error="bad_state")
    try:
        tokens, sub, gmail_email, scope = await google.exchange_code(code)
    except google.OAuthError:
        return _frontend(back, error="google_failed")
    if GMAIL_SCOPE not in scope.split():
        return _frontend(back, error="gmail_scope_missing")
    await google.link_gmail(session, user, sub, gmail_email, tokens)
    logger.info("gmail connected: user=%s", user.id)
    resp = _frontend(back, gmail="connected")
    resp.delete_cookie(STATE_COOKIE, path="/api/v1/auth")
    resp.delete_cookie(NEXT_COOKIE, path="/api/v1/auth")
    return resp


def _me(user: User) -> Me:
    return Me(
        email=user.email,
        name=user.name,
        first_name=user.first_name,
        last_name=user.last_name,
        gmail_email=user.gmail_email,
        gmail_connected=google.gmail_connected(user),
        needs_reconnect=user.needs_reconnect,
    )


@router.get("/me", response_model=Me)
async def me(user: CurrentUser) -> Me:
    return _me(user)


@router.patch("/me", response_model=Me)
async def update_me(body: MeUpdate, user: CurrentUser, session: SessionDep) -> Me:
    await users.rename(session, user, body.first_name, body.last_name)
    return _me(user)


@router.delete("/me/gmail", response_model=Me)
async def disconnect_gmail(user: CurrentUser, session: SessionDep) -> Me:
    """Disconnect the signed-in user's Gmail. Their workspaces stay; syncing pauses."""
    await google.unlink_gmail(session, user)
    logger.info("gmail disconnected: user=%s", user.id)
    return _me(user)
