"""Upload the backend's local assets to private Hugging Face repos so a hosted backend
(Railway) can pull them on first start:

    <user>/satquery-changeformer   model repo    ChangeFormer V6 DSIFN weights + manifest + MIT LICENSE
    <user>/satquery-samples        dataset repo  sample scenes + manifest.json

    cd backend && HF_TOKEN=... .venv/bin/python scripts/publish_assets_hf.py --user <hf-user>
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from huggingface_hub import HfApi

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import Settings  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", required=True)
    args = parser.parse_args()

    api = HfApi(token=os.environ.get("HF_TOKEN"))
    data = Settings().data_dir
    backend = Path(__file__).resolve().parents[1]

    cf_repo = f"{args.user}/satquery-changeformer"
    api.create_repo(cf_repo, repo_type="model", private=True, exist_ok=True)
    cf = data / "models" / "changeformer"
    for name in ("changeformer_v6_dsifn.pt", "manifest.json"):
        api.upload_file(repo_id=cf_repo, path_or_fileobj=str(cf / name), path_in_repo=name)
    api.upload_file(
        repo_id=cf_repo,
        path_or_fileobj=str(backend / "app/models/vendor/changeformer/LICENSE"),
        path_in_repo="LICENSE",
        commit_message="ChangeFormer V6 (DSIFN-CD) weights — MIT, wgcban/ChangeFormer",
    )
    print(f"https://huggingface.co/{cf_repo}")

    s_repo = f"{args.user}/satquery-samples"
    api.create_repo(s_repo, repo_type="dataset", private=True, exist_ok=True)
    api.upload_folder(
        repo_id=s_repo,
        repo_type="dataset",
        folder_path=str(data / "samples"),
        allow_patterns=["*.tif", "manifest.json"],
        commit_message="Sample scenes (contains modified Copernicus Sentinel data 2024)",
    )
    print(f"https://huggingface.co/datasets/{s_repo}")


if __name__ == "__main__":
    main()
