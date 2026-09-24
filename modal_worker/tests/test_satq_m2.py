"""Unit tests for the M2 pipeline's pure-python parts.

Run from modal_worker/:  python -m pytest tests -q
The tokenizer tests download GeoChat's tokenizer (~500 KB) and are skipped when offline.
"""

import ast
import inspect
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from satq_m2 import geochat, imagery, metrics, splits  # noqa: E402

REPO = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------- GeoChat formatting

def test_ben_box_to_geochat_is_x_first_percent():
    assert geochat.ben_box_to_geochat("[0.65 0.0, 1.0 0.61]") == "{<65><0><100><61>|<90>}"


def test_ben_box_roundtrips_through_parser():
    ref = "[0.42 0.0, 1.0 0.95]"
    assert metrics.parse_box(geochat.ben_box_to_geochat(ref)) == metrics.parse_box(ref)


def test_question_rewrites():
    q = geochat.build_question("Where can the <ref>pastures</ref> be found?", "bounding box")
    assert q == "[refer] Where can the <p>pastures</p> be found?"
    q = geochat.build_question("Box the instance at <point>(0.29, 0.32)</point> in the image.", "bounding box")
    assert q == "[refer] Box the instance at {<29><32>} in the image."
    assert geochat.build_question("Is there water?", "binary").endswith(geochat.VQA_SHORT_SUFFIX)
    assert geochat.build_question("Pick: a) x, b) y", "mcq").endswith(geochat.MCQ_SUFFIX)
    with pytest.raises(ValueError):
        geochat.build_question("x", "unknown")


@pytest.fixture(scope="module")
def tokenizer():
    try:
        from transformers import AutoTokenizer

        return AutoTokenizer.from_pretrained("MBZUAI/geochat-7B", use_fast=False)
    except Exception as e:  # offline
        pytest.skip(f"GeoChat tokenizer unavailable: {e}")


@pytest.mark.parametrize(
    "qtype,text,answer",
    [
        ("binary", "Does this satellite image include transitional woodlands or shrubs?", "yes"),
        ("mcq", "Which season is shown? a) Winter, b) Spring, c) Autumn, d) Summer", "d"),
        ("bounding box", "Where is the <ref>pastures</ref> located?", "[0.0 0.31, 0.25 0.65]"),
        ("captioning", "Describe this satellite image.", "This satellite image, captured during the summer in Lithuania, shows forest."),
    ],
)
def test_training_labels_cover_exactly_answer_and_eos(tokenizer, qtype, text, answer):
    q = geochat.build_question(text, qtype)
    target = geochat.build_target(answer, qtype)
    ids, labels = geochat.build_training_ids(q, target, tokenizer)
    assert len(ids) == len(labels)
    assert ids.count(geochat.IMAGE_TOKEN_ID) == geochat.IMAGE_SEQ_LEN
    supervised = [t for t in labels if t != -100]
    assert supervised[-1] == tokenizer.eos_token_id
    assert tokenizer.decode(supervised, skip_special_tokens=True).strip() == target
    # the inference prompt is exactly the unsupervised prefix
    prompt_ids = geochat.build_inference_ids(q, tokenizer)
    assert ids[: len(prompt_ids)] == prompt_ids
    assert all(label == -100 for label in labels[: len(prompt_ids)])


def test_image_placeholder_follows_geochat_chunking(tokenizer):
    ids = geochat.build_inference_ids("Is there water?", tokenizer)
    assert ids[0] == tokenizer.bos_token_id
    assert ids.count(tokenizer.bos_token_id) == 1  # per-chunk BOS dropped, as in tokenizer_image_token
    first_img = ids.index(geochat.IMAGE_TOKEN_ID)
    assert ids[first_img: first_img + geochat.IMAGE_SEQ_LEN] == [geochat.IMAGE_TOKEN_ID] * geochat.IMAGE_SEQ_LEN


# ---------------------------------------------------------------- imagery

