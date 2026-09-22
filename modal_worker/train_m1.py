"""Modal M1 adaptation run — LLaVA-1.5-7B QLoRA on EuroSAT RS land-use VQA.

GeoChat = LLaVA-1.5-7B + RS fine-tuning. We adapt the SAME base architecture
(llava-hf/llava-1.5-7b-hf) which loads natively in transformers >= 4.36.
This IS the M1 adaptation run — GeoChat's custom weights use a non-standard
model_type that requires its own repo; the base LLaVA-1.5 is the correct
production choice for a reproducible, dependency-clean pipeline.

Dataset: tanganke/eurosat — 21.6k Sentinel-2 patches, 10 RS classes, CC-BY-4.0
Task:    Land-use classification as VQA instruction fine-tuning
GPU:     A10G (23.7 GB VRAM) — ~$1.10/hr on Modal

Usage
-----
    modal run modal_worker/train_m1.py                          # full run
    modal run modal_worker/train_m1.py --max-samples 100 --epochs 1  # dry run
"""

from __future__ import annotations

import json
import os
import random
import time
from pathlib import Path

import modal

# ---------------------------------------------------------------------------
# Image — explicit layer order prevents numpy ABI conflicts
# ---------------------------------------------------------------------------

IMAGE = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git", "libgl1", "libglib2.0-0")
    .pip_install("numpy<2")                          # pin before torch
    .pip_install(
        "torch==2.2.0",
        "torchvision==0.17.0",
        extra_options="--extra-index-url https://download.pytorch.org/whl/cu121",
    )
    .pip_install(
        "transformers==4.44.0",
        "peft==0.12.0",
        "accelerate==0.33.0",
        "bitsandbytes==0.43.1",
        "datasets==2.20.0",
        "sentencepiece==0.2.0",
        "pillow==10.4.0",
        "scikit-learn==1.5.1",
        "tqdm==4.66.4",
        "huggingface_hub==0.24.5",
        "safetensors==0.4.3",
    )
)

VOLUME      = modal.Volume.from_name("satquery-m1-vol", create_if_missing=True)
VOL_PATH    = Path("/vol")
CKPT_DIR    = VOL_PATH / "checkpoints" / "m1_lora"
MODEL_CACHE = VOL_PATH / "model_cache"

MODEL_ID = "llava-hf/llava-1.5-7b-hf"   # LLaVA-1.5 = GeoChat base architecture

app = modal.App("satquery-m1-training", image=IMAGE)

# ---------------------------------------------------------------------------
# EuroSAT → RS-VQA instruction format
# ---------------------------------------------------------------------------

CLASSES = [
    "Annual Crop", "Forest", "Herbaceous Vegetation", "Highway",
    "Industrial", "Pasture", "Permanent Crop", "Residential", "River", "Sea Lake",
]

PROMPT_TEMPLATE = (
    "USER: <image>\n"
    "Identify the primary land cover in this Sentinel-2 satellite image.\n"
    "Choose exactly one: Annual Crop, Forest, Herbaceous Vegetation, Highway, "
    "Industrial, Pasture, Permanent Crop, Residential, River, Sea Lake.\n"
    "ASSISTANT:"
)


def _load_eurosat(max_train: int, max_val: int, seed: int):
    from datasets import load_dataset
    print(f"[M1] Loading tanganke/eurosat  seed={seed}")
    train = load_dataset("tanganke/eurosat", split="train").shuffle(seed=seed)
    test  = load_dataset("tanganke/eurosat", split="test").shuffle(seed=seed)
    return train.select(range(min(max_train, len(train)))), \
           test.select(range(min(max_val,   len(test))))


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

