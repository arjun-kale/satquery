"""Sample scene sets for the empty state: real, openly licensed scenes fetched by
``scripts/fetch_samples.py`` into ``<data_dir>/samples``. Only samples whose files exist are listed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.api.ingest import load_metadata, store_upload
from app.schemas import RasterMetadata

router = APIRouter(prefix="/api/samples", tags=["samples"])


class SampleFile(BaseModel):
    role: Literal["image", "T1", "T2", "optical", "sar"]
    path: str


class Sample(BaseModel):
    id: str
    title: str
    kind: Literal["single", "bitemporal", "optical_sar"]
    description: str
    suggested_question: str
    source: str
    license: str
    files: list[SampleFile]


class LoadedScene(BaseModel):
    role: str
    image_id: str
    metadata: RasterMetadata


class LoadedSample(BaseModel):
    sample: Sample
    scenes: list[LoadedScene]


def _samples_dir(request: Request) -> Path:
    return request.app.state.settings.data_dir / "samples"


def _available(request: Request) -> list[Sample]:
    manifest = _samples_dir(request) / "manifest.json"
    if not manifest.exists():
        return []
    samples = [Sample.model_validate(s) for s in json.loads(manifest.read_text())["samples"]]
    base = _samples_dir(request)
    return [s for s in samples if all((base / f.path).exists() for f in s.files)]


@router.get("", response_model=list[Sample])
def list_samples(request: Request) -> list[Sample]:
    return _available(request)


@router.post("/{sample_id}/load", response_model=LoadedSample)
def load_sample(sample_id: str, request: Request) -> LoadedSample:
    sample = next((s for s in _available(request) if s.id == sample_id), None)
    if sample is None:
        raise HTTPException(404, detail=f"Sample {sample_id!r} is not available.")

    artifact_repo = request.app.state.artifact_repository
    base = _samples_dir(request)
    # Ingest each sample file once; later loads reuse the stored image ids.
    loaded_path = base / "loaded.json"
    loaded: dict[str, str] = json.loads(loaded_path.read_text()) if loaded_path.exists() else {}

    scenes = []
    for f in sample.files:
        image_id = loaded.get(f.path)
        metadata = None
        if image_id:
            try:
                metadata = load_metadata(artifact_repo, image_id)
            except FileNotFoundError:
                metadata = None
        if metadata is None:
            metadata = store_upload(artifact_repo, (base / f.path).read_bytes(), Path(f.path).name)
            loaded[f.path] = metadata.image_id
        scenes.append(LoadedScene(role=f.role, image_id=metadata.image_id, metadata=metadata))

    loaded_path.write_text(json.dumps(loaded, indent=2))
    return LoadedSample(sample=sample, scenes=scenes)
