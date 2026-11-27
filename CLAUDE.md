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

## Access (paywall)
- Only an email with access may sign up or use the app: a Stripe subscription (`trialing` = the 14-day free trial, `active`, `past_due`), free access from `/admin/access`, or an admin. One rule: `app/services/access.py`. See `docs/ACCESS.md`.
- Sign-up: better-auth's `user.create.before` hook calls `POST /internal/signup-check` (`INTERNAL_API_SECRET`, frontend `src/lib/access.ts`). Throw 402/503 from that hook, never 403 (better-auth turns a 403 into a fake success).
- New user-facing routes depend on `get_entitled_user` (402 `subscription_required`), like the `/workspaces` router. `/me` stays open. The worker only syncs users with access.
- Stripe is read-only here: the API's own webhook (`/billing/stripe/webhook`) re-reads the customer and fills `billing_customers`. The landing page (`DemuxUI`) owns checkout.
- Tests: the two test users have free access (`conftest.py`); use the `no_access` fixture to test the gate.

## UI
`frontend/theme.md` is the design system and wins over code: read it before changing UI, change it first. Generated studio apps (v3) are the exception: the interface designer gives each one its own look (theme.md §10.3). Older v1/v2 apps get Demux's tokens through `backend/app/agent/shell.py`.

## Generated apps (UI generation)
See `docs/UI_GENERATION_PLAN.md` §11. The **interface designer** (`UI_MODEL`, GLM-5.2, `app/agent/designer.py`) designs the UX and writes every app as a studio app (v3): one JSX `App({ data })` with its own look, using the studio runtime in `app-kit/src/studio.tsx` (React, Recharts, icons, data helpers; Tailwind compiled in the iframe; embedded fonts). The main agent (Qwen) never writes interface code: builds hand the designer the facts, edits go through the `change_interface` tool. After changing `app-kit/src`, run `make kit` and commit the built `backend/app/agent/kit/` (the shell inlines it; the iframe allows no network). Every global the studio exposes must be documented in `app-kit/src/studio.md` (the build fails otherwise): it is the designer's reference. The component kit (`catalog.md`) only serves older v2 apps. The build is shown live (theme.md §7.10): the workspace fills in while emails are read, and question moments (§7.15) ask one question at a time while the agent keeps working. If the prompt doesn't say how the workspace should look, the first moment asks (Demux decides / light / dark / bold / free text); the answer goes to the interface designer, never to Demux's palettes (`app/agent/look.py`). Then the design agent's clarifying questions, only for the gaps in the prompt (none for a precise prompt, up to 5 for a vague one, never about the look): `ask_user` returns at once and `get_answers` collects them (`app/services/setup.py`, `frontend/src/components/workspace/LiveBuild.tsx`). There is no layout step: the designer decides the structure.

## Admin (/admin)
- Staff only: `ADMIN_EMAILS` (env) or `users.is_admin`. Every `/api/v1/admin/*` route depends on `get_admin_user` (401 without session, 404 for non-admins, one `admin_audit` row per request).
- **Privacy:** admin responses carry ids, counts, tokens, costs, statuses, dates, prompts and edit messages only. Never email content, subjects, senders, record values, the guide, app HTML or run summaries. A new response field must be added to `ALLOWED_FIELDS` in `backend/tests/test_admin.py` (the test fails otherwise): review it against this rule first.
- **Cost metering:** every LLM call goes through `MeteredLLM` (`app/agent/llm.py`), which writes an `llm_calls` row with the prices used; bill calls with `usage_scope(...)`. Run totals are added from the same amounts.
- **Demo inbox:** `/admin/demo` writes synthetic threads into the `TEST_GMAIL` inbox over IMAP (app password); the only code that writes mail. Never point it at a user's Gmail.

## Keep it simple
No new infra (queues, caches, vector DBs) without an explicit decision.
