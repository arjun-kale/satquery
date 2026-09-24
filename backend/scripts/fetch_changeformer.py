"""Fetch the public ChangeFormer V6 (DSIFN-CD) checkpoint for local CPU inference.

    cd backend && .venv/bin/python scripts/fetch_changeformer.py

Source: https://github.com/wgcban/ChangeFormer (MIT licence), release v0.1.0.
The ~1 GB release zip also holds optimiser state; only the generator weights are kept
(<data_dir>/models/changeformer/changeformer_v6_dsifn.pt) with a manifest recording the
source URL and SHA-256 of what was saved.
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

import httpx
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import Settings  # noqa: E402

URL = (
    "https://github.com/wgcban/ChangeFormer/releases/download/v0.1.0/"
    "CD_ChangeFormerV6_DSIFN_b16_lr0.00006_adamw_train_test_200_linear_ce_multi_train_True_"
    "multi_infer_False_shuffle_AB_False_embed_dim_256.zip"
)


def main() -> None:
    out_dir = Settings().data_dir / "models" / "changeformer"
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / "release.zip"

    if not zip_path.exists():
        print(f"Downloading {URL}")
        with httpx.stream("GET", URL, follow_redirects=True, timeout=None) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            done = 0
            with open(zip_path.with_suffix(".part"), "wb") as f:
                for chunk in r.iter_bytes(1 << 20):
                    f.write(chunk)
                    done += len(chunk)
                    if total:
                        print(f"\r  {done / 1e6:.0f} / {total / 1e6:.0f} MB", end="", flush=True)
        zip_path.with_suffix(".part").rename(zip_path)
        print()

    with zipfile.ZipFile(zip_path) as z:
        name = next(n for n in z.namelist() if n.endswith("best_ckpt.pt"))
        ckpt = torch.load(io.BytesIO(z.read(name)), map_location="cpu", weights_only=False)

    state = ckpt["model_G_state_dict"]
    weights = out_dir / "changeformer_v6_dsifn.pt"
    torch.save(state, weights)
    sha = hashlib.sha256(weights.read_bytes()).hexdigest()
    (out_dir / "manifest.json").write_text(json.dumps({
        "model": "ChangeFormerV6 (embed_dim 256)",
        "trained_on": "DSIFN-CD (2 m Google Earth imagery, general land-cover change)",
        "source": URL,
        "license": "MIT (wgcban/ChangeFormer)",
        "checkpoint_entry": name,
        "best_val_acc": float(ckpt.get("best_val_acc", float("nan"))),
        "sha256": sha,
    }, indent=2))
    zip_path.unlink()
    print(f"saved {weights} ({weights.stat().st_size / 1e6:.0f} MB, sha256 {sha[:12]})")


if __name__ == "__main__":
    main()
