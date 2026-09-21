# M1 Adaptation Run — Reproducibility Record

> **Status: NOT YET EXECUTED — required gate before Phase 3.**
> Complete this record after running `training/finetune_geochat_lora.py` on GPU.

---

## Dataset

| Field | Value |
|---|---|
| Dataset | BigEarthNet-MM (multi-modal, Sentinel-1 + Sentinel-2) |
| Source | https://bigearth.net — CC-BY 4.0 |
| Revision / version | TBD — record exact download date and version tag |
| Total samples | TBD |
| Training subset size | 3,000 (target; 2,000–5,000 per plan) |
| Validation subset size | 300 (held-out, no overlap with training) |
| Split seed | 42 |
| Sample IDs file | `training/data/m1_train_ids.txt` (not committed — too large) |
| Prompt format | TBD — record exact instruction template used |

---

## Training command

```bash
python training/finetune_geochat_lora.py \
    --data_dir data/bigearthnet_subset \
    --output_dir training/checkpoints/m1_lora \
    --seed 42 \
    --max_samples 3000 \
    --val_samples 300 \
    --lora_r 16 \
    --lora_alpha 32 \
    --epochs 3 \
    --freeze_vision_encoder \
    --geochat_model_path MBZUAI/GeoChat-7B
```

---

## Hardware

| Field | Value |
|---|---|
| GPU | TBD (Modal A10G / A100 or local GPU) |
| VRAM | TBD |
| Elapsed GPU time | TBD |
| Date | TBD |

---

## Checkpoint

| Field | Value |
|---|---|
| Adapter path | `training/checkpoints/m1_lora/` (not committed — too large) |
| Checkpoint commit / hash | TBD |
| Base model | GeoChat-7B (MBZUAI/GeoChat-7B) |
| LoRA rank | 16 |
| LoRA alpha | 32 |
| Vision encoder | Frozen |

---

## Before / After Evaluation (RSVQA-LR held-out slice)

> Minimum 100 examples required. Record exact prompts and evaluation script.

| Metric | Before (base GeoChat) | After (M1 LoRA) | Delta |
|---|---|---|---|
| Accuracy | TBD | TBD | TBD |
| F1 | TBD | TBD | TBD |
| Evaluation set | RSVQA-LR held-out (100 examples) | same | — |
| Evaluation script | TBD | TBD | — |

---

## Limitations

- This is a small adaptation run (2,000–5,000 samples), not full BigEarthNet training.
- Vision backbone is frozen — only projection and language layers are adapted.
- Results are valid only for the recorded dataset split and prompt format.
- Do not generalise these results to full-corpus performance.

---

## Honesty statement

This record must be completed with real measured values before Phase 3 begins.
Do not replace this section with a promise to run it later.
If the GPU session fails, resolve it before proceeding — reduce subset size or
use a different free GPU session (Colab, Kaggle, or another Modal session).
