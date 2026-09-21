"""Spectral index computation — pure numpy, no file I/O."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def _safe_ratio(a: NDArray, b: NDArray) -> NDArray:
    """(a - b) / (a + b) clamped to [-1, 1], nodata where denominator ≈ 0."""
    denom = a.astype(float) + b.astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        result = np.where(np.abs(denom) > 1e-6, (a - b) / denom, np.nan)
    return np.clip(result, -1.0, 1.0)


def compute_ndvi(red: NDArray, nir: NDArray) -> dict:
    """Normalised Difference Vegetation Index: (NIR - Red) / (NIR + Red)."""
    index = _safe_ratio(nir, red)
    return _stats(index, name="NDVI")


def compute_mndwi(green: NDArray, swir: NDArray) -> dict:
    """Modified Normalised Difference Water Index: (Green - SWIR) / (Green + SWIR)."""
    index = _safe_ratio(green, swir)
    return _stats(index, name="MNDWI")


def compute_ndbi(swir: NDArray, nir: NDArray) -> dict:
    """Normalised Difference Built-up Index: (SWIR - NIR) / (SWIR + NIR)."""
    index = _safe_ratio(swir, nir)
    return _stats(index, name="NDBI")


def _stats(index: NDArray, *, name: str) -> dict:
    valid = index[~np.isnan(index)]
    return {
        "name": name,
        "array": index,
        "mean": float(np.mean(valid)) if valid.size else float("nan"),
        "min": float(np.min(valid)) if valid.size else float("nan"),
        "max": float(np.max(valid)) if valid.size else float("nan"),
    }
