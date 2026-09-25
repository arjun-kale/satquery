"""GeoChatAdapter — remote-sensing VLM integration (local / Modal mode).

GeoChat accepts ONLY 3-channel rendered preview PNG files.
Raw raster arrays, raw band data, and multi-band TIFFs must never reach this adapter.
The band mapping used to produce the preview is recorded in every call.

Modal mode calls the ``GeoChatInfer`` class deployed from ``modal_worker/infer.py``;
hf mode calls the Hugging Face Inference Endpoint serving ``hf_endpoint/handler.py`` (the same
model, loading and prompts). Confidence values come from the model's own token probabilities,
hence ``confidence_source="model-provided"``.
"""

from __future__ import annotations

import base64
import time
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
    def __init__(self, mode: Literal["local", "modal", "hf"] = "local") -> None:
        self._mode = mode
        self._cls = None
        self.last_weights: str | None = None
        # Seconds spent waiting for a scaled-to-zero endpoint to wake (0 when it was warm).
        self.last_wake_s: float = 0.0
        if self._mode == "modal":
            import modal

            # Lazy reference: resolved on the first remote call, so constructing the adapter
            # never needs network access or a deployed app.
            self._cls = modal.Cls.from_name(MODAL_APP, MODAL_CLASS)

    @property
    def model_mode(self) -> Literal["local", "modal", "hf"]:
        return self._mode

    def _remote(self, method: str, *args, **kwargs) -> dict:
        if self._mode == "hf":
            return self._remote_hf(method, *args, **kwargs)
        if self._mode != "modal":
            raise ModelUnavailableError(
                "GeoChat local mode is not available (no local GPU runtime); set MODEL_MODE=modal."
            )
        try:
            return getattr(self._cls(), method).remote(*args, **kwargs)
        except Exception as e:  # not deployed, no credentials, container failure, ...
            raise ModelUnavailableError(f"GeoChat Modal worker unavailable ({MODAL_APP}.{MODAL_CLASS}.{method}): {e}") from e

    def _remote_hf(self, method: str, preview_png: bytes, query: str = "", *, band_map: str) -> dict:
        import httpx

        from app.config import Settings

        settings = Settings()
        if not settings.hf_endpoint_url:
            raise ModelUnavailableError("SatQuery VLM endpoint is not configured (SATQUERY_HF_ENDPOINT_URL).")
        payload = {"inputs": {"method": method, "image": base64.b64encode(preview_png).decode(), "query": query, "band_map": band_map}}
        headers = {"Authorization": f"Bearer {settings.hf_token}"} if settings.hf_token else {}
        started = time.monotonic()
        self.last_wake_s = 0.0
        while True:
            try:
                r = httpx.post(settings.hf_endpoint_url, json=payload, headers=headers, timeout=300)
            except httpx.HTTPError as e:
                raise ModelUnavailableError(f"SatQuery VLM endpoint unreachable: {e}") from e
            waited = time.monotonic() - started
            if r.status_code in (502, 503) and waited < settings.hf_wait_s:
                # Scaled to zero or still initialising: the endpoint is waking up. Wait, retry.
                self.last_wake_s = waited
                time.sleep(10)
                continue
            if r.status_code != 200:
                raise ModelUnavailableError(f"SatQuery VLM endpoint returned {r.status_code}: {r.text[:200]}")
            data = r.json()
            data = data[0] if isinstance(data, list) else data
            if "error" in data:
                raise ModelUnavailableError(f"SatQuery VLM endpoint error: {data['error']}")
            if self.last_wake_s:
                self.last_wake_s = time.monotonic() - started
            return data

    def caption(self, preview_png: bytes, *, band_map: str) -> ModelResult:
        _validate_preview(preview_png, band_map)
        res = self._remote("caption", preview_png, band_map=band_map)
        return ModelResult(
            text=res.get("text", ""),
            confidence=float(res.get("confidence", 0.0)),
            confidence_source="model-provided",
            model_mode=self._mode,
            weights=res.get("weights"),
        )

    def answer(self, preview_png: bytes, query: str, *, band_map: str) -> ModelResult:
        _validate_preview(preview_png, band_map)
        res = self._remote("answer", preview_png, query, band_map=band_map)
        return ModelResult(
            text=res.get("text", ""),
            confidence=float(res.get("confidence", 0.0)),
            confidence_source="model-provided",
            model_mode=self._mode,
            weights=res.get("weights"),
        )

    def ground(self, preview_png: bytes, query: str, *, band_map: str) -> list[GroundingBox]:
        _validate_preview(preview_png, band_map)
        res = self._remote("ground", preview_png, query, band_map=band_map)
        self.last_weights = res.get("weights")
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
