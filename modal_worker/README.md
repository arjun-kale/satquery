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

## Volume (checkpoints + model cache)

```bash
modal volume ls satquery-m1-vol
modal volume get satquery-m1-vol /checkpoints/m1_lora/m1_results.json ./
```

## Notes
- Modal containers are ephemeral — SQLite/filesystem state lives on the backend laptop only
- `MODEL_MODE=modal` is for inference only (Phase 5), not backend state
- Never commit Modal tokens or `HF_TOKEN` to git
