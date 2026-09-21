"""Modal M1 adaptation run — GeoChat QLoRA fine-tuning on RSVQA-LR.

Run this ONCE on Modal A10G before Phase 3 begins.

Cost estimate: ~$2–4 on A10G ($1.10/hr) for 3,000 samples × 3 epochs.
Budget: $25 available — safe to run 2–3 times if needed.

Usage
-----
    modal run modal_worker/train_m1.py

Or with custom args:
    modal run modal_worker/train_m1.py::run \
        --seed 42 --max-samples 3000 --epochs 3

After the run completes:
    - Fill in training/reproduce_m1_run.md with the printed metrics.
    - Download the checkpoint from Modal Volume if needed.
"""

from __future__ import annotations

import json
import os
import random
import time
from pathlib import Path

import modal

# ---------------------------------------------------------------------------
# Modal image — CUDA 12.1, Python 3.11, all training deps
# ---------------------------------------------------------------------------

IMAGE = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git", "wget", "libgl1")
    .pip_install(
        "torch==2.2.0",
        "torchvision==0.17.0",
        "transformers==4.40.0",
        "peft==0.10.0",
        "accelerate==0.29.0",
        "bitsandbytes==0.43.0",
        "datasets==2.19.0",
        "sentencepiece==0.2.0",
        "pillow==10.3.0",
        "scikit-learn==1.4.2",
        "tqdm==4.66.2",
        "huggingface_hub==0.22.2",
        extra_options="--extra-index-url https://download.pytorch.org/whl/cu121",
    )
)

# Persistent volume for model cache and checkpoints
VOLUME = modal.Volume.from_name("satquery-m1-vol", create_if_missing=True)
VOLUME_PATH = Path("/vol")
CHECKPOINT_DIR = VOLUME_PATH / "checkpoints" / "m1_lora"
MODEL_CACHE = VOLUME_PATH / "model_cache"

app = modal.App("satquery-m1-training", image=IMAGE)

# ---------------------------------------------------------------------------
# Data helpers — RSVQA-LR (public, RS-focused VQA, CC-BY 4.0)
# ---------------------------------------------------------------------------

RSVQA_LR_URL = "https://huggingface.co/datasets/SatML/RSVQA-LR/resolve/main"


def _load_rsvqa_lr(max_samples: int, val_samples: int, seed: int):
    """Load RSVQA-LR from HuggingFace datasets, return train/val splits."""
    from datasets import load_dataset

    print(f"[M1] Loading RSVQA-LR (seed={seed}, train={max_samples}, val={val_samples})")
    ds = load_dataset("SatML/RSVQA-LR", split="train", trust_remote_code=True)

    # Deterministic shuffle + split
    ds = ds.shuffle(seed=seed)
    total = min(max_samples + val_samples, len(ds))
    ds = ds.select(range(total))
    train_ds = ds.select(range(max_samples))
    val_ds = ds.select(range(max_samples, total))

    print(f"[M1] Train: {len(train_ds)} samples, Val: {len(val_ds)} samples")
    return train_ds, val_ds


def _format_sample(sample: dict) -> dict:
    """Convert RSVQA-LR sample to GeoChat instruction format."""
    question = sample.get("question", "Describe this remote-sensing image.")
    answer = sample.get("answer", "")
    prompt = (
        f"<image>\nRemote-sensing image analysis.\n"
        f"Question: {question}\nAnswer:"
    )
    return {"prompt": prompt, "answer": answer}


# ---------------------------------------------------------------------------
# Training function
# ---------------------------------------------------------------------------

