"""End-to-end check of the deployed GeoChat worker through the backend's own adapter.

Uses held-out BigEarthNet.txt test patches exported by `train_m2.py::export_samples`, so the
inputs are real Sentinel-2 previews the adapter never saw in training.

  modal run modal_worker/train_m2.py::export_samples --mode scaled --n 3
  modal volume get satquery-m1-vol /checkpoints/m2_geochat/scaled/samples docs/evidence/m2/scaled/
  backend/.venv/bin/python modal_worker/smoke_test_infer.py docs/evidence/m2/scaled/samples
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.models.geochat import GeoChatAdapter  # noqa: E402


def main(sample_dir: str) -> None:
    d = Path(sample_dir)
    samples = json.loads((d / "samples.json").read_text())
    adapter = GeoChatAdapter(mode="modal")
    report = []
    for pid, qas in samples.items():
        png = (d / f"{pid}.png").read_bytes()
        t0 = time.time()
        cap = adapter.caption(png, band_map="B4/B3/B2")
        entry = {"patch_id": pid, "caption": cap.text, "caption_confidence": cap.confidence, "seconds_first_call": None}
        entry["seconds_first_call"] = round(time.time() - t0, 1)
        vqa = next((q for q in qas if q["type"] in ("binary", "mcq")), None)
        if vqa:
            ans = adapter.answer(png, vqa["question"], band_map="B4/B3/B2")
            entry["vqa"] = {"question": vqa["question"], "reference": vqa["reference_output"], "answer": ans.text, "confidence": ans.confidence}
        ref = next((q for q in qas if q["type"] == "bounding box" and "<p>" in q["question"]), None)
        if ref:
            phrase = ref["question"].split("<p>")[1].split("</p>")[0]
            boxes = adapter.ground(png, phrase, band_map="B4/B3/B2")
            entry["grounding"] = {"phrase": phrase, "reference": ref["reference_output"], "boxes": [b.__dict__ for b in boxes]}
        report.append(entry)
        print(json.dumps(entry, indent=2))
    (d / "smoke_test_report.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main(sys.argv[1])
