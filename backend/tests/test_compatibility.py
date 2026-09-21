"""Tests for two-image compatibility checks."""

from __future__ import annotations

import io
import numpy as np
import pytest
import rasterio
from rasterio.crs import CRS
from rasterio.transform import from_bounds

from app.ingestion.compatibility import check_compatibility


def _make_tiff(
    epsg: int,
    west: float, south: float, east: float, north: float,
    width: int = 32, height: int = 32,
) -> bytes:
    transform = from_bounds(west, south, east, north, width, height)
    buf = io.BytesIO()
    with rasterio.open(
        buf, "w", driver="GTiff",
        height=height, width=width, count=1, dtype="uint8",
        crs=CRS.from_epsg(epsg), transform=transform,
    ) as ds:
        ds.write(np.zeros((height, width), dtype="uint8"), 1)
    buf.seek(0)
    return buf.read()


def test_compatible_images():
    a = _make_tiff(4326, 77.0, 28.0, 77.1, 28.1)
    b = _make_tiff(4326, 77.05, 28.05, 77.15, 28.15)
    report = check_compatibility(a, b)
    assert report.compatible is True
    assert report.rejection_reason is None


def test_crs_mismatch():
    a = _make_tiff(4326, 77.0, 28.0, 77.1, 28.1)
    b = _make_tiff(32644, 500000, 2800000, 501000, 2801000)
    report = check_compatibility(a, b)
    assert report.compatible is False
    assert "CRS_MISMATCH" in report.rejection_reason


def test_no_overlap():
    a = _make_tiff(4326, 77.0, 28.0, 77.1, 28.1)
    b = _make_tiff(4326, 90.0, 28.0, 90.1, 28.1)
    report = check_compatibility(a, b)
    assert report.compatible is False
    assert "NO_OVERLAP" in report.rejection_reason
