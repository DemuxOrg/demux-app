# Single entry point for dev commands. Run from the repo root.
.PHONY: setup install db up down reset migrate migration backend frontend gen-api lint test

install:  ## install dependencies (backend with uv, frontend with pnpm)
	cd backend && uv sync
	cd frontend && pnpm install

setup: install  ## install deps and create env files if missing
	[ -f .env ] || cp .env.example .env
	[ -f frontend/.env.local ] || cp frontend/.env.local.example frontend/.env.local

db:  ## start Postgres only (also creates demux_test on first run)
	docker compose up -d --wait postgres

up:  ## build and start the whole stack in Docker (postgres + backend + frontend)
	docker compose up -d --build --wait

down:  ## stop the whole stack (keeps the Postgres data volume)
	docker compose down

reset:  ## stop the stack and delete the Postgres data volume
	docker compose down -v

migrate:  ## apply migrations
	cd backend && uv run alembic upgrade head

migration:  ## create a migration: make migration m="message"
	cd backend && uv run alembic revision --autogenerate -m "$(m)"

backend:  ## API on :8000 (native dev; use make up for the Docker stack)
	cd backend && uv run uvicorn app.main:app --reload --port 8000

frontend:  ## web app on :3000 (native dev; use make up for the Docker stack)
	cd frontend && pnpm dev --port 3000

gen-api:  ## regenerate frontend API types (backend must be running)
	cd frontend && pnpm gen:api

lint:
	cd backend && uv run ruff check . && uv run ruff format --check .
	cd frontend && pnpm lint && pnpm exec tsc --noEmit

test:
	cd backend && uv run pytest
