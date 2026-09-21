"""Tests for the MockModelAdapter — all methods, no GPU required."""

from __future__ import annotations

import numpy as np
import pytest

from app.models.mock import MockModelAdapter
from app.models.base import RawRasterBoundaryError


ADAPTER = MockModelAdapter()
FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100  # minimal fake PNG bytes
BAND_MAP = "B4/B3/B2"


def test_mock_mode_label():
    assert ADAPTER.model_mode == "mock"


def test_caption_returns_result():
    result = ADAPTER.caption(FAKE_PNG, band_map=BAND_MAP)
    assert "[MOCK]" in result.text
    assert result.model_mode == "mock"
    assert result.confidence_source == "unavailable"


def test_answer_returns_result():
    result = ADAPTER.answer(FAKE_PNG, "Is there water?", band_map=BAND_MAP)
    assert "Is there water?" in result.text
    assert result.model_mode == "mock"


def test_ground_returns_boxes():
    boxes = ADAPTER.ground(FAKE_PNG, "vehicle", band_map=BAND_MAP)
    assert len(boxes) >= 1
    assert boxes[0].label is not None


def test_detect_change_returns_mask():
    mask_result = ADAPTER.detect_change(FAKE_PNG, FAKE_PNG, band_map=BAND_MAP)
    assert mask_result.mask.dtype == bool
    assert mask_result.mask.any()  # some pixels changed


def test_detect_change_area_with_georeference():
    from affine import Affine
    from rasterio.crs import CRS
    transform = Affine(10.0, 0.0, 500000.0, 0.0, -10.0, 2800000.0)
    crs = CRS.from_epsg(32644)
    result = ADAPTER.detect_change(FAKE_PNG, FAKE_PNG, band_map=BAND_MAP,
                                   affine_transform=transform, crs=crs)
    assert result.changed_area_m2 is not None
    assert result.changed_area_m2 > 0


def test_detect_change_area_none_without_georeference():
    result = ADAPTER.detect_change(FAKE_PNG, FAKE_PNG, band_map=BAND_MAP)
    assert result.changed_area_m2 is None
