"""Tests proving raw raster arrays cannot cross the adapter boundary."""

from __future__ import annotations

import numpy as np
import pytest

from app.models.base import RawRasterBoundaryError, assert_preview_input
from app.models.mock import MockModelAdapter
from app.models.geochat import GeoChatAdapter


MOCK = MockModelAdapter()
BAND_MAP = "B4/B3/B2"
RAW_ARRAY = np.random.randint(0, 3000, (3, 64, 64), dtype=np.uint16)
FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100


def test_assert_preview_input_raises_on_ndarray():
    with pytest.raises(RawRasterBoundaryError):
        assert_preview_input(RAW_ARRAY)


def test_assert_preview_input_passes_on_bytes():
    assert_preview_input(FAKE_PNG)  # must not raise


def test_mock_caption_rejects_raw_array():
    with pytest.raises(RawRasterBoundaryError):
        MOCK.caption(RAW_ARRAY, band_map=BAND_MAP)


def test_mock_answer_rejects_raw_array():
    with pytest.raises(RawRasterBoundaryError):
        MOCK.answer(RAW_ARRAY, "query", band_map=BAND_MAP)


def test_mock_ground_rejects_raw_array():
    with pytest.raises(RawRasterBoundaryError):
        MOCK.ground(RAW_ARRAY, "vehicle", band_map=BAND_MAP)


def test_mock_detect_change_rejects_raw_array_before():
    with pytest.raises(RawRasterBoundaryError):
        MOCK.detect_change(RAW_ARRAY, FAKE_PNG, band_map=BAND_MAP)


def test_mock_detect_change_rejects_raw_array_after():
    with pytest.raises(RawRasterBoundaryError):
        MOCK.detect_change(FAKE_PNG, RAW_ARRAY, band_map=BAND_MAP)


def test_geochat_caption_rejects_raw_array():
    geochat = GeoChatAdapter(mode="local")
    with pytest.raises(RawRasterBoundaryError):
        geochat.caption(RAW_ARRAY, band_map=BAND_MAP)


def test_geochat_answer_rejects_raw_array():
    geochat = GeoChatAdapter(mode="local")
    with pytest.raises(RawRasterBoundaryError):
        geochat.answer(RAW_ARRAY, "query", band_map=BAND_MAP)
