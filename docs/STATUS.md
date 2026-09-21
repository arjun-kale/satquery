# SatQuery AI — Model Status

## GeoChat

| Field | Value |
|---|---|
| **Source repo** | https://github.com/mbzuai-oryx/GeoChat |
| **Checkpoint** | TBD — pin revision before Phase 5 |
| **Licence (code)** | Apache-2.0 |
| **Licence (weights)** | **UNVERIFIED** — do not distribute or use publicly until checked |
| **Upstream deps** | Vicuna-derived weights — licence must be confirmed separately |
| **Local use** | Unverified |
| **Redistribution** | Unverified |
| **Commercial use** | Unverified |
| **Status** | Stub — raises `ModelUnavailableError` until Phase 5 |

> Action required before Phase 5: review GeoChat model card and all upstream
> weight licences. Record outcome here before any public-facing demo.

---

## ChangeFormer

| Field | Value |
|---|---|
| **Source repo** | https://github.com/wgcban/ChangeFormer |
| **Checkpoint** | TBD — pin revision before Phase 5 |
| **Licence (code)** | MIT |
| **Licence (weights)** | Not explicitly stated — verify before redistribution |
| **Status** | Stub — raises `ModelUnavailableError` until Phase 5 |

---

## Team LoRA Checkpoint (M1)

| Field | Value |
|---|---|
| **Base model** | GeoChat (see above) |
| **Training dataset** | BigEarthNet-MM (subset — see `training/reproduce_m1_run.md`) |
| **Checkpoint path** | TBD after training run |
| **Status** | **NOT YET TRAINED** — required gate before Phase 3 |

See `training/reproduce_m1_run.md` for the full reproducibility record.

---

## MockModelAdapter

| Field | Value |
|---|---|
| **Status** | Active — used for all local dev and tests |
| **Output** | Deterministic fixtures, clearly labelled `model_mode=mock` |
| **GPU required** | No |
