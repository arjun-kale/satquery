"""Job lifecycle endpoints — create, poll, trace, artifacts."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.schemas import JobRecord
from app.state import JobStatus

router = APIRouter(prefix="/api", tags=["jobs"])


class CreateJobRequest(BaseModel):
    image_ids: list[str]
    query: str


@router.post("/jobs", response_model=JobRecord, status_code=201)
def create_job(body: CreateJobRequest, request: Request) -> JobRecord:
    """Create an analysis job from image id(s) and a natural-language query."""
    repo = request.app.state.job_repository
    job = repo.create()
    # Stub: immediately transition to VALIDATED (orchestration in Phase 3)
    job = repo.transition(job.id, JobStatus.VALIDATED)
    return job


@router.get("/jobs/{job_id}", response_model=JobRecord)
def get_job(job_id: str, request: Request) -> JobRecord:
    """Poll job status and fetch the final structured result."""
    repo = request.app.state.job_repository
    try:
        return repo.get(job_id)
    except KeyError:
        raise HTTPException(404, detail=f"Job {job_id!r} not found.")


@router.get("/jobs/{job_id}/trace")
def get_trace(job_id: str, request: Request) -> dict:
    """Fetch the immutable execution trace (stub — full impl in Phase 3)."""
    repo = request.app.state.job_repository
    try:
        job = repo.get(job_id)
    except KeyError:
        raise HTTPException(404, detail=f"Job {job_id!r} not found.")
    return {
        "job_id": job.id,
        "status": job.status,
        "trace_steps": [],
        "note": "Full ObservableExecutionTrace implemented in Phase 3.",
    }


@router.get("/jobs/{job_id}/artifacts/{name}")
def get_artifact(job_id: str, name: str, request: Request) -> FileResponse:
    """Fetch a named artifact (preview, mask, GeoJSON) for a job."""
    artifact_repo = request.app.state.artifact_repository
    if not artifact_repo.artifact_exists(job_id, name):
        raise HTTPException(404, detail=f"Artifact {name!r} not found for job {job_id!r}.")
    path = artifact_repo.artifact_path(job_id, name)
    return FileResponse(path)
