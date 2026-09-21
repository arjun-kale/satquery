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
            max_band = ds.count
            safe_indices = tuple(min(b, max_band) for b in band_indices)
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

    band_map = f"B{safe_indices[0]}/B{safe_indices[1]}/B{safe_indices[2]}"
    return buf.read(), band_map
