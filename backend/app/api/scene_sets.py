"""POST /api/scene-sets/validate — the checks a scene set must pass before questions are asked.

Every check is computed from the stored rasters and their metadata. Nothing here is estimated:
a check that can't be decided from the files is reported as ``warn`` with the reason.
"""

from __future__ import annotations

from typing import Literal

import rasterio
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.api.ingest import load_metadata
from app.schemas import RasterMetadata
from app.storage.artifacts import ArtifactRepository

router = APIRouter(prefix="/api/scene-sets", tags=["scene-sets"])

SceneSetKind = Literal["single", "bitemporal", "optical_sar"]
CheckStatus = Literal["pass", "warn", "fail"]


class ValidateRequest(BaseModel):
    kind: SceneSetKind
    image_ids: list[str]


class ValidationCheck(BaseModel):
    id: str
    label: str
    status: CheckStatus
    value: str | None = None
    reason: str | None = None


class ValidateResponse(BaseModel):
    kind: SceneSetKind
    passed: bool
    checks: list[ValidationCheck]


_EXPECTED_COUNT = {"single": 1, "bitemporal": 2, "optical_sar": 2}


@router.post("/validate", response_model=ValidateResponse)
def validate_scene_set(body: ValidateRequest, request: Request) -> ValidateResponse:
    artifact_repo: ArtifactRepository = request.app.state.artifact_repository
    try:
        metas = [load_metadata(artifact_repo, i) for i in body.image_ids]
    except FileNotFoundError as exc:
        raise HTTPException(404, detail=str(exc))

    checks = run_checks(body.kind, metas, artifact_repo)
    return ValidateResponse(
        kind=body.kind,
        passed=all(c.status != "fail" for c in checks),
        checks=checks,
    )


def run_checks(
    kind: SceneSetKind, metas: list[RasterMetadata], artifact_repo: ArtifactRepository
) -> list[ValidationCheck]:
    expected = _EXPECTED_COUNT[kind]
    checks: list[ValidationCheck] = []

    count_ok = len(metas) == expected
    checks.append(ValidationCheck(
        id="count", label="Scenes", status="pass" if count_ok else "fail",
        value=f"{len(metas)} of {expected}",
        reason=None if count_ok else f"This scene set needs {expected} image{'s' if expected > 1 else ''}.",
    ))
    if not count_ok:
        return checks

    formats = [m.format for m in metas]
    checks.append(ValidationCheck(
        id="format", label="Format",
        status="pass" if all(f == "GTiff" for f in formats) else "warn",
        value=" / ".join("GeoTIFF" if f == "GTiff" else f for f in formats),
        reason=None if all(f == "GTiff" for f in formats)
        else "PNG is accepted only for benchmark images. Upload the GeoTIFF to keep georeferencing.",
    ))

    georef = [m.crs is not None for m in metas]
    if all(georef):
        checks.append(ValidationCheck(
            id="georef", label="Georeferenced", status="pass",
            value=" / ".join(sorted({m.crs or "" for m in metas})),
        ))
    else:
        checks.append(ValidationCheck(
            id="georef", label="Georeferenced",
            # A single ungeoreferenced image can still be described; a pair can't be aligned.
            status="warn" if kind == "single" else "fail",
            value="missing",
            reason="Without georeferencing, coordinates and areas can't be computed."
            if kind == "single" else "Both images need georeferencing to check that they cover the same area.",
        ))

    if kind == "optical_sar":
        a, b = metas[0].modality, metas[1].modality
        ok = (a, b) == ("optical", "sar")
        checks.append(ValidationCheck(
            id="modality", label="Optical + SAR",
            status="pass" if ok else "warn",
            value=f"{a} / {b}",
            reason=None if ok else "The file tags don't declare one optical and one SAR scene. Check the roles.",
        ))

    if kind == "single":
        m = metas[0]
        checks.append(ValidationCheck(
            id="gsd", label="Ground sample distance",
            status="pass" if m.gsd_m else "warn",
            value=f"{m.gsd_m:g} m" if m.gsd_m else "unknown",
            reason=None if m.gsd_m else "Areas and the scale bar won't be available.",
        ))
        return checks

    if not all(georef):
        return checks

    checks.extend(_pair_checks(kind, metas, artifact_repo))
    return checks


def _pair_checks(
    kind: SceneSetKind, metas: list[RasterMetadata], artifact_repo: ArtifactRepository
) -> list[ValidationCheck]:
    a, b = metas
    checks: list[ValidationCheck] = []

    with rasterio.open(artifact_repo.find_upload(a.image_id)) as dsa, \
            rasterio.open(artifact_repo.find_upload(b.image_id)) as dsb:
        same_crs = dsa.crs.equals(dsb.crs)
        checks.append(ValidationCheck(
            id="same_crs", label="Same CRS", status="pass" if same_crs else "fail",
            value=a.crs if same_crs else f"{a.crs} vs {b.crs}",
            reason=None if same_crs else "These two images use different coordinate systems. Upload a co-registered pair.",
        ))
        if not same_crs:
            return checks

        overlap = _overlap_fraction(dsa.bounds, dsb.bounds)
        checks.append(ValidationCheck(
            id="overlap", label="Same area",
            status="pass" if overlap >= 0.9 else "warn" if overlap > 0 else "fail",
            value=f"{overlap * 100:.0f}% overlap",
            reason=None if overlap >= 0.9
            else "These two images don't overlap the same area." if overlap == 0
            else "The images only partly overlap; results cover the shared area less reliably.",
        ))

        same_grid = (dsa.width, dsa.height) == (dsb.width, dsb.height)
        checks.append(ValidationCheck(
            id="grid", label="Pixel grid", status="pass" if same_grid else "warn",
            value=f"{dsa.width}×{dsa.height}" if same_grid
            else f"{dsa.width}×{dsa.height} vs {dsb.width}×{dsb.height}",
            reason=None if same_grid else "Grids differ; both are resampled to the same quick-look size for comparison.",
        ))

    if a.gsd_m and b.gsd_m:
        close = abs(a.gsd_m - b.gsd_m) / max(a.gsd_m, b.gsd_m) <= 0.1
        checks.append(ValidationCheck(
            id="gsd", label="Ground sample distance", status="pass" if close else "warn",
            value=f"{a.gsd_m:g} m / {b.gsd_m:g} m",
            reason=None if close else "Resolutions differ by more than 10%.",
        ))

    if kind == "bitemporal":
        if a.acquired_at and b.acquired_at:
            differ = a.acquired_at != b.acquired_at
            checks.append(ValidationCheck(
                id="dates", label="Two dates", status="pass" if differ else "warn",
                value=f"{a.acquired_at} → {b.acquired_at}",
                reason=None if differ else "Both images carry the same date.",
            ))
        else:
            checks.append(ValidationCheck(
                id="dates", label="Two dates", status="warn", value="not in metadata",
                reason="The files don't record acquisition dates; make sure T1 is the earlier image.",
            ))
    return checks


def _overlap_fraction(ba, bb) -> float:
    """Intersection area over the smaller footprint, in the shared CRS."""
    w = min(ba.right, bb.right) - max(ba.left, bb.left)
    h = min(ba.top, bb.top) - max(ba.bottom, bb.bottom)
    if w <= 0 or h <= 0:
        return 0.0
    smaller = min((ba.right - ba.left) * (ba.top - ba.bottom), (bb.right - bb.left) * (bb.top - bb.bottom))
    return min(1.0, (w * h) / smaller) if smaller > 0 else 0.0
