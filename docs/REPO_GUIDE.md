# Demux repo guide

Read this first. It explains how the repo is laid out, what every file is responsible for, and where to put new code.

**What Demux is:** it turns a user's Gmail into structured, refreshable *workspaces* (tables, cards, Kanban) using an LLM extraction pipeline. **This repo is Phase 0**: only the skeleton exists (users, workspaces CRUD, health check, a plain UI). Gmail, LLM calls, real auth and background jobs are *not* built yet.

## 1. Big picture

```
Browser (Next.js :3000)  ──HTTP/JSON──▶  FastAPI (:8000)  ──asyncpg──▶  PostgreSQL 17 (docker, :5432)
   src/lib/api.ts                          /api/v1/...                    databases: demux, demux_test
```

- **Two ways to run it:** the whole stack in Docker (`make up`), or Postgres in Docker and backend/frontend natively (`make db` + `make backend` + `make frontend`).
- The frontend only talks to the backend's REST API. Types for that API are **generated** from the backend's OpenAPI schema.

## 2. Getting running

Everything in Docker (backend and frontend run with hot reload, source bind-mounted):

```bash
make setup && make up
```

Or natively on your machine:

```bash
make setup && make db && make migrate
make backend      # terminal 1
make frontend     # terminal 2
```

Open <http://localhost:3000> (backend status should say *ok*) and <http://localhost:8000/api/docs> (interactive API docs).

## 3. Repo layout

```
.
├── README.md  CLAUDE.md  SPEC.md  Makefile  docker-compose.yml  .env.example  .gitignore
├── .github/workflows/ci.yml
├── docker/init-test-db.sql
├── docs/REPO_GUIDE.md          ← you are here
├── app-kit/                    ← component kit for generated apps (Vite → backend/app/agent/kit/)
├── backend/                    ← Python / FastAPI
│   └── Dockerfile  .dockerignore
└── frontend/                   ← TypeScript / Next.js
    └── Dockerfile  .dockerignore
```

### UI generation (generated workspace apps)

| Path | Responsible for |
|---|---|
| `app-kit/src/` | The component kit: shadcn-style primitives (`ui/`), blocks such as Board, DataTable, Timeline, Calendar, Chart, Dashboard (`blocks/`), data helpers (`lib/data.ts`), the runtime that compiles the app's JSX and renders it (`index.tsx`), and `catalog.md`, the agent's reference. `make kit` builds it. |
| `backend/app/agent/kit/` | The built kit (`kit.js`, `kit.css`, `catalog.md`), committed: the shell inlines it into every v2 app. |
| `backend/app/agent/shell.py` | The fixed iframe shell: CSP, fonts, tokens, palettes, bridge; v1 (old HTML apps) or v2 (kit apps) by `app_runtime`. |
| `backend/app/agent/palettes.py` | The five palettes (theme.md §10.3). |
| `backend/app/agent/appcheck.py` | Static rules + headless render check every app must pass before it is stored. |
| `backend/app/agent/gallery.py` | Every kit block on sample data through the real shell (`uv run python -m app.agent.gallery out.html teal`). |
| `backend/app/services/setup.py` + `POST /workspaces/{id}/setup` | The user's setup answers during a build: look, clarifying questions, layouts. |
| `frontend/src/components/workspace/BuildFlow.tsx` | The five-step build screen (theme.md §7.10). |

### Root files

| File | Responsible for |
|---|---|
| `README.md` | 5-minute quick start. |
| `SPEC.md` | The original Phase 0 spec this repo was built from. |
| `CLAUDE.md` | Conventions for AI coding sessions (and good rules for humans too). |
| `Makefile` | The single entry point for dev commands (`make setup`, `install`, `up`, `down`, `reset`, `db`, `migrate`, `backend`, `frontend`, `lint`, `test`, `gen-api`, `migration m="..."`). |
| `docker-compose.yml` | Runs the full dev stack: Postgres 17 (healthcheck, persistent `pgdata` volume), backend (bind-mounted source, uvicorn `--reload`, migrations applied at start), worker (same image, `python -m app.worker`) and frontend (bind-mounted source, `next dev`). All read the root `.env`. |
| `docker-compose.prod.yml` | Production-like stack: the `prod` targets of both Dockerfiles, `ENV=prod`, no bind mounts, restart policies, Postgres not published. |
| `docker/init-test-db.sql` | Runs on first DB start; creates the extra `demux_test` database used by tests. |
| `.env.example` | Every environment variable with safe dev defaults. `make setup` copies it to `.env` (git-ignored). |
| `.github/workflows/ci.yml` | CI: backend (ruff + pytest on a Postgres service) and frontend (eslint + tsc + `next build`). |

