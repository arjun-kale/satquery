"""File-system artifact repository — uploads and results live under generated IDs."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4


class ArtifactRepository:
    def __init__(self, base_dir: Path) -> None:
        self.uploads_dir = base_dir / "uploads"
        self.artifacts_dir = base_dir / "artifacts"

    def initialize(self) -> None:
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    def new_image_id(self) -> str:
        return str(uuid4())

    def upload_path(self, image_id: str, suffix: str = ".tif") -> Path:
        return self.uploads_dir / f"{image_id}{suffix}"

    def find_upload(self, image_id: str) -> Path:
        """The stored raster for *image_id*, whatever suffix it was uploaded with."""
        for path in self.uploads_dir.glob(f"{image_id}.*"):
            if path.suffix != ".json":
                return path
        raise FileNotFoundError(f"Uploaded file not found for image {image_id!r}")

    def metadata_path(self, image_id: str) -> Path:
        return self.uploads_dir / f"{image_id}.json"

    def preview_path(self, image_id: str) -> Path:
        previews = self.uploads_dir.parent / "previews"
        previews.mkdir(parents=True, exist_ok=True)
        return previews / f"{image_id}.png"

    def artifact_path(self, job_id: str, name: str) -> Path:
        job_dir = self.artifacts_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        return job_dir / name

    def artifact_exists(self, job_id: str, name: str) -> bool:
        return self.artifact_path(job_id, name).exists()

    def list_artifacts(self, job_id: str) -> list[str]:
        job_dir = self.artifacts_dir / job_id
        if not job_dir.exists():
            return []
        return [p.name for p in job_dir.iterdir() if p.is_file()]
