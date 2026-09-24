"""Stratified train / held-out eval subsets of BigEarthNet.txt.

- Imagery: only patches present in the LMDB on the volume (Lithuania, Summer).
- Held-out: training rows come from the official ``train`` split and eval rows from the official
  ``test`` split. The official splits are patch-disjoint, and that is re-checked here, so no eval
  image is ever seen in training.
- Stratification: the budget is split evenly across the four annotation types (binary and mcq are
  VQA, captioning, bounding box is referring-expression grounding), then within each type across
  categories in proportion to their frequency (largest-remainder rounding). A head(N) slice or a
  proportional-by-type sample would give captioning ~4% of the budget.
"""

from __future__ import annotations

import hashlib
import json

import pandas as pd

TYPES = ("binary", "mcq", "bounding box", "captioning")
TASK_FAMILY = {"binary": "VQA", "mcq": "VQA", "captioning": "captioning", "bounding box": "grounding"}


def _largest_remainder(total: int, weights: dict[str, int]) -> dict[str, int]:
    s = sum(weights.values())
    raw = {k: total * w / s for k, w in weights.items()}
    out = {k: int(v) for k, v in raw.items()}
    for k in sorted(raw, key=lambda k: (raw[k] - out[k], k), reverse=True)[: total - sum(out.values())]:
        out[k] += 1
    return out


def _even_split(total: int, keys: tuple[str, ...]) -> dict[str, int]:
    base, rem = divmod(total, len(keys))
    return {k: base + (1 if i < rem else 0) for i, k in enumerate(keys)}


def stratified_sample(pool: pd.DataFrame, n: int, seed: int) -> pd.DataFrame:
    pool = pool.assign(_cat=pool["category"].fillna("(none)"))
    parts = []
    for qtype, quota in _even_split(n, TYPES).items():
        tpool = pool[pool["type"] == qtype]
        if len(tpool) < quota:
            raise ValueError(f"Only {len(tpool)} '{qtype}' rows available, need {quota}")
        per_cat = _largest_remainder(quota, tpool["_cat"].value_counts().to_dict())
        for cat, k in sorted(per_cat.items()):
            if k:
                parts.append(tpool[tpool["_cat"] == cat].sample(n=k, random_state=seed))
    out = pd.concat(parts).drop(columns="_cat")
    # Shuffle so any prefix of the manifest is still mixed across types
    return out.sample(frac=1, random_state=seed).reset_index(drop=True)


def distribution(df: pd.DataFrame) -> dict:
    cats = df.assign(category=df["category"].fillna("(none)"))
    return {
        "n": int(len(df)),
        "unique_patches": int(df["patch_id"].nunique()),
        "by_type": {k: int(v) for k, v in df["type"].value_counts().sort_index().items()},
        "by_task_family": {k: int(v) for k, v in df["type"].map(TASK_FAMILY).value_counts().sort_index().items()},
        "by_type_category": {
            f"{t} / {c}": int(v) for (t, c), v in cats.groupby(["type", "category"]).size().sort_index().items()
        },
    }


def manifest_hash(df: pd.DataFrame) -> str:
    return hashlib.sha256("\n".join(df["ID"].astype(str)).encode()).hexdigest()[:16]


def build_splits(
    annotations: pd.DataFrame,
    available_patches: set[str],
    n_train: int,
    n_eval: int,
    seed: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    have_img = annotations["patch_id"].isin(available_patches)
    usable = annotations[have_img]
    train = stratified_sample(usable[usable["split"] == "train"], n_train, seed)
    held_out = stratified_sample(usable[usable["split"] == "test"], n_eval, seed)

    overlap = set(train["patch_id"]) & set(held_out["patch_id"])
    if overlap:
        raise AssertionError(f"{len(overlap)} patches appear in both train and eval subsets")

    stats = {
        "seed": seed,
        "source_rows": int(len(annotations)),
        "rows_without_imagery_dropped": int((~have_img).sum()),
        "train_source_split": "train",
        "eval_source_split": "test",
        "train_eval_patch_overlap": 0,
        "train": {**distribution(train), "manifest_hash": manifest_hash(train)},
        "eval": {**distribution(held_out), "manifest_hash": manifest_hash(held_out)},
    }
    return train, held_out, stats


def dumps(stats: dict) -> str:
    return json.dumps(stats, indent=2, sort_keys=True)
