"""GeoChatAdapter — remote-sensing VLM integration (local / Modal mode).

GeoChat accepts ONLY 3-channel rendered preview PNG files.
Raw raster arrays, raw band data, and multi-band TIFFs must never reach this adapter.
The band mapping used to produce the preview is recorded in every call.

Modal mode calls the ``GeoChatInfer`` class deployed from ``modal_worker/infer.py``
(GeoChat-7B + the M2 BigEarthNet.txt LoRA). Confidence values come from the model's own
token probabilities (see infer.py), hence ``confidence_source="model-provided"``.
"""

from __future__ import annotations

from typing import Literal

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
MODAL_APP = "satquery-m1-infer"
MODAL_CLASS = "GeoChatInfer"


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
        self._cls = None
        if self._mode == "modal":
            import modal

            # Lazy reference: resolved on the first remote call, so constructing the adapter
            # never needs network access or a deployed app.
            self._cls = modal.Cls.from_name(MODAL_APP, MODAL_CLASS)

    @property
    def model_mode(self) -> Literal["local", "modal"]:
        return self._mode

    def _remote(self, method: str, *args, **kwargs) -> dict:
        if self._mode != "modal":
            raise ModelUnavailableError(
                "GeoChat local mode is not available (no local GPU runtime); set MODEL_MODE=modal."
            )
        try:
            return getattr(self._cls(), method).remote(*args, **kwargs)
        except Exception as e:  # not deployed, no credentials, container failure, ...
            raise ModelUnavailableError(f"GeoChat Modal worker unavailable ({MODAL_APP}.{MODAL_CLASS}.{method}): {e}") from e

    def caption(self, preview_png: bytes, *, band_map: str) -> ModelResult:
        _validate_preview(preview_png, band_map)
        res = self._remote("caption", preview_png, band_map=band_map)
        return ModelResult(
            text=res.get("text", ""),
            confidence=float(res.get("confidence", 0.0)),
            confidence_source="model-provided",
            model_mode="modal",
        )

    def answer(self, preview_png: bytes, query: str, *, band_map: str) -> ModelResult:
        _validate_preview(preview_png, band_map)
        res = self._remote("answer", preview_png, query, band_map=band_map)
        return ModelResult(
            text=res.get("text", ""),
            confidence=float(res.get("confidence", 0.0)),
            confidence_source="model-provided",
            model_mode="modal",
        )

    def ground(self, preview_png: bytes, query: str, *, band_map: str) -> list[GroundingBox]:
        _validate_preview(preview_png, band_map)
        res = self._remote("ground", preview_png, query, band_map=band_map)
        return [
            GroundingBox(
                label=box["label"],
                confidence=float(box["confidence"]),
                x_min=box["x_min"],
                y_min=box["y_min"],
                x_max=box["x_max"],
                y_max=box["y_max"],
            )
            for box in res.get("boxes", [])
        ]

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
