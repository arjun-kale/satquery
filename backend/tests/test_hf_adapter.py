"""model_mode="hf": the adapter calls the Hugging Face Inference Endpoint and waits out cold starts."""

from __future__ import annotations

import httpx
import pytest

from app.models.base import ModelUnavailableError
from app.models.geochat import GeoChatAdapter

PNG = b"\x89PNG\r\n\x1a\nfake"


class FakeEndpoint:
    def __init__(self, cold_replies: int, body: dict | list):
        self.cold_replies = cold_replies
        self.body = body
        self.calls: list[dict] = []

    def __call__(self, url, json, headers, timeout):
        self.calls.append({"url": url, "json": json, "headers": headers})
        if self.cold_replies:
            self.cold_replies -= 1
            return httpx.Response(503, text="Service Unavailable: initializing")
        return httpx.Response(200, json=self.body)


@pytest.fixture
def hf_env(monkeypatch):
    monkeypatch.setenv("SATQUERY_HF_ENDPOINT_URL", "https://endpoint.example/satquery-vlm")
    monkeypatch.setenv("HF_TOKEN", "hf_test_token")
    monkeypatch.setattr("time.sleep", lambda s: None)


def test_hf_answer_waits_out_cold_start(hf_env, monkeypatch):
    fake = FakeEndpoint(2, [{"text": "A reservoir.", "confidence": 0.71, "weights": "geochat-7b + m2-lora (sha256 abc)"}])
    monkeypatch.setattr(httpx, "post", fake)

    adapter = GeoChatAdapter(mode="hf")
    result = adapter.answer(PNG, "what is this?", band_map="B04/B03/B02")

    assert result.text == "A reservoir."
    assert result.model_mode == "hf"
    assert result.weights.startswith("geochat-7b + m2-lora")
    assert len(fake.calls) == 3  # two 503s while waking, then the answer
    assert adapter.last_wake_s >= 0
    sent = fake.calls[-1]
    assert sent["headers"]["Authorization"] == "Bearer hf_test_token"
    assert sent["json"]["inputs"]["method"] == "answer"
    assert sent["json"]["inputs"]["query"] == "what is this?"


def test_hf_gives_up_after_wait_budget(hf_env, monkeypatch):
    monkeypatch.setenv("SATQUERY_HF_WAIT_S", "0")
    monkeypatch.setattr(httpx, "post", FakeEndpoint(99, {}))
    with pytest.raises(ModelUnavailableError, match="503"):
        GeoChatAdapter(mode="hf").caption(PNG, band_map="B04/B03/B02")


def test_hf_without_endpoint_url_is_unavailable(monkeypatch):
    monkeypatch.delenv("SATQUERY_HF_ENDPOINT_URL", raising=False)
    with pytest.raises(ModelUnavailableError, match="not configured"):
        GeoChatAdapter(mode="hf").caption(PNG, band_map="B04/B03/B02")
