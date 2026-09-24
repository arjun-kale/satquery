"""Modal inference worker: GeoChat-7B (converted, see train_m2.py) + the M2 BigEarthNet.txt LoRA.

App/class names are unchanged so backend/app/models/geochat.py keeps working.
Deploy: modal deploy modal_worker/infer.py

- Prompts use the same GeoChat conventions the adapter was trained and evaluated with (satq_m2.geochat).
- ``ground`` returns the boxes the model actually generated, parsed from GeoChat's
  ``{<x1><y1><x2><y2>|<theta>}`` syntax into 0-1 fractions (y from the top, as the UI expects).
  No box in the output means no boxes returned.
- ``confidence`` is the geometric-mean probability of the generated tokens under greedy decoding.
  It is a real model-derived number, but it is not a calibrated probability of correctness.
"""

import io
import json
import math
from pathlib import Path

import modal

VOLUME = modal.Volume.from_name("satquery-m1-vol", create_if_missing=True)
VOL = Path("/vol")
BASE_DIR = VOL / "models" / "geochat-7b-llava-hf"
ADAPTER_DIR = VOL / "checkpoints" / "m2_geochat" / "scaled" / "final"
HERE = Path(__file__).resolve().parent

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("torch==2.6.0", "torchvision==0.21.0", index_url="https://download.pytorch.org/whl/cu124")
    .pip_install(
        "transformers==4.51.3", "peft==0.15.2", "accelerate==1.6.0", "bitsandbytes==0.45.5",
        "sentencepiece==0.2.0", "protobuf", "safetensors", "pillow", "numpy",
    )
    .add_local_dir(HERE / "satq_m2", "/root/satq_m2")
)

app = modal.App("satquery-m1-infer")


@app.cls(
    image=image,
    gpu="A10G",
    volumes={str(VOL): VOLUME},
    timeout=600,
    # Zero-budget default: no always-on GPU ($1.10/h ≈ $26/day). Expect a cold start of ~1-2 min
    # after 5 idle minutes; raise min_containers for a demo window.
    min_containers=0,
    scaledown_window=300,
)
class GeoChatInfer:
    @modal.enter()
    def setup(self):
        import torch
        from transformers import BitsAndBytesConfig, CLIPImageProcessor, LlamaTokenizer, LlavaForConditionalGeneration

        if not BASE_DIR.exists():
            raise RuntimeError(f"{BASE_DIR} missing: run `modal run modal_worker/train_m2.py --until verify` first")
        self.tok = LlamaTokenizer.from_pretrained(BASE_DIR)
        self.improc = CLIPImageProcessor.from_pretrained(BASE_DIR)
        model = LlavaForConditionalGeneration.from_pretrained(
            BASE_DIR,
            quantization_config=BitsAndBytesConfig(
                load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True, llm_int8_skip_modules=["vision_tower", "multi_modal_projector", "lm_head"],
            ),
            torch_dtype=torch.bfloat16,
            device_map={"": 0},
        )
        manifest = ADAPTER_DIR.parent / "final_manifest.json"
        if manifest.exists():
            from peft import PeftModel

            model = PeftModel.from_pretrained(model, str(ADAPTER_DIR))
            sha = json.loads(manifest.read_text())["files"]["adapter_model.safetensors"]["sha256"]
            self.weights = f"geochat-7b + m2-lora (sha256 {sha[:12]})"
        else:
            self.weights = "geochat-7b (no M2 adapter found; base model)"
        self.model = model.eval()
        print(f"Loaded {self.weights}")

    def _generate(self, png_bytes: bytes, question: str, max_new_tokens: int) -> tuple[str, float]:
        import torch
        from PIL import Image
        from satq_m2 import geochat as G
        from satq_m2.imagery import expand2square

        img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
        img = expand2square(img, tuple(int(x * 255) for x in self.improc.image_mean))
        pixel = self.improc(images=[img], return_tensors="pt")["pixel_values"].to("cuda", torch.bfloat16)
        ids = torch.tensor([G.build_inference_ids(question, self.tok)], device="cuda")
        with torch.inference_mode():
            out = self.model.generate(
                input_ids=ids, attention_mask=torch.ones_like(ids), pixel_values=pixel,
                do_sample=False, num_beams=1, max_new_tokens=max_new_tokens,
                output_scores=True, return_dict_in_generate=True,
                pad_token_id=G.PAD_TOKEN_ID, eos_token_id=self.tok.eos_token_id,
            )
        new = out.sequences[0, ids.shape[1]:]
        logps = [
            torch.log_softmax(s[0].float(), -1)[t].item()
            for s, t in zip(out.scores, new) if t.item() != self.tok.eos_token_id
        ]
        conf = math.exp(sum(logps) / len(logps)) if logps else 0.0
        return self.tok.decode(new, skip_special_tokens=True).strip(), conf

    @modal.method()
    def answer(self, png_bytes: bytes, query: str, band_map: str = "B4/B3/B2") -> dict:
        text, conf = self._generate(png_bytes, query, 128)
        return {"text": text, "confidence": conf, "weights": self.weights, "band_map": band_map}

    @modal.method()
    def caption(self, png_bytes: bytes, band_map: str = "B4/B3/B2") -> dict:
        text, conf = self._generate(
            png_bytes, "Describe this satellite image, including the land cover types and their spatial layout.", 512
        )
        return {"text": text, "confidence": conf, "weights": self.weights, "band_map": band_map}

    @modal.method()
    def ground(self, png_bytes: bytes, query: str, band_map: str = "B4/B3/B2") -> dict:
        import re

        from satq_m2.metrics import parse_box

        text, conf = self._generate(png_bytes, f"[refer] Give me the location of <p>{query}</p>", 96)
        boxes = []
        for m in re.finditer(r"\{[^{}]*\}", text):
            b = parse_box(m.group(0))
            if b:
                boxes.append({"label": query, "confidence": conf, "x_min": b[0], "y_min": b[1], "x_max": b[2], "y_max": b[3]})
        return {"text": text, "confidence": conf, "boxes": boxes, "weights": self.weights, "band_map": band_map}
