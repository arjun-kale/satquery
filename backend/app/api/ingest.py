"""POST /api/ingest — content-validated raster upload; per-image metadata and quick-looks."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Query, Response
from fastapi.responses import FileResponse

from app.ingestion.preview import render_preview, render_window, stretch_params
from app.ingestion.raster import ingest_raster, RasterIngestError
from app.schemas import IngestResponse, RasterMetadata
from app.storage.artifacts import ArtifactRepository

router = APIRouter(prefix="/api", tags=["ingest"])

_MAX_BYTES = 500 * 1024 * 1024  # 500 MB


def store_upload(
    artifact_repo: ArtifactRepository,
    content: bytes,
    filename: str,
    *,
    benchmark_fixture: bool = False,
) -> RasterMetadata:
    """Validate, persist the raster and its metadata; raise RasterIngestError on bad content."""
    image_id = artifact_repo.new_image_id()
    metadata = ingest_raster(content, filename, image_id, benchmark_fixture=benchmark_fixture)
    suffix = "." + filename.rsplit(".", 1)[-1].lower()
    artifact_repo.upload_path(image_id, suffix).write_bytes(content)
    artifact_repo.metadata_path(image_id).write_text(metadata.model_dump_json())
    return metadata


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

    try:
        metadata = store_upload(
            request.app.state.artifact_repository,
            content,
            file.filename or "upload",
            benchmark_fixture=benchmark_fixture,
        )
    except RasterIngestError as exc:
        raise HTTPException(422, detail={"code": "INVALID_FORMAT", "message": str(exc)})

    return IngestResponse(image_id=metadata.image_id, metadata=metadata)


def load_metadata(artifact_repo: ArtifactRepository, image_id: str) -> RasterMetadata:
    """Stored metadata, re-derived from the raster for uploads made before it was persisted."""
    meta_path = artifact_repo.metadata_path(image_id)
    if meta_path.exists():
        return RasterMetadata.model_validate_json(meta_path.read_text())
    path = artifact_repo.find_upload(image_id)
    metadata = ingest_raster(path.read_bytes(), path.name, image_id, benchmark_fixture=True)
    meta_path.write_text(metadata.model_dump_json())
    return metadata


@router.get("/images/{image_id}", response_model=RasterMetadata)
def get_image_metadata(image_id: str, request: Request) -> RasterMetadata:
    try:
        return load_metadata(request.app.state.artifact_repository, image_id)
    except FileNotFoundError:
        raise HTTPException(404, detail=f"Image {image_id!r} not found.")


@router.get("/images/{image_id}/preview.png")
def get_image_preview(image_id: str, request: Request) -> FileResponse:
    """Quick-look of one scene (same rendering the analysis tools use), cached on disk."""
    artifact_repo: ArtifactRepository = request.app.state.artifact_repository
    cached = artifact_repo.preview_path(image_id)
    if not cached.exists():
        try:
            png, _ = render_preview(artifact_repo.find_upload(image_id).read_bytes())
        except FileNotFoundError:
            raise HTTPException(404, detail=f"Image {image_id!r} not found.")
        cached.write_bytes(png)
    return FileResponse(cached, media_type="image/png")


_WINDOW_MAX = 256


@router.get("/images/{image_id}/window.png")
def get_image_window(
    image_id: str,
    request: Request,
    col0: int = Query(..., description="Left column of the window, in native scene pixels."),
    row0: int = Query(..., description="Top row of the window, in native scene pixels."),
    size: int = Query(64, ge=8, le=_WINDOW_MAX),
) -> Response:
    """Native-resolution pixels (no resampling) for the loupe, stretched exactly like the preview."""
    artifact_repo: ArtifactRepository = request.app.state.artifact_repository
    try:
        raw = artifact_repo.find_upload(image_id).read_bytes()
    except FileNotFoundError:
        raise HTTPException(404, detail=f"Image {image_id!r} not found.")
    cache = artifact_repo.preview_path(image_id).with_suffix(".stretch.json")
    if cache.exists():
        params = json.loads(cache.read_text())
    else:
        params = stretch_params(raw)
        cache.write_text(json.dumps(params))
    png = render_window(raw, col0, row0, size, params)
    return Response(png, media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})
