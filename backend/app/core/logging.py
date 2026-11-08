"""Logging setup and request-id middleware.

Responsible for:
- Configuring logging: JSON lines in prod, human-readable lines in dev/test.
- Tagging every log line with the current request id (via a ContextVar).
- `RequestIdMiddleware`: reads or generates an id per request, logs method/path/status
  /duration, and returns the id in the `X-Request-ID` response header.

PRIVACY RULE: never log request or response bodies. They will contain email content
later. Log ids and counts only.
"""

import json
import logging
import time
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import Env

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")

logger = logging.getLogger("app.request")


class RequestIdFilter(logging.Filter):
    """Copies the current request id onto every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def setup_logging(env: Env, level: str) -> None:
    handler = logging.StreamHandler()
    handler.addFilter(RequestIdFilter())
    if env == Env.PROD:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-7s [%(request_id)s] %(name)s: %(message)s")
        )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        token = request_id_ctx.set(request_id)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            request_id_ctx.reset(token)
        response.headers["X-Request-ID"] = request_id
        duration_ms = (time.perf_counter() - start) * 1000
        # The log line is emitted with the id re-set so the filter can pick it up.
        token = request_id_ctx.set(request_id)
        logger.info(
            "%s %s -> %s (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        request_id_ctx.reset(token)
        return response
