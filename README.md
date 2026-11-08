# Demux

Turns a user's Gmail into structured, refreshable workspaces (tables, cards, Kanban) using an LLM extraction pipeline. This repo is the Phase 0 foundation: backend, frontend, DB, tooling. No Gmail/LLM/auth yet.

Stack: FastAPI + SQLAlchemy (async) + Postgres 17 · Next.js (App Router) + Tailwind · `uv`, `pnpm`, `make`.

## Quick start (~5 minutes)

Prerequisites: Docker, [uv](https://docs.astral.sh/uv/), Node 22+, [pnpm](https://pnpm.io/), make.

```bash
make setup     # install deps, create .env and frontend/.env.local from the examples
make db        # start Postgres (creates demux + demux_test databases)
make migrate   # create tables
make backend   # API on http://localhost:8000  (docs: /api/docs)
make frontend  # web app on http://localhost:3000   (in a second terminal)
```

Open http://localhost:3000 — the backend status should read **ok**.

## Everyday commands

| Command | What it does |
|---|---|
| `make lint` | ruff + eslint + `tsc --noEmit` |
| `make test` | backend tests (needs `make db`) |
| `make migration m="msg"` | autogenerate an Alembic migration |
| `make gen-api` | regenerate frontend API types (backend must be running) |

## Learn the repo
Read [`docs/REPO_GUIDE.md`](docs/REPO_GUIDE.md) for what every file does, with examples, and [`CLAUDE.md`](CLAUDE.md) for conventions.
