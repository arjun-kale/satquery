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
