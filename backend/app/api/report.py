import json
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/jobs", tags=["report"])

@router.get("/{job_id}/report")
def download_report(job_id: str, request: Request):
    """Download an auditable JSON report for the job execution."""
    repo = request.app.state.job_repository
    artifact_repo = request.app.state.artifact_repository
    
    try:
        job = repo.get(job_id)
    except KeyError:
        raise HTTPException(404, detail=f"Job {job_id!r} not found.")
        
    trace_data = None
    if artifact_repo.artifact_exists(job_id, "trace.json"):
        trace_path = artifact_repo.artifact_path(job_id, "trace.json")
        trace_data = json.loads(trace_path.read_text()).get("trace")
        
    artifacts = []
    for artifact_file in ["preview.png", "preview_b.png", "index_mask.png", "change_mask.png", "fused_preview.png", "grounding_boxes.json", "change_regions.json"]:
        if artifact_repo.artifact_exists(job_id, artifact_file):
            artifacts.append(f"/api/jobs/{job_id}/artifacts/{artifact_file}")
            
    report = {
        "job_id": job.id,
        "status": job.status,
        "failure_reason": job.failure_reason,
        "created_at": job.created_at.isoformat() if hasattr(job.created_at, "isoformat") else str(job.created_at),
        "artifacts": artifacts,
        "execution_summary": trace_data,
    }
    
    return JSONResponse(
        content=report,
        headers={"Content-Disposition": f'attachment; filename="satquery_report_{job_id}.json"'}
    )
