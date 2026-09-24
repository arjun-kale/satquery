"""Per-type scoring for BigEarthNet.txt predictions.

binary / mcq (VQA): exact match on the parsed answer (first word / standalone option letter).
bounding box (grounding): Acc@0.5 IoU and mean IoU; accepts GeoChat ``{<x1><y1><x2><y2>|<t>}``
    (0-100), BigEarthNet.txt ``[x1 y1, x2 y2]`` (0-1) and plain 4-number lists, so the base model
    is not penalised for a formatting choice.
captioning: ROUGE-L F1, corpus BLEU-4 and LULC-class F1 (which of the 19 BigEarthNet classes the
    caption mentions vs. the reference: a factual check that n-gram overlap can't give).
Unparseable answers count as wrong; they are never dropped from the denominator.
"""

from __future__ import annotations

import math
import re
from collections import Counter

_GEOCHAT_BOX = re.compile(r"\{\s*<(\d+(?:\.\d+)?)>\s*<(\d+(?:\.\d+)?)>\s*<(\d+(?:\.\d+)?)>\s*<(\d+(?:\.\d+)?)>")
_BEN_BOX = re.compile(r"\[\s*([\d.]+)\s+([\d.]+)\s*,\s*([\d.]+)\s+([\d.]+)\s*\]")
_LIST_BOX = re.compile(r"[\[(]\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*[\])]")

LULC_CLASS_PATTERNS = {
    "urban fabric": r"urban fabric",
    "industrial or commercial units": r"industrial or commercial",
    "arable land": r"arable land",
    "permanent crops": r"permanent crop",
    "pastures": r"pasture",
    "complex cultivation patterns": r"complex cultivation",
    "agriculture with natural vegetation": r"principally occupied by agriculture|significant areas of natural vegetation",
    "agro-forestry areas": r"agro-?forestry",
    "broad-leaved forest": r"broad-?leaved|broadleaf",
    "coniferous forest": r"coniferous",
    "mixed forest": r"mixed forest",
    "natural grassland and sparsely vegetated areas": r"natural grassland|sparsely vegetated",
    "moors, heathland and sclerophyllous vegetation": r"moors|heathland|sclerophyllous",
    "transitional woodland, shrub": r"transitional woodland",
    "beaches, dunes, sands": r"beach|dunes|sands",
    "inland wetlands": r"inland wetland",
    "coastal wetlands": r"coastal wetland",
    "inland waters": r"inland water",
    "marine waters": r"marine water",
}


def parse_box(text: str):
    for rx, scale in ((_GEOCHAT_BOX, 100.0), (_BEN_BOX, 1.0), (_LIST_BOX, None)):
        m = rx.search(text)
        if m:
            v = [float(x) for x in m.groups()]
            s = scale if scale is not None else (100.0 if max(v) > 1.0 else 1.0)
            v = [min(max(x / s, 0.0), 1.0) for x in v]
            return (min(v[0], v[2]), min(v[1], v[3]), max(v[0], v[2]), max(v[1], v[3]))
    return None


def box_iou(a, b) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def parse_binary(text: str):
    m = re.match(r"\W*(yes|no)\b", text.strip().lower())
    return m.group(1) if m else None


def parse_mcq(text: str):
    # The letter must stand alone ("b", "b)", "(b).") so the article "a" in a sentence doesn't count
    m = re.match(r"\W*\(?([a-d])(?:[).:,]|\s*$)", text.strip().lower())
    return m.group(1) if m else None


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def rouge_l_f1(pred: str, ref: str) -> float:
    p, r = _words(pred), _words(ref)
    if not p or not r:
        return 0.0
    prev = [0] * (len(r) + 1)
    for pw in p:
        cur = [0]
        for j, rw in enumerate(r):
            cur.append(prev[j] + 1 if pw == rw else max(prev[j + 1], cur[j]))
        prev = cur
    lcs = prev[-1]
    if lcs == 0:
        return 0.0
    prec, rec = lcs / len(p), lcs / len(r)
    return 2 * prec * rec / (prec + rec)


def corpus_bleu4(preds: list[str], refs: list[str]) -> float:
    matches, totals = [0] * 4, [0] * 4
    pred_len = ref_len = 0
    for pred, ref in zip(preds, refs):
        p, r = _words(pred), _words(ref)
        pred_len += len(p)
        ref_len += len(r)
        for n in range(1, 5):
            pc = Counter(tuple(p[i : i + n]) for i in range(len(p) - n + 1))
            rc = Counter(tuple(r[i : i + n]) for i in range(len(r) - n + 1))
            matches[n - 1] += sum(min(c, rc[g]) for g, c in pc.items())
            totals[n - 1] += max(len(p) - n + 1, 0)
    if pred_len == 0 or min(matches) == 0:
        return 0.0
    log_prec = sum(math.log(m / t) for m, t in zip(matches, totals)) / 4
    bp = 1.0 if pred_len > ref_len else math.exp(1 - ref_len / pred_len)
    return bp * math.exp(log_prec)