def test_render_rgb_shape_and_stretch():
    rng = np.random.default_rng(0)
    bands = rng.integers(0, 3000, size=(3, 120, 120)).astype(np.int32)
    img = imagery.render_rgb(bands)
    assert img.size == (geochat.IMAGE_SIZE, geochat.IMAGE_SIZE) and img.mode == "RGB"
    arr = np.asarray(img)
    assert arr.max() > 200  # stretched, not the dark /10000 rendering


def test_render_matches_backend_preview_normalisation():
    backend = (REPO / "backend/app/ingestion/preview.py").read_text()
    fn = next(
        n for n in ast.walk(ast.parse(backend)) if isinstance(n, ast.FunctionDef) and n.name == "_normalise"
    )
    ours = ast.parse(inspect.getsource(imagery._normalise)).body[0]
    strip = lambda f: ast.dump(ast.Module(body=f.body, type_ignores=[]))  # noqa: E731
    assert strip(fn) == strip(ours), "train-time rendering drifted from backend preview rendering"


# ---------------------------------------------------------------- splits

def _synthetic(n_patches=400, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    cats = {"binary": ["presence", "count", "area"], "mcq": ["season", "adjacency"], "bounding box": ["point", "reference"], "captioning": [None]}
    for p in range(n_patches):
        split = "train" if p < n_patches * 0.6 else "test"
        for t, cs in cats.items():
            for c in cs:
                for _ in range(int(rng.integers(1, 4)) if t != "captioning" else 1):
                    rows.append({"ID": f"{p}-{t}-{c}-{len(rows)}", "patch_id": f"P{p}", "type": t, "category": c, "split": split})
    return pd.DataFrame(rows)


def test_splits_even_by_type_and_patch_disjoint():
    df = _synthetic()
    train, held_out, stats = splits.build_splits(df, set(df.patch_id), n_train=120, n_eval=40)
    assert train["type"].value_counts().to_dict() == {t: 30 for t in splits.TYPES}
    assert held_out["type"].value_counts().to_dict() == {t: 10 for t in splits.TYPES}
    assert set(train.split) == {"train"} and set(held_out.split) == {"test"}
    assert not set(train.patch_id) & set(held_out.patch_id)
    assert stats["train"]["n"] == 120 and stats["eval"]["n"] == 40


def test_splits_drop_patches_without_imagery_and_are_deterministic():
    df = _synthetic()
    keep = {f"P{p}" for p in range(0, 400, 2)}
    a, b, s = splits.build_splits(df, keep, 80, 20, seed=1)
    a2, b2, _ = splits.build_splits(df, keep, 80, 20, seed=1)
    assert set(a.patch_id) <= keep and set(b.patch_id) <= keep
    assert s["rows_without_imagery_dropped"] > 0
    assert list(a.ID) == list(a2.ID) and list(b.ID) == list(b2.ID)


def test_splits_refuse_when_a_type_is_short():
    df = _synthetic(n_patches=20)
    with pytest.raises(ValueError):
        splits.build_splits(df, set(df.patch_id), n_train=4000, n_eval=10)


def test_largest_remainder_sums_exactly():
    out = splits._largest_remainder(10, {"a": 1, "b": 1, "c": 1})
    assert sum(out.values()) == 10


# ---------------------------------------------------------------- metrics

@pytest.mark.parametrize(
    "pred,ref,ok",
    [("Yes, there is.", "yes", True), ("no", "yes", False), ("I don't know", "no", False), ("Not sure", "no", False)],
)
def test_binary(pred, ref, ok):
    assert metrics.score_record("binary", pred, ref)["correct"] is ok


@pytest.mark.parametrize(
    "pred,ref,ok",
    [("b", "b", True), ("B) Complex", "b", True), ("(c).", "c", True), ("A forest and a field", "a", False), ("The answer is d", "d", False)],
)
def test_mcq(pred, ref, ok):
    assert metrics.score_record("mcq", pred, ref)["correct"] is ok


def test_box_formats_and_iou():
    ref = "[0.6 0.44, 1.0 0.9]"
    assert metrics.score_record("bounding box", "{<60><44><100><90>|<90>}", ref)["iou"] == pytest.approx(1.0)
    assert metrics.score_record("bounding box", "[0.6, 0.44, 1.0, 0.9]", ref)["correct"]
    assert metrics.score_record("bounding box", "[60, 44, 100, 90]", ref)["correct"]
    assert not metrics.score_record("bounding box", "top right", ref)["parsed"]
    assert not metrics.score_record("bounding box", "{<0><0><30><30>|<90>}", ref)["correct"]


def test_caption_metrics():
    ref = "The image shows coniferous forest next to pastures and inland waters."
    assert metrics.rouge_l_f1(ref, ref) == pytest.approx(1.0)
    assert metrics.corpus_bleu4([ref], [ref]) == pytest.approx(1.0)
    assert metrics.lulc_classes(ref) == {"coniferous forest", "pastures", "inland waters"}
    assert metrics.lulc_f1("Mostly coniferous forest.", ref) == pytest.approx(0.5)
    assert metrics.rouge_l_f1("", ref) == 0.0


def test_aggregate_and_table():
    recs = []
    for t, pred, ref in [("binary", "yes", "yes"), ("binary", "no", "yes"), ("mcq", "a", "a"),
                         ("bounding box", "{<0><0><50><50>|<90>}", "[0.0 0.0, 0.5 0.5]"), ("captioning", "pastures", "pastures")]:
        recs.append({"type": t, "category": "c", "prediction": pred, "reference_output": ref, "score": metrics.score_record(t, pred, ref)})
    agg = metrics.aggregate(recs)
    assert agg["binary"] == {"n": 2, "accuracy": 0.5, "by_category": {"c": {"n": 2, "accuracy": 0.5}}}
    rows = metrics.before_after_table(agg, agg)
    assert all(r["delta"] == 0 for r in rows) and all(r["small_sample"] for r in rows)
    assert "⚠ small n" in metrics.table_markdown(rows)


def test_table_separates_constant_answer_mcq_categories():
    def mk(acc_by_cat):
        cats = {c: {"n": 10, "accuracy": a} for c, a in acc_by_cat.items()}
        return {"mcq": {"n": 10 * len(cats), "accuracy": sum(acc_by_cat.values()) / len(cats), "by_category": cats}}

    base = mk({"country": 0.0, "season": 0.0, "area": 0.5, "count": 0.3})
    adapted = mk({"country": 1.0, "season": 1.0, "area": 0.5, "count": 0.3})
    rows = {r["metric"]: r for r in metrics.before_after_table(base, adapted)}
    assert rows["VQA — multiple choice (accuracy)"]["delta"] == pytest.approx(0.5)  # inflated by constants
    dep = rows["VQA — multiple choice, image-dependent categories only (accuracy)"]
    assert dep["delta"] == pytest.approx(0.0) and dep["n"] == 20


def test_grounding_rows_split_by_prompt_kind_with_trivial_baseline():
    def rec(cat, pred, ref):
        return {"type": "bounding box", "category": cat, "prediction": pred, "reference_output": ref,
                "score": metrics.score_record("bounding box", pred, ref)}

    big, small = "[0.0 0.2, 1.0 1.0]", "[0.8 0.8, 1.0 1.0]"
    full = "{<0><0><100><100>|<90>}"
    recs = [rec("reference", full, big), rec("reference", full, small),
            rec("point", "{<80><80><100><100>|<90>}", small), rec("point", "{<80><80><100><100>|<90>}", small)]
    agg = metrics.aggregate(recs)
    triv = metrics.trivial_baselines(recs)
    rows = {r["metric"]: r for r in metrics.before_after_table(agg, agg, trivial=triv)}
    ref_row = rows["Grounding — referring expression (Acc@0.5 IoU)"]
    # whole-image answers score exactly the trivial baseline: no real grounding
    assert ref_row["adapted"] == pytest.approx(0.5) and ref_row["trivial_baseline"] == pytest.approx(0.5)
    pt_row = rows["Grounding — point-prompted (Acc@0.5 IoU)"]
    assert pt_row["adapted"] == pytest.approx(1.0) and pt_row["trivial_baseline"] == pytest.approx(0.0)
