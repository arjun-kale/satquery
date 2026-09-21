"""Unit tests for spectral index functions."""

import numpy as np
import pytest

from app.tools.spectral import compute_ndvi, compute_mndwi, compute_ndbi


def _arr(*values):
    return np.array(values, dtype=float)


def test_ndvi_known_value():
    red = _arr(100.0)
    nir = _arr(300.0)
    result = compute_ndvi(red, nir)
    # (300 - 100) / (300 + 100) = 0.5
    assert result["name"] == "NDVI"
    assert abs(result["mean"] - 0.5) < 1e-6


def test_ndvi_zero_denominator_is_nan():
    red = _arr(0.0)
    nir = _arr(0.0)
    result = compute_ndvi(red, nir)
    assert np.isnan(result["mean"])


def test_mndwi_known_value():
    green = _arr(200.0)
    swir = _arr(100.0)
    result = compute_mndwi(green, swir)
    # (200 - 100) / (200 + 100) = 0.333...
    assert abs(result["mean"] - (1 / 3)) < 1e-6


def test_ndbi_known_value():
    swir = _arr(300.0)
    nir = _arr(100.0)
    result = compute_ndbi(swir, nir)
    # (300 - 100) / (300 + 100) = 0.5
    assert abs(result["mean"] - 0.5) < 1e-6


def test_ndvi_clipped_to_minus_one():
    red = _arr(1000.0)
    nir = _arr(0.0)
    result = compute_ndvi(red, nir)
    assert result["min"] >= -1.0
    assert result["max"] <= 1.0
