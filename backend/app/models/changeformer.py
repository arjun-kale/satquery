"""ChangeFormerAdapter — ChangeFormer V6 bi-temporal change detection, run locally on CPU.

Weights: the public DSIFN-CD checkpoint (MIT, wgcban/ChangeFormer), fetched by
``scripts/fetch_changeformer.py`` into ``<data_dir>/models/changeformer``. The model is small
enough (~41 M parameters) that CPU inference on the two 512 px quick-looks takes seconds, so it
needs no GPU worker. Without the weights file, every call raises ModelUnavailableError.

It was trained on 2 m Google Earth imagery; on 10 m Sentinel-2 quick-looks its masks are a real
model output but outside its training distribution, and the trace says so.
"""

from __future__ import annotations

import io
import json
import threading
from pathlib import Path
from typing import Literal

import numpy as np

from app.models.base import (
    BaseModelAdapter,
    ChangeMask,
    GroundingBox,
    ModelResult,
    ModelUnavailableError,
    assert_preview_input,
)
from app.tools.geodesy import change_area_m2

WEIGHTS_FILE = "changeformer_v6_dsifn.pt"
TILE = 256  # the network's training input size

_lock = threading.Lock()
_loaded: dict[Path, object] = {}


def default_weights_dir() -> Path:
    from app.config import Settings

    return Settings().data_dir / "models" / "changeformer"


class ChangeFormerAdapter(BaseModelAdapter):
    """ChangeFormer V6 for bi-temporal change detection on co-registered RGB quick-looks."""

    def __init__(self, mode: Literal["local", "modal"] = "local", weights_dir: Path | None = None) -> None:
        # `mode` is accepted for interface compatibility; inference always runs locally on CPU.
        self._dir = Path(weights_dir) if weights_dir else default_weights_dir()
        manifest = self._dir / "manifest.json"
        self.manifest: dict = json.loads(manifest.read_text()) if manifest.exists() else {}

    @property
    def model_mode(self) -> Literal["local"]:
        return "local"

    @property
    def weights(self) -> str:
        sha = self.manifest.get("sha256", "")[:12]
        return f"changeformer-v6 dsifn (sha256 {sha})" if sha else "changeformer-v6 dsifn"

    def _model(self):
        path = self._dir / WEIGHTS_FILE
        if not path.exists():
            raise ModelUnavailableError(
                f"ChangeFormer weights not found at {path}. Run scripts/fetch_changeformer.py."
            )
        with _lock:
            if path not in _loaded:
                import torch

                from app.models.vendor.changeformer.ChangeFormer import ChangeFormerV6

                net = ChangeFormerV6(embed_dim=256)
                state = torch.load(path, map_location="cpu", weights_only=True)
                net.load_state_dict({k.removeprefix("module."): v for k, v in state.items()})
                _loaded[path] = net.eval()
            return _loaded[path]

    def caption(self, preview_png: bytes, *, band_map: str) -> ModelResult:
        raise NotImplementedError("ChangeFormerAdapter does not support captioning.")

    def answer(self, preview_png: bytes, query: str, *, band_map: str) -> ModelResult:
        raise NotImplementedError("ChangeFormerAdapter does not support VQA.")

    def ground(self, preview_png: bytes, query: str, *, band_map: str) -> list[GroundingBox]:
        raise NotImplementedError("ChangeFormerAdapter does not support grounding.")

    def detect_change(
        self,
        preview_before: bytes,
        preview_after: bytes,
        *,
        band_map: str,
        affine_transform=None,
        crs=None,
    ) -> ChangeMask:
        """Run ChangeFormer tile by tile (256 px) over a co-registered preview pair.

        Confidence is the mean softmax probability of "change" over the pixels predicted as
        changed (or of "no change" over the whole image when nothing is predicted as changed).
        """
        assert_preview_input(preview_before)
        assert_preview_input(preview_after)
        net = self._model()

        import torch
        from PIL import Image

        a = np.asarray(Image.open(io.BytesIO(preview_before)).convert("RGB"), dtype=np.float32) / 255.0
        b = np.asarray(Image.open(io.BytesIO(preview_after)).convert("RGB"), dtype=np.float32) / 255.0
        if a.shape != b.shape:
            raise ValueError("ChangeFormer needs two quick-looks of the same size.")
        h, w, _ = a.shape
        ph, pw = -(-h // TILE) * TILE, -(-w // TILE) * TILE

        def to_tensor(x: np.ndarray):
            padded = np.pad(x, ((0, ph - h), (0, pw - w), (0, 0)), mode="reflect")
            # Same normalisation as ChangeFormer's training loader: mean 0.5, std 0.5.
            return torch.from_numpy((padded - 0.5) / 0.5).permute(2, 0, 1)

        ta, tb = to_tensor(a), to_tensor(b)
        prob = torch.zeros(ph, pw)
        with torch.inference_mode():
            for y in range(0, ph, TILE):
                for x in range(0, pw, TILE):
                    out = net(ta[None, :, y:y + TILE, x:x + TILE], tb[None, :, y:y + TILE, x:x + TILE])[-1]
                    prob[y:y + TILE, x:x + TILE] = torch.softmax(out, dim=1)[0, 1]
        p_change = prob[:h, :w].numpy()
        mask = p_change > 0.5
        confidence = float(p_change[mask].mean()) if mask.any() else float((1 - p_change).mean())

        area = change_area_m2(mask, affine_transform, crs) if affine_transform is not None and crs is not None else None
        return ChangeMask(mask=mask, changed_area_m2=area, confidence=confidence, confidence_source="model-provided")

    @staticmethod
    def mask_to_area(mask: np.ndarray, affine_transform, crs) -> float:
        """Convert a binary mask to m² — deterministic, independent of model."""
        return change_area_m2(mask, affine_transform, crs)
