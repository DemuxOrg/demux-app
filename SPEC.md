# Demux — Repo Bootstrap Spec (Phase 0)

> Hand this file to Claude Code. Goal: a clean, minimal, runnable monorepo that we extend feature by feature.
> **Do not build product features yet.** No Gmail, no LLM, no auth flow. Just the skeleton, done well.

## 1. Context (short)

Demux turns a user's Gmail into structured, refreshable workspaces (tables, cards, Kanban) using an LLM extraction pipeline. This phase only sets up the foundation that every later feature plugs into.

## 2. Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.x (async) + asyncpg, Alembic |
| Python tooling | `uv` (deps + venv), `ruff` (lint + format), `pytest` + `httpx` |
| Frontend | Next.js (latest stable, App Router), TypeScript strict, Tailwind CSS, `pnpm` |
| Frontend tooling | ESLint + Prettier, `openapi-typescript` for generated API types |
| Database | PostgreSQL 17 via Docker Compose |
| Orchestration | `docker compose` for Postgres only; backend and frontend run natively in dev |

Use latest stable versions of every package at install time. Don't pin to versions from memory.

## 3. Repo layout

```
demux/
├── README.md
├── CLAUDE.md                 # conventions for future Claude Code sessions (see §9)
├── Makefile                  # single entry point for dev commands
├── docker-compose.yml        # postgres only
├── .env.example
├── .gitignore
├── .github/workflows/ci.yml
├── backend/
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py            # async-aware, reads DB URL from settings
│   │   └── versions/
│   ├── app/
│   │   ├── main.py           # app factory, CORS, router registration
│   │   ├── core/
│   │   │   ├── config.py     # pydantic-settings, loads .env
│   │   │   └── logging.py    # structured logging, request id
│   │   ├── db/
│   │   │   ├── base.py       # DeclarativeBase, common mixins (id, timestamps)
│   │   │   └── session.py    # async engine + get_session dependency
│   │   ├── api/
│   │   │   ├── deps.py       # shared deps incl. get_current_user (stub, see §6)
│   │   │   └── routes/
│   │   │       ├── health.py
│   │   │       └── workspaces.py
│   │   ├── models/           # SQLAlchemy models
│   │   │   ├── user.py
│   │   │   └── workspace.py
│   │   ├── schemas/          # Pydantic request/response models
│   │   │   └── workspace.py
│   │   ├── services/         # business logic; routes stay thin
│   │   │   └── workspaces.py
│   │   └── pipeline/         # EMPTY placeholder for future Gmail/LLM pipeline
│   │       └── README.md     # one paragraph: what will live here
│   └── tests/
│       ├── conftest.py       # test DB, async client fixture
│       ├── test_health.py
│       └── test_workspaces.py
└── frontend/
    ├── package.json
    ├── next.config.ts
    ├── src/
    │   ├── app/
    │   │   ├── layout.tsx
    │   │   ├── page.tsx              # landing: backend health status
    │   │   └── workspaces/
    │   │       ├── page.tsx          # list + create form
    │   │       └── [id]/page.tsx     # detail view
    │   ├── lib/
    │   │   ├── api.ts                # typed fetch wrapper using generated types
    │   │   └── api-types.ts          # GENERATED from OpenAPI, do not edit
    │   └── components/
    └── .env.local.example
```

## 4. Backend requirements

