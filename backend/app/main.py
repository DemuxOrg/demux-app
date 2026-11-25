"""FastAPI application factory.

Responsible for assembling the app: logging, request-id middleware, CORS (allowing
the frontend origin with credentials, for future cookie auth), exception handlers, and
mounting all routers under `/api/v1`. OpenAPI docs live at `/api/docs` and
`/api/openapi.json`. Run with `make backend` (uvicorn app.main:app).
"""

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api.routes import admin, auth, billing, health, workspaces
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
    # The app shell inlines the component kit (~1 MB); gzip makes it ~300 KB on the wire.
    app.add_middleware(GZipMiddleware, minimum_size=2048)
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
    api_v1.include_router(auth.router)
    api_v1.include_router(workspaces.router)
    api_v1.include_router(workspaces.shell_router)
    api_v1.include_router(admin.router)
    api_v1.include_router(billing.router)
    app.include_router(api_v1)
    return app


app = create_app()
