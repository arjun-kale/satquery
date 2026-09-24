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


def stretch_params(file_bytes: bytes, band_indices: tuple[int, int, int] = (1, 2, 3)) -> dict:
    """The per-band 2-98 % limits of the whole scene (from a decimated read), so a native-resolution
    window can be rendered with exactly the preview's stretch."""
    with rasterio.MemoryFile(file_bytes) as memfile:
        with memfile.open() as ds:
            if (ds.tags().get("modality") or "").lower() == "sar":
                return {"mode": "sar_db", "range": list(SAR_DB_RANGE)}
            safe = [min(b, ds.count) for b in band_indices]
            f = max(1, max(ds.width, ds.height) // 2048)
            out_shape = (len(safe), ds.height // f, ds.width // f)
            arr = ds.read(safe, out_shape=out_shape).astype(float)
    limits = [[float(np.nanpercentile(b, 2)), float(np.nanpercentile(b, 98))] for b in arr]
    return {"mode": "rgb", "bands": safe, "limits": limits}


def render_window(file_bytes: bytes, col0: int, row0: int, size: int, params: dict) -> bytes:
    """A size×size window of native pixels starting at (col0, row0), no resampling.

    Pixels outside the scene are transparent.
    """
    from rasterio.windows import Window

    win = Window(col0, row0, size, size)
    with rasterio.MemoryFile(file_bytes) as memfile:
        with memfile.open() as ds:
            if params["mode"] == "sar_db":
                band = ds.read(1, window=win, boundless=True, fill_value=0).astype(float)
                inside = band > 0
                with np.errstate(divide="ignore", invalid="ignore"):
                    db = 10.0 * np.log10(np.where(inside, band, np.nan))
                lo, hi = params["range"]
                grey = np.nan_to_num((np.clip(db, lo, hi) - lo) / (hi - lo) * 255, nan=0).astype(np.uint8)
                rgb = np.stack([grey] * 3, axis=-1)
            else:
                arr = ds.read(params["bands"], window=win, boundless=True, masked=True).astype(float)
                inside = ~np.ma.getmaskarray(arr).all(axis=0)
                chans = []
                for b, (lo, hi) in zip(arr.filled(np.nan), params["limits"]):
                    chans.append(np.zeros_like(b, dtype=np.uint8) if hi == lo else
                                 np.nan_to_num((np.clip(b, lo, hi) - lo) / (hi - lo) * 255, nan=0).astype(np.uint8))
                rgb = np.stack(chans, axis=-1)
            # Boundless reads mark outside pixels as masked/fill; also treat out-of-range indices as outside.
            rows = np.arange(row0, row0 + size)[:, None]
            cols = np.arange(col0, col0 + size)[None, :]
            inside = inside & (rows >= 0) & (rows < ds.height) & (cols >= 0) & (cols < ds.width)

    alpha = np.where(inside, 255, 0).astype(np.uint8)
    img = Image.fromarray(np.dstack([rgb, alpha]), mode="RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
