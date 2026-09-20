"""Health route kept separate so it can grow without polluting app startup."""

from fastapi import Request

from app.schemas import HealthResponse

def health(request: Request) -> HealthResponse:
    repository = request.app.state.job_repository
    repository.initialize()
    settings = request.app.state.settings
    return HealthResponse(model_mode=settings.model_mode)
