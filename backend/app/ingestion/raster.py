"""Content-validated raster metadata extraction."""

from __future__ import annotations

import hashlib
import io
from pathlib import Path
from typing import Any

import rasterio
from rasterio.crs import CRS
from rasterio.warp import transform_bounds
from pyproj import Transformer

from app.schemas import RasterMetadata


_GEOTIFF_DRIVERS = {"GTiff"}
_ALLOWED_DRIVERS = {"GTiff", "PNG", "JPEG"}


class RasterIngestError(ValueError):
    """Raised when a file fails content validation."""


def ingest_raster(
    file_bytes: bytes,
    filename: str,
    image_id: str,
    *,
    benchmark_fixture: bool = False,
) -> RasterMetadata:
    """Validate and extract metadata from a raster upload.

    PNG/JPEG accepted only when *benchmark_fixture* is True.
    """
    checksum = _sha256(file_bytes)

    with rasterio.MemoryFile(file_bytes) as memfile:
        try:
            with memfile.open() as ds:
                driver = ds.driver
        except Exception as exc:
            raise RasterIngestError(f"Cannot open file as a raster: {exc}") from exc

        if driver not in _ALLOWED_DRIVERS:
            raise RasterIngestError(
                f"Unsupported format '{driver}'. Accepted: GeoTIFF, PNG, JPEG."
            )

        if driver != "GTiff" and not benchmark_fixture:
            raise RasterIngestError(
                f"'{driver}' uploads are only accepted when benchmark_fixture=true."
            )

        with memfile.open() as ds:
            return _extract(ds, image_id, filename, checksum)


def _extract(ds: Any, image_id: str, filename: str, checksum: str) -> RasterMetadata:
    crs: CRS | None = ds.crs
    crs_str = crs.to_string() if crs else None
    transform = ds.transform

    gsd_m: float | None = None
    extent_wgs84: list[float] | None = None
    is_georeferenced = crs is not None

    corners_wgs84: list[list[float]] | None = None
    if crs and transform:
        gsd_m = _gsd_metres(transform, crs)
        try:
            west, south, east, north = transform_bounds(
                crs, "EPSG:4326", *ds.bounds
            )
            extent_wgs84 = [west, south, east, north]
            corners_wgs84 = _corners_wgs84(transform, ds.width, ds.height, crs)
        except Exception:
            extent_wgs84 = None

    tags = ds.tags()
    sensor_tags: dict[str, str] = {}
    for key in (
        "TIFFTAG_IMAGEDESCRIPTION", "satellite", "sensor", "SENSOR",
        "modality", "polarisation", "acquired_at", "source", "license",
    ):
        val = tags.get(key)
        if val:
            sensor_tags[key] = val

    # Determine preview band map for 3-band images
    preview_band_map: str | None = None
    if ds.count >= 3:
        preview_band_map = "B1/B2/B3"  # placeholder; overwritten by preview.py

    return RasterMetadata(
        image_id=image_id,
        filename=filename,
        checksum_sha256=checksum,
        format=ds.driver,
        width=ds.width,
        height=ds.height,
        band_count=ds.count,
        dtype=str(ds.dtypes[0]),
        crs=crs_str,
        gsd_m=gsd_m,
        extent_wgs84=extent_wgs84,
        corners_wgs84=corners_wgs84,
        modality=_modality(tags),
        acquired_at=tags.get("acquired_at") or tags.get("ACQUISITION_DATE"),
        nodata=ds.nodata,
        sensor_tags=sensor_tags,
        preview_band_map=preview_band_map,
        is_georeferenced=is_georeferenced,
    )


def _gsd_metres(transform: Any, crs: CRS) -> float:
    """Derive GSD from the affine transform, converting to metres if needed."""
    pixel_width = abs(transform.a)
    pixel_height = abs(transform.e)
    pixel_size = (pixel_width + pixel_height) / 2.0

    # If CRS is geographic (degrees), convert to metres at centroid
    if crs.is_geographic:
        transformer = Transformer.from_crs(crs, crs.geodetic_crs, always_xy=True)
        # 1 degree at equator ≈ 111_320 m; use pyproj for accuracy
        lat = transform.f + transform.e * 0.5
        lon = transform.c + transform.a * 0.5
        _, lat_m = transformer.transform(lon, lat)
        # metres per degree latitude
        metre_per_deg = 111_320.0
        pixel_size = pixel_size * metre_per_deg

    return round(pixel_size, 4)


def _corners_wgs84(transform: Any, width: int, height: int, crs: CRS) -> list[list[float]]:
    """[lon, lat] of the four outer pixel corners, clockwise from upper-left."""
    proj = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    corners = []
    for col, row in ((0, 0), (width, 0), (width, height), (0, height)):
        x, y = transform @ (col, row)
        lon, lat = proj.transform(x, y)
        corners.append([round(lon, 8), round(lat, 8)])
    return corners


def _modality(tags: dict[str, str]) -> str:
    """Only trust what the file declares; never guess modality from pixel statistics."""
    declared = (tags.get("modality") or "").lower()
    if declared in ("optical", "sar"):
        return declared
    sensor = " ".join(tags.get(k, "") for k in ("sensor", "SENSOR", "satellite")).lower()
    if any(s in sensor for s in ("sentinel-1", "sar", "risat", "eos-04")):
        return "sar"
    if any(s in sensor for s in ("sentinel-2", "landsat", "liss", "cartosat", "resourcesat")):
        return "optical"
    return "unknown"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
