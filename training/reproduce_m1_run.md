# M1 Training Reproducibility Record

This document records the results of the M1 fine-tuning run on Modal, serving as the clearing gate for Phase 3.

## Dry Run Results (Gate Cleared)

The dry run successfully proved the pipeline works end-to-end, and the model learned (accuracy improved from 20% to 40% with just 100 samples).

```json
{
  "base_model": "llava-hf/llava-1.5-7b-hf",
  "note": "LLaVA-1.5-7B = GeoChat base architecture. Native transformers support.",
  "dataset": "tanganke/eurosat (Sentinel-2, 10 RS classes, CC-BY-4.0)",
  "seed": 42,
  "train_samples": 100,
  "val_samples": 300,
  "lora_r": 16,
  "lora_alpha": 32,
  "target_modules": [
    "q_proj",
    "v_proj",
    "k_proj",
    "o_proj",
    "gate_proj",
    "up_proj"
  ],
  "epochs": 1,
  "freeze_vision": true,
  "gpu": "NVIDIA A10G",
  "vram_gb": 23.7,
  "elapsed_seconds": 563.5,
  "before": {
    "accuracy": 0.2,
    "correct": 20,
    "total": 100
  },
  "after": {
    "accuracy": 0.4,
    "correct": 40,
    "total": 100
  },
  "delta_accuracy": 0.2,
  "checkpoint": "/vol/checkpoints/m1_lora/final"
}
```

*Note: For the full production model, run `modal run modal_worker/train_m1.py` without arguments.*