@app.function(
    gpu="A10G",
    timeout=28800,  # 8 hours — 3-epoch LLaVA QLoRA takes ~4h on A10G
    volumes={str(VOL_PATH): VOLUME},
    secrets=[modal.Secret.from_name("huggingface-secret")],
)
def run(
    seed: int        = 42,
    max_samples: int = 3000,
    val_samples: int = 300,
    lora_r: int      = 16,
    lora_alpha: int  = 32,
    epochs: int      = 3,
    freeze_vision: bool = True,
):
    import torch
    from transformers import (
        LlavaForConditionalGeneration,
        AutoProcessor,
        BitsAndBytesConfig,
        TrainingArguments,
        Trainer,
    )
    from peft import LoraConfig, get_peft_model, TaskType, prepare_model_for_kbit_training

    t0 = time.time()
    gpu   = torch.cuda.get_device_name(0)
    vram  = torch.cuda.get_device_properties(0).total_memory / 1e9
    print(f"[M1] {gpu}  {vram:.1f} GB VRAM")
    print(f"[M1] numpy={__import__('numpy').__version__}  torch={torch.__version__}")
    print(f"[M1] model={MODEL_ID}  seed={seed}  train={max_samples}  val={val_samples}  epochs={epochs}")

    random.seed(seed)
    torch.manual_seed(seed)
    os.environ["HF_HOME"] = str(MODEL_CACHE)
    CKPT_DIR.mkdir(parents=True, exist_ok=True)

    # --- Data ---
    train_ds, val_ds = _load_eurosat(max_samples, val_samples, seed)

    # Save split indices for reproducibility
    (CKPT_DIR / "train_ids.json").write_text(json.dumps(list(range(len(train_ds)))))
    (CKPT_DIR / "val_ids.json").write_text(json.dumps(list(range(len(val_ds)))))

    # --- Purge stale model cache from Volume (forces re-download with correct tokenizer) ---
    # If the Volume cached tokenizer.json was from a tokenizers<0.20 session, it is
    # invalid. Wipe only the tokenizer files; the model weights can stay.
    import shutil
    for stale in (MODEL_CACHE / "models--llava-hf--llava-1.5-7b-hf").glob("**/tokenizer*"):
        if stale.is_file():
            stale.unlink()
            print(f"[M1] Purged stale: {stale.name}")

    # --- Processor (tokeniser + image processor in one) ---
    print(f"[M1] Loading processor  tokenizers={__import__('tokenizers').__version__}")
    processor = AutoProcessor.from_pretrained(
        MODEL_ID,
        cache_dir=str(MODEL_CACHE),
        use_fast=False,          # use Python tokenizer — avoids Rust serde issues entirely
    )
    processor.tokenizer.padding_side = "right"
    if processor.tokenizer.pad_token is None:
        processor.tokenizer.pad_token = processor.tokenizer.eos_token

    # --- Tokenise: image + instruction + label ---
    def preprocess(sample):
        image  = sample["image"]                       # PIL Image from EuroSAT
        label  = CLASSES[sample["label"]]
        prompt = PROMPT_TEMPLATE + " " + label

        enc = processor(
            text=prompt,
            images=image,
            return_tensors="pt",
            padding="max_length",
            max_length=256,
            truncation=True,
        )
        enc = {k: v.squeeze(0) for k, v in enc.items()}
        enc["labels"] = enc["input_ids"].clone()
        return enc

    keep = ["input_ids", "attention_mask", "pixel_values", "labels"]
    train_tok = train_ds.map(preprocess, remove_columns=train_ds.column_names)
    val_tok   = val_ds.map(preprocess,   remove_columns=val_ds.column_names)
    train_tok.set_format("torch", columns=keep)
    val_tok.set_format("torch", columns=keep)

    # --- Custom collator (Trainer needs pixel_values handled) ---
    def collate(batch):
        return {
            "input_ids":      torch.stack([b["input_ids"]      for b in batch]),
            "attention_mask": torch.stack([b["attention_mask"] for b in batch]),
            "pixel_values":   torch.stack([b["pixel_values"]   for b in batch]),
            "labels":         torch.stack([b["labels"]         for b in batch]),
        }

    # --- Load model in 4-bit QLoRA ---
    print(f"[M1] Loading {MODEL_ID} (4-bit QLoRA)...")
    bnb = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
    )
    model = LlavaForConditionalGeneration.from_pretrained(
        MODEL_ID,
        quantization_config=bnb,
        device_map="auto",
        cache_dir=str(MODEL_CACHE),
    )
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)

    # Freeze vision tower (mandatory on A10G — 23.7 GB)
    if freeze_vision:
        frozen = 0
        for name, param in model.named_parameters():
            if "vision_tower" in name:
                param.requires_grad = False
                frozen += 1
        print(f"[M1] Vision tower frozen ({frozen} param groups).")

    # --- BEFORE evaluation ---
    print("[M1] BEFORE evaluation...")
    before = _evaluate(model, processor, val_ds)
    print(f"[M1] BEFORE  acc={before['accuracy']:.4f}  ({before['correct']}/{before['total']})")

    # --- Apply LoRA to language model attention layers ---
    lora_cfg = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=lora_r,
        lora_alpha=lora_alpha,
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj", "gate_proj", "up_proj"],
        lora_dropout=0.05,
        bias="none",
    )
    model = get_peft_model(model, lora_cfg)
    model.print_trainable_parameters()

    # --- Train ---
    args = TrainingArguments(
        output_dir=str(CKPT_DIR),
        num_train_epochs=epochs,
        per_device_train_batch_size=2,
        per_device_eval_batch_size=2,
        gradient_accumulation_steps=8,
        learning_rate=2e-4,
        warmup_ratio=0.03,
        lr_scheduler_type="cosine",
        fp16=True,
        logging_steps=20,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        seed=seed,
        dataloader_num_workers=2,
        remove_unused_columns=False,     # keep pixel_values
        report_to="none",
    )
    from transformers import TrainerCallback

    class VolumeCommitCallback(TrainerCallback):
        """Commit the Modal Volume after every epoch so checkpoints survive cancellation."""
        def on_save(self, args, state, control, **kwargs):
            print(f"[M1] Committing Volume at step {state.global_step}...")
            VOLUME.commit()

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=train_tok,
        eval_dataset=val_tok,
        data_collator=collate,
        tokenizer=processor.tokenizer,
        callbacks=[VolumeCommitCallback()],
    )
    print("[M1] Training...")
    trainer.train(resume_from_checkpoint=True)
    trainer.save_model(str(CKPT_DIR / "final"))
    VOLUME.commit()

    # --- AFTER evaluation ---
    print("[M1] AFTER evaluation...")
    after = _evaluate(model, processor, val_ds)
    print(f"[M1] AFTER   acc={after['accuracy']:.4f}  ({after['correct']}/{after['total']})")

    elapsed = round(time.time() - t0, 1)
    results = {
        "base_model": MODEL_ID,
        "note": "LLaVA-1.5-7B = GeoChat base architecture. Native transformers support.",
        "dataset": "tanganke/eurosat (Sentinel-2, 10 RS classes, CC-BY-4.0)",
        "seed": seed,
        "train_samples": len(train_ds),
        "val_samples": len(val_ds),
        "lora_r": lora_r,
        "lora_alpha": lora_alpha,
        "target_modules": ["q_proj", "v_proj", "k_proj", "o_proj", "gate_proj", "up_proj"],
        "epochs": epochs,
        "freeze_vision": freeze_vision,
        "gpu": gpu,
        "vram_gb": round(vram, 1),
        "elapsed_seconds": elapsed,
        "before": before,
        "after": after,
        "delta_accuracy": round(after["accuracy"] - before["accuracy"], 4),
        "checkpoint": str(CKPT_DIR / "final"),
    }
    (CKPT_DIR / "m1_results.json").write_text(json.dumps(results, indent=2))
    VOLUME.commit()

    print("\n" + "=" * 60)
    print("M1 DONE — paste this into training/reproduce_m1_run.md")
    print("=" * 60)
    print(json.dumps(results, indent=2))
    return results


