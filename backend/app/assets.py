"""First-start asset bootstrap for hosted deployments (e.g. Railway).

Model weights and sample scenes are gitignored. When the corresponding private Hugging Face repos
are configured, anything missing under ``data_dir`` is downloaded once; later starts reuse the
persistent volume. Runs in a background thread so the API is healthy while it downloads.
"""

from __future__ import annotations

import logging
import threading

from app.config import Settings

log = logging.getLogger("satquery.assets")


def ensure_assets(settings: Settings) -> None:
    from huggingface_hub import snapshot_download

    from app.models.changeformer import WEIGHTS_FILE

    if settings.hf_changeformer_repo:
        dest = settings.data_dir / "models" / "changeformer"
        if not (dest / WEIGHTS_FILE).exists():
            log.info("downloading ChangeFormer weights from %s", settings.hf_changeformer_repo)
            snapshot_download(settings.hf_changeformer_repo, local_dir=dest, token=settings.hf_token,
                              allow_patterns=["*.pt", "manifest.json", "LICENSE"])
    if settings.hf_samples_repo:
        dest = settings.data_dir / "samples"
        if not (dest / "manifest.json").exists():
            log.info("downloading sample scenes from %s", settings.hf_samples_repo)
            snapshot_download(settings.hf_samples_repo, repo_type="dataset", local_dir=dest, token=settings.hf_token,
                              allow_patterns=["*.tif", "manifest.json"])


def ensure_assets_in_background(settings: Settings) -> None:
    def run() -> None:
        try:
            ensure_assets(settings)
        except Exception:  # noqa: BLE001 — a missing asset shows up as an honest "unavailable" later
            log.exception("asset bootstrap failed")

    threading.Thread(target=run, name="asset-bootstrap", daemon=True).start()
