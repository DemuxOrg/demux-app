"""FastAPI application factory.

Responsible for assembling the app: logging, request-id middleware, CORS (allowing
the frontend origin with credentials, for future cookie auth), exception handlers, and
mounting all routers under `/api/v1`. OpenAPI docs live at `/api/docs` and
`/api/openapi.json`. Run with `make backend` (uvicorn app.main:app).
"""

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health, workspaces
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import RequestIdMiddleware, setup_logging


def create_app() -> FastAPI:
    setup_logging(settings.ENV, settings.LOG_LEVEL)

    app = FastAPI(
        title="Demux API",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.FRONTEND_URL],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    register_exception_handlers(app)

    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(health.router)
    api_v1.include_router(workspaces.router)
    app.include_router(api_v1)
    return app


app = create_app()
