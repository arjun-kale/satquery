# SatQuery AI — SIH 2026 Master Build Plan
## Team SPT02 "Team Invincible" · PS 26167 · ISRO / Department of Space

**Compiled:** 19 September 2026  
**Sources:** Evidence Base v2 · Build Plan v1 · PS 26167 official record

---

## Table of Contents

1. [What This Competition Actually Is](#1)
2. [Mandatory Requirements Checklist](#2)
3. [Unique Selling Propositions](#3)
4. [Architecture](#4)
5. [SatCore — The Differentiating Component](#5)
6. [Specialist Tool Layer](#6)
7. [Controller and Execution Trace](#7)
8. [Data Strategy](#8)
9. [Evaluation Harness — Build This First](#9)
10. [Training Recipe](#10)
11. [Build Phases and Exit Criteria](#11)
12. [Demonstration Script](#12)
13. [Panel Defense — Four Hostile Objections](#13)
14. [Effort Allocation](#14)
15. [Cut List — Do Not Build](#15)
16. [Claims Matrix](#16)
17. [Open Items — Verify Before Architecture Freezes](#17)

---

## 1. What This Competition Actually Is

**This is not a pitch contest. It is a benchmark competition.**

The PS Background paragraph assigns every dataset a scoring role:

> *Final evaluation will use prescribed public benchmark test subsets and an  
> ISRO/SAC evaluation dataset. Scores will be normalised before combining  
> different metrics.*

| Benchmark | Role in Scoring |
|---|---|
| **BigEarthNet.txt** | Mandatory adaptation corpus — compliance, not scored |
| **VRSBench + RSVQA** | Score single-image captioning, grounding, VQA |
| **CDVQA** | Score bi-temporal change VQA |
| **Hidden ISRO/SAC set** | Co-registered Cartosat-2S optical + RISAT SAR pairs |

**Strategic consequence:** metric performance wins. A beautiful DAG
visualiser with fabricated time-savings numbers loses regardless of deck
quality.

**Effort corollary:** 55% of team time goes into adaptation, training and
evaluation. The UI is built last and compressed first.

---

## 2. Mandatory Requirements Checklist

Every item is an explicit PS requirement. An incomplete item is a
compliance failure before the panel scores a single metric.

| # | Requirement | How We Satisfy It |
|---|---|---|
| M1 | At least one visual/VL component fine-tuned/adapted on BigEarthNet.txt or open RS data | SatCore — LoRA fine-tune of 3B–7B base VLM on BigEarthNet.txt |
| M2 | PS verbatim: "generic LLM/VLM without RS adaptation does not satisfy requirements" | The field fails here. We don't. |
| M3 | Single-image VQA mandatory | SatCore VQA head, evaluated on RSVQA |
| M4 | Single-image captioning **or** text-guided region grounding | SatCore captioning + referring-expression grounding head, VRSBench |
| M5 | Bi-temporal change description or change-VQA | SatCore change branch, trained on CDVQA |
| M6 | Cross-modal optical + SAR joint analysis | SatCore band adapter + SAR calibration chain |
| M7 | Agentic orchestration | Controller compiling a typed DAG; trace as scored artefact |
| M8 | GeoTIFF/TIFF input for geospatial imagery | Rasterio ingestion layer, preserving CRS/affine/band depth |
| M9 | Observable execution trace: task, models/tools, parameters, outputs | Schema-validated Pydantic `ObservableExecutionTrace` |
| M10 | Visual evidence, confidence, summaries, downloadable reports | Change masks, bounding boxes, confidence, PDF/GeoJSON report |
| M11 | Input compatibility checking | Ingestion layer: GSD, CRS, band count, co-registration |

---

## 3. Unique Selling Propositions

Seven claims we can make that no generic competitor team can make. Each
is earned by a specific build component. None is asserted — all are
demonstrated live or with a measured number.

---

### USP 1 — Wavelength-Keyed Band Adapter: One Model, Every Sensor

**What it is:** A sensor-agnostic patch embedding that keys each band
projection on its physical descriptor — centre wavelength for optical,
polarisation + frequency for SAR — rather than assuming 3 RGB channels.

**Why it wins:** Most competitors convert GeoTIFF to 8-bit PNG, losing
all multi-spectral depth. We run one backbone across RGB benchmark inputs,
12-band Sentinel-2, dual-pol SAR, and the unseen Cartosat-2S/RISAT
evaluation configuration — because an unfamiliar band still has a
wavelength and still gets an embedding.

**Demo moment:** Load a Cartosat-2S GeoTIFF live. Print band count, CRS
and GSD to three decimal places. Run inference. Nothing crashes.

---

### USP 2 — The Only Team That Satisfies the Mandatory Adaptation Clause

**What it is:** SatCore is fine-tuned on BigEarthNet.txt — the PS's own
named dataset, satisfying M1.

**Why it wins:** Most of the 500 competing teams will submit an off-the-
shelf VLM wrapped in an agentic API. The PS states this explicitly fails
compliance. A panel checking the mandatory list eliminates those teams
without running a single evaluation query.

**Demo moment:** Before/after adaptation table on VRSBench, RSVQA and CDVQA.

---

### USP 3 — Indian SAR Validation on NISAR via Bhoonidhi STAC

**What it is:** The SAR branch is validated on NISAR S-SAR obtained
through Bhoonidhi's STAC API — openly licensed under Indian Space Policy 2023.

**Why it wins:** Every other team will either skip SAR entirely or claim
Sentinel-1 generalises to RISAT without testing it. We show the claim on
ISRO-distributed Indian radar data, with a live Bhoonidhi API call in the trace.

**Demo moment:** Live Bhoonidhi STAC query returning a NISAR scene. Run
SAR calibration. Show σ⁰ map.

---

### USP 4 — Measured GSD Degradation Curve

**What it is:** Resample one scene across 0.5 / 1 / 2 / 5 / 10 / 30 m,
run the full pipeline at each step, plot accuracy-vs-GSD.

**Why it wins:** Every team will be asked "how does your system perform
at ISRO's sensor resolution?" Most will wave at a table someone else
produced. We show our own primary data curve.

**Panel quote:** *"Cartosat-2S at 0.65 m sits here — between RSVQA-LR
and RSVQA-HR, both of which we trained on."*

---

### USP 5 — Schema-Validated Typed DAG as the Scored Artefact

**What it is:** The controller emits an `ObservableExecutionTrace` — a
Pydantic-typed, schema-validated object: task classification, tool
selection, parameters, timing, confidence, outputs.

**Why it wins:** The PS states verbatim: *"Internal reasoning text is
neither required nor evaluated."* Most teams show a chat bubble. We show
the artefact the judges are scoring.

**Demo moment:** Trace panel live. Every field populated, typed,
timestamped. Paraphrased query resolves to an identical DAG — with the
measured routing-consistency percentage.

---

### USP 6 — Physical SAR Calibration Chain

**What it is:** Raw RISAT/NISAR DN converted to σ⁰_dB before any neural
head sees the data. Refined Lee filter despeckles. Cross-modal physical
consistency rules flag optical–SAR contradictions.

**Why it wins:** An ISRO microwave scientist will ask within two minutes:
"How did you handle speckle noise and incidence angle corrections?" Teams
feeding raw DN to a generic vision model cannot answer.

$$\sigma^0_{\text{dB}} = 10\log_{10}(\text{DN}^2 \cdot K) - 10\log_{10}(\sin\theta)$$

*(K and θ read from RISAT/NISAR product metadata — see §17 open item 4.)*

---

### USP 7 — Full Sovereign Deployment: No Foreign Inference Dependency

**What it is:** Every component — vision encoder, controller, language
decoder, geodesy engine — runs on-premise or on India-hosted
MeitY-empanelled infrastructure. Zero calls to OpenAI, Anthropic, Gemini
or any foreign API.

**Why it wins:** Teams built on GPT-4o or Gemini API fail compliance
review by this panel on architecture grounds before evaluation begins.

**Architecture slide annotation:** *"All inference: on-premise /
MeitY-empanelled cloud. Indian Space Policy 2023 compliant."*

---

## 4. Architecture

```
╔══════════════════════════════════════════════════════════════════╗
║                    SATQUERY AI — SYSTEM OVERVIEW                 ║
╚══════════════════════════════════════════════════════════════════╝

  [ Natural Language Query ] + [ 1 or 2 Images ]
                        │
                        ▼
  ┌──────────────────────────────────────────────────────────┐
  │  LAYER 0 — INGESTION                                     │
  │  Dual-path intake:                                       │
  │  PNG/JPEG (benchmark datasets only per PS)               │
  │  GeoTIFF/TIFF → Rasterio: CRS · Affine · GSD            │
  │                            Band count · Sensor ID        │
  │                            Co-registration check         │
  │  Compatibility checks (M11): all inputs validated        │
  └───────────────────────────────┬──────────────────────────┘
                                  │
                                  ▼
  ┌──────────────────────────────────────────────────────────┐
  │  LAYER 1 — SATCORE (Fine-tuned VLM)        [SW 2.0]     │
  │  · Wavelength-keyed band adapter  (USP 1)               │
  │  · GSD conditioning token                               │
  │  · Fixed ground-extent tiling                           │
  │  ┌──────────┬──────────────┬──────────────────────────┐  │
  │  │ VQA head │ Caption head │ Grounding head           │  │
  │  │ (RSVQA)  │ (VRSBench)   │ (referring expression)  │  │
  │  └──────────┴──────────────┴──────────────────────────┘  │
  │  ┌──────────────────────────────────────────────────┐  │
  │  │ Change branch  (siamese SatCore → CDVQA head)    │  │
  │  └──────────────────────────────────────────────────┘  │
  └───────────────────────────────┬──────────────────────────┘
                                  │
                                  ▼
  ┌──────────────────────────────────────────────────────────┐
  │  LAYER 2 — SPECIALIST TOOLS         [SW 1.0 + 2.0]      │
  │  SAR pipeline       GroundingDINO      Geodesy engine   │
  │  DN → σ⁰_dB         bbox detection     CPU-only          │
  │  Refined Lee        ~3.8 GB VRAM       deterministic    │
  │  Cross-modal                           Affine → WGS84   │
  │  consistency                           Polygon delta     │
  │  Spectral: NDVI · MNDWI · NDBI band math                │
  └───────────────────────────────┬──────────────────────────┘
                                  │
                                  ▼
  ┌──────────────────────────────────────────────────────────┐
  │  LAYER 3 — CONTROLLER (quantised 7B)       [SW 3.0]     │
  │  Semantic compiler only.                                 │
  │  Never sees pixels. Never emits a number.                │
  │  Constrained JSON decode → Pydantic schema.              │
  │  Emits: ObservableExecutionTrace (§7)                    │
  └───────────────────────────────┬──────────────────────────┘
                                  │
                                  ▼
  ┌──────────────────────────────────────────────────────────┐
  │  LAYER 4 — OUTPUT                                        │
  │  ObservableExecutionTrace (schema-validated JSON)        │
  │  Change mask · bbox · σ⁰ map (GeoTIFF)                  │
  │  Confidence per output · PDF/GeoJSON report              │
  │  UI: trace panel + visual evidence + DAG timeline        │
  └──────────────────────────────────────────────────────────┘

  DEPLOYMENT: On-premise or MeitY-empanelled cloud.
  No foreign inference API. Indian Space Policy 2023 compliant.
```

---

## 5. SatCore — The Differentiating Component

SatCore is the project's only non-replaceable component. Everything else
is tooling.

### 5.1 The Problem With Fixed Patch Embeddings

A standard ViT patch embedding takes exactly 3 channels. Evaluation
inputs are: RGB benchmark images (3ch), Sentinel-2 (up to 12 bands),
Sentinel-1 (2 pols), Cartosat-2S + RISAT (unknown band config — hidden
set). A stock model breaks on entry 3 and fails silently on entry 4.

### 5.2 Wavelength-Keyed Band Adapter

```python
from pydantic import BaseModel
from typing import Optional
import torch, torch.nn as nn

class BandDescriptor(BaseModel):
    centre_wavelength_nm: Optional[float] = None  # optical
    radar_frequency_ghz:  Optional[float] = None  # SAR
    polarisation:         Optional[str]   = None  # VV, VH, HH, HV

class SatCorePatchEmbed(nn.Module):
    """
    Per-band spatial projection + physical band embedding, summed.
    All bands then attention-pooled into one token sequence.
    An unseen band (Cartosat-2S, RISAT) still has a wavelength
    and still gets a valid embedding — degrades gracefully.
    """
    def forward(self, bands: list, descriptors: list):
        tokens = []
        for band, desc in zip(bands, descriptors):
            spatial = self.patch_proj(band)           # [N_patches, D]
            phys    = self.band_embed(desc)           # [D]
            tokens.append(spatial + phys.unsqueeze(0))
        return self.pool(torch.stack(tokens, dim=0))  # [N_patches, D]
```

### 5.3 GSD Conditioning

```python
GSD_x = abs(transform[0])   # metres per pixel, x-axis
GSD_y = abs(transform[5])   # metres per pixel, y-axis
# Encode as conditioning token. Model told physical scale, not guessing.
# For benchmark PNG/JPEG: pass dataset's nominal GSD.
```

### 5.4 Fixed Ground-Extent Tiling

Tile every input by fixed ground area (e.g. 1.2 km × 1.2 km), not fixed
pixel count. Resample to model's token grid. Same ground content, same
model input size, regardless of sensor. GSD ladder becomes learnable.

### 5.5 Change Branch

Siamese SatCore encoders → change head over difference features.
Trained on CDVQA. Outputs spatial change confidence mask where reference
masks exist.

### 5.6 Nyquist Guardrail — Calibrated, Not Hair-Trigger

**Critical:** Cartosat-2S at 0.65 m resolves vehicles, structures and
boats comfortably. An aggressive guardrail refuses hidden-set questions,
scoring zero on those items. A refusal only beats a wrong answer when the
task is physically unresolvable.

Rule: trigger only when target feature size falls below **2–3× input GSD**.
- Cartosat-2S: almost never fires
- Sentinel-2 10 m on small-object queries: fires
- Emit structured refusal in trace — naming the physical limit and minimum sensor
- Log every trigger — show the firing rate, not just the mechanism

---

## 6. Specialist Tool Layer

Every numerical result — coordinate, area, pixel count, spectral value —
comes from here. Never from the language model.

### 6.1 SAR Physical Calibration Chain

**Step 1 — Backscatter calibration:**

$$\sigma^0_{\text{dB}} = 10\log_{10}(\text{DN}^2 \cdot K) - 10\log_{10}(\sin\theta)$$

K = sensor-specific calibration factor; θ = local incidence angle.
**Both read from RISAT/NISAR product metadata. Do not hardcode K.**
See §17 open item 4.

**Step 2 — Adaptive despeckling:**
Refined Lee filter, 5×5 kernel. Suppresses multiplicative speckle while
preserving linear infrastructure edges.

**Step 3 — Cross-modal physical consistency:**
- Water: expect MNDWI > 0.3 (optical) AND σ⁰_dB < −18 dB (SAR)
- Cloud-masked optical + SAR penetration: log in trace — *"Optical
  occluded by cloud mask; water boundary verified via C-band SAR"*
- Optical/SAR contradiction: flag as ambiguous, never average

### 6.2 Geodesy Engine (CPU-only, deterministic)

```
pixel bounding box (visual head)
      │
      ▼  affine transform from GeoTIFF geotransform
[X_geo, Y_geo]ᵀ = [[A,B],[D,E]] · [U_px,V_px]ᵀ + [C,F]ᵀ
      │
      ▼  CRS → EPSG:4326 via pyproj
geographic coordinates · area in hectares (Shapely + GDAL)
      │
      ▼  polygon delta for change analysis
geometrical symmetrical difference → net area change
```

### 6.3 Spectral Band Math

Fully deterministic, on calibrated surface reflectance:
- MNDWI = (ρ_green − ρ_swir) / (ρ_green + ρ_swir)
- NDVI = (ρ_nir − ρ_red) / (ρ_nir + ρ_red)
- NDBI = (ρ_swir − ρ_nir) / (ρ_swir + ρ_nir)

### 6.4 Memory Management (16 GB GPU Demo Config)

| Component | VRAM | When Loaded |
|---|---|---|
| Controller LLM (INT4 7B) | ~5.5 GB | Always |
| SatCore visual backbone (BF16 3B–4B) | ~6.5 GB | Always |
| GroundingDINO | ~3.8 GB | On-demand, released after grounding |
| Geodesy + SAR pipeline | CPU only | Always |

**Total peak: ~15.8 GB.** Fits one RTX 4090 / RTX 4080.  
Production target: dual A100-80GB on on-premise or MeitY-empanelled node
(E2E Networks A100-80GB: ₹189/hr on-demand — verify current rates).

---

## 7. Controller and Execution Trace

### 7.1 The Controller Is a Compiler, Not an Oracle

Receives: user query + ingestion metadata. Never sees pixels. Outputs
exactly one thing: `ObservableExecutionTrace`. Never emits a number,
never generates free-form Python, never calls an external API.

### 7.2 Schema (the scored artefact)

```python
from pydantic import BaseModel, Field
from typing import List, Literal, Optional
from datetime import datetime

class ToolStep(BaseModel):
    step_id:      int
    tool_name:    Literal[
        "satcore_vqa", "satcore_captioning", "satcore_grounding",
        "satcore_change_vqa", "sar_radiometric_calibration",
        "sar_despeckle_lee", "optical_spectral_index",
        "grounding_dino_detector", "geodesy_affine_transform",
        "crossmodal_consistency_check", "nyquist_guardrail"
    ]
    input_layers: List[str]
    parameters:   dict = Field(default_factory=dict)
    output_key:   str
    latency_ms:   Optional[float] = None
    confidence:   Optional[float] = None

class ObservableExecutionTrace(BaseModel):
    trace_id:              str
    timestamp:             datetime
    task_classification:   Literal[
        "single_vqa", "single_captioning", "single_grounding",
        "bitemporal_change_vqa", "bitemporal_change_description",
        "optical_sar_fusion"
    ]
    input_summary:         dict        # sensor_id, GSD, band_count, CRS
    pipeline_dag:          List[ToolStep]
    requires_nyquist_check: bool
    nyquist_result:        Optional[str]
    final_answer:          str
    visual_evidence_keys:  List[str]
    confidence_overall:    float
    downloadable_report_uri: str
```

### 7.3 Routing Consistency

Paraphrase each test-suite query 10 ways. Measure % resolving to an
identical tool sequence. Report in trace panel and on a slide.
**Target: ≥97%.**

### 7.4 Constrained Decoding

Use `outlines` or `lm-format-enforcer`. Schema violation → caught and
retried. Never propagated to the tool layer.

---

## 8. Data Strategy

### 8.1 BigEarthNet.txt — Mandatory Adaptation Corpus

Source: arXiv:2603.29630 · https://txt.bigearth.net · CC-BY-4.0

| Property | Value |
|---|---|
| Pairs | 464,044 co-registered Sentinel-1 + Sentinel-2 |
| Annotations | 9.6M: captions, VQA pairs, referring-expression bounding boxes |
| Mandatory requirements covered | M1, M3, M4 (both captioning and grounding), M6 |
| Gap | Bi-temporal change — filled by CDVQA |
| Licence | CC-BY-4.0. No Indian geospatial restriction on European training data. |

### 8.2 Copernicus — Development Backbone

- STAC: `https://stac.dataspace.copernicus.eu/v1/`
- Sentinel-2 L2A (12 bands, surface reflectance) + Sentinel-1 GRD (C-band)
- Instant registration. 2,000 req/min, 4 concurrent connections, 12 TB/30d
- CC-BY-4.0

### 8.3 Bhoonidhi STAC API — Indian Sensor Validation

- Base: `https://bhoonidhi-api.nrsc.gov.in/data/collections`
- Auth: JWT Bearer token. SDK: `bhoonidhi-downloader` (PyPI, MIT)
- **NISAR S-SAR** — Open Data under Indian Space Policy 2023
- IRS products ≥5 m, Landsat-8/9 regional mirror, Sentinel regional mirror

Use case: validate SAR branch on NISAR. Show live Bhoonidhi API call in
demo trace. Indian, ISRO-distributed, openly licensed — most credible SAR
validation available to a student team.

**Note:** Cartosat-2S / RISAT < 5 m → priced/government gate. Do not
plan around it.

### 8.4 Change Data

CDVQA + Copernicus bi-temporal Sentinel-2 pairs over documented change
areas (flood zones, construction, deforestation).

### 8.5 What All Prior Research Missed

Neither the Gemini output, the Codex file, nor the strategy document
opened the PS's own dataset link (arXiv:2603.29630). Both treated
optical–SAR fusion as a data-access problem requiring RISAT. It is a
solved data problem — 464k co-registered pairs named in the problem
statement. The real remaining gap is bi-temporal change supervision only.

---

## 9. Evaluation Harness — Build This First

Before touching a model. You cannot optimise what you cannot measure.

### 9.1 Benchmark Loading

- Load VRSBench, RSVQA-LR, RSVQA-HR, CDVQA with official test splits
- Reproduce one published baseline number — proves harness correctness
- Build normalised score aggregator

### 9.2 GSD Ladder Test

Resample one scene: 0.5 / 1 / 2 / 5 / 10 / 30 m. Run full pipeline at
each step. Plot accuracy vs GSD.

This is your degradation curve — primary data, produced by your own
pipeline. No competitor will have it. Key annotation: *"Cartosat-2S at
0.65 m sits here — between RSVQA-HR and our Sentinel-2 training data."*

### 9.3 Indian SAR Proxy Set

NISAR S-SAR via Bhoonidhi STAC + co-located Sentinel-2, co-registered
manually. Paired queries matching PS evaluation format. Run full pipeline.
Structurally identical to the hidden ISRO/SAC set.

### 9.4 Routing Consistency Measurement

10 paraphrase variants per query type. Measure % → identical tool DAG.
Report in trace panel and slide. Minimum target: 97%.

### 9.5 Before vs. After Adaptation Table

| Benchmark | Base model | SatCore (post-adaptation) | Δ |
|---|---|---|---|
| VRSBench | measure | measure | +? |
| RSVQA-LR | measure | measure | +? |
| RSVQA-HR | measure | measure | +? |
| CDVQA | measure | measure | +? |

Fill from harness. Proves M1 is satisfied and that it matters.

---

## 10. Training Recipe

### Stage 1 — Cross-Modal RS Adaptation (M1 + M6)

| | |
|---|---|
| Data | BigEarthNet.txt: 464k S1/S2 pairs, 9.6M annotations |
| Tasks | Captioning, VQA, referring-expression grounding (jointly) |
| Method | LoRA/QLoRA on 3B–7B base |
| GSD augmentation | Resample S2: 10 / 20 / 30 m; S1: across available resolutions |
| Exit criterion | Measurable improvement over base on VRSBench and RSVQA-LR test sets |

### Stage 2 — Resolution Generalisation (hidden-set transfer)

| | |
|---|---|
| Data | VRSBench + RSVQA train splits |
| GSD augmentation | Extend ladder to 0.5 m by downsampling high-res VRSBench images |
| Exit criterion | Meaningful accuracy at both ends of GSD ladder; no catastrophic collapse |

### Stage 3 — Change VQA (M5)

| | |
|---|---|
| Data | CDVQA + Copernicus bi-temporal Sentinel-2 pairs |
| Method | LoRA fine-tune of change branch |
| Exit criterion | CDVQA test accuracy exceeds base model |

### Multi-Scale Augmentation Throughout

Every sample resampled to random GSD within its range at each epoch.
Model spans the gap it will be tested across.

### Base Model Selection Criteria (priority order)

1. Patch-embed layer is modifiable
2. Licence permits on-premise deployment — verify from model card directly
3. LoRA training fits GPU (≤16 GB for 3B, ≤24 GB for 7B in INT4)
4. Prior RS fine-tuning community
5. RGB benchmark score — last criterion, not first

Candidates: Qwen2.5-VL-3B/7B, InternVL2. **Verify all licences.**
LLaMA/Vicuna-derived weights carry research licences, not Apache 2.0.

---

## 11. Build Phases and Exit Criteria

Internal deadlines at 75% of real milestones. Phase 5 is the only
compressible phase.

| Phase | What Gets Built | Exit Criterion |
|---|---|---|
| **1 — MEASURE** | Evaluation harness · GeoTIFF ingestion · Tiler · Baseline metrics | Reproduce one published baseline. Normalised score on demand < 5 min. |
| **2 — ADAPT** | Band adapter · GSD conditioning · LoRA Stage 1 on BigEarthNet.txt · Before/after table | Model accepts 12-band S2 and 2-pol S1. Measurable improvement. M1 satisfied. |
| **3 — COVER** | LoRA Stages 2+3 · SAR calibration · Change branch · GroundingDINO · Geodesy · GSD ladder test · Indian SAR proxy set | All five mandatory items working end-to-end. CDVQA above base. σ⁰ map produced. Degradation curve complete. |
| **4 — CONTROL** | Controller · constrained JSON decode · ObservableExecutionTrace · Tool registry · Routing consistency · Cross-modal rules · Nyquist guardrail | Trace validates on every test-suite query. Routing consistency measured. |
| **5 — SURFACE** *(last, compress first)* | GUI · Trace panel · DAG timeline · PDF/GeoJSON report · Bhoonidhi live API call | Full demo script runs without intervention. Report downloads correctly. |

---

## 12. Demonstration Script

Five phases. Each has one specific moment that establishes technical depth
before a word of explanation is spoken.

---

### Phase 1 — Ingestion (2 minutes)

**Action:** Upload a multi-band GeoTIFF. Do not use a PNG.

**System prints immediately:**
```
Input verified:
  Format:       GeoTIFF (multi-band)
  CRS:          EPSG:32644 (UTM Zone 44N)
  GSD:          10.002 m × 10.002 m
  Band count:   12 (B2–B8A, B11, B12 + SCL)
  Extent:       22.1471°N – 22.2684°N, 79.1823°E – 79.3041°E
  Sensor ID:    Sentinel-2A L2A
  Nyquist check: PASSED for requested feature scale
```

**Why this wins:** Competitor loaded a `.jpg` into a drag-and-drop form.
You print geodetic coordinates to four decimal places before anyone speaks.

---

### Phase 2 — Orchestration (3 minutes)

**Action:** Query: *"What water bodies are visible, and are any partially
cloud-masked?"*

**System shows:** Live trace — not a chat bubble.

```json
{
  "task_classification": "single_vqa",
  "input_summary": {"GSD_m": 10.0, "band_count": 12},
  "pipeline_dag": [
    {"step_id": 1, "tool_name": "optical_spectral_index",
     "parameters": {"index": "MNDWI"}, "latency_ms": 43},
    {"step_id": 2, "tool_name": "satcore_vqa",
     "parameters": {"gsd_m": 10.0}, "latency_ms": 1820, "confidence": 0.89},
    {"step_id": 3, "tool_name": "geodesy_affine_transform",
     "latency_ms": 12}
  ],
  "confidence_overall": 0.87
}
```

**Why this wins:** The PS explicitly says internal reasoning text is not
evaluated. You are showing the artefact being scored.

---

### Phase 3 — Complex Bi-temporal + SAR Query (5 minutes)

**Action:** Load co-registered optical/SAR pair. Query: *"Use the SAR
and optical images together to identify where cloud cover prevents optical
mapping but water can still be confirmed."*

**System:**
1. Runs optical cloud detection
2. Runs SAR calibration → prints: *"σ⁰ calibration: K=[from metadata],
   θ=[from metadata]. Refined Lee 5×5 applied."*
3. Applies cross-modal consistency rule
4. Trace logs: *"Optical occluded in 3 tiles. C-band SAR (σ⁰ < −18 dB)
   confirms standing water. Area: 4.2 ha."*

**Why this wins:** PS requirement M6. Nobody else in the room has a live
SAR calibration chain. The panel scientist stops typing.

---

### Phase 4 — Guardrail Demo (2 minutes)

**Action:** Load Sentinel-2 10 m scene. Query: *"Count all motorcycles
parked in this area."*

**System:**
```
[GUARDRAIL TRIGGERED]
Target feature: motorcycle (~2 m)
Input GSD:      10.0 m
Ratio:          5.0× below resolution limit (threshold: 2–3×)
Task rejected: sub-pixel hallucination prevention.
Minimum recommended sensor: Cartosat-2S (0.65 m GSD).
```

**Why this wins:** You demonstrated where the system fails before the
panel asks. That signals more engineering maturity than any feature that
succeeds.

---

### Phase 5 — Compliance (1 minute)

Architecture diagram: *"All inference: on-premise / MeitY-empanelled
cloud. No foreign API calls."*

Bhoonidhi STAC call in trace: *"Our SAR validation data was obtained
through ISRO's own Bhoonidhi API, under Indian Space Policy 2023's
open-data provisions for NISAR."*

**Why this wins:** Most teams have GPT-4o calls somewhere in their
architecture. This annotation eliminates them without a benchmark score.

---

## 13. Panel Defense — Four Hostile Objections

If the panel does not raise these, the demo should already have answered them.

---

### H1 — "You trained on 10 m Sentinel-2 and will be scored on 0.65 m Cartosat-2S. Your numbers will collapse on our set."

Show the GSD degradation curve. Annotate where Cartosat-2S sits. Point
out that RSVQA-LR (≈10 m) and RSVQA-HR (≈0.15 m) already bracket it —
if the model generalises across prescribed public benchmarks, it
generalises to the hidden set. Add: multi-scale GSD augmentation
throughout training; fixed-ground-extent tiling so pixel count changes
but ground content does not.

---

### H2 — "An LLM orchestrating GIS pipelines is non-deterministic."

The controller is a compiler, not an oracle. It sees no pixels and emits
no numbers — only a schema-validated tool DAG. Every raster operation,
calibration and geodetic computation is fully deterministic and bit-
reproducible. We measured routing consistency across paraphrase variants:
N%. LLM probabilism is sandboxed by constrained JSON decoding. Show the
Pydantic schema. Show the consistency number.

---

### H3 — "You cannot handle RISAT SAR without understanding radar physics."

No neural head sees raw DN. The SAR calibration chain runs first: DN →
σ⁰_dB using calibration constant and incidence angle from product
metadata, then Refined Lee despeckling. Validated on NISAR S-SAR via
Bhoonidhi — same C-band wavelength as RISAT. Show the σ⁰ output map.
If pressed: Sentinel-1 and RISAT are both C-band — the transfer is a
resolution and calibration convention problem, not a physics problem.

---

### H4 — "This is just Bhuvan with a chat interface."

Bhuvan is a GIS map viewer. It does not accept a user-uploaded GeoTIFF
and run an agentic reasoning pipeline over it. It does not perform bi-
temporal change VQA. It does not output a schema-validated execution trace
scored against a benchmark suite. The differentiation is not the UI — it
is the agentic orchestration of fine-tuned specialist models over native
multi-band GeoTIFF inputs, with a scored observable trace, satisfying a
benchmark evaluation the Bhuvan portal was never designed to pass.
Then show VRSBench and RSVQA numbers.

---

## 14. Effort Allocation

| Workstream | Share | Reason |
|---|---|---|
| Model adaptation + evaluation harness | **55%** | This is what is scored. Cannot be compressed. |
| Geodesy layer + SAR physics | **20%** | Mandatory. Panel's home territory. |
| Controller, typed DAG, trace | **15%** | Mandatory. Explicitly evaluated by the PS. |
| GUI, visualiser, report export | **10%** | Required deliverable, not a scoring axis. |

A beautiful real-time DAG animation scores zero on a normalised metric
combination. Build it last.

---

## 15. Cut List — Do Not Build

| Item | Why |
|---|---|
| TCO models, GeM hardware tiers, staffing tables | Not scored. Cite IndiaAI/E2E per-hour rates with URLs if asked. |
| Analyst-hours time-saving claim ("7–15 hours") | Unsourced across three research passes. One NRSC question ends it. |
| Live Bhoonidhi ordering of Cartosat-2S / RISAT | <5 m priced gate. Use API live only for NISAR and ≥5 m products. |
| Foreign-hosted LLM APIs (GPT-4o, Gemini, Claude API) | Architecture constraint. Visibly absent from the running system. |
| Conversational chat transcript as primary UI | Internal reasoning text is not evaluated. The trace is. |
| Second orchestration framework | One controller, one registry, one schema. |
| RemoteCLIP as a VQA or captioning component | Contrastive aligner with no text decoder. Cannot do VQA. Remove from every diagram immediately. |
| "68/500, 68× median" competitive claim | No source. Coincidental numerics. One challenge removes it. |
| ERDAS/ArcGIS per-seat pricing | No tender document found across three research passes. |
| DPDP Act 2023 as the primary compliance frame | DPDP governs personal data. This PS concerns land-imaging satellite imagery. Use: Indian Space Policy 2023 + 2021 Geospatial Guidelines. |

---

## 16. Claims Matrix

Six claims Team Invincible can make that the field cannot. Each is
earned, falsifiable, and demonstrated rather than asserted.

| # | Claim | Earned by | How Demonstrated |
|---|---|---|---|
| C1 | "One backbone ingests RGB, 12-band multispectral and dual-pol SAR via wavelength-keyed band adapter. Unseen Cartosat-2S config degrades gracefully." | §5.2 | Live GeoTIFF ingestion, band count printed, inference runs |
| C2 | "Here is our measured accuracy-vs-GSD curve from 0.5 m to 30 m, Cartosat-2S annotated." | §9.2 | Slide with the curve — primary data from our own pipeline |
| C3 | "We validated the SAR branch on NISAR S-SAR from Bhoonidhi's STAC API — Indian, ISRO-distributed, openly licensed." | §8.3 | Live Bhoonidhi API call visible in demo trace |
| C4 | "Paraphrased queries compile to an identical tool DAG N% of the time — measured across the test suite." | §9.4 | The N% number, shown in trace panel and slide |
| C5 | "Adapted on BigEarthNet.txt as the PS specifies — the mandatory clause most competing teams will skip." | §10 | Before/after adaptation table on all four benchmarks |
| C6 | "No weights, imagery or coordinates leave Indian infrastructure." | §7 | Architecture slide annotation + no external API call in trace |

---

## 17. Open Items — Verify Before Architecture Freezes

| # | Item | Why Blocking | Where |
|---|---|---|---|
| 1 | **sih.gov.in live page** — deadline, submission count, evaluation-criteria table | Deadline may be 20 Sep 2026 — today | sih.gov.in directly. One minute. |
| 2 | **txt.bigearth.net** — download mechanics, split sizes, band subsets, tile geometry, baselines | Phase 1 harness depends on it | Project site + arXiv:2603.29630 |
| 3 | **CDVQA** — paper, split sizes, metric definitions, download | Bi-temporal branch training and evaluation | arXiv + GitHub repo referenced in PS |
| 4 | **RISAT and NISAR product manuals** — calibration constant K, polarisation, incidence-angle metadata field names | σ⁰ formula uses K from metadata. Do not hardcode. | SAC/NRSC technical docs; earthdata.nasa.gov |
| 5 | **Base model candidate licences** — read each model card directly | Research-only licence kills the sovereignty claim | Hugging Face model repos |
| 6 | **Bhoonidhi API spec** — token lifetime, concurrency limits, open collections for non-government users | Phase 5 demo Bhoonidhi call depends on auth | bhoonidhi.nrsc.gov.in/bhoonidhi-api/ |
| 7 | **GSD + metric definitions for VRSBench, RSVQA-LR, RSVQA-HR, CDVQA** | GSD ladder annotation and harness calibration | Each dataset's original paper |
| 8 | **Confirm Sentinel-1 and RISAT are both C-band** | Validates H3 defense; narrows SAR transfer risk | RISAT product manual + Sentinel-1 mission overview |
| 9 | **Your own GSD degradation curve** | Highest-value output of the entire build. Primary data you own. | Run Phase 3 evaluation harness at each GSD step. |

---

*End of document.*

---
**Revision log:**  
v1.0 — 19 Sep 2026 — Compiled from Evidence Base v2, Build Plan v1,
and strategy research. Three documents synthesised, disputed claims
resolved, two new findings folded in: BigEarthNet.txt dataset contents
(464k co-registered S1/S2 pairs, 9.6M annotations) and NISAR open
access via Bhoonidhi STAC API.