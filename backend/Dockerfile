# Backend image, used by two compose services: `backend` (the API) and `worker` (agent
# runs and scheduled syncs). One image on purpose: they share the same code and
# dependencies and only run a different command, so two Dockerfiles would just drift.
#
# Targets:
#   dev  – dev deps included (pytest, ruff); compose bind-mounts ./backend over /app.
#   prod – source baked in, runs as a non-root user, no reload.
#
# /opt/.venv and /opt/pw-browsers live outside /app so the dev bind mount never shadows them.

FROM python:3.12-slim AS base

COPY --from=ghcr.io/astral-sh/uv:0.8.22 /uv /uvx /bin/

ENV UV_PROJECT_ENVIRONMENT=/opt/.venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
    PATH=/opt/.venv/bin:$PATH

WORKDIR /app

# Dependencies first so this layer is cached independently of source changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Headless Chromium (+ its system libraries) for the agent's app checks. libatomic1 is
# needed by the Node binary bundled with Playwright and missing from slim images.
RUN apt-get update && apt-get install -y --no-install-recommends libatomic1 \
    && playwright install --with-deps --only-shell chromium \
    && rm -rf /var/lib/apt/lists/*

EXPOSE 8000


FROM base AS dev
RUN uv sync --frozen
COPY . .
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]


FROM base AS prod
COPY . .
# Chromium needs a writable home directory (crash reports, profile).
RUN useradd --system --create-home demux && chmod -R a+rX /opt/pw-browsers
USER demux
# --proxy-headers: trust X-Forwarded-* from the reverse proxy that terminates HTTPS.
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
