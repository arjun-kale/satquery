"""GeoChatAdapter — remote-sensing VLM integration (local / Modal mode).

GeoChat accepts ONLY 3-channel rendered preview PNG files.
Raw raster arrays, raw band data, and multi-band TIFFs must never reach this adapter.
The band mapping used to produce the preview is recorded in every call.
"""

from __future__ import annotations

from typing import Literal
import modal

from app.models.base import (
    BaseModelAdapter,
    ChangeMask,
    GroundingBox,
    ModelResult,
    ModelUnavailableError,
    RawRasterBoundaryError,
    assert_preview_input,
)

_MAX_PREVIEW_BYTES = 10 * 1024 * 1024   # 10 MB

def _validate_preview(preview_png: bytes, band_map: str) -> None:
    assert_preview_input(preview_png)
    if not isinstance(preview_png, bytes):
        raise RawRasterBoundaryError("preview_png must be bytes (a PNG file).")
    if len(preview_png) > _MAX_PREVIEW_BYTES:
        raise ValueError("Preview PNG exceeds 10 MB adapter limit.")
    if not band_map:
        raise ValueError("band_map must be provided and non-empty.")


class GeoChatAdapter(BaseModelAdapter):
    def __init__(self, mode: Literal["local", "modal"] = "local") -> None:
        self._mode = mode
        self._model = None
        if self._mode == "modal":
            try:
                self.infer_cls = modal.Cls.lookup("satquery-m1-infer", "GeoChatInfer")
            except Exception as e:
                print(f"Warning: Could not lookup satquery-m1-infer: {e}")

    @property
    def model_mode(self) -> Literal["local", "modal"]:
        return self._mode

    def caption(self, preview_png: bytes, *, band_map: str) -> ModelResult:
        _validate_preview(preview_png, band_map)
        if self._mode == "modal":
            res = self.infer_cls().caption.remote(preview_png, band_map=band_map)
            return ModelResult(
                text=res.get("text", ""),
                confidence=res.get("confidence", 0.0),
                confidence_source="model-provided",
                model_mode="modal"
            )
        raise ModelUnavailableError("local mode not implemented")

    def answer(self, preview_png: bytes, query: str, *, band_map: str) -> ModelResult:
        _validate_preview(preview_png, band_map)
        if self._mode == "modal":
            res = self.infer_cls().answer.remote(preview_png, query, band_map=band_map)
            return ModelResult(
                text=res.get("text", ""),
                confidence=res.get("confidence", 0.0),
                confidence_source="model-provided",
                model_mode="modal"
            )
        raise ModelUnavailableError("local mode not implemented")

    def ground(self, preview_png: bytes, query: str, *, band_map: str) -> list[GroundingBox]:
        _validate_preview(preview_png, band_map)
        if self._mode == "modal":
            res = self.infer_cls().ground.remote(preview_png, query, band_map=band_map)
            boxes = []
            for box in res.get("boxes", []):
                boxes.append(GroundingBox(
                    label=box["label"],
                    confidence=box["confidence"],
                    x_min=box["x_min"],
                    y_min=box["y_min"],
                    x_max=box["x_max"],
                    y_max=box["y_max"],
                ))
            return boxes
        raise ModelUnavailableError("local mode not implemented")

    def detect_change(
        self,
        preview_before: bytes,
        preview_after: bytes,
        *,
        band_map: str,
        affine_transform=None,
        crs=None,
    ) -> ChangeMask:
        raise NotImplementedError("Use ChangeFormerAdapter")
