# Demux

Turns a user's Gmail into structured, refreshable workspaces (tables, cards, Kanban) using an LLM extraction pipeline. This repo is the Phase 0 foundation: backend, frontend, DB, tooling. No Gmail/LLM/auth yet.

Stack: FastAPI + SQLAlchemy (async) + Postgres 17 · Next.js (App Router) + Tailwind · `uv`, `pnpm`, `make`.

## Quick start (~5 minutes)

Prerequisites: Docker, [uv](https://docs.astral.sh/uv/), Node 22+, [pnpm](https://pnpm.io/), make.

**Everything in Docker** (hot reload included):

```bash
make setup     # install deps, create .env and frontend/.env.local from the examples
make up        # build + start postgres, backend, frontend
```

**Or natively** (backend and frontend on your machine):

```bash
make setup     # install deps, create .env and frontend/.env.local from the examples
make db        # start Postgres (creates demux + demux_test databases)
make migrate   # create tables
make backend   # API on http://localhost:8000  (docs: /api/docs)
make frontend  # web app on http://localhost:3000   (in a second terminal)
```

Open http://localhost:3000 — the backend status should read **ok**. `make down` stops the Docker stack (add `make reset` to also wipe the database).

## Everyday commands

| Command | What it does |
|---|---|
| `make up` / `make down` | start / stop the full stack in Docker (`down` keeps the DB volume) |
| `make install` | install backend deps (uv) and frontend deps (pnpm) |
| `make lint` | ruff + eslint + `tsc --noEmit` |
| `make test` | backend tests (needs `make db`) |
| `make migration m="msg"` | autogenerate an Alembic migration |
| `make gen-api` | regenerate frontend API types (backend must be running) |

## Learn the repo
Read [`docs/REPO_GUIDE.md`](docs/REPO_GUIDE.md) for what every file does, with examples, and [`CLAUDE.md`](CLAUDE.md) for conventions.
