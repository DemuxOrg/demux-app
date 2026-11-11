# Backend image. Dev-oriented: the compose file bind-mounts ./backend over /app and
# runs uvicorn with --reload (see docker-compose.yml), so only dependencies are baked
# in here. /opt/.venv lives outside /app on purpose so the bind mount never shadows it.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.8.22 /uv /uvx /bin/

ENV UV_PROJECT_ENVIRONMENT=/opt/.venv \
    UV_COMPILE_BYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies first so this layer is cached independently of source changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

EXPOSE 8000

# `make backend` (native dev) uses --reload too; the compose dev stack overrides this
# command to run migrations first.
CMD ["/opt/.venv/bin/python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
