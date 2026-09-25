"""Publish the SatQuery VLM (converted GeoChat-7B + M2 LoRA + endpoint handler) to a private
Hugging Face model repo, straight from the Modal volume (no 14 GB round trip through a laptop).

    HF_TOKEN=... modal run modal_worker/publish_hf.py --repo-id <user>/satquery-vlm

CPU only. The token is read from the local environment for this run (Secret.from_local_environ)
and is not stored in Modal.
"""

from pathlib import Path

import modal

VOLUME = modal.Volume.from_name("satquery-m1-vol")
VOL = Path("/vol")
BASE_DIR = VOL / "models" / "geochat-7b-llava-hf"
ADAPTER_DIR = VOL / "checkpoints" / "m2_geochat" / "scaled" / "final"
HERE = Path(__file__).resolve().parent

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("huggingface_hub[hf_transfer]==0.36.2")
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
    .add_local_dir(HERE.parent / "hf_endpoint", "/root/hf_endpoint")
    .add_local_dir(HERE / "satq_m2", "/root/satq_m2", ignore=["__pycache__"])
)

app = modal.App("satquery-publish-hf")


@app.function(
    image=image,
    volumes={str(VOL): VOLUME},
    secrets=[modal.Secret.from_local_environ(["HF_TOKEN"])],
    timeout=3 * 60 * 60,
    cpu=2,
)
def publish(repo_id: str) -> str:
    import os

    from huggingface_hub import HfApi

    api = HfApi(token=os.environ["HF_TOKEN"])
    api.create_repo(repo_id, repo_type="model", private=True, exist_ok=True)

    print("uploading base model (converted GeoChat-7B, llava-hf layout)…")
    api.upload_folder(repo_id=repo_id, folder_path=str(BASE_DIR), commit_message="Base: converted GeoChat-7B (llava-hf layout)")

    print("uploading M2 adapter…")
    for name in ("adapter_model.safetensors", "adapter_config.json"):
        api.upload_file(repo_id=repo_id, path_or_fileobj=str(ADAPTER_DIR / name), path_in_repo=f"m2/{name}")
    api.upload_file(
        repo_id=repo_id,
        path_or_fileobj=str(ADAPTER_DIR.parent / "final_manifest.json"),
        path_in_repo="m2/final_manifest.json",
        commit_message="M2 LoRA adapter (scaled run) + manifest",
    )

    print("uploading endpoint handler…")
    api.upload_folder(repo_id=repo_id, folder_path="/root/hf_endpoint", commit_message="Inference Endpoint handler")
    api.upload_folder(repo_id=repo_id, folder_path="/root/satq_m2", path_in_repo="satq_m2", commit_message="Prompt / box helpers")
    return f"https://huggingface.co/{repo_id}"


@app.local_entrypoint()
def main(repo_id: str):
    print(publish.remote(repo_id))