def lulc_classes(text: str) -> set[str]:
    t = text.lower()
    return {name for name, rx in LULC_CLASS_PATTERNS.items() if re.search(rx, t)}


def lulc_f1(pred: str, ref: str) -> float:
    p, r = lulc_classes(pred), lulc_classes(ref)
    if not p and not r:
        return 1.0
    tp = len(p & r)
    if tp == 0:
        return 0.0
    prec, rec = tp / len(p), tp / len(r)
    return 2 * prec * rec / (prec + rec)


def score_record(qtype: str, prediction: str, reference_output: str) -> dict:
    """Per-example score. ``reference_output`` is the raw BigEarthNet.txt answer."""
    if qtype == "binary":
        return {"correct": parse_binary(prediction) == reference_output.strip().lower()}
    if qtype == "mcq":
        return {"correct": parse_mcq(prediction) == reference_output.strip().lower()}
    if qtype == "bounding box":
        pred, gt = parse_box(prediction), parse_box(reference_output)
        if gt is None:
            raise ValueError(f"Reference box unparseable: {reference_output!r}")
        iou = box_iou(pred, gt) if pred is not None else 0.0
        return {"iou": iou, "correct": iou >= 0.5, "parsed": pred is not None}
    if qtype == "captioning":
        return {"rouge_l": rouge_l_f1(prediction, reference_output), "lulc_f1": lulc_f1(prediction, reference_output)}
    raise ValueError(qtype)


def aggregate(records: list[dict]) -> dict:
    """records: dicts with type, category, prediction, reference_output and a 'score' from score_record."""
    by_type: dict[str, list[dict]] = {}
    for r in records:
        by_type.setdefault(r["type"], []).append(r)
    out: dict[str, dict] = {}
    for qtype, rs in sorted(by_type.items()):
        n = len(rs)
        if qtype in ("binary", "mcq"):
            out[qtype] = {"n": n, "accuracy": sum(r["score"]["correct"] for r in rs) / n}
        elif qtype == "bounding box":
            out[qtype] = {
                "n": n,
                "acc_at_0.5_iou": sum(r["score"]["correct"] for r in rs) / n,
                "mean_iou": sum(r["score"]["iou"] for r in rs) / n,
                "parse_rate": sum(r["score"]["parsed"] for r in rs) / n,
            }
        elif qtype == "captioning":
            out[qtype] = {
                "n": n,
                "rouge_l": sum(r["score"]["rouge_l"] for r in rs) / n,
                "bleu4": corpus_bleu4([r["prediction"] for r in rs], [r["reference_output"] for r in rs]),
                "lulc_f1": sum(r["score"]["lulc_f1"] for r in rs) / n,
            }
        cats: dict[str, list[dict]] = {}
        for r in rs:
            cats.setdefault(r.get("category") or "(none)", []).append(r)
        if qtype != "captioning":
            out[qtype]["by_category"] = {
                c: {"n": len(v), "accuracy": sum(x["score"]["correct"] for x in v) / len(v)} for c, v in sorted(cats.items())
            }
        if qtype == "bounding box":
            for c, v in cats.items():
                out[qtype]["by_category"][c]["mean_iou"] = sum(x["score"]["iou"] for x in v) / len(v)
    return out


FULL_IMAGE_BOX = (0.0, 0.0, 1.0, 1.0)


def trivial_baselines(records: list[dict]) -> dict[str, float]:
    """What an image-blind strategy scores on the same references, keyed like before_after_table rows.

    binary / MCQ: always give the most common answer. Grounding: always return the whole image.
    A model gain only means something where it clearly beats these.
    """
    out: dict[str, float] = {}

    def majority(rs):
        return Counter(r["reference_output"].strip().lower() for r in rs).most_common(1)[0][1] / len(rs) if rs else None

    by_type: dict[str, list[dict]] = {}
    for r in records:
        by_type.setdefault(r["type"], []).append(r)
    out["binary"] = majority(by_type.get("binary", []))
    out["mcq"] = majority(by_type.get("mcq", []))
    out["mcq*"] = majority([r for r in by_type.get("mcq", []) if r.get("category") not in CONSTANT_ANSWER_MCQ])
    boxes = by_type.get("bounding box", [])
    for cat in ("point", "reference"):
        rs = [r for r in boxes if r.get("category") == cat]
        if rs:
            ious = [box_iou(FULL_IMAGE_BOX, parse_box(r["reference_output"])) for r in rs]
            out[f"bbox:{cat}"] = sum(i >= 0.5 for i in ious) / len(ious)
    if boxes:
        out["bounding box/mean_iou"] = sum(box_iou(FULL_IMAGE_BOX, parse_box(r["reference_output"])) for r in boxes) / len(boxes)
    return {k: v for k, v in out.items() if v is not None}


