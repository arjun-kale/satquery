"""HTTP tests for the workspace endpoints: image metadata/preview and scene-set validation."""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import rasterio
from fastapi.testclient import TestClient
from rasterio.transform import from_origin

from app.config import Settings
from app.main import create_app


def _tif(epsg: int = 32643, x0: float = 700000, tags: dict | None = None, date: str | None = None) -> bytes:
    buf = io.BytesIO()
    with rasterio.open(
        buf, "w", driver="GTiff", width=32, height=32, count=3, dtype="uint8",
        crs=f"EPSG:{epsg}", transform=from_origin(x0, 1400000, 10, 10),
    ) as ds:
        ds.write(np.random.default_rng(1).integers(0, 255, (3, 32, 32), dtype="uint8"))
        ds.update_tags(**(tags or {}), **({"acquired_at": date} if date else {}))
    return buf.getvalue()


def _client(tmp_path: Path) -> TestClient:
    settings = Settings(data_dir=tmp_path, database_path=tmp_path / "db.sqlite", model_mode="mock")
    return TestClient(create_app(settings))


def _upload(client: TestClient, data: bytes, name: str = "scene.tif") -> str:
    r = client.post("/api/ingest", files={"file": (name, data, "image/tiff")})
    assert r.status_code == 200, r.text
    return r.json()["image_id"]


def test_metadata_and_preview_round_trip(tmp_path):
    with _client(tmp_path) as client:
        image_id = _upload(client, _tif(tags={"modality": "optical"}, date="2024-05-05"))
        meta = client.get(f"/api/images/{image_id}").json()
        assert meta["modality"] == "optical"
        assert meta["acquired_at"] == "2024-05-05"
        assert len(meta["corners_wgs84"]) == 4
        preview = client.get(f"/api/images/{image_id}/preview.png")
        assert preview.status_code == 200
        assert preview.headers["content-type"] == "image/png"


def test_bitemporal_pair_passes_every_check(tmp_path):
    with _client(tmp_path) as client:
        a = _upload(client, _tif(date="2024-05-05"))
        b = _upload(client, _tif(date="2024-12-16"))
        r = client.post("/api/scene-sets/validate", json={"kind": "bitemporal", "image_ids": [a, b]}).json()
        assert r["passed"] is True
        checks = {c["id"]: c for c in r["checks"]}
        assert checks["same_crs"]["value"] == "EPSG:32643"
        assert checks["overlap"]["value"] == "100% overlap"
        assert checks["dates"]["value"] == "2024-05-05 → 2024-12-16"


def test_pair_with_different_crs_fails_with_reason(tmp_path):
    with _client(tmp_path) as client:
        a = _upload(client, _tif(epsg=32643))
        b = _upload(client, _tif(epsg=32644))
        r = client.post("/api/scene-sets/validate", json={"kind": "bitemporal", "image_ids": [a, b]}).json()
        assert r["passed"] is False
        failing = [c for c in r["checks"] if c["status"] == "fail"]
        assert failing[0]["id"] == "same_crs"
        assert "EPSG:32643 vs EPSG:32644" == failing[0]["value"]


def test_disjoint_pair_fails_overlap(tmp_path):
    with _client(tmp_path) as client:
        a = _upload(client, _tif(x0=700000))
        b = _upload(client, _tif(x0=900000))
        r = client.post("/api/scene-sets/validate", json={"kind": "bitemporal", "image_ids": [a, b]}).json()
        assert {c["id"]: c["status"] for c in r["checks"]}["overlap"] == "fail"


def test_cancel_unknown_job_is_404(tmp_path):
    with _client(tmp_path) as client:
        assert client.post("/api/jobs/nope/cancel").status_code == 404


def test_native_window_is_unresampled_and_transparent_outside(tmp_path):
    from PIL import Image as PILImage

    with _client(tmp_path) as client:
        image_id = _upload(client, _tif())
        inside = client.get(f"/api/images/{image_id}/window.png", params={"col0": 0, "row0": 0, "size": 16})
        assert inside.status_code == 200
        img = PILImage.open(io.BytesIO(inside.content))
        assert img.size == (16, 16)  # native pixels: no resampling to the preview size
        assert img.getpixel((0, 0))[3] == 255
        edge = client.get(f"/api/images/{image_id}/window.png", params={"col0": 24, "row0": 24, "size": 16})
        img = PILImage.open(io.BytesIO(edge.content))
        assert img.getpixel((15, 15))[3] == 0  # pixel (39, 39) is outside the 32×32 scene
        assert img.getpixel((0, 0))[3] == 255
