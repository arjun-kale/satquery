"""Sentinel-2 RGB rendering and the M2 dataset built on the upstream BigEarthNet.txt loader."""

from __future__ import annotations

import numpy as np
from PIL import Image

from .geochat import IMAGE_SIZE, build_question, build_target

RGB_BANDS = ("B04", "B03", "B02")


def _normalise(arr: np.ndarray) -> np.ndarray:
    # Must stay identical to backend/app/ingestion/preview.py::_normalise: the adapter is served on
    # previews rendered by that function, so it has to be trained on the same rendering.
    lo, hi = np.nanpercentile(arr, 2), np.nanpercentile(arr, 98)
    if hi == lo:
        return np.zeros_like(arr, dtype=np.uint8)
    clipped = np.clip(arr, lo, hi)
    return ((clipped - lo) / (hi - lo) * 255).astype(np.uint8)


def render_rgb(bands: np.ndarray, size: int = IMAGE_SIZE) -> Image.Image:
    """(3, H, W) raw reflectance in R, G, B order -> per-band 2-98% stretched RGB, LANCZOS-resized."""
    if bands.ndim != 3 or bands.shape[0] != 3:
        raise ValueError(f"Expected (3, H, W) R/G/B stack, got {bands.shape}")
    bands = bands.astype(np.float64)
    rgb = np.stack([_normalise(b) for b in bands], axis=-1)
    return Image.fromarray(rgb, mode="RGB").resize((size, size), Image.LANCZOS)


def expand2square(img: Image.Image, background_color: tuple[int, int, int]) -> Image.Image:
    """geochat.mm_utils.expand2square: pad non-square inputs with the CLIP mean colour."""
    w, h = img.size
    if w == h:
        return img
    side = max(w, h)
    out = Image.new(img.mode, (side, side), background_color)
    out.paste(img, ((side - w) // 2, (side - h) // 2))
    return out


class M2Dataset:
    """Wraps the dataset repo's own ``BENTxTDataset`` (vendored as ben_txt_datamodule.py).

    ``manifest_path`` is a parquet produced by ``splits.build_splits``: a row subset of
    BigEarthNet.txt.parquet with all original columns, so it is a valid ``metadata_file`` for the
    upstream loader. No filters are passed, so row order matches the manifest.
    """

    def __init__(self, manifest_path: str, lmdb_path: str):
        import pandas as pd
        from ben_txt_datamodule import BENTxTDataset

        self.meta = pd.read_parquet(manifest_path).reset_index(drop=True)
        self.ben = BENTxTDataset(
            lmdb_file=lmdb_path,
            metadata_file=manifest_path,
            bands=RGB_BANDS,
            img_size=120,
            # Keep the tags: build_question maps them to GeoChat's <p>..</p> / {<x><y>} syntax
            ref_token=["<ref>", "</ref>"],
            point_token=["<point>", "</point>"],
        )
        if len(self.ben) != len(self.meta):
            raise RuntimeError(f"Upstream loader saw {len(self.ben)} rows, manifest has {len(self.meta)}")

    def __len__(self) -> int:
        return len(self.meta)

    def __getitem__(self, idx: int) -> dict:
        sample = self.ben[idx]
        row = self.meta.iloc[idx]
        return {
            "image": render_rgb(sample["image_input"].numpy()),
            "question": build_question(sample["text_input"], row["type"]),
            "target": build_target(sample["reference_output"], row["type"]),
            "reference_output": sample["reference_output"],
            "type": row["type"],
            "category": row["category"] if row["category"] is not None else "",
            "row_id": str(row["ID"]),
            "patch_id": row["patch_id"],
        }
