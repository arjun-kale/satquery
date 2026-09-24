"""RGB / false-colour preview generation from a GeoTIFF."""

from __future__ import annotations

import io
import numpy as np
import rasterio
from PIL import Image


def render_preview(
    file_bytes: bytes,
    *,
    band_indices: tuple[int, int, int] = (1, 2, 3),
    size: tuple[int, int] = (512, 512),
) -> tuple[bytes, str]:
    """Render a preview PNG from the given bands.

    Parameters
    ----------
    file_bytes:
        Raw raster file bytes.
    band_indices:
        1-based band indices to use as (R, G, B). Default: first three bands.
    size:
        Output image size (width, height) in pixels.

    Returns
    -------
    (png_bytes, band_map_label)
        ``band_map_label`` records the exact mapping, e.g. ``'B4/B3/B2'``.
    """
    with rasterio.MemoryFile(file_bytes) as memfile:
        with memfile.open() as ds:
            if (ds.tags().get("modality") or "").lower() == "sar":
                return _render_sar_db(ds.read(1).astype(float), size)
            max_band = ds.count
            safe_indices = tuple(min(b, max_band) for b in band_indices)
            names = [d or f"B{i}" for i, d in enumerate(ds.descriptions or (), start=1)]
            r = ds.read(safe_indices[0]).astype(float)
            g = ds.read(safe_indices[1]).astype(float)
            b = ds.read(safe_indices[2]).astype(float)

    def _normalise(arr: np.ndarray) -> np.ndarray:
        lo, hi = np.nanpercentile(arr, 2), np.nanpercentile(arr, 98)
        if hi == lo:
            return np.zeros_like(arr, dtype=np.uint8)
        clipped = np.clip(arr, lo, hi)
        return ((clipped - lo) / (hi - lo) * 255).astype(np.uint8)

    rgb = np.stack([_normalise(r), _normalise(g), _normalise(b)], axis=-1)
    img = Image.fromarray(rgb, mode="RGB").resize(size, Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    label = lambda i: names[i - 1] if i - 1 < len(names) else f"B{i}"  # noqa: E731
    band_map = "/".join(label(i) for i in safe_indices)
    return buf.read(), band_map


SAR_DB_RANGE = (-25.0, 0.0)


def _render_sar_db(linear: np.ndarray, size: tuple[int, int]) -> tuple[bytes, str]:
    """Greyscale quick-look of band 1 backscatter in dB with a fixed, labelled stretch.

    A fixed stretch (not a percentile one) keeps brightness comparable across scenes.
    """
    with np.errstate(divide="ignore", invalid="ignore"):
        db = 10.0 * np.log10(np.where(linear > 0, linear, np.nan))
    lo, hi = SAR_DB_RANGE
    grey = np.nan_to_num((np.clip(db, lo, hi) - lo) / (hi - lo) * 255, nan=0).astype(np.uint8)
    img = Image.fromarray(grey, mode="L").convert("RGB").resize(size, Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue(), f"B1 dB [{lo:g}, {hi:g}]"
