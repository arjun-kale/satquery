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
        from app.assets import ensure_assets_in_background
        ensure_assets_in_background(active_settings)
        app.state.job_repository = repository
        app.state.artifact_repository = artifact_repo
        yield

    app = FastAPI(
        title="SatQuery API",
        version="0.2.0",
        description="Local geospatial-analysis MVP API.",
        lifespan=lifespan,
    )
    # Enable CORS for Next.js frontend (local and production)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "https://satquery.vercel.app"] + active_settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["x-vercel-ai-ui-message-stream"],
    )
    app.add_api_route(
        "/health",
        health,
        methods=["GET"],
        response_model=HealthResponse,
        tags=["health"],
    )
    from app.api.report import router as report_router
    from app.api.scene_sets import router as scene_sets_router
    from app.api.samples import router as samples_router
    from app.api.chat import router as chat_router
    app.include_router(ingest_router)
    app.include_router(scene_sets_router)
    app.include_router(samples_router)
    app.include_router(chat_router)
    app.include_router(jobs_router)
    app.include_router(report_router)
    return app


app = create_app()
