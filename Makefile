# Single entry point for dev commands. Run from the repo root.
.PHONY: setup install env db up down restart reset logs ps docker-test prod-up prod-down prod-logs \
	migrate migration backend worker frontend gen-api eval-agent lint test

COMPOSE_PROD = docker compose -f docker-compose.prod.yml

install:  ## install dependencies (backend with uv, frontend with pnpm)
	cd backend && uv sync
	cd backend && uv run playwright install chromium
	cd frontend && pnpm install

setup: install  ## install deps and create env files if missing
	[ -f .env ] || cp .env.example .env
	cd backend && uv run python scripts/ensure_keys.py ../.env
	[ -f frontend/.env.local ] || cp frontend/.env.local.example frontend/.env.local

# ---- Docker stack (only Docker + make needed) ----

env:  ## create .env from .env.example if missing, then fill SECRET_KEY / TOKEN_ENCRYPTION_KEY
	@[ -f .env ] || (cp .env.example .env && echo "created .env from .env.example")
	@docker compose build -q backend
	@docker compose run --rm --no-deps -T -v "$(CURDIR)/.env:/tmp/demux.env" backend \
		python scripts/ensure_keys.py /tmp/demux.env

up: env  ## build and start everything in Docker (postgres + backend + worker + frontend)
	docker compose up -d --build --wait
	@echo "frontend: http://localhost:3000   API docs: http://localhost:8000/api/docs"

down:  ## stop everything (keeps the Postgres data volume)
	docker compose down

restart:  ## restart the backend and worker (e.g. after editing .env or agent code)
	docker compose up -d --force-recreate --wait backend worker

reset:  ## stop everything and delete the Postgres data volume
	docker compose down -v

logs:  ## follow logs of every service (make logs s=worker for one)
	docker compose logs -f --tail=100 $(s)

ps:  ## show the state of every service
	docker compose ps

docker-test:  ## run the backend test suite inside the backend container (stack must be up)
	docker compose exec -e ENV=test -e GOOGLE_CLIENT_ID=test-client -e GOOGLE_CLIENT_SECRET=test-secret \
		backend python -m pytest $(ARGS)

db:  ## start Postgres only (also creates demux_test on first run)
	docker compose up -d --wait postgres

prod-up: env  ## build and start the production-like stack (docker-compose.prod.yml)
	$(COMPOSE_PROD) up -d --build --wait

prod-down:  ## stop the production-like stack (keeps its data volume)
	$(COMPOSE_PROD) down

prod-logs:  ## follow logs of the production-like stack
	$(COMPOSE_PROD) logs -f --tail=100 $(s)

# ---- Native dev (uv + pnpm on your machine; Postgres via make db) ----

migrate:  ## apply migrations
	cd backend && uv run alembic upgrade head

migration:  ## create a migration: make migration m="message"
	cd backend && uv run alembic revision --autogenerate -m "$(m)"

backend:  ## API on :8000 (native dev; use make up for the Docker stack)
	cd backend && uv run uvicorn app.main:app --reload --port 8000

worker:  ## agent worker: runs builds/edits/syncs, schedules syncs
	cd backend && uv run python -m app.worker

frontend:  ## web app on :3000
	cd frontend && pnpm dev --port 3000

gen-api:  ## regenerate frontend API types (backend must be running)
	cd frontend && pnpm gen:api

eval-agent:  ## run the agent eval scenarios (costs money): make eval-agent ARGS="--scenario 01"
	cd backend && uv run python -m eval.agent $(ARGS)

lint:
	cd backend && uv run ruff check . && uv run ruff format --check .
	cd frontend && pnpm lint && pnpm exec tsc --noEmit

test:
	cd backend && uv run pytest
