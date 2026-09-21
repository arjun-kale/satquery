"""POST /api/ingest — content-validated raster upload."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Query
from fastapi.responses import JSONResponse

from app.ingestion.raster import ingest_raster, RasterIngestError
from app.schemas import IngestResponse

router = APIRouter(prefix="/api", tags=["ingest"])

_MAX_BYTES = 500 * 1024 * 1024  # 500 MB


@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    request: Request,
    file: UploadFile = File(...),
    benchmark_fixture: bool = Query(False, description="Set true for benchmark PNG/JPEG fixtures."),
) -> IngestResponse:
    """Validate and ingest a raster file. GeoTIFF/TIFF only unless benchmark_fixture=true."""
    content = await file.read(_MAX_BYTES + 1)
    if len(content) > _MAX_BYTES:
        raise HTTPException(413, detail="File exceeds 500 MB limit.")

    artifact_repo = request.app.state.artifact_repository
    image_id = artifact_repo.new_image_id()

    try:
        metadata = ingest_raster(
            content,
            file.filename or "upload",
            image_id,
            benchmark_fixture=benchmark_fixture,
        )
    except RasterIngestError as exc:
        raise HTTPException(422, detail={"code": "INVALID_FORMAT", "message": str(exc)})

    # Persist the upload
    suffix = "." + (file.filename or "upload").rsplit(".", 1)[-1].lower()
    upload_path = artifact_repo.upload_path(image_id, suffix)
    upload_path.write_bytes(content)

    return IngestResponse(image_id=image_id, metadata=metadata)
