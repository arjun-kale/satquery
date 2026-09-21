"""Integration tests for raster ingestion — uses in-memory GeoTIFF fixtures."""

from __future__ import annotations

import io
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_bounds
from rasterio.crs import CRS

from app.ingestion.raster import ingest_raster, RasterIngestError


def _make_geotiff(bands: int = 3, width: int = 64, height: int = 64) -> bytes:
    """Create a minimal in-memory GeoTIFF with a known CRS and transform."""
    transform = from_bounds(77.0, 28.0, 77.1, 28.1, width, height)
    buf = io.BytesIO()
    with rasterio.open(
        buf,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=bands,
        dtype="uint16",
        crs=CRS.from_epsg(4326),
        transform=transform,
    ) as ds:
        for b in range(1, bands + 1):
            ds.write(np.random.randint(0, 3000, (height, width), dtype="uint16"), b)
    buf.seek(0)
    return buf.read()


def _make_png() -> bytes:
    """Tiny valid PNG bytes (1×1 red pixel)."""
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), color=(255, 0, 0)).save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


# ---------------------------------------------------------------------------

def test_geotiff_returns_metadata():
    data = _make_geotiff()
    meta = ingest_raster(data, "sample.tif", "img-001")
    assert meta.image_id == "img-001"
    assert meta.band_count == 3
    assert meta.width == 64
    assert meta.height == 64
    assert meta.crs is not None
    assert meta.gsd_m is not None and meta.gsd_m > 0
    assert meta.checksum_sha256 != ""
    assert meta.extent_wgs84 is not None and len(meta.extent_wgs84) == 4


def test_checksum_is_deterministic():
    data = _make_geotiff()
    m1 = ingest_raster(data, "a.tif", "id-1")
    m2 = ingest_raster(data, "a.tif", "id-1")
    assert m1.checksum_sha256 == m2.checksum_sha256


def test_png_without_flag_is_rejected():
    data = _make_png()
    with pytest.raises(RasterIngestError, match="benchmark_fixture"):
        ingest_raster(data, "photo.png", "img-002", benchmark_fixture=False)


def test_png_with_flag_is_accepted():
    data = _make_png()
    meta = ingest_raster(data, "fixture.png", "img-003", benchmark_fixture=True)
    assert meta.format == "PNG"


def test_non_raster_bytes_are_rejected():
    garbage = b"this is not a raster file at all"
    with pytest.raises(RasterIngestError):
        ingest_raster(garbage, "bad.tif", "img-004")


def test_georeferenced_flag():
    data = _make_geotiff()
    meta = ingest_raster(data, "geo.tif", "img-005")
    assert meta.is_georeferenced is True
