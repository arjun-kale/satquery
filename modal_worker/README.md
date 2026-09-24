# SatQuery Modal Worker

Modal worker for GPU inference and M1 training. Never hosts stateful backend.

## Setup

```bash
pip install modal
modal setup          # authenticate once
modal secret create huggingface-secret HF_TOKEN=<your_hf_token>
```

## M1 Training Run (required gate before Phase 3)

**Estimated cost: ~$2–4 on A10G. $25 budget available.**

```bash
# Dry run — check image builds and imports
modal run modal_worker/train_m1.py --help

# Full training run
modal run modal_worker/train_m1.py

# Custom params (smaller test run first)
modal run modal_worker/train_m1.py --max-samples 500 --epochs 1
```

After it finishes:
1. Copy the printed JSON into `training/reproduce_m1_run.md`
2. Note the checkpoint path from Modal Volume
3. Phase 3 is now unblocked

## M2 — GeoChat-7B LoRA on BigEarthNet.txt (the PS adaptation run)

`train_m2.py` is a staged pipeline; every stage can be re-run safely and writes evidence to the volume.

```bash
# 0. Once: convert GeoChat to the llava-hf layout and check it against the original GeoChat code
modal run --detach modal_worker/train_m2.py --mode debug --until verify

# 1. Debug run (128 train / 40 eval rows, minutes). To test resume, stop it mid-training
#    (`modal app stop <app-id>`) and run the same command again: it continues from the last checkpoint.
modal run --detach modal_worker/train_m2.py --mode debug

# 2. Scaled run (size it from the debug run's measured throughput)
modal run --detach modal_worker/train_m2.py --mode scaled --n-train 3200

# 3. Copy evidence into docs/evidence/m2/, read actual cost from Modal billing, regenerate docs/STATUS.md
python modal_worker/m2_report.py --mode debug --mode scaled
```

Run artifacts live under `/checkpoints/m2_geochat/<mode>/` on the volume (`M2_CKPT_DIR`):
`data/` (split manifests + distribution), `checkpoint-*/`, `final/` (LoRA adapter), `loss_history.json`,
`events.jsonl` (start/resume/checkpoint/finish), `eval/` (per-example predictions + metrics), `results.json`.

Unit tests for the data, prompting and metric code (no GPU needed):

```bash
cd modal_worker && python -m pytest tests -q
```

`ben_txt_datamodule.py` and `example_data_loading.py` are vendored unchanged from the
`BIFOLD-BigEarthNetv2-0/BigEarthNet.txt` dataset repo (CDLA-Permissive-1.0).

## Inference

`infer.py` serves the converted GeoChat plus the scaled M2 adapter (falls back to base GeoChat, and says
so in every response, if no adapter exists). `modal deploy modal_worker/infer.py`

## Volume (checkpoints + model cache)

```bash
modal volume ls satquery-m1-vol
modal volume get satquery-m1-vol /checkpoints/m1_lora/m1_results.json ./
```

## Notes
- Modal containers are ephemeral — SQLite/filesystem state lives on the backend laptop only
- `MODEL_MODE=modal` is for inference only (Phase 5), not backend state
- Never commit Modal tokens or `HF_TOKEN` to git
