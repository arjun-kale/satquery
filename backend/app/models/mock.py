"""MockModelAdapter — deterministic fixture outputs; no GPU or internet required."""

from __future__ import annotations

from typing import Literal

import numpy as np

from app.models.base import (
    BaseModelAdapter,
    ChangeMask,
    GroundingBox,
    ModelResult,
    assert_preview_input,
)
from app.tools.geodesy import change_area_m2


class MockModelAdapter(BaseModelAdapter):
    """Returns hard-coded, deterministic outputs for local tests and offline demos.

    Every result is clearly labelled ``model_mode='mock'`` so the UI can
    display a visible disclaimer.
    """

    @property
    def model_mode(self) -> Literal["mock"]:
        return "mock"

    def caption(self, preview_png: bytes, *, band_map: str) -> ModelResult:
        assert_preview_input(preview_png)
        return ModelResult(
            text=(
                f"[MOCK] Scene captured using band mapping {band_map}. "
                "Vegetation cover detected in the central region."
            ),
            confidence=0.0,
            confidence_source="unavailable",
            model_mode="mock",
        )

    def answer(self, preview_png: bytes, query: str, *, band_map: str) -> ModelResult:
        assert_preview_input(preview_png)
        return ModelResult(
            text=f"[MOCK] Answer to '{query}': placeholder response (band map: {band_map}).",
            confidence=0.0,
            confidence_source="unavailable",
            model_mode="mock",
        )

    def ground(self, preview_png: bytes, query: str, *, band_map: str) -> list[GroundingBox]:
        assert_preview_input(preview_png)
        return [
            GroundingBox(
                label=f"[MOCK] {query}",
                confidence=0.0,
                x_min=0.1,
                y_min=0.1,
                x_max=0.4,
                y_max=0.4,
            )
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
        assert_preview_input(preview_before)
        assert_preview_input(preview_after)

        # Deterministic 10% changed mask
        mask = np.zeros((64, 64), dtype=bool)
        mask[28:36, 28:36] = True  # fixed 8×8 changed region

        area: float | None = None
        if affine_transform is not None and crs is not None:
            area = change_area_m2(mask, affine_transform, crs)

        return ChangeMask(
            mask=mask,
            changed_area_m2=area,
            confidence=0.0,
            confidence_source="unavailable",
        )
