"""Model adapter interface — all adapters implement this contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray


class ModelUnavailableError(RuntimeError):
    """Raised when a model is not loaded and mock mode is not active."""


class RawRasterBoundaryError(ValueError):
    """Raised when a caller tries to pass raw raster arrays to a VLM adapter.

    VLM adapters accept preview PNG bytes only — never raw band arrays.
    """


@dataclass
class GroundingBox:
    label: str
    confidence: float
    x_min: float
    y_min: float
    x_max: float
    y_max: float


@dataclass
class ChangeMask:
    """Binary change mask + deterministic area calculation."""
    mask: NDArray           # bool array, shape (H, W)
    changed_area_m2: float | None  # None when georeferencing unavailable
    confidence: float
    confidence_source: Literal["model-provided", "rule-derived", "unavailable"]


@dataclass
class ModelResult:
    text: str
    confidence: float
    confidence_source: Literal["model-provided", "rule-derived", "unavailable"]
    model_mode: Literal["mock", "local", "modal", "hf"]
    # Which weights produced this output, as reported by the inference worker.
    weights: str | None = None


class BaseModelAdapter(ABC):
    """All model adapters implement this contract.

    IMPORTANT: ``caption``, ``answer``, and ``ground`` accept **preview PNG
    bytes only**.  Raw raster arrays, raw band data, or file paths must never
    cross this boundary.  Enforce with :func:`assert_preview_input`.
    """

    @property
    @abstractmethod
    def model_mode(self) -> Literal["mock", "local", "modal", "hf"]:
        ...

    @abstractmethod
    def caption(self, preview_png: bytes, *, band_map: str) -> ModelResult:
        """Generate a natural-language scene description."""
        ...

    @abstractmethod
    def answer(self, preview_png: bytes, query: str, *, band_map: str) -> ModelResult:
        """Answer a natural-language question about the scene."""
        ...

    @abstractmethod
    def ground(self, preview_png: bytes, query: str, *, band_map: str) -> list[GroundingBox]:
        """Return bounding boxes for objects matching *query*."""
        ...

    @abstractmethod
    def detect_change(
        self,
        preview_before: bytes,
        preview_after: bytes,
        *,
        band_map: str,
        affine_transform=None,
        crs=None,
    ) -> ChangeMask:
        """Return a binary change mask for a co-registered preview pair."""
        ...


def assert_preview_input(value: object) -> None:
    """Raise RawRasterBoundaryError if *value* is a numpy array.

    Call at the top of every VLM method to enforce the preview-only boundary.
    """
    if isinstance(value, np.ndarray):
        raise RawRasterBoundaryError(
            "Raw raster arrays cannot cross the model adapter boundary. "
            "Pass a rendered preview PNG (bytes) instead."
        )
