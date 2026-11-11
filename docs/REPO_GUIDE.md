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
├── backend/                    ← Python / FastAPI
│   └── Dockerfile  .dockerignore
└── frontend/                   ← TypeScript / Next.js
    └── Dockerfile  .dockerignore
```

### Root files

| File | Responsible for |
|---|---|
| `README.md` | 5-minute quick start. |
| `SPEC.md` | The original Phase 0 spec this repo was built from. |
| `CLAUDE.md` | Conventions for AI coding sessions (and good rules for humans too). |
| `Makefile` | The single entry point for dev commands (`make setup`, `install`, `up`, `down`, `reset`, `db`, `migrate`, `backend`, `frontend`, `lint`, `test`, `gen-api`, `migration m="..."`). |
| `docker-compose.yml` | Runs the full dev stack: Postgres 17 (healthcheck, persistent `pgdata` volume), backend (bind-mounted source, uvicorn `--reload`, migrations applied at start) and frontend (bind-mounted source, `next dev`). |
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
| `Dockerfile`, `.dockerignore` | Dev image: Python 3.12 + uv, deps from `uv.lock` into `/opt/.venv` (kept outside `/app` so the compose bind mount never shadows it). |
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
| `api/deps.py` | `get_current_user` — a **dev stub** (returns `dev@demux.local`; 401 in `ENV=prod`). Real Google auth will replace only this function. |
| `api/routes/health.py` | `GET /api/v1/health` — runs `SELECT 1`, returns 503 if the DB is down. |
| `api/routes/workspaces.py` | `GET/POST /api/v1/workspaces`, `GET/DELETE /api/v1/workspaces/{id}`. |
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
| `Dockerfile`, `.dockerignore` | Dev image: Node 22 + pnpm (corepack), deps from the lockfile; the compose anonymous volume at `/app/node_modules` keeps the image's copy alive under the bind mount. |
| `.env.local.example` | `NEXT_PUBLIC_API_URL` (backend base URL). Copied to `.env.local` by `make setup`. |
| `next.config.ts`, `tsconfig.json` (strict), `eslint.config.mjs`, `.prettierrc` | Tooling config. |
| `src/app/layout.tsx` | Shared layout: nav bar, fonts, global CSS. |
| `src/app/page.tsx` | `/` — shows backend health (ok/down), links to workspaces. |
| `src/app/workspaces/page.tsx` | `/workspaces` — list, create form (name + prompt), delete; shows the 409 limit error. |
| `src/app/workspaces/[id]/page.tsx` | `/workspaces/<id>` — server wrapper that reads the id and renders the client component below. |
| `src/components/WorkspaceDetail.tsx` | Detail view: name, prompt, status badge, "coming soon" placeholder. |
| `src/components/StatusBadge.tsx` | Colored pill for `draft / building / ready / failed`. |
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
5. **Auth:** the backend will own Google OAuth and Gmail tokens; the frontend never sees them.
6. **Keep it simple:** no queues, caches or vector DBs without an explicit team decision.

## 7. Where the next work goes

- **Phase 1:** Google OAuth (replace `get_current_user`), httpOnly session cookie.
- **Later:** Gmail fetch + LLM extraction in `backend/app/pipeline/`, workspace rendering components in `frontend/src/components/`, background refresh.

## 8. Troubleshooting

- *Backend won't start, "field required"* → `.env` is missing; run `make setup`.
- *Frontend shows backend "down"* → backend not running, or `NEXT_PUBLIC_API_URL` / `FRONTEND_URL` mismatch (CORS).
- *`make up` container unhealthy* → `docker compose logs backend` (or `frontend`) for details; the backend waits for Postgres to be healthy before starting.
- *Changed dependencies (pyproject/uv.lock or package.json)* → source hot-reloads, but deps are baked into the images: re-run `make up` to rebuild them.
- *Tests fail to connect* → run `make db`; the `demux_test` database is created only when the Postgres volume is first created (`make reset` then `make db`/`make up` to recreate).
