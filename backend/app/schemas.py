"""API contracts for Phase 0 health and Phase 1 ingestion surfaces."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.state import JobStatus


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    database: Literal["ok"] = "ok"
    model_mode: Literal["mock", "local", "modal", "hf"]


class ErrorResponse(BaseModel):
    request_id: str = Field(description="Identifier to use when diagnosing a failed request.")
    code: str
    message: str


class JobRecord(BaseModel):
    id: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    failure_reason: str | None = None


class RasterMetadata(BaseModel):
    """Extracted metadata from a validated raster upload."""

    image_id: str
    filename: str
    checksum_sha256: str
    format: str
    width: int
    height: int
    band_count: int
    dtype: str
    crs: str | None
    gsd_m: float | None = Field(None, description="Ground sample distance in metres.")
    extent_wgs84: list[float] | None = Field(
        None, description="[west, south, east, north] in WGS-84."
    )
    corners_wgs84: list[list[float]] | None = Field(
        None,
        description="[lon, lat] of the UL, UR, LR, LL pixel corners, for pixel → geo readouts.",
    )
    modality: Literal["optical", "sar", "unknown"] = Field(
        "unknown", description="Declared by file tags only; 'unknown' when the metadata doesn't say."
    )
    acquired_at: str | None = Field(None, description="Acquisition date from file tags, if present.")
    nodata: float | None = None
    sensor_tags: dict[str, str] = Field(default_factory=dict)
    preview_band_map: str | None = Field(
        None, description="Band mapping used for preview, e.g. 'B4/B3/B2'."
    )
    is_georeferenced: bool = True


class IngestResponse(BaseModel):
    image_id: str
    metadata: RasterMetadata


class CompatibilityReport(BaseModel):
    compatible: bool
    rejection_reason: str | None = None
