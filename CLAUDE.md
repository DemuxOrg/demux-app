# CLAUDE.md — conventions for Claude Code sessions

Demux turns a user's Gmail into structured, refreshable workspaces using an LLM extraction pipeline. Phase 0 is only the skeleton. See `docs/REPO_GUIDE.md` for a full tour.

## Running things
Everything goes through the `Makefile` at the repo root: `make setup`, `make install`, `make up`, `make down`, `make db`, `make migrate`, `make backend`, `make frontend`, `make gen-api`, `make lint`, `make test`.

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
The **backend owns the Google OAuth flow and Gmail tokens**. The frontend never sees Google access/refresh tokens. Don't use NextAuth/Auth.js for Gmail tokens. Until Phase 1, `get_current_user` (`app/api/deps.py`) is a dev stub that 401s in `ENV=prod`.

## Keep it simple
No new infra (queues, caches, vector DBs) without an explicit decision.
