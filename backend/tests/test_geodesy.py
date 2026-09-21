"""Unit tests for geodesy utilities."""

import math
import numpy as np
import pytest
from affine import Affine
from rasterio.crs import CRS

from app.tools.geodesy import pixel_to_wgs84, bounding_box_wgs84, change_area_m2


# Projected CRS: UTM zone 44N (India)
UTM_CRS = CRS.from_epsg(32644)

# Simple affine: 10 m pixels, origin at (500000 E, 2800000 N) UTM44N
TRANSFORM = Affine(10.0, 0.0, 500000.0, 0.0, -10.0, 2800000.0)


def test_pixel_to_wgs84_returns_tuple():
    lat, lon = pixel_to_wgs84(0, 0, TRANSFORM, UTM_CRS)
    assert isinstance(lat, float)
    assert isinstance(lon, float)
    # Origin is in India — rough sanity check
    assert 20.0 < lat < 30.0
    assert 70.0 < lon < 90.0


def test_bounding_box_wgs84_shape():
    bbox = bounding_box_wgs84(TRANSFORM, width=100, height=100, crs=UTM_CRS)
    assert len(bbox) == 4
    west, south, east, north = bbox
    assert west < east
    assert south < north


def test_change_area_m2_all_true():
    mask = np.ones((10, 10), dtype=bool)
    area = change_area_m2(mask, TRANSFORM, UTM_CRS)
    # 100 pixels × 10 m × 10 m = 10 000 m²
    assert abs(area - 10_000.0) < 1.0


def test_change_area_m2_empty_mask():
    mask = np.zeros((10, 10), dtype=bool)
    area = change_area_m2(mask, TRANSFORM, UTM_CRS)
    assert area == 0.0
