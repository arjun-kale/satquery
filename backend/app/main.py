"""FastAPI entrypoint for the local, zero-budget MVP backend."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import health
from app.api.ingest import router as ingest_router
from app.api.jobs import router as jobs_router
from app.schemas import HealthResponse
from app.config import Settings
from app.storage.jobs import JobRepository
from app.storage.artifacts import ArtifactRepository


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create an app with injectable settings so tests never touch real data."""

    active_settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        active_settings.data_dir.mkdir(parents=True, exist_ok=True)

        repository = JobRepository(active_settings.database_path)
        repository.initialize()

        artifact_repo = ArtifactRepository(active_settings.data_dir)
        artifact_repo.initialize()

        app.state.settings = active_settings
        app.state.job_repository = repository
        app.state.artifact_repository = artifact_repo
        yield

    app = FastAPI(
        title="SatQuery API",
        version="0.2.0",
        description="Local geospatial-analysis MVP API.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=active_settings.allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Request-ID"],
    )
    app.add_api_route(
        "/health",
        health,
        methods=["GET"],
        response_model=HealthResponse,
        tags=["health"],
    )
    app.include_router(ingest_router)
    app.include_router(jobs_router)
    return app


app = create_app()
