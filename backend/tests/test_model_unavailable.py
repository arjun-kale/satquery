"""Tests proving model-disabled adapters return ModelUnavailableError, not 500."""

from __future__ import annotations

import pytest

from app.models.base import ModelUnavailableError
from app.models.geochat import GeoChatAdapter
from app.models.changeformer import ChangeFormerAdapter


FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
BAND_MAP = "B4/B3/B2"


def test_geochat_caption_raises_model_unavailable():
    adapter = GeoChatAdapter(mode="local")
    with pytest.raises(ModelUnavailableError, match="GeoChat"):
        adapter.caption(FAKE_PNG, band_map=BAND_MAP)


def test_geochat_answer_raises_model_unavailable():
    adapter = GeoChatAdapter(mode="local")
    with pytest.raises(ModelUnavailableError):
        adapter.answer(FAKE_PNG, "Is there flooding?", band_map=BAND_MAP)


def test_geochat_ground_raises_model_unavailable():
    adapter = GeoChatAdapter(mode="local")
    with pytest.raises(ModelUnavailableError):
        adapter.ground(FAKE_PNG, "vehicle", band_map=BAND_MAP)


def test_changeformer_raises_model_unavailable(tmp_path):
    adapter = ChangeFormerAdapter(mode="local", weights_dir=tmp_path)
    with pytest.raises(ModelUnavailableError, match="ChangeFormer"):
        adapter.detect_change(FAKE_PNG, FAKE_PNG, band_map=BAND_MAP)


def test_changeformer_modal_raises_model_unavailable(tmp_path):
    adapter = ChangeFormerAdapter(mode="modal", weights_dir=tmp_path)
    with pytest.raises(ModelUnavailableError):
        adapter.detect_change(FAKE_PNG, FAKE_PNG, band_map=BAND_MAP)


def test_geochat_modal_worker_failure_raises_model_unavailable():
    """An undeployed/unreachable Modal worker must surface as ModelUnavailableError, not a crash."""
    adapter = GeoChatAdapter(mode="modal")

    class Unreachable:
        def __call__(self):
            raise RuntimeError("App 'satquery-m1-infer' not found")

    adapter._cls = Unreachable()
    with pytest.raises(ModelUnavailableError, match="GeoChat Modal worker unavailable"):
        adapter.ground(FAKE_PNG, "pastures", band_map=BAND_MAP)


def test_changeformer_runs_on_real_weights_when_present():
    """Real inference path (skipped on machines without scripts/fetch_changeformer.py weights)."""
    import io

    import numpy as np
    from PIL import Image

    from app.models.changeformer import WEIGHTS_FILE, default_weights_dir

    if not (default_weights_dir() / WEIGHTS_FILE).exists():
        pytest.skip("ChangeFormer weights not fetched")

    def png(color):
        buf = io.BytesIO()
        Image.new("RGB", (300, 200), color).save(buf, format="PNG")
        return buf.getvalue()

    result = ChangeFormerAdapter().detect_change(png((40, 90, 40)), png((40, 90, 40)), band_map=BAND_MAP)
    assert result.mask.shape == (200, 300)  # padded to 256-px tiles internally, cropped back
    assert result.mask.dtype == bool
    assert result.confidence_source == "model-provided"
    assert 0.0 <= result.confidence <= 1.0
