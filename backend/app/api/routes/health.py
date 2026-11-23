"""`GET /api/v1/health`.

Responsible for reporting liveness plus database reachability (runs `SELECT 1`).
Returns 200 `{"status":"ok","db":"ok"}`, or 503 if the database cannot be reached.
The frontend landing page uses this to show backend status.
"""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.deps import SessionDep

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/health")
async def health(session: SessionDep) -> dict[str, str]:
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        logger.exception("health check: database unreachable")
        return JSONResponse(  # type: ignore[return-value]
            status_code=503, content={"status": "error", "db": "down"}
        )
    return {"status": "ok", "db": "ok"}
