"""ChangeFormerAdapter — Siamese change detection model (local / Modal mode).

Accepts a co-registered RGB preview pair. Output is a binary mask artifact
converted to a deterministic area when georeferencing is available.

Licence status: Apache-2.0 (ChangeFormer repo) — verify weights separately.
See docs/STATUS.md.
"""

from __future__ import annotations

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


class ChangeFormerAdapter(BaseModelAdapter):
    """Wrapper around ChangeFormer for bi-temporal change detection.

    Like GeoChatAdapter, this raises ModelUnavailableError until weights are
    loaded in Phase 5.  The mask output is always saved as a binary artifact
    and the changed area is derived deterministically from the mask + geotransform.
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
                f"ChangeFormer model is not loaded (mode='{self._mode}'). "
                "Set MODEL_MODE=mock for local development."
            )

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
        """Run ChangeFormer on a co-registered preview pair.

        Parameters
        ----------
        preview_before / preview_after:
            Rendered RGB PNG bytes — never raw raster arrays.
        band_map:
            Band mapping label recorded in the trace (e.g. 'B4/B3/B2').
        affine_transform / crs:
            Optional georeferencing; when provided, area is calculated
            deterministically from the mask pixel count.
        """
        assert_preview_input(preview_before)
        assert_preview_input(preview_after)
        self._require_model()
        raise NotImplementedError  # reached only when model is loaded (Phase 5)

    @staticmethod
    def mask_to_area(
        mask: np.ndarray, affine_transform, crs
    ) -> float:
        """Convert a binary mask to m² — deterministic, independent of model."""
        return change_area_m2(mask, affine_transform, crs)
