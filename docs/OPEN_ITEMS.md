# SatQuery AI — Open Items

Items that are unresolved pending external sources or decisions.

---

## SAR water backscatter threshold

**Status:** Unset / configurable — do NOT hardcode.

The −18 dB water detection threshold commonly cited for Sentinel-1 is sensor-,
polarisation-, and season-dependent and has not been verified against
RISAT-1/2 or NISAR product specifications.

`tools/sar.py` deliberately requires the threshold to be supplied as a
parameter. It will remain configurable until a verified source is recorded here.

**Required before hardcoding:**
- Specific Sentinel-1 GRD product documentation confirming the threshold
- Equivalent confirmation for RISAT or NISAR if those sensors are used
- Test results on a known water/non-water scene

---

## SAR sensor calibration constants

**Status:** Parameter-fed — no hardcoded product constants.

`calibrate()` requires `calibration_factor` and `incidence_angle_rad` to be
sourced from the product metadata header. Document the specific metadata field
names per sensor before integrating a new SAR data source.

---

## GeoChat licence status

**Status:** Unverified for redistribution and commercial use.

Pin the checkpoint revision and check the model card plus all upstream
dependencies (including Vicuna-derived weights) before any public-facing demo.
Record the outcome in `docs/STATUS.md` when Phase 2 begins.

---

## Bhoonidhi / STAC integration

**Status:** Deferred. Use public staged samples for the MVP.
No credentials required for Phase 0–1.

---

## Evidence UI: gaps against `SATQUERY_UX_BRIEF.md`

**Status:** Open. The redesigned UI renders honest fallbacks for each of these; none is faked.

- **Streaming (§8):** the UI polls `GET /api/jobs/{id}/trace`, which the executor rewrites after
  every step, instead of the AI SDK UI Message Stream over SSE. Every row is still a recorded
  backend state change, but granularity is per step (no `data-progress` tile counts, no
  cold-start event: the UI only says the GPU worker *may* be starting after 15 s on a VLM step).
- **Stop (§8.5):** `POST /api/jobs/{id}/cancel` stops the run *before the next step*; a step that
  is already running (e.g. a Modal GPU call) finishes first. The UI labels Stop that way.
- **Placeholder steps:** `sar_calibrate`, `sar_despeckle`, `mndwi` and `geochat_summary` return
  `{"simulated": true}` — no computation runs. The UI marks them "Placeholder step". The SAR DAG
  needs calibration metadata before these can be wired to `app/tools/sar.py`.
- **ChangeFormer:** no weights are loaded, so change detection only works in mock mode (fixed
  placeholder mask, labelled as such). In `modal` mode the step fails with a plain message.
- **Persistence:** analyses are restored from the backend's own traces, keyed by ids kept in the
  browser (`localStorage`), not an SQLite analyses table.
- **Pixel values under the cursor / σ⁰ readout:** not available — the browser only has the 512 px
  quick-look, so the readout shows pixel coordinates and lat/lon only.