## 4. Backend (`backend/`)

Request flow — **routes → services → models**:

```
HTTP request
  → app/api/routes/workspaces.py   (parse + validate with schemas, no logic)
  → app/services/workspaces.py     (business rules, DB queries, always filtered by user_id)
  → app/models/workspace.py        (SQLAlchemy table definition)
```

### Config & tooling

| File | Responsible for |
|---|---|
| `pyproject.toml` | Dependencies (managed by `uv`), ruff and pytest settings. |
| `Dockerfile`, `.dockerignore` | One image for the API and the worker. Python 3.12 + uv, deps from `uv.lock` into `/opt/.venv`, headless Chromium in `/opt/pw-browsers` (both outside `/app` so the dev bind mount never shadows them). Targets: `dev` (+ dev deps) and `prod` (source baked in, non-root). |
| `alembic.ini` | Alembic config. Does **not** hold the DB URL. |
| `alembic/env.py` | Runs migrations (async). Takes the DB URL from settings and the tables from `app.models`. |
| `alembic/versions/*.py` | One file per schema change. The initial one creates `users` and `workspaces`. |

### `app/` — the application

| File | Responsible for |
|---|---|
| `main.py` | App factory: logging, request-id + CORS middleware, error handlers, mounts routers under `/api/v1`. Run by `uvicorn app.main:app`. |
| `core/config.py` | `Settings` (pydantic-settings) loaded from env/`.env`. Missing `DATABASE_URL` or `FRONTEND_URL` stops startup. |
| `core/logging.py` | JSON logs in prod, readable in dev; adds a request id to every log line and to the `X-Request-ID` response header. Never logs bodies. |
| `core/errors.py` | The `AppError` family (`NotFoundError`, `ConflictError`, …) and handlers that return `{ "error": { "code", "message" } }`. No stack traces outside dev. |
| `db/base.py` | `Base` plus `IdMixin` (UUID pk) and `TimestampMixin` (`created_at`, `updated_at`). |
| `db/session.py` | The async engine and `get_session` (commit on success, rollback on error). |
| `models/user.py`, `models/workspace.py` | Table definitions. `models/__init__.py` registers them so Alembic sees them. |
| `schemas/workspace.py` | Pydantic request/response shapes (`WorkspaceCreate`, `WorkspaceRead`). API boundary only. |
| `services/workspaces.py` | list / create / get / delete workspaces, and the **max 2 per user** rule. |
| `services/users.py` | The user's first and last name (`PATCH /me`, from the profile page). |
| `api/deps.py` | `get_current_user`: resolves the better-auth session cookie to a verified user (dev user with Gmail in `ENV=test`). `get_entitled_user`: 402 without access. `get_stripe`: the Stripe client. |
| `api/routes/auth.py` | Gmail connection (`/auth/google/login?next=` → Google → `/callback`, needs a signed-in user, returns to the page it started from) and `GET` / `PATCH /me`. |
| `auth/session.py`, `auth/google.py` | Session-cookie lookup in `auth_sessions`; Gmail OAuth, encrypted tokens, refresh. |
| `models/auth.py` | Tables written by better-auth (sessions, password accounts, email codes); owned by Alembic. |
| `api/routes/health.py` | `GET /api/v1/health` — runs `SELECT 1`, returns 503 if the DB is down. |
| `api/routes/workspaces.py` | `GET/POST /api/v1/workspaces`, `GET/DELETE /api/v1/workspaces/{id}`. |
| `api/routes/admin.py`, `services/admin.py`, `schemas/admin.py` | `/api/v1/admin`: usage overview, users, user and workspace detail, access (free-access grants, Stripe customers) (staff only, see CLAUDE.md § Admin). |
| `services/access.py`, `models/access.py` | Who may sign up and use Demux: the access rule, free-access grants, `billing_customers` (see `docs/ACCESS.md`). |
| `services/billing.py`, `billing/stripe_api.py` | Mirrors Stripe customers and subscriptions (read-only REST client, webhook signature check). |
| `api/routes/billing.py`, `schemas/billing.py` | Server-to-server: the Stripe webhook and the sign-up check the frontend asks before creating an account. Not in the OpenAPI schema. |
| `models/usage.py` | `llm_calls` (one row per LLM call, priced at call time) and `mailbox_daily_stats` (messages received per user per day, counted from ids). |
| `models/admin.py`, `services/admin_audit.py` | `admin_audit` (who viewed what) and `demo_seeds`. |
| `services/demo.py`, `mail/demo_inbox.py` | Demo inbox: the LLM writes synthetic threads for a persona, IMAP appends them to `TEST_GMAIL`. Run by the worker. |
| `services/mailbox_stats.py` | Which per-day mail counts the worker still has to take. |
| `pipeline/` | **Empty on purpose.** Future home of the Gmail → LLM extraction code (see its README). |