# Rows of the before/after table: (label, key, metric). Keys: a type, "mcq*" (image-dependent MCQ
# categories) or "bbox:<category>" (grounding split by prompt kind: the two behave very differently).
TABLE_ROWS = [
    ("VQA — binary (accuracy)", "binary", "accuracy"),
    ("VQA — multiple choice (accuracy)", "mcq", "accuracy"),
    ("VQA — multiple choice, image-dependent categories only (accuracy)", "mcq*", "accuracy"),
    ("Grounding — point-prompted (Acc@0.5 IoU)", "bbox:point", "accuracy"),
    ("Grounding — referring expression (Acc@0.5 IoU)", "bbox:reference", "accuracy"),
    ("Grounding — mean IoU, all", "bounding box", "mean_iou"),
    ("Captioning — ROUGE-L F1", "captioning", "rouge_l"),
    ("Captioning — BLEU-4", "captioning", "bleu4"),
    ("Captioning — LULC-class F1", "captioning", "lulc_f1"),
]

MIN_MEANINGFUL_N = 100

# In the Lithuania/Summer subset these MCQ categories have (near-)constant answers (country is always
# Lithuania, season always Summer, climate zone "cold, ..." in ~96% of rows), so a model can score
# them without looking at the image. They are reported separately so they cannot inflate the VQA gain.
CONSTANT_ANSWER_MCQ = ("country", "season", "climate zone")


def _image_dependent_mcq(metrics: dict):
    cats = (metrics.get("mcq") or {}).get("by_category") or {}
    kept = [v for c, v in cats.items() if c not in CONSTANT_ANSWER_MCQ]
    n = sum(v["n"] for v in kept)
    return (sum(v["accuracy"] * v["n"] for v in kept) / n, n) if n else (None, 0)


def _row_values(metrics: dict, key: str, metric: str):
    """(value, n) for one table row key, or (None, 0) if absent."""
    if key == "mcq*":
        return _image_dependent_mcq(metrics)
    if key.startswith("bbox:"):
        c = ((metrics.get("bounding box") or {}).get("by_category") or {}).get(key[5:])
        return (c[metric], c["n"]) if c and metric in c else (None, 0)
    m = metrics.get(key)
    return (m[metric], m["n"]) if m else (None, 0)


def before_after_table(base: dict, adapted: dict, trivial: dict | None = None) -> list[dict]:
    trivial = trivial or {}
    rows = []
    for label, key, metric in TABLE_ROWS:
        (bv, _), (av, n) = _row_values(base, key, metric), _row_values(adapted, key, metric)
        if bv is None or av is None:
            continue
        rows.append({
            "metric": label,
            "base": bv,
            "adapted": av,
            "delta": av - bv,
            "n": n,
            "trivial_baseline": trivial.get(key if metric != "mean_iou" else f"{key}/mean_iou"),
            # 95% half-width for a proportion near 0.5 at this n, so small slices are flagged as such
            "approx_95ci_halfwidth": 1.96 * math.sqrt(0.25 / n),
            "small_sample": n < MIN_MEANINGFUL_N,
        })
    return rows


def table_markdown(rows: list[dict]) -> str:
    lines = [
        "| Benchmark (held-out BigEarthNet.txt test split) | Base model (GeoChat-7B) | Post-adaptation (GeoChat-7B + M2 LoRA) | Δ | Trivial baseline¹ | n |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        flag = " ⚠ small n" if r["small_sample"] else ""
        triv = "—" if r.get("trivial_baseline") is None else f"{r['trivial_baseline']:.3f}"
        lines.append(
            f"| {r['metric']} | {r['base']:.3f} | {r['adapted']:.3f} | {r['delta']:+.3f} | {triv} | {r['n']}{flag} |"
        )
    lines.append("")
    lines.append("¹ Image-blind strategy on the same references: most common answer (VQA), whole-image box (grounding).")
    return "\n".join(lines)