@app.function(
    gpu="A10G",
    timeout=7200,          # 2-hour hard limit
    volumes={str(VOLUME_PATH): VOLUME},
    secrets=[modal.Secret.from_name("huggingface-secret")],
)
def run(
    seed: int = 42,
    max_samples: int = 3000,
    val_samples: int = 300,
    lora_r: int = 16,
    lora_alpha: int = 32,
    epochs: int = 3,
    geochat_model: str = "MBZUAI/GeoChat-7B",
    freeze_vision: bool = True,
):
    """Main M1 training function — runs on Modal A10G."""
    import torch
    from transformers import (
        AutoTokenizer,
        AutoModelForCausalLM,
        BitsAndBytesConfig,
        TrainingArguments,
        Trainer,
        DataCollatorForSeq2Seq,
    )
    from peft import LoraConfig, get_peft_model, TaskType

    t_start = time.time()
    print(f"[M1] GPU: {torch.cuda.get_device_name(0)}")
    print(f"[M1] VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
    print(f"[M1] Seed={seed}, samples={max_samples}, val={val_samples}, epochs={epochs}")

    random.seed(seed)
    torch.manual_seed(seed)
    os.environ["HF_HOME"] = str(MODEL_CACHE)
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

    # --- Load dataset ---
    train_ds, val_ds = _load_rsvqa_lr(max_samples, val_samples, seed)

    # --- Record sample IDs for reproducibility ---
    train_ids = [str(s.get("id", i)) for i, s in enumerate(train_ds)]
    val_ids = [str(s.get("id", i)) for i, s in enumerate(val_ds)]
    (CHECKPOINT_DIR / "train_ids.json").write_text(json.dumps(train_ids))
    (CHECKPOINT_DIR / "val_ids.json").write_text(json.dumps(val_ids))
    VOLUME.commit()

    # --- Load tokenizer ---
    print(f"[M1] Loading tokenizer: {geochat_model}")
    tokenizer = AutoTokenizer.from_pretrained(
        geochat_model, trust_remote_code=True, cache_dir=str(MODEL_CACHE)
    )
    tokenizer.pad_token = tokenizer.eos_token

    # --- Tokenise ---
    def tokenise(batch):
        prompts = [_format_sample(s)["prompt"] + " " + _format_sample(s)["answer"]
                   for s in batch]
        return tokenizer(prompts, truncation=True, max_length=512, padding="max_length")

    train_tok = train_ds.map(lambda b: tokenise([b]), batched=False,
                             remove_columns=train_ds.column_names)
    val_tok = val_ds.map(lambda b: tokenise([b]), batched=False,
                         remove_columns=val_ds.column_names)
    train_tok = train_tok.with_format("torch")
    val_tok = val_tok.with_format("torch")

    # --- Load model in 4-bit (QLoRA) ---
    print(f"[M1] Loading model in 4-bit: {geochat_model}")
    bnb_cfg = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        geochat_model,
        quantization_config=bnb_cfg,
        device_map="auto",
        trust_remote_code=True,
        cache_dir=str(MODEL_CACHE),
    )

    # --- Freeze vision encoder if requested ---
    if freeze_vision:
        frozen = 0
        for name, param in model.named_parameters():
            if any(k in name.lower() for k in ["vision", "visual", "clip", "patch_embed"]):
                param.requires_grad = False
                frozen += 1
        print(f"[M1] Froze {frozen} vision encoder parameter groups.")

    # --- BEFORE evaluation ---
    print("[M1] Running BEFORE evaluation on val set...")
    before_metrics = _evaluate(model, tokenizer, val_ds)
    print(f"[M1] BEFORE accuracy: {before_metrics['accuracy']:.4f}")

    # --- Apply LoRA ---
    lora_cfg = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=lora_r,
        lora_alpha=lora_alpha,
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
        lora_dropout=0.05,
        bias="none",
    )
    model = get_peft_model(model, lora_cfg)
    model.print_trainable_parameters()

    # --- Training ---
    training_args = TrainingArguments(
        output_dir=str(CHECKPOINT_DIR),
        num_train_epochs=epochs,
        per_device_train_batch_size=4,
        per_device_eval_batch_size=4,
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
        fp16=True,
        logging_steps=50,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        seed=seed,
        report_to="none",
        dataloader_num_workers=2,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_tok,
        eval_dataset=val_tok,
        tokenizer=tokenizer,
    )

    print("[M1] Starting training...")
    trainer.train()
    trainer.save_model(str(CHECKPOINT_DIR / "final"))
    VOLUME.commit()

    # --- AFTER evaluation ---
    print("[M1] Running AFTER evaluation on val set...")
    after_metrics = _evaluate(model, tokenizer, val_ds)
    print(f"[M1] AFTER accuracy: {after_metrics['accuracy']:.4f}")

    elapsed = time.time() - t_start

    # --- Write results record ---
    results = {
        "seed": seed,
        "max_samples": max_samples,
        "val_samples": val_samples,
        "lora_r": lora_r,
        "lora_alpha": lora_alpha,
        "epochs": epochs,
        "freeze_vision": freeze_vision,
        "base_model": geochat_model,
        "dataset": "RSVQA-LR (SatML/RSVQA-LR)",
        "gpu": torch.cuda.get_device_name(0),
        "elapsed_seconds": round(elapsed, 1),
        "before": before_metrics,
        "after": after_metrics,
        "delta_accuracy": round(after_metrics["accuracy"] - before_metrics["accuracy"], 4),
        "checkpoint_dir": str(CHECKPOINT_DIR / "final"),
    }

    results_path = CHECKPOINT_DIR / "m1_results.json"
    results_path.write_text(json.dumps(results, indent=2))
    VOLUME.commit()

    print("\n" + "=" * 60)
    print("M1 TRAINING COMPLETE — copy these into reproduce_m1_run.md")
    print("=" * 60)
    print(json.dumps(results, indent=2))
    return results


# ---------------------------------------------------------------------------
# Evaluation helper
# ---------------------------------------------------------------------------

def _evaluate(model, tokenizer, val_ds) -> dict:
    """Simple accuracy on RSVQA-LR yes/no/number questions."""
    import torch

    model.eval()
    correct = 0
    total = 0

    with torch.no_grad():
        for sample in list(val_ds)[:100]:  # cap at 100 for speed
            formatted = _format_sample(sample)
            inputs = tokenizer(
                formatted["prompt"],
                return_tensors="pt",
                truncation=True,
                max_length=256,
            ).to(model.device)
            out = model.generate(**inputs, max_new_tokens=16, do_sample=False)
            pred = tokenizer.decode(out[0], skip_special_tokens=True)
            pred_ans = pred.split("Answer:")[-1].strip().lower()
            gt_ans = str(formatted["answer"]).strip().lower()
            if pred_ans.startswith(gt_ans) or gt_ans in pred_ans:
                correct += 1
            total += 1

    acc = correct / total if total else 0.0
    return {"accuracy": round(acc, 4), "correct": correct, "total": total}


# ---------------------------------------------------------------------------
# Local entrypoint — for testing without Modal
# ---------------------------------------------------------------------------

@app.local_entrypoint()
def main(
    seed: int = 42,
    max_samples: int = 3000,
    val_samples: int = 300,
    lora_r: int = 16,
    lora_alpha: int = 32,
    epochs: int = 3,
):
    result = run.remote(
        seed=seed,
        max_samples=max_samples,
        val_samples=val_samples,
        lora_r=lora_r,
        lora_alpha=lora_alpha,
        epochs=epochs,
    )
    print("\n[DONE] Results:")
    print(json.dumps(result, indent=2))
    print("\n→ Now fill in training/reproduce_m1_run.md with these values.")