**App setup**
- App factory in `app/main.py`. Routes mounted under `/api/v1`. OpenAPI at `/api/docs` and `/api/openapi.json`.
- CORS allows the frontend origin from config (`FRONTEND_URL`), with credentials enabled (we'll use cookies for auth later).
- Settings via `pydantic-settings`: `DATABASE_URL`, `FRONTEND_URL`, `ENV` (`dev`/`test`/`prod`), `LOG_LEVEL`. Fail fast on missing required vars.
- Logging: JSON logs in prod, readable logs in dev. Middleware adds a request id to each log line and the `X-Request-ID` response header. **Never log request/response bodies** (they'll contain email content later).

**Database**
- Async SQLAlchemy 2.x with typed `Mapped[...]` columns.
- Base mixin: `id` (UUID, server-generated), `created_at`, `updated_at` (timezone-aware, UTC).
- Alembic configured for async and autogenerate. Initial migration creates the two tables below.

**Models (minimal, extend later)**

`users`
- `id` UUID PK
- `email` text unique not null
- `created_at`, `updated_at`

`workspaces`
- `id` UUID PK
- `user_id` UUID FK → users.id, on delete cascade, indexed
- `name` text not null
- `prompt` text not null (the user's natural-language request)
- `config` JSONB not null default `{}` (future: planned fields, Gmail queries, display component)
- `status` enum: `draft | building | ready | failed`, default `draft`
- `last_refreshed_at` timestamptz nullable
- `created_at`, `updated_at`

**Endpoints**
- `GET /api/v1/health` → `{ "status": "ok", "db": "ok" }` (actually runs `SELECT 1`; returns 503 if DB unreachable)
- `GET /api/v1/workspaces` → list current user's workspaces
- `POST /api/v1/workspaces` → create (`name`, `prompt`). Enforce **max 2 workspaces per user** (MVP constraint) → 409 with a clear message.
- `GET /api/v1/workspaces/{id}` → 404 if not found **or not owned by current user** (don't leak existence)
- `DELETE /api/v1/workspaces/{id}` → 204

Every query filters by `user_id`. User isolation is a hard rule from day one, not something to retrofit.

**Error format**: consistent JSON `{ "error": { "code": "...", "message": "..." } }` via exception handlers. No stack traces in non-dev responses.

## 5. Frontend requirements

- Next.js App Router, TypeScript `strict: true`, Tailwind. No component library yet (keep it plain; we may add shadcn/ui later).
- `NEXT_PUBLIC_API_URL` env var for the backend base URL.
- `src/lib/api-types.ts` is generated by `pnpm gen:api` (runs `openapi-typescript` against `http://localhost:8000/api/openapi.json`). `src/lib/api.ts` wraps `fetch` with these types, sends `credentials: "include"`, and throws a typed error from the backend error format.
- Pages:
  - `/` — shows backend health (ok / down). Link to `/workspaces`.
  - `/workspaces` — list workspaces, simple create form (name + prompt textarea), delete button. Show the 409 limit error nicely.
  - `/workspaces/[id]` — name, prompt, status badge, placeholder area that says "Workspace view coming soon".
- Use client components only where interaction is needed. Keep styling minimal and clean.

## 6. Auth (stub only in this phase)

Real auth (Google OAuth with Gmail read-only scope, tokens stored server-side, httpOnly session cookie) is **Phase 1**. Prepare for it, don't build it:

- `get_current_user` dependency in `api/deps.py`. In `ENV=dev` / `test`, it returns (and creates if missing) a fixed dev user `dev@demux.local`.
- In `ENV=prod`, it raises 401. This guarantees the stub can't silently ship.
- All workspace routes depend on `get_current_user`, so swapping in real auth later touches one function.

Architectural note for later (put it in `CLAUDE.md`): the **backend owns the Google OAuth flow and Gmail tokens**. The frontend never sees Google access/refresh tokens. Don't use NextAuth/Auth.js for Gmail tokens.

## 7. Dev experience

`Makefile` targets (all must work from repo root):

| Target | Does |
|---|---|
| `make setup` | `uv sync` in backend, `pnpm install` in frontend, copy `.env.example` files if missing |
| `make db` | `docker compose up -d postgres` |
| `make migrate` | `alembic upgrade head` |
| `make migration m="msg"` | `alembic revision --autogenerate -m "$(m)"` |
| `make backend` | `uvicorn app.main:app --reload --port 8000` |
| `make frontend` | `pnpm dev` on port 3000 |
| `make gen-api` | regenerate frontend API types (backend must be running) |
| `make lint` | ruff check + format check; eslint + `tsc --noEmit` |
| `make test` | pytest |

`docker-compose.yml`: one `postgres:17` service, named volume, healthcheck, port 5432, credentials from `.env`. Create a second database `demux_test` for tests (init script).

`.env.example` contains every variable with safe dev defaults. `.env` and `.env.local` are git-ignored.

## 8. Tests & CI

- Backend tests run against the real Postgres test DB (not SQLite — we'll rely on JSONB and enums). Each test runs inside a transaction that's rolled back.
- Required tests: health ok; create/list/get/delete workspace; 2-workspace limit returns 409; user A cannot read user B's workspace (404).
- GitHub Actions `ci.yml`: backend job (Postgres service container, `uv sync`, ruff, pytest) and frontend job (`pnpm install`, eslint, `tsc --noEmit`, `next build`).

## 9. CLAUDE.md (create it)

Short file with conventions for future sessions:
- How to run everything (point to Makefile).
- Backend layering: routes → services → models. Routes stay thin. Pydantic schemas at the API boundary only.
- Every DB query on user data filters by `user_id`.
- Never log email content, prompts, or extracted data. Log ids and counts.
- After changing API schemas: `make gen-api` and commit the generated types.
- Schema changes always go through an Alembic migration.
- Backend owns OAuth + Gmail tokens (see §6).
- Keep it simple: no new infra (queues, caches, vector DBs) without an explicit decision.

## 10. Out of scope for this phase

Google OAuth, Gmail API, LLM calls, background jobs/queues, the extraction pipeline, workspace rendering components, deployment config, Docker images for backend/frontend.

## 11. Acceptance criteria

Done when, from a fresh clone:

1. `make setup && make db && make migrate` succeeds with no manual steps beyond the copied `.env`.
2. `make backend` + `make frontend` → `http://localhost:3000` shows backend health **ok**.
3. You can create two workspaces in the UI, the third shows the limit error, delete works, detail page loads.
4. `http://localhost:8000/api/docs` shows all endpoints.
5. `make lint` and `make test` pass with zero errors.
6. CI workflow passes on push.
7. `README.md` lets a new developer get running in under 5 minutes.

Work in small commits, one per logical step (scaffold backend → DB + migrations → endpoints + tests → frontend → Makefile/CI/docs). Stop and ask if a requirement conflicts with what the tooling supports.
