"""GeoChatAdapter — remote-sensing VLM integration (local / Modal mode).

GeoChat accepts ONLY 3-channel rendered preview PNG files.
Raw raster arrays, raw band data, and multi-band TIFFs must never reach this adapter.
The band mapping used to produce the preview is recorded in every call.

Licence status: UNVERIFIED — see docs/STATUS.md before any public-facing use.
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
_REQUIRED_CHANNELS = 3


def _validate_preview(preview_png: bytes, band_map: str) -> None:
    """Enforce the preview-only boundary before any model call."""
    assert_preview_input(preview_png)   # rejects numpy arrays
    if not isinstance(preview_png, bytes):
        raise RawRasterBoundaryError("preview_png must be bytes (a PNG file).")
    if len(preview_png) > _MAX_PREVIEW_BYTES:
        raise ValueError("Preview PNG exceeds 10 MB adapter limit.")
    if not band_map:
        raise ValueError("band_map must be provided and non-empty.")


class GeoChatAdapter(BaseModelAdapter):
    """Wrapper around GeoChat for captioning, VQA and grounding.

    In 'local' mode the model weights must be present at the path configured
    by SATQUERY_GEOCHAT_MODEL_PATH.  In 'modal' mode the call is dispatched
    to a Modal function.  Neither path is active until Phase 5; until then
    this adapter raises ModelUnavailableError to produce a clear
    ``model_unavailable`` result instead of an unhandled 500.
    """

    def __init__(self, mode: Literal["local", "modal"] = "local") -> None:
        self._mode = mode
        self._model = None  # loaded lazily in Phase 5

    @property
    def model_mode(self) -> Literal["local", "modal"]:
        return self._mode

    def _require_model(self) -> None:
        if self._model is None:
            raise ModelUnavailableError(
                f"GeoChat model is not loaded (mode='{self._mode}'). "
                "Set MODEL_MODE=mock for local development."
            )

    def caption(self, preview_png: bytes, *, band_map: str) -> ModelResult:
        _validate_preview(preview_png, band_map)
        self._require_model()
        raise NotImplementedError  # reached only when model is loaded (Phase 5)

    def answer(self, preview_png: bytes, query: str, *, band_map: str) -> ModelResult:
        _validate_preview(preview_png, band_map)
        self._require_model()
        raise NotImplementedError

    def ground(self, preview_png: bytes, query: str, *, band_map: str) -> list[GroundingBox]:
        _validate_preview(preview_png, band_map)
        self._require_model()
        raise NotImplementedError

    def detect_change(
        self,
        preview_before: bytes,
        preview_after: bytes,
        *,
        band_map: str,
        affine_transform=None,
        crs=None,
    ) -> ChangeMask:
        """GeoChat does not perform change detection — use ChangeFormerAdapter."""
        raise NotImplementedError(
            "detect_change is not supported by GeoChatAdapter. "
            "Use ChangeFormerAdapter for bi-temporal change analysis."
        )