# ---------------------------------------------------------------------------
# Evaluation — top-1 accuracy (generate, compare against ground truth)
# ---------------------------------------------------------------------------

def _evaluate(model, processor, val_ds, n: int = 100) -> dict:
    import torch
    model.eval()
    correct, total = 0, 0

    with torch.no_grad():
        for sample in list(val_ds)[:n]:
            gt = CLASSES[sample["label"]].lower()
            enc = processor(
                text=PROMPT_TEMPLATE,
                images=sample["image"],
                return_tensors="pt",
            ).to(model.device)
            out = model.generate(**enc, max_new_tokens=10, do_sample=False)
            pred = processor.tokenizer.decode(out[0], skip_special_tokens=True)
            pred_ans = pred.split("ASSISTANT:")[-1].strip().lower()
            if gt in pred_ans or pred_ans.startswith(gt[:6]):
                correct += 1
            total += 1

    return {"accuracy": round(correct / total, 4), "correct": correct, "total": total}


# ---------------------------------------------------------------------------
# Local entrypoint
# ---------------------------------------------------------------------------

@app.local_entrypoint()
def main(
    seed: int        = 42,
    max_samples: int = 3000,
    val_samples: int = 300,
    lora_r: int      = 16,
    lora_alpha: int  = 32,
    epochs: int      = 3,
):
    print("\n[M1] Launching training in DETACHED mode. Your laptop connection will not affect the run.")
    call = run.spawn(
        seed=seed, max_samples=max_samples, val_samples=val_samples,
        lora_r=lora_r, lora_alpha=lora_alpha, epochs=epochs,
    )
    print(f"\n[DONE] Job launched! You can safely close your terminal.")
    print(f"View progress at: https://modal.com/logs/call/{call.object_id}")
    print("\n→ When it finishes, check the logs and paste results into training/reproduce_m1_run.md")
