"""Job lifecycle endpoints — create, poll, trace, artifacts."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.schemas import JobRecord
from app.state import JobStatus
from typing import Literal

from app.orchestration.cancel import request_cancel
from app.orchestration.router import QueryRouter, QueryType
from app.orchestration.executor import DAGExecutor

router = APIRouter(prefix="/api", tags=["jobs"])

# Initialize singleton router (loads the lightweight sentence-transformer model in memory)
query_router = QueryRouter()

class CreateJobRequest(BaseModel):
    image_ids: list[str]
    query: str
    scene_set_kind: Literal["single", "bitemporal", "optical_sar"] | None = None
    # Set only when the user picked an intent after the router said it was unsure.
    task: QueryType | None = None


@router.post("/jobs", response_model=JobRecord, status_code=201)
def create_job(body: CreateJobRequest, request: Request, background_tasks: BackgroundTasks) -> JobRecord:
    """Create an analysis job from image id(s) and a natural-language query."""
    repo = request.app.state.job_repository
    job = repo.create()

    # Execute the DAG asynchronously in the background so we don't block the API.
    # The executor itself will handle the state transitions (RECEIVED -> VALIDATED -> ROUTING).
    artifact_repo = request.app.state.artifact_repository
    executor = DAGExecutor(
        query_router, repo, artifact_repo, model_mode=request.app.state.settings.model_mode
    )
    background_tasks.add_task(
        executor.execute,
        job.id,
        body.query,
        {"image_ids": body.image_ids},
        scene_set_kind=body.scene_set_kind,
        forced_task=body.task.value if body.task else None,
    )

    return job


@router.post("/jobs/{job_id}/cancel", response_model=JobRecord)
def cancel_job(job_id: str, request: Request) -> JobRecord:
    """Ask a running job to stop. It stops before its next step; a running step finishes first."""
    repo = request.app.state.job_repository
    try:
        job = repo.get(job_id)
    except KeyError:
        raise HTTPException(404, detail=f"Job {job_id!r} not found.")
    if job.status not in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.REJECTED):
        request_cancel(job_id)
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
    """Fetch the immutable execution trace."""
    repo = request.app.state.job_repository
    artifact_repo = request.app.state.artifact_repository
    
    try:
        job = repo.get(job_id)
    except KeyError:
        raise HTTPException(404, detail=f"Job {job_id!r} not found.")
        
    trace_data = None
    schema_version = None
    if artifact_repo.artifact_exists(job_id, "trace.json"):
        import json
        trace_path = artifact_repo.artifact_path(job_id, "trace.json")
        saved = json.loads(trace_path.read_text())
        trace_data = saved.get("trace")
        schema_version = saved.get("schema_version")

    return {
        "schema_version": schema_version,
        "job_id": job.id,
        "status": job.status,
        "trace": trace_data,
        "failure_reason": job.failure_reason,
    }


@router.get("/jobs/{job_id}/artifacts/{name}")
def get_artifact(job_id: str, name: str, request: Request) -> FileResponse:
    """Fetch a named artifact (preview, mask, GeoJSON) for a job."""
    artifact_repo = request.app.state.artifact_repository
    if not artifact_repo.artifact_exists(job_id, name):
        raise HTTPException(404, detail=f"Artifact {name!r} not found for job {job_id!r}.")
    path = artifact_repo.artifact_path(job_id, name)
    return FileResponse(path)


