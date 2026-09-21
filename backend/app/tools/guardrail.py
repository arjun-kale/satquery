"""Guardrail: reject analysis requests where the target is under-resolved."""

from __future__ import annotations


NYQUIST_FACTOR = 2.5  # target must be ≥ 2.5× GSD


class GuardrailTriggered(ValueError):
    """Raised when the target size is too small for the image GSD."""


def check_resolution(target_size_m: float, gsd_m: float) -> None:
    """Raise GuardrailTriggered when target_size_m < NYQUIST_FACTOR × gsd_m.

    Examples
    --------
    >>> check_resolution(5.0, 0.65)   # Cartosat-2S vehicle — must NOT raise
    >>> check_resolution(1.0, 0.65)   # sub-pixel target — MUST raise
    """
    threshold = NYQUIST_FACTOR * gsd_m
    if target_size_m < threshold:
        raise GuardrailTriggered(
            f"Target ({target_size_m} m) is below the resolution threshold "
            f"({NYQUIST_FACTOR}× GSD = {threshold:.2f} m). "
            "Analysis rejected to prevent spurious results."
        )
