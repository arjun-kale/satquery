"""The /api/chat endpoint speaks the AI SDK UI Message Stream protocol with real run events."""

from __future__ import annotations

import json

from tests.test_api_workspace import _client, _tif, _upload


def _parts(text: str) -> list:
    out = []
    for line in text.splitlines():
        if line.startswith("data: "):
            payload = line[len("data: "):]
            out.append(payload if payload == "[DONE]" else json.loads(payload))
    return out


def _ask(client, image_ids, question, kind="single"):
    body = {
        "id": "chat-1",
        "trigger": "submit-message",
        "messages": [{"id": "m1", "role": "user", "parts": [{"type": "text", "text": question}]}],
        "image_ids": image_ids,
        "scene_set_kind": kind,
        "local_id": "local-1",
    }
    with client.stream("POST", "/api/chat", json=body) as r:
        assert r.headers["x-vercel-ai-ui-message-stream"] == "v1"
        assert r.headers["content-type"].startswith("text/event-stream")
        return _parts(r.read().decode())


def test_chat_streams_protocol_parts_in_order(tmp_path):
    with _client(tmp_path) as client:
        image_id = _upload(client, _tif(tags={"modality": "optical"}))
        parts = _ask(client, [image_id], "describe this satellite image")

    types = [p if isinstance(p, str) else p["type"] for p in parts]
    assert types[0] == "start" and parts[0]["messageMetadata"]["localId"] == "local-1"
    assert types[1] == "data-job"
    assert types[-2:] == ["finish", "[DONE]"]
    assert "reasoning-start" not in types  # the pipeline produces no reasoning text

    started = [p["toolName"] for p in parts if isinstance(p, dict) and p["type"] == "tool-input-available"]
    assert started == ["preview", "geochat_caption"]
    assert types.count("tool-output-available") == 2

    traces = [p for p in parts if isinstance(p, dict) and p["type"] == "data-trace"]
    assert all(t["id"] == parts[1]["data"]["jobId"] for t in traces)  # reconciled in place by id
    assert traces[-1]["data"]["status"] == "COMPLETED"

    delta = next(p for p in parts if isinstance(p, dict) and p["type"] == "text-delta")
    assert delta["delta"].startswith("[MOCK]")
    assert parts[-2]["finishReason"] == "stop"


def test_chat_reports_rejection_without_tools(tmp_path):
    with _client(tmp_path) as client:
        image_id = _upload(client, _tif())
        parts = _ask(client, [image_id], "order a pizza for me please")

    types = [p if isinstance(p, str) else p["type"] for p in parts]
    assert "tool-input-available" not in types
    last_trace = [p for p in parts if isinstance(p, dict) and p["type"] == "data-trace"][-1]
    assert last_trace["data"]["status"] == "REJECTED"
    assert parts[-2]["finishReason"] == "error"
