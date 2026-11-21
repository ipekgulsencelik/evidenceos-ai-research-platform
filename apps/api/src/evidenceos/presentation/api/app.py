"""Application factory and composition root."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from evidenceos.domain.errors import InvalidProjectTitle, ProjectNotFound
from evidenceos.infrastructure.config import Settings, get_settings
from evidenceos.presentation.api.routes.health import router as health_router
from evidenceos.presentation.api.routes.projects import router as projects_router

class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = str(uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_async_engine(config.database_url, pool_pre_ping=True)
        app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            yield
        finally:
            await engine.dispose()

    app = FastAPI(
        title="EvidenceOS API",
        description="Evidence-first legal and academic research platform (foundation release)",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if config.app_env != "production" else None,
        redoc_url=None,
    )
    app.add_middleware(RequestIdMiddleware)
    if config.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=config.cors_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type", "Authorization"],
        )

    @app.exception_handler(ProjectNotFound)
    async def handle_not_found(request: Request, exc: ProjectNotFound) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(InvalidProjectTitle)
    async def handle_invalid_title(request: Request, exc: InvalidProjectTitle) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    app.include_router(health_router, prefix="/api/v1")
    app.include_router(projects_router, prefix="/api/v1")
    return app


app = create_app()
