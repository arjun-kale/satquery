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


def test_changeformer_raises_model_unavailable():
    adapter = ChangeFormerAdapter(mode="local")
    with pytest.raises(ModelUnavailableError, match="ChangeFormer"):
        adapter.detect_change(FAKE_PNG, FAKE_PNG, band_map=BAND_MAP)


def test_changeformer_modal_raises_model_unavailable():
    adapter = ChangeFormerAdapter(mode="modal")
    with pytest.raises(ModelUnavailableError):
        adapter.detect_change(FAKE_PNG, FAKE_PNG, band_map=BAND_MAP)