### `tests/`

| File | Responsible for |
|---|---|
| `conftest.py` | Uses the real Postgres `demux_test` DB; wraps every test in a transaction that is rolled back; provides `client` and `other_client` (a second user). |
| `test_health.py` | Health returns ok. |
| `test_workspaces.py` | CRUD, the 409 limit, user isolation (404 for someone else's workspace), validation error format. |

### Examples

**Calling the API**

```bash
curl -X POST localhost:8000/api/v1/workspaces \
  -H 'Content-Type: application/json' \
  -d '{"name":"Invoices","prompt":"Track invoices from my email"}'
# 201 → {"id":"…","name":"Invoices","status":"draft",…}

# After 2 workspaces, a third returns 409:
# {"error":{"code":"conflict","message":"Workspace limit reached: you can have at most 2 workspaces."}}
```

**Adding a new endpoint** (e.g. rename a workspace)

1. Schema in `schemas/workspace.py` → `WorkspaceUpdate`.
2. Logic in `services/workspaces.py` → `rename_workspace(session, user_id, id, name)`. **Filter by `user_id`.**
3. Thin route in `api/routes/workspaces.py` that calls it.
4. Test in `tests/test_workspaces.py`.
5. `make gen-api` and commit `frontend/src/lib/api-types.ts`.

**Changing the database**

1. Edit a model in `app/models/`.
2. `make migration m="add color to workspaces"` and review the generated file in `alembic/versions/`.
3. `make migrate`.

## 5. Frontend (`frontend/`)

| File | Responsible for |
|---|---|
| `package.json` | Scripts: `dev`, `build`, `lint`, `gen:api`, `format`. |
| `Dockerfile`, `.dockerignore` | Node 22 + pnpm (corepack), deps from the lockfile. Targets: `dev` (`next dev`; the compose anonymous volume at `/app/node_modules` keeps the image's copy alive under the bind mount) and `prod` (`next build` + `next start`; `NEXT_PUBLIC_API_URL` is a build arg). |
| `.env.local.example` | `NEXT_PUBLIC_API_URL`, login settings (`AUTH_DATABASE_URL`, `BETTER_AUTH_*`) and SMTP for sign-in codes. Copied to `.env.local` by `make setup`. |
| `theme.md` | The design system (colours, type, components, copy). Source of truth for all UI. |
| `next.config.ts`, `tsconfig.json` (strict), `eslint.config.mjs`, `.prettierrc` | Tooling config. |
| `src/app/layout.tsx`, `globals.css` | Instrument Sans, design tokens (theme.md §10.2), the sky backdrop and page-transition CSS. |
| `src/proxy.ts` | Sends visitors without a session cookie to `/login`. |
| `src/app/login/page.tsx` + `components/auth/` | Sign in / create account, then the 6-digit email code. |
| `src/app/api/auth/[...all]/route.ts`, `src/lib/auth.ts`, `src/lib/email.ts` | better-auth server (Postgres, email OTP) and the SMTP sender. |
| `src/app/(app)/layout.tsx` + `components/shell/` | The signed-in shell (the `(app)` route group adds no URL segment): the Notion-like sidebar (Create workspace, the workspace list, the account menu, Log out) and the `me` + workspace list it shares with pages through `useShell()`. |
| `src/app/(app)/workspaces/page.tsx` | `/workspaces` — where sign-in lands: opens the last workspace, else Create. |
| `src/app/(app)/workspaces/new/page.tsx` + `components/home/` | `/workspaces/new` — connect Gmail if needed, then "Hello, first name" and the prompt card. |
| `src/app/(app)/profile/page.tsx` + `components/profile/` | `/profile` — edit first and last name (`PATCH /me`), see the sign-in email, connect or switch Gmail. |
| `src/lib/gmail.ts` | Sending the user to Google to connect Gmail and reading the result when they come back. |
| `src/app/(app)/workspaces/[id]/page.tsx` | `/workspaces/<id>` — server wrapper that reads the id and renders the client component below. |
| `src/components/WorkspaceDetail.tsx` + `components/workspace/` | Workspace view: build progress, the generated app in a sandboxed iframe, the chat drawer. |
| `src/components/ui/`, `brand/`, `motion/` | Buttons, fields, spinner; the logo; calm view transitions. |
| `src/lib/api.ts` | Typed `fetch` wrapper (`api.listWorkspaces()`, …). Sends cookies; throws `ApiError` built from the backend error format. |
| `src/lib/api-types.ts` | **Generated** by `make gen-api` from the OpenAPI schema. Never edit by hand. |

**Using the API client**

```ts
import { api, ApiError } from "@/lib/api";

try {
  await api.createWorkspace({ name: "Invoices", prompt: "Track invoices" });
} catch (e) {
  if (e instanceof ApiError && e.status === 409) alert(e.message); // limit reached
}
```

Keep components server-side by default; add `"use client"` only where there is interaction.

## 6. Rules that matter

1. **User isolation:** every query on user data filters by `user_id`. Other users' rows are a 404.
2. **No sensitive logging:** never log email content, prompts or extracted data — ids and counts only.
3. **Migrations:** schema changes always go through Alembic.
4. **API changes:** run `make gen-api` and commit the generated types.
5. **Auth:** login is better-auth (frontend); the backend owns Google OAuth and Gmail tokens, which the frontend never sees.
6. **Keep it simple:** no queues, caches or vector DBs without an explicit team decision.

## 7. Where the next work goes

- **Done:** login (better-auth, email code) and the Gmail connection (backend OAuth). Not built yet: phone / SMS sign-in, password reset.
- **Later:** Gmail fetch + LLM extraction in `backend/app/pipeline/`, workspace rendering components in `frontend/src/components/`, background refresh.
- **Done:** UI generation v2 (component kit, palettes, setup questions, layouts, progress screen): see `docs/UI_GENERATION_PLAN.md` and the UI generation table in §3.

## 8. Troubleshooting

- *Backend won't start, "field required"* → `.env` is missing; run `make setup`.
- *Frontend shows backend "down"* → backend not running, or `NEXT_PUBLIC_API_URL` / `FRONTEND_URL` mismatch (CORS).
- *`make up` container unhealthy* → `docker compose logs backend` (or `frontend`) for details; the backend waits for Postgres to be healthy before starting.
- *Changed dependencies (pyproject/uv.lock or package.json)* → source hot-reloads, but deps are baked into the images: re-run `make up` to rebuild them.
- *Tests fail to connect* → run `make db`; the `demux_test` database is created only when the Postgres volume is first created (`make reset` then `make db`/`make up` to recreate).
