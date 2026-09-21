"""GeoChat LoRA/QLoRA fine-tuning script — Phase 2 M1 adaptation run.

This script must be executed by the team on a GPU (Modal A10/A100 or equivalent)
before Phase 3 begins. See training/reproduce_m1_run.md for the full
reproducibility record including dataset split, seed, command, metrics and hardware.

Usage
-----
    python training/finetune_geochat_lora.py \
        --data_dir data/bigearthnet_subset \
        --output_dir training/checkpoints/m1_lora \
        --seed 42 \
        --max_samples 3000 \
        --val_samples 300 \
        --lora_r 16 \
        --lora_alpha 32 \
        --epochs 3

Requirements
------------
    pip install transformers peft datasets accelerate bitsandbytes tqdm

Note: Freeze the vision backbone if VRAM < 24 GB (use --freeze_vision_encoder).
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GeoChat LoRA fine-tuning — M1 adaptation run.")
    parser.add_argument("--data_dir", type=Path, required=True,
                        help="Directory containing the BigEarthNet subset.")
    parser.add_argument("--output_dir", type=Path, required=True,
                        help="Where to save the LoRA adapter checkpoint.")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducibility.")
    parser.add_argument("--max_samples", type=int, default=3000,
                        help="Training samples (2000–5000 per plan).")
    parser.add_argument("--val_samples", type=int, default=300,
                        help="Held-out validation samples.")
    parser.add_argument("--lora_r", type=int, default=16,
                        help="LoRA rank.")
    parser.add_argument("--lora_alpha", type=int, default=32,
                        help="LoRA alpha scaling.")
    parser.add_argument("--epochs", type=int, default=3,
                        help="Training epochs.")
    parser.add_argument("--freeze_vision_encoder", action="store_true",
                        help="Freeze GeoChat vision backbone (required if VRAM < 24 GB).")
    parser.add_argument("--geochat_model_path", type=str,
                        default="MBZUAI/GeoChat-7B",
                        help="HuggingFace model ID or local path.")
    return parser.parse_args()


def set_seed(seed: int) -> None:
    random.seed(seed)
    try:
        import numpy as np
        np.random.seed(seed)
        import torch
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
    except ImportError:
        pass


def main() -> None:
    args = parse_args()
    set_seed(args.seed)

    print(f"[M1] Seed: {args.seed}")
    print(f"[M1] Training samples: {args.max_samples}")
    print(f"[M1] Validation samples: {args.val_samples}")
    print(f"[M1] LoRA r={args.lora_r}, alpha={args.lora_alpha}")
    print(f"[M1] Freeze vision encoder: {args.freeze_vision_encoder}")
    print(f"[M1] Output: {args.output_dir}")

    # --- Import heavy deps here so the file is importable without GPU ---
    try:
        from transformers import AutoTokenizer, AutoModelForCausalLM, TrainingArguments, Trainer
        from peft import LoraConfig, get_peft_model, TaskType
    except ImportError as e:
        raise SystemExit(
            f"Missing dependency: {e}\n"
            "Run: pip install transformers peft datasets accelerate bitsandbytes"
        ) from e

    print(f"[M1] Loading base model: {args.geochat_model_path}")
    tokenizer = AutoTokenizer.from_pretrained(args.geochat_model_path, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        args.geochat_model_path,
        trust_remote_code=True,
        load_in_4bit=True,  # QLoRA
        device_map="auto",
    )

    if args.freeze_vision_encoder:
        for name, param in model.named_parameters():
            if "vision" in name.lower():
                param.requires_grad = False
        print("[M1] Vision encoder frozen.")

    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        target_modules=["q_proj", "v_proj"],
        lora_dropout=0.05,
        bias="none",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # Dataset loading — replace with actual BigEarthNet loader
    print("[M1] TODO: load BigEarthNet subset from", args.data_dir)
    print("[M1] Record sample IDs and split seed in training/reproduce_m1_run.md")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "seed": args.seed,
        "max_samples": args.max_samples,
        "val_samples": args.val_samples,
        "lora_r": args.lora_r,
        "lora_alpha": args.lora_alpha,
        "freeze_vision_encoder": args.freeze_vision_encoder,
        "base_model": args.geochat_model_path,
        "status": "NOT_YET_RUN",
    }
    (args.output_dir / "run_meta.json").write_text(json.dumps(meta, indent=2))
    print("[M1] Run metadata written. Complete the training loop and update reproduce_m1_run.md.")


if __name__ == "__main__":
    main()
