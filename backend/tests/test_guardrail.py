"""Unit tests for the resolution guardrail."""

import pytest

from app.tools.guardrail import check_resolution, GuardrailTriggered, NYQUIST_FACTOR


def test_triggers_when_target_below_threshold():
    """1 m target at 0.65 m GSD: 1 < 2.5 × 0.65 = 1.625 → must raise."""
    with pytest.raises(GuardrailTriggered):
        check_resolution(target_size_m=1.0, gsd_m=0.65)


def test_cartosat2s_vehicle_does_not_trigger():
    """5 m vehicle at 0.65 m GSD: 5 > 1.625 → must NOT raise."""
    check_resolution(target_size_m=5.0, gsd_m=0.65)  # no exception


def test_exactly_at_threshold_passes():
    """target == 2.5 × gsd is at the boundary — should not raise."""
    gsd = 1.0
    check_resolution(target_size_m=NYQUIST_FACTOR * gsd, gsd_m=gsd)


def test_just_below_threshold_triggers():
    gsd = 1.0
    with pytest.raises(GuardrailTriggered):
        check_resolution(target_size_m=NYQUIST_FACTOR * gsd - 0.01, gsd_m=gsd)


def test_error_message_contains_threshold():
    with pytest.raises(GuardrailTriggered, match="threshold"):
        check_resolution(1.0, 1.0)
