"""M2: LoRA adaptation of GeoChat-7B on BigEarthNet.txt (VQA + captioning + grounding).

Stages (each is idempotent and leaves evidence files on the volume):

  convert_geochat   MBZUAI/geochat-7B ships in the original LLaVA training layout
                    (GeoChatLlamaForCausalLM, model_type "geochat"), which transformers cannot
                    load. Convert it once to the llava-hf layout, reproducing GeoChat's vision
                    tower (CLIP-336 with position embeddings interpolated to 504px).
  verify_geochat    Run the ORIGINAL GeoChat code (its repo, transformers 4.31) and the converted
                    model on identical inputs; the pipeline refuses to continue unless token ids,
                    pixel values and next-token logits match.
  build_splits      Stratified train subset (official train split) and held-out eval subset
                    (official test split, patch-disjoint), with the distribution logged.
  evaluate(base)    Pre-adaptation metrics on the held-out subset.
  train             QLoRA; resumes from the newest checkpoint in M2_CKPT_DIR; persists the loss
                    history and an event log.
  evaluate(adapted) Post-adaptation metrics on the same held-out subset.
  finalize          results.json with the before/after table.

Usage (from the repo root):
  modal run --detach modal_worker/train_m2.py --mode debug
  modal run --detach modal_worker/train_m2.py --mode scaled --n-train 3200
Then export evidence and cost: python modal_worker/m2_report.py --mode debug
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import modal

APP_NAME = "satquery-m2-geochat"
app = modal.App(APP_NAME)

VOLUME = modal.Volume.from_name("satquery-m1-vol", create_if_missing=True)
VOL = Path("/vol")
LMDB_PATH = VOL / "Encoded-BigEarthNet"
PARQUET_PATH = VOL / "BigEarthNet.txt.parquet"
HF_HOME = VOL / "model_cache"
GEOCHAT_HF_DIR = VOL / "models" / "geochat-7b-llava-hf"

# Pinned upstream revisions
GEOCHAT_REPO = "MBZUAI/geochat-7B"
GEOCHAT_REVISION = "cca91eb4c40d833c60579a5af95a7514181fe291"
GEOCHAT_CODE_COMMIT = "4850920e005a849bd224d0ce35aa9db031fa5155"  # github.com/mbzuai-oryx/GeoChat
CLIP_REPO = "openai/clip-vit-large-patch14-336"
CLIP_REVISION = "ce19dc912ca5cd21c8a653c79e251e808ccabcd1"
BEN_TXT_REPO = "BIFOLD-BigEarthNetv2-0/BigEarthNet.txt"
BEN_TXT_REVISION = "72d865f2146f0a85b720f7f3ca1cdbaeafc3d316"
BEN_LMDB_REPO = "hackelle/BigEarthNetV2-Lithuania-Summer-LMDB"

A10G_USD_PER_HOUR = 1.10  # Modal list price; actual cost is read from `modal billing report`


def m2_ckpt_dir(mode: str) -> Path:
    """M2_CKPT_DIR: every artifact of one run (debug or scaled) lives under here."""
    return VOL / "checkpoints" / "m2_geochat" / mode


RUN_CONFIGS = {
    # Debug: small enough to finish in minutes; checkpoints often so the resume path gets exercised.
    "debug": dict(n_train=128, n_eval=40, epochs=1, batch_size=2, grad_accum=4, save_steps=4, save_every_min=5, lr=1e-4),
    # Scaled: n_train is sized from the debug run's measured throughput (see STATUS.md).
    "scaled": dict(n_train=3200, n_eval=400, epochs=1, batch_size=2, grad_accum=8, save_steps=10, save_every_min=10, lr=1e-4),
}
LORA = dict(r=32, lora_alpha=64, lora_dropout=0.05)
# LoRA on the language model only. CLIP also has q/k/v_proj modules; GeoChat keeps its vision tower
# frozen, and so do we.
LORA_TARGET_REGEX = r".*language_model.*\.(q_proj|k_proj|v_proj|o_proj|gate_proj|up_proj|down_proj)"
MAX_NEW_TOKENS = {"binary": 8, "mcq": 8, "bounding box": 32, "captioning": 512}
EVAL_BATCH = 8
SEED = 42

HERE = Path(__file__).resolve().parent

train_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "torch==2.6.0",
        "torchvision==0.21.0",
        "lightning==2.5.1",  # imported by the upstream ben_txt_datamodule.py
        index_url="https://download.pytorch.org/whl/cu124",
        extra_index_url="https://pypi.org/simple",
    )
    .pip_install(
        "transformers==4.51.3",
        "peft==0.15.2",
        "accelerate==1.6.0",
        "bitsandbytes==0.45.5",
        "sentencepiece==0.2.0",
        "protobuf",
        "safetensors",
        "huggingface_hub[hf_transfer]",
        "pandas",
        "pyarrow",
        "lmdb",
        "pillow",
    )
    .env({"HF_HOME": str(HF_HOME), "HF_HUB_ENABLE_HF_TRANSFER": "1", "TOKENIZERS_PARALLELISM": "false"})
    .add_local_dir(HERE / "satq_m2", "/root/satq_m2")
    .add_local_file(HERE / "ben_txt_datamodule.py", "/root/ben_txt_datamodule.py")
)

# The original GeoChat stack, used only as the reference implementation in verify_geochat.
reference_image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("git")
    .pip_install("torch==2.0.1", "torchvision==0.15.2", index_url="https://download.pytorch.org/whl/cu118")
    .pip_install(
        "transformers==4.31.0",
        "tokenizers==0.13.3",
        "huggingface_hub==0.16.4",
        "accelerate==0.21.0",
        "sentencepiece==0.1.99",
        "einops==0.6.1",
        "timm==0.6.13",
        "numpy<2",
        "pillow",
        "protobuf<4",
        "safetensors==0.3.1",
    )
    .run_commands(
        "git clone https://github.com/mbzuai-oryx/GeoChat /opt/GeoChat",
        f"cd /opt/GeoChat && git checkout {GEOCHAT_CODE_COMMIT} && pip install --no-deps -e .",
    )
    .env({"HF_HOME": str(HF_HOME)})
)

volumes = {str(VOL): VOLUME}


# ----------------------------------------------------------------------------- helpers

def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log_event(mode: str, event: str, **fields) -> None:
    d = m2_ckpt_dir(mode)
    d.mkdir(parents=True, exist_ok=True)
    rec = {"ts": _now(), "event": event, "modal_task_id": os.environ.get("MODAL_TASK_ID"), **fields}
    with open(d / "events.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")
    print(f"[event] {json.dumps(rec)}", flush=True)


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True, default=str))
    tmp.replace(path)


def _dir_manifest(path: Path) -> dict:
    import hashlib

    files = {}
    for p in sorted(path.rglob("*")):
        if p.is_file():
            h = hashlib.sha256()
            with open(p, "rb") as f:
                for block in iter(lambda: f.read(1 << 20), b""):
                    h.update(block)
            files[str(p.relative_to(path))] = {"bytes": p.stat().st_size, "sha256": h.hexdigest()}
    return files


def _bnb_config():
    import torch
    from transformers import BitsAndBytesConfig

    return BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        # Vision tower, projector and lm_head stay in bf16: quantizing CLIP degrades image features
        llm_int8_skip_modules=["vision_tower", "multi_modal_projector", "lm_head"],
    )


def _load_base_4bit():
    import torch
    from transformers import LlavaForConditionalGeneration

    return LlavaForConditionalGeneration.from_pretrained(
        GEOCHAT_HF_DIR, quantization_config=_bnb_config(), torch_dtype=torch.bfloat16, device_map={"": 0}
    )


def _load_tokenizer_and_image_processor():
    from transformers import CLIPImageProcessor, LlamaTokenizer

    tok = LlamaTokenizer.from_pretrained(GEOCHAT_HF_DIR)
    improc = CLIPImageProcessor.from_pretrained(GEOCHAT_HF_DIR)
    return tok, improc


# ----------------------------------------------------------------------------- stage 0: data

@app.function(image=train_image, volumes=volumes, timeout=3600, cpu=2, memory=8192)
def ensure_dataset() -> dict:
    """Fetch annotations and the Lithuania-Summer LMDB onto the volume if they are missing."""
    import shutil

    from huggingface_hub import hf_hub_download

    VOLUME.reload()
    if not PARQUET_PATH.exists():
        p = hf_hub_download(BEN_TXT_REPO, "BigEarthNet.txt.parquet", repo_type="dataset", revision=BEN_TXT_REVISION)
        shutil.copy(p, PARQUET_PATH)
    LMDB_PATH.mkdir(parents=True, exist_ok=True)
    for name in ("data.mdb", "lock.mdb"):
        if not (LMDB_PATH / name).exists():
            # hf_hub_download keeps the repo subfolder, so download to the cache and copy into place
            p = hf_hub_download(BEN_LMDB_REPO, name, subfolder="BENv2_lithuania_summer.lmdb", repo_type="dataset")
            shutil.copy(p, LMDB_PATH / name)
    VOLUME.commit()
    return {
        "parquet_bytes": PARQUET_PATH.stat().st_size,
        "lmdb_bytes": (LMDB_PATH / "data.mdb").stat().st_size,
    }


# ----------------------------------------------------------------------------- stage 1: convert

def _interpolate_clip_pos_embedding(weight, image_size: int = 504, patch_size: int = 14):
    """Exact port of GeoChat's CLIPVisionTower.clip_interpolate_embeddings (bicubic, align_corners)."""
    import math

    import torch

    pos = weight.unsqueeze(0)
    _, seq_len, dim = pos.shape
    new_seq_len = (image_size // patch_size) ** 2 + 1
    if new_seq_len == seq_len:
        return weight
    old_side = int(math.sqrt(seq_len - 1))
    new_side = image_size // patch_size
    cls_tok, grid = pos[:, :1, :], pos[:, 1:, :]
    grid = grid.permute(0, 2, 1).reshape(1, dim, old_side, old_side)
    grid = torch.nn.functional.interpolate(grid, size=new_side, mode="bicubic", align_corners=True)
    grid = grid.reshape(1, dim, new_side * new_side).permute(0, 2, 1)
    return torch.cat([cls_tok, grid], dim=1)[0]


@app.function(image=train_image, volumes=volumes, timeout=5400, cpu=8, memory=65536)
def convert_geochat() -> dict:
    import torch
    from huggingface_hub import snapshot_download
    from satq_m2 import geochat as G
    from transformers import (
        AddedToken,
        CLIPImageProcessor,
        CLIPVisionConfig,
        CLIPVisionModel,
        GenerationConfig,
        LlamaConfig,
        LlamaTokenizer,
        LlavaConfig,
        LlavaForConditionalGeneration,
        LlavaProcessor,
    )

    VOLUME.reload()
    report_path = GEOCHAT_HF_DIR / "conversion.json"
    if report_path.exists():
        return json.loads(report_path.read_text())

    src = Path(snapshot_download(GEOCHAT_REPO, revision=GEOCHAT_REVISION))
    src_cfg = json.loads((src / "config.json").read_text())
    index = json.loads((src / "pytorch_model.bin.index.json").read_text())
    sd_src = {}
    for shard in sorted(set(index["weight_map"].values())):
        sd_src.update(torch.load(src / shard, map_location="cpu", weights_only=True))

    # GeoChat's loader rebuilds its vision tower from CLIP-336 and interpolates to 504px at load
    # time (builder.py calls vision_tower.load_model()), so that is the tower it actually runs.
    clip = CLIPVisionModel.from_pretrained(CLIP_REPO, revision=CLIP_REVISION, torch_dtype=torch.float32)
    clip_sd = clip.state_dict()
    pos_key = "vision_model.embeddings.position_embedding.weight"
    clip_sd[pos_key] = _interpolate_clip_pos_embedding(clip_sd[pos_key], G.IMAGE_SIZE, G.PATCH_SIZE)
    # Diagnostic only: how far the vision copy stored in the GeoChat checkpoint is from that tower
    stored_prefix = "model.vision_tower.vision_tower."
    vt_diff = max(
        (sd_src[stored_prefix + k].float() - v.float()).abs().max().item()
        for k, v in clip_sd.items()
        if stored_prefix + k in sd_src and sd_src[stored_prefix + k].shape == v.shape
    )

    vocab = 32064  # llava-hf layout: 32000 + <image>, <pad>, padded to a multiple of 64
    text_cfg = LlamaConfig(
        vocab_size=vocab,
        hidden_size=src_cfg["hidden_size"],
        intermediate_size=src_cfg["intermediate_size"],
        num_hidden_layers=src_cfg["num_hidden_layers"],
        num_attention_heads=src_cfg["num_attention_heads"],
        num_key_value_heads=src_cfg["num_key_value_heads"],
        max_position_embeddings=src_cfg["max_position_embeddings"],
        rms_norm_eps=src_cfg["rms_norm_eps"],
        hidden_act=src_cfg["hidden_act"],
        rope_scaling=src_cfg["rope_scaling"],
        tie_word_embeddings=False,
        bos_token_id=1,
        eos_token_id=2,
        pad_token_id=G.PAD_TOKEN_ID,
    )
    vision_cfg = CLIPVisionConfig.from_pretrained(CLIP_REPO, revision=CLIP_REVISION)
    vision_cfg.image_size = G.IMAGE_SIZE
    if src_cfg["mm_projector_type"] != "mlp2x_gelu" or src_cfg["mm_vision_select_layer"] != -2:
        raise ValueError("GeoChat config differs from the LLaVA-1.5 layout this converter handles")
    cfg = LlavaConfig(
        vision_config=vision_cfg.to_dict(),
        text_config=text_cfg.to_dict(),
        image_token_index=G.IMAGE_TOKEN_ID,
        projector_hidden_act="gelu",
        vision_feature_select_strategy="default",  # drop CLS = GeoChat's "patch" features
        vision_feature_layer=-2,
        image_seq_length=G.IMAGE_SEQ_LEN,
        pad_token_id=G.PAD_TOKEN_ID,
    )

    # The checkpoint carries RoPE inv_freq buffers (persistent in transformers 4.31), stored in low
    # precision. GeoChat never uses them for sequences <= 4096 tokens: in 4.31 the cos/sin tables are
    # built at init from the standard fp32 inv_freq, before the checkpoint loads, and only rebuilt for
    # longer sequences. transformers 4.51 recomputes the standard values too, so they are dropped. The
    # deviation is recorded, and the logit comparison in verify_geochat is the end-to-end check.
    head_dim = src_cfg["hidden_size"] // src_cfg["num_attention_heads"]
    std_inv_freq = 1.0 / (10000.0 ** (torch.arange(0, head_dim, 2, dtype=torch.float32) / head_dim))
    inv_freq_keys = [k for k in sd_src if k.endswith("rotary_emb.inv_freq")]
    inv_freq_diff = max(
        (((sd_src[k].float() - std_inv_freq).abs() / std_inv_freq).max().item() for k in inv_freq_keys), default=0.0
    )
    if inv_freq_diff > 0.05:  # anything beyond rounding would mean a different RoPE base: stop
        raise ValueError(f"GeoChat rotary inv_freq differs from standard RoPE (max relative diff {inv_freq_diff})")

    sd = {}
    for k, v in sd_src.items():
        if k.startswith("model.vision_tower.") or k in inv_freq_keys:
            continue
        if k.startswith("model.mm_projector.0."):
            sd["multi_modal_projector.linear_1." + k.split(".")[-1]] = v
        elif k.startswith("model.mm_projector.2."):
            sd["multi_modal_projector.linear_2." + k.split(".")[-1]] = v
        elif k == "lm_head.weight":
            sd["language_model.lm_head.weight"] = v
        elif k.startswith("model."):
            sd["language_model." + k] = v
        else:
            raise KeyError(f"Unmapped GeoChat tensor {k}")
    for k, v in clip_sd.items():
        sd["vision_tower." + k] = v.to(torch.float16)
    # New rows for <image>/<pad>/padding: mean of existing rows (what resize_token_embeddings does)
    for k in ("language_model.model.embed_tokens.weight", "language_model.lm_head.weight"):
        w = sd[k]
        extra = w.float().mean(0, keepdim=True).to(w.dtype).expand(vocab - w.shape[0], -1)
        sd[k] = torch.cat([w, extra], 0)
    sd = {k: v.to(torch.float16) for k, v in sd.items()}

    with torch.device("meta"):
        model = LlavaForConditionalGeneration(cfg)
    expected = set(model.state_dict().keys())
    missing, unexpected = expected - set(sd), set(sd) - expected
    if missing or unexpected:
        raise KeyError(
            f"State dict mismatch: {len(missing)} missing {sorted(missing)[:10]}, "
            f"{len(unexpected)} unexpected {sorted(unexpected)[:10]}"
        )
    model.load_state_dict(sd, strict=True, assign=True)
    model.generation_config = GenerationConfig(
        bos_token_id=1, eos_token_id=2, pad_token_id=G.PAD_TOKEN_ID, do_sample=False, num_beams=1,
        # never generate the placeholder / padding rows added above
        suppress_tokens=list(range(32000, vocab)),
    )
    GEOCHAT_HF_DIR.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(GEOCHAT_HF_DIR, safe_serialization=True, max_shard_size="5GB")

    tok = LlamaTokenizer.from_pretrained(src)
    tok.add_tokens([AddedToken(G.IMAGE_TOKEN, special=True, normalized=False)], special_tokens=True)
    tok.add_special_tokens({"pad_token": G.PAD_TOKEN})
    if tok.convert_tokens_to_ids(G.IMAGE_TOKEN) != G.IMAGE_TOKEN_ID or tok.pad_token_id != G.PAD_TOKEN_ID:
        raise ValueError("Added token ids do not match the llava-hf layout")
    improc = CLIPImageProcessor.from_pretrained(
        CLIP_REPO, revision=CLIP_REVISION,
        size={"shortest_edge": G.IMAGE_SIZE}, crop_size={"height": G.IMAGE_SIZE, "width": G.IMAGE_SIZE},
    )
    LlavaProcessor(
        image_processor=improc, tokenizer=tok, patch_size=G.PATCH_SIZE,
        vision_feature_select_strategy="default", num_additional_image_tokens=1,
    ).save_pretrained(GEOCHAT_HF_DIR)

    report = {
        "created_at": _now(),
        "source": {"repo": GEOCHAT_REPO, "revision": GEOCHAT_REVISION, "tensors": len(sd_src)},
        "dropped_rope_inv_freq_buffers": {"count": len(inv_freq_keys), "max_relative_diff_vs_standard": inv_freq_diff},
        "vision_tower": {
            "repo": CLIP_REPO, "revision": CLIP_REVISION, "image_size": G.IMAGE_SIZE,
            "max_abs_diff_vs_checkpoint_copy": vt_diff,
        },
        "target_layout": "llava-hf LlavaForConditionalGeneration (transformers 4.51.3)",
        "tensors_written": len(sd),
        "files": {p.name: p.stat().st_size for p in sorted(GEOCHAT_HF_DIR.iterdir()) if p.is_file()},
    }
    _write_json(report_path, report)
    VOLUME.commit()
    return report


# ----------------------------------------------------------------------------- stage 2: verify

@app.function(image=reference_image, volumes=volumes, gpu="A10G", timeout=2400)
def geochat_reference(png: bytes, questions: list[str], max_new_tokens: int = 40) -> list[dict]:
    """Original GeoChat implementation (repo code + transformers 4.31) on the given inputs."""
    import io

    import numpy as np
    import torch
    from geochat.constants import DEFAULT_IMAGE_TOKEN, IMAGE_TOKEN_INDEX
    from geochat.conversation import conv_templates
    from geochat.mm_utils import process_images, tokenizer_image_token
    from geochat.model.builder import load_pretrained_model
    from huggingface_hub import snapshot_download
    from PIL import Image

    VOLUME.reload()
    path = snapshot_download(GEOCHAT_REPO, revision=GEOCHAT_REVISION)
    tokenizer, model, image_processor, _ = load_pretrained_model(path, None, "geochat-7B", device="cuda")
    img = Image.open(io.BytesIO(png)).convert("RGB")
    pixel = process_images([img], image_processor, model.config).to("cuda", torch.float16)
    out = []
    for q in questions:
        conv = conv_templates["llava_v1"].copy()
        conv.append_message(conv.roles[0], DEFAULT_IMAGE_TOKEN + "\n" + q)
        conv.append_message(conv.roles[1], None)
        prompt = conv.get_prompt()
        ids = tokenizer_image_token(prompt, tokenizer, IMAGE_TOKEN_INDEX, return_tensors="pt").unsqueeze(0).cuda()
        with torch.inference_mode():
            logits = model(input_ids=ids, images=pixel).logits[0, -1].float().cpu().numpy()
            gen = model.generate(ids, images=pixel, do_sample=False, num_beams=1, max_new_tokens=max_new_tokens, use_cache=True)
        new = gen[0, ids.shape[1]:].tolist()
        # Raw float32 bytes rather than arrays: this image has numpy 1.x, the caller numpy 2.x
        out.append({
            "prompt": prompt,
            "input_ids": ids[0].tolist(),
            "pixel_values": pixel[0].float().cpu().numpy().astype(np.float32).tobytes(),
            "last_logits": logits.astype(np.float32).tobytes(),
            "generated_ids": new,
            "generated_text": tokenizer.decode(new, skip_special_tokens=True).strip(),
        })
    return out


@app.function(image=train_image, volumes=volumes, gpu="A10G", timeout=2700)
def verify_geochat() -> dict:
    import io

    import lmdb
    import numpy as np
    import torch
    from PIL import Image
    from safetensors.numpy import load as st_load
    from satq_m2 import geochat as G
    from satq_m2.imagery import RGB_BANDS, expand2square, render_rgb
    from transformers import LlavaForConditionalGeneration

    VOLUME.reload()
    out_path = GEOCHAT_HF_DIR / "verification.json"
    if out_path.exists():
        prev = json.loads(out_path.read_text())
        if prev.get("passed"):
            return prev

    env = lmdb.open(str(LMDB_PATH), readonly=True, lock=False)
    with env.begin() as txn:
        # the LMDB can also hold Sentinel-1 entries; take the first Sentinel-2 patch
        key, buf = next((k, v) for k, v in txn.cursor() if k.startswith(b"S2"))
    bands = st_load(bytes(buf))
    img = render_rgb(np.stack([bands[b] for b in RGB_BANDS]))
    png = io.BytesIO()
    img.save(png, format="PNG")
    questions = [
        G.build_question("Is there any coniferous forest in this image?", "binary"),
        G.build_question("Where can the <ref>pastures</ref> be found?", "bounding box"),
        G.build_question("Describe this satellite image.", "captioning"),
    ]
    ref = geochat_reference.remote(png.getvalue(), questions)

    tok, improc = _load_tokenizer_and_image_processor()
    img_rt = expand2square(Image.open(io.BytesIO(png.getvalue())).convert("RGB"), tuple(int(x * 255) for x in improc.image_mean))
    pixel = improc(images=[img_rt], return_tensors="pt")["pixel_values"]
    model = LlavaForConditionalGeneration.from_pretrained(GEOCHAT_HF_DIR, torch_dtype=torch.float16, device_map={"": 0})
    model.eval()

    checks = []
    for q, r in zip(questions, ref):
        ours = G.build_inference_ids(q, tok)
        theirs = []
        for t in r["input_ids"]:
            theirs.extend([G.IMAGE_TOKEN_ID] * G.IMAGE_SEQ_LEN if t == -200 else [t])
        ids = torch.tensor([ours], device="cuda")
        with torch.inference_mode():
            logits = model(input_ids=ids, pixel_values=pixel.to("cuda", torch.float16)).logits[0, -1, :32000].float().cpu().numpy()
            gen = model.generate(input_ids=ids, attention_mask=torch.ones_like(ids), pixel_values=pixel.to("cuda", torch.float16),
                                 do_sample=False, num_beams=1, max_new_tokens=40)
        new = gen[0, ids.shape[1]:].tolist()
        ref_logits = np.frombuffer(r["last_logits"], dtype=np.float32)[:32000]
        ref_pixel = np.frombuffer(r["pixel_values"], dtype=np.float32).reshape(pixel[0].shape)
        cos = float(np.dot(logits, ref_logits) / (np.linalg.norm(logits) * np.linalg.norm(ref_logits)))
        text = tok.decode(new, skip_special_tokens=True).strip()
        checks.append({
            "question": q,
            "input_ids_identical": ours == theirs,
            "input_ids_first_mismatch": next((i for i, (a, b) in enumerate(zip(ours, theirs)) if a != b), None),
            "pixel_max_abs_diff": float(np.abs(pixel[0].numpy() - ref_pixel).max()),
            "logits_cosine": cos,
            "logits_max_abs_diff": float(np.abs(logits - ref_logits).max()),
            "argmax_identical": int(logits.argmax()) == int(ref_logits.argmax()),
            "top5_overlap": len(set(np.argsort(-logits)[:5]) & set(np.argsort(-ref_logits)[:5])),
            "reference_text": r["generated_text"],
            "converted_text": text,
            "generation_identical": text == r["generated_text"],
        })
    del model
    torch.cuda.empty_cache()

    # The training/eval path runs the converted model in 4-bit; record what it says on the same inputs.
    q4 = _load_base_4bit()
    q4.eval()
    for q, c in zip(questions, checks):
        ids = torch.tensor([G.build_inference_ids(q, tok)], device="cuda")
        with torch.inference_mode():
            gen = q4.generate(input_ids=ids, attention_mask=torch.ones_like(ids), pixel_values=pixel.to("cuda", torch.bfloat16),
                              do_sample=False, num_beams=1, max_new_tokens=40)
        c["converted_4bit_text"] = tok.decode(gen[0, ids.shape[1]:], skip_special_tokens=True).strip()

    passed = all(
        c["input_ids_identical"] and c["pixel_max_abs_diff"] < 1e-2 and c["argmax_identical"] and c["logits_cosine"] > 0.995
        for c in checks
    )
    result = {
        "verified_at": _now(),
        "passed": passed,
        "criteria": "identical input ids; pixel max|diff|<1e-2; identical next-token argmax; logits cosine>0.995",
        "reference": f"github.com/mbzuai-oryx/GeoChat@{GEOCHAT_CODE_COMMIT} with transformers 4.31.0, fp16",
        "converted": "llava-hf layout, transformers 4.51.3, fp16 (4-bit output recorded for information)",
        "sample_patch": key.decode(),
        "checks": checks,
    }
    _write_json(out_path, result)
    VOLUME.commit()
    return result


# ----------------------------------------------------------------------------- stage 3: splits

@app.function(image=train_image, volumes=volumes, timeout=1800, cpu=2, memory=16384)
def build_splits(mode: str, n_train: int, n_eval: int) -> dict:
    import lmdb
    import pandas as pd
    from satq_m2 import splits as S

    VOLUME.reload()
    d = m2_ckpt_dir(mode) / "data"
    stats_path = d / "split_stats.json"
    if stats_path.exists():
        stats = json.loads(stats_path.read_text())
        if (stats["train"]["n"], stats["eval"]["n"]) != (n_train, n_eval):
            raise ValueError(
                f"{d} already holds a {stats['train']['n']}/{stats['eval']['n']} split; refusing to mix it with "
                f"{n_train}/{n_eval}. Use a fresh mode directory."
            )
        return stats

    ann = pd.read_parquet(PARQUET_PATH, filters=[("country", "==", "Lithuania"), ("season", "==", "Summer")])
    env = lmdb.open(str(LMDB_PATH), readonly=True, lock=False, readahead=False)
    with env.begin() as txn:
        available = {p for p in ann["patch_id"].unique() if txn.get(p.encode()) is not None}
    train, held_out, stats = S.build_splits(ann, available, n_train, n_eval, seed=SEED)
    stats.update({
        "annotations": f"{BEN_TXT_REPO}@{BEN_TXT_REVISION} (BigEarthNet.txt.parquet)",
        "imagery": f"{BEN_LMDB_REPO} (Sentinel-2 B04/B03/B02, 120x120 @10m)",
        "filters": {"country": "Lithuania", "season": "Summer"},
        "patches_with_imagery": len(available),
        "patches_in_filter": int(ann["patch_id"].nunique()),
    })
    d.mkdir(parents=True, exist_ok=True)
    train.to_parquet(d / "train.parquet", index=False)
    held_out.to_parquet(d / "eval.parquet", index=False)
    _write_json(stats_path, stats)
    log_event(mode, "splits_built", train=stats["train"]["by_type"], eval=stats["eval"]["by_type"])
    VOLUME.commit()
    return stats


# ----------------------------------------------------------------------------- stage 4: evaluate

@app.function(image=train_image, volumes=volumes, gpu="A10G", timeout=7200)
def evaluate(mode: str, which: str) -> dict:
    """which='base': GeoChat as converted; which='adapted': GeoChat + M2_CKPT_DIR/final LoRA."""
    import torch
    from satq_m2 import geochat as G
    from satq_m2 import metrics as M
    from satq_m2.imagery import M2Dataset

    VOLUME.reload()
    ckpt = m2_ckpt_dir(mode)
    out_dir = ckpt / "eval"
    metrics_path = out_dir / f"{which}_metrics.json"
    adapter_dir = ckpt / "final"
    adapter_sha = None
    if which == "adapted":
        manifest = json.loads((ckpt / "final_manifest.json").read_text())
        adapter_sha = manifest["files"]["adapter_model.safetensors"]["sha256"]
    if metrics_path.exists():
        prev = json.loads(metrics_path.read_text())
        if prev.get("adapter_sha256") == adapter_sha:
            return prev

    tok, improc = _load_tokenizer_and_image_processor()
    ds = M2Dataset(str(ckpt / "data" / "eval.parquet"), str(LMDB_PATH))
    model = _load_base_4bit()
    if which == "adapted":
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, str(adapter_dir))
    elif which != "base":
        raise ValueError(which)
    model.eval()

    started = time.time()
    order = sorted(range(len(ds)), key=lambda i: ds.meta.iloc[i]["type"])
    records = []
    for start in range(0, len(order), EVAL_BATCH):
        idxs = order[start: start + EVAL_BATCH]
        items = [ds[i] for i in idxs]
        # batches never mix types; a type boundary just starts a new (smaller) batch
        by_type: dict[str, list] = {}
        for it in items:
            by_type.setdefault(it["type"], []).append(it)
        for qtype, group in by_type.items():
            seqs = [G.build_inference_ids(it["question"], tok) for it in group]
            width = max(map(len, seqs))
            ids = torch.full((len(seqs), width), G.PAD_TOKEN_ID, dtype=torch.long)
            mask = torch.zeros_like(ids)
            for j, s in enumerate(seqs):  # left padding for batched generation
                ids[j, width - len(s):] = torch.tensor(s)
                mask[j, width - len(s):] = 1
            pixel = improc(images=[it["image"] for it in group], return_tensors="pt")["pixel_values"]
            with torch.inference_mode():
                gen = model.generate(
                    input_ids=ids.cuda(), attention_mask=mask.cuda(), pixel_values=pixel.to("cuda", torch.bfloat16),
                    do_sample=False, num_beams=1, max_new_tokens=MAX_NEW_TOKENS[qtype],
                    pad_token_id=G.PAD_TOKEN_ID, eos_token_id=tok.eos_token_id,
                )
            for it, g in zip(group, gen[:, width:]):
                pred = tok.decode(g, skip_special_tokens=True).strip()
                records.append({
                    "row_id": it["row_id"], "patch_id": it["patch_id"], "type": it["type"], "category": it["category"],
                    "question": it["question"], "reference_output": it["reference_output"], "prediction": pred,
                    "score": M.score_record(it["type"], pred, it["reference_output"]),
                })
        print(f"[eval:{which}] {len(records)}/{len(ds)}", flush=True)

    result = {
        "which": which,
        "mode": mode,
        "evaluated_at": _now(),
        "n": len(records),
        "eval_manifest_hash": json.loads((ckpt / "data" / "split_stats.json").read_text())["eval"]["manifest_hash"],
        "adapter_sha256": adapter_sha,
        "quantization": "4-bit NF4 (same as training)",
        "decoding": "greedy",
        "seconds": round(time.time() - started, 1),
        "metrics": M.aggregate(records),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / f"{which}_predictions.jsonl", "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    _write_json(metrics_path, result)
    log_event(mode, "eval_done", which=which, n=len(records), seconds=result["seconds"])
    VOLUME.commit()
    return result


# ----------------------------------------------------------------------------- stage 5: train

def _train(mode: str) -> dict:
    import torch
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from satq_m2 import geochat as G
    from satq_m2.imagery import M2Dataset
    from transformers import Trainer, TrainerCallback, TrainingArguments, set_seed
    from transformers.trainer_utils import get_last_checkpoint

    VOLUME.reload()
    cfg = RUN_CONFIGS[mode]
    ckpt = m2_ckpt_dir(mode)
    final_dir = ckpt / "final"
    summary_path = ckpt / "train_summary.json"
    if (ckpt / "final_manifest.json").exists():
        log_event(mode, "train_skipped", reason="final adapter already exists")
        return json.loads(summary_path.read_text())

    resume = get_last_checkpoint(str(ckpt)) if ckpt.exists() else None
    log_event(mode, "train_start", resume_from_checkpoint=resume, gpu=torch.cuda.get_device_name(0))
    set_seed(SEED)

    tok, improc = _load_tokenizer_and_image_processor()
    train_ds = M2Dataset(str(ckpt / "data" / "train.parquet"), str(LMDB_PATH))

    model = _load_base_4bit()
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(
        model, use_gradient_checkpointing=True, gradient_checkpointing_kwargs={"use_reentrant": False}
    )
    # Needed with gradient checkpointing on a frozen 4-bit base: without it the checkpointed
    # blocks get inputs that don't require grad and the LoRA weights silently receive no gradient.
    model.enable_input_require_grads()
    # Architecture decision: a FRESH LoRA on GeoChat, not a continuation of the M1 EuroSAT adapter.
    # M1 was trained on generic LLaVA-1.5 (different base weights), so its adapter doesn't apply to
    # GeoChat, and GeoChat is already remote-sensing adapted by its authors.
    model = get_peft_model(model, LoraConfig(**LORA, target_modules=LORA_TARGET_REGEX, bias="none", task_type="CAUSAL_LM"))
    trainable, total = model.get_nb_trainable_parameters()
    lora_modules = sorted({n.split(".lora_A")[0].rsplit(".", 1)[-1] for n, _ in model.named_parameters() if "lora_A" in n})
    if any("vision" in n for n, p in model.named_parameters() if p.requires_grad):
        raise RuntimeError("LoRA leaked into the vision tower")
    print(f"trainable params {trainable:,} / {total:,}; LoRA on {lora_modules}", flush=True)

    # Token counts for throughput reporting (text is cheap to tokenize; image tokens are constant)
    seq_tokens = sum(len(G.build_training_ids(q, t, tok)[0]) for q, t in zip(
        (G.build_question(r.input, r.type) for r in train_ds.meta.itertuples()),
        (G.build_target(r.output, r.type) for r in train_ds.meta.itertuples()),
    ))

    class Collator:
        def __call__(self, examples):
            enc = [G.build_training_ids(ex["question"], ex["target"], tok) for ex in examples]
            width = max(len(ids) for ids, _ in enc)
            input_ids = torch.full((len(enc), width), G.PAD_TOKEN_ID, dtype=torch.long)
            labels = torch.full((len(enc), width), -100, dtype=torch.long)
            attn = torch.zeros((len(enc), width), dtype=torch.long)
            for i, (ids, lab) in enumerate(enc):  # right padding for training
                input_ids[i, : len(ids)] = torch.tensor(ids)
                labels[i, : len(lab)] = torch.tensor(lab)
                attn[i, : len(ids)] = 1
            pixel = improc(images=[ex["image"] for ex in examples], return_tensors="pt")["pixel_values"]
            return {"input_ids": input_ids, "attention_mask": attn, "labels": labels, "pixel_values": pixel}

    examples_per_step = cfg["batch_size"] * cfg["grad_accum"]

    def per_example_loss(outputs, labels, num_items_in_batch=None):
        """Mean answer-token CE per example, averaged over the examples of one optimizer step.

        Two reasons for not using LLaVA's built-in loss:
        - Task balance: a token-level mean lets a ~220-token caption outweigh a 2-token yes/no answer
          ~100:1, so VQA and grounding would barely train. Here each example counts equally.
        - Scale: transformers 4.51 sees LLaVA's **lm_kwargs, assumes the model normalises across
          gradient accumulation and skips dividing by grad_accum, but LLaVA returns a plain mean, so
          the logged loss came out grad_accum (4x) too high. Dividing by examples_per_step here makes
          the logged per-step loss the true mean.
        """
        logits = outputs["logits"] if isinstance(outputs, dict) else outputs[0]
        shift_labels = labels[:, 1:].to(logits.device)
        tok = torch.nn.functional.cross_entropy(
            logits[:, :-1, :].float().transpose(1, 2), shift_labels, ignore_index=-100, reduction="none"
        )
        mask = shift_labels.ne(-100)
        per_example = (tok * mask).sum(1) / mask.sum(1).clamp(min=1)
        return per_example.sum() / examples_per_step

    loss_path = ckpt / "loss_history.json"

    class EvidenceCallback(TrainerCallback):
        """Persists the loss history and an event log, and commits the volume on every save."""

        def __init__(self):
            self.history: list[dict] = []
            self.last_save = time.time()

        def on_train_begin(self, args, state, control, **kw):
            # state is already restored from the checkpoint here when resuming
            if loss_path.exists():
                self.history = [h for h in json.loads(loss_path.read_text()) if h["step"] <= state.global_step]
            if resume:
                log_event(mode, "resumed", from_checkpoint=resume, global_step=state.global_step,
                          loss_history_kept=len(self.history))

        def on_log(self, args, state, control, logs=None, **kw):
            if logs and "loss" in logs:
                self.history.append({
                    "step": state.global_step, "loss": logs["loss"], "learning_rate": logs.get("learning_rate"),
                    "grad_norm": logs.get("grad_norm"), "epoch": logs.get("epoch"), "time": _now(),
                })
                _write_json(loss_path, self.history)

        def on_step_end(self, args, state, control, **kw):
            # Bound lost work on preemption by wall-clock time too, whatever the step time turns out to be
            if time.time() - self.last_save > cfg["save_every_min"] * 60:
                control.should_save = True

        def on_save(self, args, state, control, **kw):
            self.last_save = time.time()
            path = Path(args.output_dir) / f"checkpoint-{state.global_step}"
            size = sum(p.stat().st_size for p in path.rglob("*") if p.is_file())
            log_event(mode, "checkpoint_saved", step=state.global_step, path=str(path), bytes=size)
            VOLUME.commit()

    args = TrainingArguments(
        output_dir=str(ckpt),
        per_device_train_batch_size=cfg["batch_size"],
        gradient_accumulation_steps=cfg["grad_accum"],
        num_train_epochs=cfg["epochs"],
        learning_rate=cfg["lr"],
        lr_scheduler_type="cosine",
        warmup_ratio=0.03,
        max_grad_norm=1.0,
        bf16=True,  # not fp16: fp16 with a 4-bit base is prone to NaN losses
        logging_steps=1,
        logging_first_step=True,
        save_strategy="steps",
        save_steps=cfg["save_steps"],
        save_total_limit=2,
        dataloader_num_workers=4,
        remove_unused_columns=False,
        report_to="none",
        seed=SEED,
        data_seed=SEED,
    )
    trainer = Trainer(
        model=model, args=args, train_dataset=train_ds, data_collator=Collator(),
        compute_loss_func=per_example_loss, callbacks=[EvidenceCallback()],
    )
    t0 = time.time()
    out = trainer.train(resume_from_checkpoint=resume)
    segment_seconds = time.time() - t0

    trainer.model.save_pretrained(str(final_dir))
    files = _dir_manifest(final_dir)
    if files.get("adapter_model.safetensors", {}).get("bytes", 0) == 0:
        raise RuntimeError("Final adapter file missing or empty")
    _write_json(ckpt / "final_manifest.json", {"path": str(final_dir), "files": files, "saved_at": _now()})

    history = json.loads(loss_path.read_text())
    k = max(1, len(history) // 5)
    first, last = history[:k], history[-k:]
    summary = {
        "mode": mode,
        "config": cfg,
        "lora": {**LORA, "target_modules": LORA_TARGET_REGEX, "modules": lora_modules},
        "trainable_params": trainable,
        "total_params": total,
        "train_rows": len(train_ds),
        "epochs": cfg["epochs"],
        "global_steps": trainer.state.global_step,
        "effective_batch": cfg["batch_size"] * cfg["grad_accum"],
        "train_tokens_per_epoch": seq_tokens,
        "resumed_from_checkpoint": resume,
        "this_segment_seconds": round(segment_seconds, 1),
        "trainer_metrics_this_segment": out.metrics,
        "loss_first_20pct_mean": sum(h["loss"] for h in first) / len(first),
        "loss_last_20pct_mean": sum(h["loss"] for h in last) / len(last),
        "loss_any_nan": any(h["loss"] != h["loss"] for h in history),
    }
    summary["loss_decreased"] = summary["loss_last_20pct_mean"] < summary["loss_first_20pct_mean"]
    _write_json(summary_path, summary)
    log_event(mode, "train_done", global_step=trainer.state.global_step, final_adapter_bytes=files["adapter_model.safetensors"]["bytes"],
              loss_decreased=summary["loss_decreased"])
    VOLUME.commit()
    return summary


@app.function(image=train_image, volumes=volumes, gpu="A10G", timeout=45 * 60)
def train_debug() -> dict:
    return _train("debug")


@app.function(image=train_image, volumes=volumes, gpu="A10G", timeout=4 * 3600)
def train_scaled() -> dict:
    return _train("scaled")


@app.function(image=train_image, volumes=volumes, timeout=600, cpu=1, memory=4096)
def export_samples(mode: str = "scaled", n: int = 8) -> list[str]:
    """Render held-out eval patches (never seen in training) to PNG for smoke tests and demos.

    Writes <M2_CKPT_DIR>/samples/<patch_id>.png plus samples.json with each patch's questions and
    reference answers.
    """
    from satq_m2.imagery import M2Dataset

    VOLUME.reload()
    ckpt = m2_ckpt_dir(mode)
    ds = M2Dataset(str(ckpt / "data" / "eval.parquet"), str(LMDB_PATH))
    out = ckpt / "samples"
    out.mkdir(parents=True, exist_ok=True)
    samples: dict[str, list] = {}
    for i in range(len(ds)):
        pid = ds.meta.iloc[i]["patch_id"]
        if pid not in samples and len(samples) >= n:
            continue
        item = ds[i]
        if pid not in samples:
            item["image"].save(out / f"{pid}.png")
            samples[pid] = []
        samples[pid].append({k: item[k] for k in ("type", "question", "reference_output")})
    _write_json(out / "samples.json", samples)
    VOLUME.commit()
    return sorted(samples)


# ----------------------------------------------------------------------------- orchestration

@app.function(image=train_image, volumes=volumes, timeout=8 * 3600, cpu=1, memory=2048)
def pipeline(mode: str, n_train: int, app_id: str, git_commit: str, until: str = "all") -> dict:
    from satq_m2 import metrics as M

    if mode not in RUN_CONFIGS:
        raise ValueError(f"mode must be one of {list(RUN_CONFIGS)}")
    cfg = dict(RUN_CONFIGS[mode])
    if n_train:
        cfg["n_train"] = n_train
    VOLUME.reload()
    ckpt = m2_ckpt_dir(mode)
    ckpt.mkdir(parents=True, exist_ok=True)
    with open(ckpt / "runs.jsonl", "a") as f:
        f.write(json.dumps({"ts": _now(), "app_id": app_id, "git_commit": git_commit, "until": until, "config": cfg}) + "\n")
    VOLUME.commit()

    ensure_dataset.remote()
    conversion = convert_geochat.remote()
    verification = verify_geochat.remote()
    if not verification["passed"]:
        raise RuntimeError("Converted GeoChat does not match the reference implementation; see verification.json")
    if until == "verify":
        return {"conversion": conversion, "verification": verification}

    stats = build_splits.remote(mode, cfg["n_train"], cfg["n_eval"])
    base = evaluate.remote(mode, "base")
    if until == "base_eval":
        return {"splits": stats, "base": base["metrics"]}

    summary = (train_debug if mode == "debug" else train_scaled).remote()
    adapted = evaluate.remote(mode, "adapted")

    rows = M.before_after_table(base["metrics"], adapted["metrics"])
    VOLUME.reload()
    results = {
        "mode": mode,
        "base_model": f"{GEOCHAT_REPO}@{GEOCHAT_REVISION} (converted to llava-hf; verification passed)",
        "adapter": str(ckpt / "final"),
        "eval_split": f"BigEarthNet.txt official test split, Lithuania/Summer, n={adapted['n']}",
        "train": {k: summary[k] for k in ("train_rows", "global_steps", "loss_first_20pct_mean", "loss_last_20pct_mean", "loss_decreased")},
        "table": rows,
        "table_markdown": M.table_markdown(rows),
        "finalized_at": _now(),
    }
    _write_json(ckpt / "results.json", results)
    log_event(mode, "pipeline_done", app_id=app_id)
    VOLUME.commit()
    return results


@app.local_entrypoint()
def main(mode: str = "debug", n_train: int = 0, until: str = "all"):
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "modal_worker"], capture_output=True, text=True).stdout.strip()
        commit += "+dirty" if dirty else ""
    except Exception:
        commit = "unknown"
    app_id = getattr(app, "app_id", None) or "unknown"
    print(f"app_id={app_id} git={commit} mode={mode} until={until}")
    result = pipeline.remote(mode, n_train, app_id, commit, until)
    print(json.dumps({k: v for k, v in result.items() if k != "table"}, indent=2, default=str)[:6000])
