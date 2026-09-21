"""Two-image compatibility check — CRS and spatial overlap validation."""

from __future__ import annotations

from rasterio.crs import CRS
from rasterio.warp import transform_bounds
import rasterio

from app.schemas import CompatibilityReport


def check_compatibility(file_bytes_a: bytes, file_bytes_b: bytes) -> CompatibilityReport:
    """Check that two rasters share a CRS and have spatial overlap."""
    with rasterio.MemoryFile(file_bytes_a) as mfa, rasterio.MemoryFile(file_bytes_b) as mfb:
        with mfa.open() as dsa, mfb.open() as dsb:
            return _compare(dsa, dsb)


def _compare(dsa, dsb) -> CompatibilityReport:
    crs_a: CRS | None = dsa.crs
    crs_b: CRS | None = dsb.crs

    if crs_a is None or crs_b is None:
        return CompatibilityReport(
            compatible=False,
            rejection_reason="One or both images are not georeferenced.",
        )

    if not crs_a.equals(crs_b):
        return CompatibilityReport(
            compatible=False,
            rejection_reason=(
                f"CRS_MISMATCH: image A is {crs_a.to_string()!r}, "
                f"image B is {crs_b.to_string()!r}."
            ),
        )

    # Check spatial overlap in the shared CRS
    bounds_a = dsa.bounds
    bounds_b = dsb.bounds

    overlap = not (
        bounds_a.right < bounds_b.left
        or bounds_b.right < bounds_a.left
        or bounds_a.top < bounds_b.bottom
        or bounds_b.top < bounds_a.bottom
    )

    if not overlap:
        return CompatibilityReport(
            compatible=False,
            rejection_reason="NO_OVERLAP: the two images do not share a spatial footprint.",
        )

    return CompatibilityReport(compatible=True)
