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

    if crs and transform:
        gsd_m = _gsd_metres(transform, crs)
        try:
            west, south, east, north = transform_bounds(
                crs, "EPSG:4326", *ds.bounds
            )
            extent_wgs84 = [west, south, east, north]
        except Exception:
            extent_wgs84 = None

    sensor_tags: dict[str, str] = {}
    for key in ("TIFFTAG_IMAGEDESCRIPTION", "satellite", "sensor", "SENSOR"):
        val = ds.tags().get(key)
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


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
