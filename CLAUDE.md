# CLAUDE.md — conventions for Claude Code sessions

Demux turns a user's Gmail into structured, refreshable workspaces using an LLM extraction pipeline. Phase 0 is only the skeleton. See `docs/REPO_GUIDE.md` for a full tour.

## Running things
Everything goes through the `Makefile` at the repo root: `make up` / `make down` (whole stack in Docker), `make logs`, `make restart`, `make prod-up`, `make setup`, `make install`, `make db`, `make migrate`, `make backend`, `make frontend`, `make gen-api`, `make kit`, `make lint`, `make test`. Dev data: `make users` (list accounts), `make delete-user email=…`, `make wipe` (every account, keeps the schema), `make reset` (drops the whole volume).

## Backend conventions
- Layering: **routes → services → models**. Routes stay thin (parse input, call a service, return a schema). Business logic lives in `app/services/`.
- Pydantic schemas live at the API boundary only (`app/schemas/`); services and models don't import them.
- **Every DB query on user data filters by `user_id`.** Another user's row is reported as 404, never 403.
- **Never log email content, prompts, or extracted data.** Log ids and counts.
- Schema changes always go through an Alembic migration (`make migration m="..."`).
- Errors use the `{ "error": { "code", "message" } }` shape (`app/core/errors.py`).

## Frontend conventions
- After changing API schemas: run `make gen-api` (backend running) and commit `frontend/src/lib/api-types.ts`.
- Client components only where interaction is needed.

## Auth
- **Login** is better-auth in the Next.js app (`frontend/src/lib/auth.ts`): email + password, verified by a 6-digit emailed code (10 minutes). Its tables (`auth_sessions`, `auth_accounts`, `auth_verifications`, login columns of `users`) are created by **Alembic**, not by better-auth (`backend/app/models/auth.py`); change both together. The backend resolves the `demux.session_token` cookie itself (`app/auth/session.py`).
- **Gmail** is a separate connection: the **backend owns the Google OAuth flow and Gmail tokens**; the Gmail address may differ from the login email. The frontend never sees Google tokens. Don't use better-auth social providers for Gmail tokens.
- In `ENV=test` with no cookie, `get_current_user` returns a dev user with Gmail connected.

## UI
`frontend/theme.md` is the design system and wins over code: read it before changing UI, change it first. Generated apps get the same tokens through `backend/app/agent/shell.py`.

## Generated apps (UI generation)
See `docs/UI_GENERATION_PLAN.md`. The agent writes a small JSX app composed from the component kit in `app-kit/` (shadcn-style, React + Radix + Recharts). After changing `app-kit/src`, run `make kit` and commit the built `backend/app/agent/kit/` (the shell inlines it; the iframe allows no network). Every global the kit exposes must be documented in `app-kit/src/catalog.md` (the build fails otherwise): it is the agent's reference. During a build the user picks a look, answers optional clarifying questions and picks layouts (`app/services/setup.py`, `frontend/src/components/workspace/BuildFlow.tsx`).

## Keep it simple
No new infra (queues, caches, vector DBs) without an explicit decision.
