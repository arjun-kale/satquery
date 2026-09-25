"""Hugging Face Inference Endpoint handler for the SatQuery VLM (GeoChat-7B + M2 LoRA).

Mirrors modal_worker/infer.py so the endpoint returns exactly what the Modal worker did:
same 4-bit NF4 loading, same GeoChat prompt conventions (satq_m2), same confidence
(geometric-mean token probability under greedy decoding), same box parsing.

Repository layout expected at ``path`` (the endpoint's model repo):
    config.json, model-*.safetensors, tokenizer files   converted GeoChat-7B (llava-hf layout)
    m2/adapter_model.safetensors, m2/adapter_config.json, m2/final_manifest.json   M2 LoRA
    satq_m2/                                            prompt / box helpers
    handler.py, requirements.txt                        this file

Request:  {"inputs": {"method": "caption" | "answer" | "ground",
                      "image": "<base64 PNG>", "query": "...", "band_map": "B04/B03/B02"}}
Response: {"text", "confidence", "weights", "band_map"} (+ "boxes" for ground)

``caption`` runs with the M2 adapter disabled (base weights): M2 was trained on
Lithuania/Summer captions only and reproduces that template elsewhere. ``answer`` and
``ground`` use the adapter. Every response names the weights that produced it.
"""

from __future__ import annotations

import base64
import contextlib
import io
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

CAPTION_PROMPT = "Describe this satellite image, including the land cover types and their spatial layout."


class EndpointHandler:
    def __init__(self, path: str = ""):
        import torch
        from transformers import BitsAndBytesConfig, CLIPImageProcessor, LlamaTokenizer, LlavaForConditionalGeneration

        root = Path(path or ".")
        sys.path.insert(0, str(root))  # satq_m2 ships inside the repo

        self.tok = LlamaTokenizer.from_pretrained(root)
        self.improc = CLIPImageProcessor.from_pretrained(root)
        model = LlavaForConditionalGeneration.from_pretrained(
            root,
            quantization_config=BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.bfloat16,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
                llm_int8_skip_modules=["vision_tower", "multi_modal_projector", "lm_head"],
            ),
            torch_dtype=torch.bfloat16,
            device_map={"": 0},
        )
        self.base_weights = "geochat-7b (base weights, M2 adapter off)"
        adapter = root / "m2"
        self.has_adapter = (adapter / "adapter_model.safetensors").exists()
        if self.has_adapter:
            from peft import PeftModel

            model = PeftModel.from_pretrained(model, str(adapter))
            manifest = adapter / "final_manifest.json"
            sha = json.loads(manifest.read_text())["files"]["adapter_model.safetensors"]["sha256"] if manifest.exists() else ""
            self.weights = f"geochat-7b + m2-lora (sha256 {sha[:12]})"
        else:
            self.weights = "geochat-7b (no M2 adapter found; base model)"
        self.model = model.eval()

    def _generate(self, png: bytes, question: str, max_new_tokens: int, use_adapter: bool = True) -> tuple[str, float]:
        import torch
        from PIL import Image
        from satq_m2 import geochat as G
        from satq_m2.imagery import expand2square

        img = Image.open(io.BytesIO(png)).convert("RGB")
        img = expand2square(img, tuple(int(x * 255) for x in self.improc.image_mean))
        pixel = self.improc(images=[img], return_tensors="pt")["pixel_values"].to("cuda", torch.bfloat16)
        ids = torch.tensor([G.build_inference_ids(question, self.tok)], device="cuda")
        base_only = self.model.disable_adapter() if self.has_adapter and not use_adapter else contextlib.nullcontext()
        with torch.inference_mode(), base_only:
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

    def __call__(self, data: dict[str, Any]) -> dict[str, Any]:
        req = data.get("inputs", data)
        method = req.get("method")
        png = base64.b64decode(req["image"])
        query = req.get("query", "")
        band_map = req.get("band_map", "B4/B3/B2")

        if method == "answer":
            text, conf = self._generate(png, query, 128)
            return {"text": text, "confidence": conf, "weights": self.weights, "band_map": band_map}
        if method == "caption":
            text, conf = self._generate(png, CAPTION_PROMPT, 512, use_adapter=False)
            return {"text": text, "confidence": conf, "weights": self.base_weights, "band_map": band_map}
        if method == "ground":
            from satq_m2.metrics import parse_box

            text, conf = self._generate(png, f"[refer] Give me the location of <p>{query}</p>", 96)
            boxes = []
            for m in re.finditer(r"\{[^{}]*\}", text):
                b = parse_box(m.group(0))
                if b:
                    boxes.append({"label": query, "confidence": conf, "x_min": b[0], "y_min": b[1], "x_max": b[2], "y_max": b[3]})
            return {"text": text, "confidence": conf, "boxes": boxes, "weights": self.weights, "band_map": band_map}
        return {"error": f"unknown method {method!r}; expected caption, answer or ground"}
