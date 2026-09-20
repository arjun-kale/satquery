# SatQuery AI — Zero-Budget MVP Execution Plan

## Purpose and scope

This implementation plan reflects the selected stack:

- **UI:** Next.js + TypeScript, deployed on Vercel Hobby for the prototype.
- **API and geospatial processing:** Python 3.11+ + FastAPI.
- **Remote-sensing models:** GeoChat for single-image captioning, VQA and
  grounding; ChangeFormer for bi-temporal change masks. RSGPT and TEOChat are
  evaluation alternatives, not initial dependencies.
- **Native raster/SAR analysis:** Rasterio/GDAL, NumPy, SciPy, PyProj and
  Shapely.
- **Execution trace:** Pydantic schemas and a deterministic, typed tool router.
- **GPU:** Modal's free credit for short M1 training and inference experiments;
  every GPU feature needs a local/mock fallback so development is not blocked.
- **Cost:** zero. Use open-source packages, public/open data and free tiers.

The MVP proves the workflow and produces evidence. It does **not** claim
full-corpus BigEarthNet.txt adaptation, native learned multispectral/SAR VLM
understanding, a live Bhoonidhi integration, or sovereign production hosting.
Those are later validation milestones, not claims we make before measuring them.

## Verdict

This plan is deliberately more shippable than the master plan: it substitutes
citable open remote-sensing models for an unaffordable custom backbone, keeps
all numerical EO work deterministic, and avoids a chat-transcript UI,
RemoteCLIP-as-VQA, fabricated cost claims, and hosted LLM APIs.

However, **M1 adaptation is a compliance gate, not a later enhancement**. An
off-the-shelf GeoChat integration is remote-sensing adapted by its authors, not
by this team. Before the frontend work begins, the team must complete and
record one small, reproducible adaptation experiment using BigEarthNet.txt or
another permitted open remote-sensing training set. Full-corpus training is not
required for this MVP; an honest executed run is.

---

## 1. Fixed architecture decisions

| # | Decision | Choice | Rationale |
|---|---|---|---|
| ADR-001 | Frontend | Next.js App Router + TypeScript + Tailwind CSS on Vercel | Fast, polished demo UI and Git-based preview deployments on a free tier. |
| ADR-002 | Backend | FastAPI + Pydantic, Python 3.11+ | Best fit for raster tooling, ML integrations and typed trace schemas. |
| ADR-003 | Persistence | Filesystem for uploads/results plus SQLite for local metadata; no database in the first vertical slice | Zero setup and a portable judge-laptop demo. PostgreSQL is a later migration only if concurrent users are needed. |
| ADR-004 | Job model | Asynchronous FastAPI jobs with polling | GeoTIFF processing and GPU inference cannot be held in a browser request. No Celery, Redis or message broker. |
| ADR-005 | Single-image RS VLM | GeoChat adapter | GeoChat is designed for remote-sensing captioning, VQA and grounding. It receives a rendered 3-channel preview, never raw bands. |
| ADR-006 | Change model | ChangeFormer adapter | A specialist Siamese remote-sensing change model is a better MVP fit than asking a general VLM to infer change. |
| ADR-007 | Controller | Local sentence-transformer template matching + deterministic typed DAG | Canonical query templates improve paraphrase coverage without stochastic routing. Thresholded matching and the executor are deterministic; ambiguous queries are rejected. |
| ADR-008 | Raster and geodesy | Rasterio/GDAL, NumPy/SciPy, PyProj, Shapely | Standard open-source EO stack; coordinates and numerical answers stay deterministic. |
| ADR-009 | GPU execution | Modal worker for short, manual GPU jobs; local mock/model-disabled mode by default | Fits the budget without making the product unusable when the free credit is unavailable. |
| ADR-010 | Vercel boundary | Vercel hosts only the UI; browser uploads directly to the backend | Do not bundle models/GDAL in Vercel Functions or proxy large rasters through Vercel. |
| ADR-011 | Demo deployment | FastAPI + SQLite run on the team laptop; a temporary Cloudflare Tunnel is used only for remote public-sample demos | Resolves where state lives and keeps the backend portable. Never deploy the backend itself to Modal while SQLite/filesystem persistence is used. |
| ADR-012 | Visual system | Dark-default mission-control/GIS interface with functional colour tokens | The imagery and evidence lead; colours communicate modality, state and confidence rather than decoration. |

### Data-flow boundary

```text
Browser / Next.js UI (Vercel, or local Next.js for an offline demo)
   ├─ displays metadata, preview, masks, trace and report
   └─ uploads raster directly to FastAPI
                         │
                         ▼
FastAPI backend (team laptop; temporary tunnel only when remote access is required)
   ├─ validates GeoTIFF/TIFF/PNG/JPEG
   ├─ preserves native bands for GIS/SAR calculations
   ├─ creates RGB / false-colour preview for GeoChat only
   ├─ runs ChangeFormer on co-registered preview pairs
   ├─ compiles and executes a typed tool DAG
   └─ returns visual evidence + ObservableExecutionTrace
```

**Critical rule:** no generic VLM receives raw 12-band Sentinel-2 data or raw
SAR DN. Native bands are used only by deterministic raster/SAR tools. Any VLM
input is a documented RGB or false-colour render with its band mapping recorded
in the trace.

### Vercel and Modal limits

Vercel is a frontend host, not the ML backend. Do not deploy PyTorch, GeoChat,
ChangeFormer, GDAL or uploaded raster storage in a Vercel Function. Keep API
URLs in `NEXT_PUBLIC_API_BASE_URL`; keep no model secrets in the frontend.

The Vercel Hobby plan, Cloudflare Tunnel and Modal are suitable for a prototype
but not the final sovereign-hosting claim. Do not send restricted imagery or
sensitive coordinates through any of them. For a sovereign/offline demo, run
both Next.js and FastAPI locally; use the Vercel/tunnel route only with public
sample imagery. Modal remains a GPU worker, never the stateful backend: its
ephemeral containers are incompatible with the SQLite/filesystem persistence
chosen in ADR-003.

---

## 2. MVP capability boundary

| Capability | MVP status | Implementation |
|---|---|---|
| GeoTIFF/TIFF ingestion and compatibility report | Must build | Rasterio metadata, checksum, CRS/GSD/band count checks |
| Native spectral indices and geodesy | Must build | NDVI/MNDWI/NDBI, affine transform, PyProj, Shapely |
| SAR calibration/despeckling | Must build as a parameterised prototype | Metadata-fed calibration interface; document unverified sensor field mappings |
| Satellite captioning/VQA/grounding | Must integrate | GeoChat over RGB/false-colour previews |
| Bi-temporal change evidence | Must integrate | ChangeFormer mask + deterministic area calculation |
| Agentic orchestration / trace | Must build | Local embedding-template matcher, deterministic router, tool registry, Pydantic `ObservableExecutionTrace` |
| Team-executed RS adaptation (M1) | **Must complete before Phase 3** | 2,000–5,000-sample LoRA/QLoRA run over GeoChat projection/language layers, with frozen vision backbone if VRAM requires it |
| Next.js evidence UI | Must build | Upload, job state, map/preview, mask, trace, report |
| Full BigEarthNet.txt adaptation | Later | Scale only after the required small, reproducible adaptation run is measured |
| Wavelength-keyed SatCore band adapter | Later | Design interface now; do not implement/train a custom backbone for MVP |
| Full benchmark scores / GSD curve | Later evidence | Build harness plumbing after the vertical slice works |
| Bhoonidhi live STAC | Optional | Use public, staged samples first; no credentials required for MVP |

**M1 gate:** Phase 2 must produce a team-executed, reproducible small LoRA run
on BigEarthNet.txt (or another PS-permitted open RS training dataset), a pinned
checkpoint, and before/after metrics on a held-out VRSBench or RSVQA-LR slice.
It is acceptable for the slice to be as small as 100 examples and for the delta
to be small; it is not acceptable to omit the run or invent the result.

**Honesty requirement:** the repository and demo must label GeoChat/ChangeFormer
as existing open-model integrations, plus the separate team LoRA checkpoint.
It must not claim SatCore, full-corpus training, or benchmark performance beyond
the exact recorded experiment.

---

## 3. Repository layout

```text
SatQuery/
├── frontend/                         # Next.js application deployed to Vercel
│   ├── app/
│   │   ├── page.tsx                  # workspace / upload page
│   │   ├── jobs/[id]/page.tsx        # persisted job result view
│   │   ├── api/health/route.ts       # lightweight UI health check only
│   │   └── globals.css                # design tokens and dark-default base styles
│   ├── components/
│   │   ├── RasterUpload.tsx
│   │   ├── MetadataPanel.tsx
│   │   ├── EvidenceViewer.tsx
│   │   ├── TracePanel.tsx
│   │   ├── DagTimeline.tsx
│   │   ├── GuardrailBanner.tsx
│   │   └── StatusIndicator.tsx
│   ├── lib/api.ts
│   └── .env.example                  # NEXT_PUBLIC_API_BASE_URL only
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── schemas.py                # API DTOs and trace models
│   │   ├── api/
│   │   │   ├── ingest.py
│   │   │   ├── jobs.py
│   │   │   └── health.py
│   │   ├── ingestion/
│   │   │   ├── raster.py
│   │   │   ├── compatibility.py
│   │   │   └── preview.py
│   │   ├── tools/
│   │   │   ├── spectral.py
│   │   │   ├── sar.py
│   │   │   ├── geodesy.py
│   │   │   ├── guardrail.py
│   │   │   └── registry.py
│   │   ├── models/
│   │   │   ├── base.py
│   │   │   ├── geochat.py
│   │   │   ├── changeformer.py
│   │   │   └── mock.py
│   │   ├── orchestration/
│   │   │   ├── schema.py
│   │   │   ├── router.py
│   │   │   └── executor.py
│   │   ├── storage/
│   │   │   ├── jobs.py               # SQLite / filesystem repository
│   │   │   └── artifacts.py
│   │   └── reports/
│   │       └── geojson.py
│   ├── tests/
│   ├── requirements.txt
│   └── .env.example
├── modal_worker/
│   ├── app.py                        # optional Modal functions; no UI code
│   └── README.md
├── training/
│   ├── finetune_geochat_lora.py       # Phase 2 M1 run
│   └── reproduce_m1_run.md            # commands, data split and measured output
├── data/
│   └── seed/                         # small public, committed demo fixtures only
├── docs/
│   ├── adr/
│   ├── STATUS.md
│   ├── OPEN_ITEMS.md
│   ├── KNOWN_LIMITATIONS.md
│   └── RUNBOOK.md
├── README.md
└── execution_plan.md
```

Do not commit model weights, downloaded datasets, user uploads, Modal tokens,
or Vercel tokens. Git-ignore `data/uploads/`, `data/artifacts/`, model caches,
`.env*` (except examples), and SQLite runtime files. Add
`training/finetune_geochat_lora.py` and `training/reproduce_m1_run.md` when
Phase 2 starts; the latter records source dataset revision, sample IDs/split,
prompt format, command, seed, checkpoint, hardware, elapsed GPU time and metrics.

---

## 4. Frontend design system — mission-control / professional GIS

### Design rules

The audience is a panel on a projector, a remote-sensing analyst, and the demo
operator under pressure. The reference class is QGIS, Sentinel Hub EO Browser,
NASA Worldview, Grafana and Datadog—not a consumer SaaS landing page.

1. **Imagery is the hero.** Chrome is quiet: no glassmorphism, marketing
   gradients, oversized shadows, illustrations or decorative colour.
2. **Dark is the default.** Do not build a light theme for the MVP. The
   blue-shifted near-black background preserves contrast around bright rasters
   under projector lighting.
3. **Every non-neutral hue has one data meaning.** Cyan identifies optical
   evidence; violet identifies SAR evidence; green, amber and red identify
   status/confidence. Never use these colours as interchangeable decoration.
4. **Scientific visualisations keep scientific ramps.** NDVI uses brown→green,
   water indices use blue, and SAR backscatter uses grayscale or amber. Never
   brand-tint a raster or mask.
5. **Measured values are monospace.** CRS, GSD, coordinates, checksums, tool
   names, latency and trace JSON use the mono face. UI labels and prose use the
   sans face.
6. **Surfaces are flat and sharp.** Default cards have a 1px border and 8px
   radius; compact status chips use 4px. Avoid 16px+ radii and soft shadows.

### Token contract

Define these properties in `frontend/app/globals.css`, then expose semantic
Tailwind utilities from the same values. Do not place raw hex values in React
components.

```css
:root {
  --bg-base: #0A0E14;
  --bg-surface: #121821;
  --bg-surface-2: #1B222D;
  --border-subtle: #232B38;
  --border-default: #2E3846;

  --text-primary: #E6EAF0;
  --text-secondary: #9AA5B4;
  --text-muted: #616E80;

  --accent-optical: #22D3EE;
  --accent-sar: #C084FC;
  --status-success: #4ADE80;
  --status-warning: #FBBF24;
  --status-critical: #F87171;

  --radius-card: 8px;
  --radius-pill: 4px;
}
```

Use self-hosted `Inter` through `next/font` for UI text and self-hosted
`JetBrains Mono` (or IBM Plex Mono) for measured data. Base type is 14–15px in
dense panels and 16px for primary reading; never render text below 12px. Use
`lucide-react` line icons only.

| Semantic use | Visual treatment |
|---|---|
| Optical-derived evidence | `--accent-optical` border/dot/chart series plus an explicit `OPTICAL` text label |
| SAR-derived evidence | `--accent-sar` border/dot/chart series plus an explicit `SAR` text label |
| `VALIDATED` / `COMPLETED` / confidence ≥0.8 | Success dot/bar and text label |
| `REJECTED`, guardrail, or confidence 0.5–0.8 | Warning dot/bar and text label |
| `FAILED` or confidence <0.5 | Critical dot/bar and text label |

Never communicate state through colour alone: pair every dot, bar or coloured
border with text and, where useful, a Lucide icon. Confidence must state whether
it is `model-provided`, `rule-derived`, or `unavailable`.

### Component requirements

| Component | Required treatment |
|---|---|
| `TracePanel` | Console-like rows, never chat bubbles. Mono step number/tool name; modality dot + label; right-aligned mono latency; thin confidence bar using the status scale. |
| `DagTimeline` | Horizontal, thin-line flow. Nodes show icon, tool name and latency. Only the active optical node may use a restrained cyan pulse; no animated gradients or large spinners. |
| `GuardrailBanner` | Amber 1px left border and warning icon, not a red toast. State that the system correctly prevented an unresolvable request. |
| `MetadataPanel` | Compact key/value grid modeled on a QGIS properties dialog. Values are right-aligned mono: CRS, GSD, extent, band count, sensor, checksum. |
| `StatusIndicator` | The only job-status component. Reuse its dot + label for `RECEIVED → VALIDATED → ROUTING → EXECUTING → COMPLETED/REJECTED/FAILED` everywhere. |
| `EvidenceViewer` | Large, uncluttered raster area over a dark background; overlays have legend, modality label and visible opacity control. Native scientific ramps are mandatory. |

Use shadcn/ui primitives for accessible dialogs, buttons, tabs and tooltips, but
apply this token system rather than its default rounded marketing appearance.
Use MapLibre GL JS for map/viewer integration. MapLibre itself has no token or
licence fee, but it does **not** provide raster basemap tiles: the MVP should
work with the uploaded raster alone and add a public tile source only after its
terms and usage limits are reviewed. Use Recharts only when a measured GSD or
confidence series actually exists.

### Visual acceptance criteria

- No gradients, glass effects, rounded-pill primary buttons, heavy shadows or
  chat-bubble layouts exist in the shipped UI.
- Every optical/SAR artifact and trace step is distinguishable by the same
  cyan/violet token **and** textual modality label.
- Scientific layers retain their native ramps and have a legend.
- Metadata and trace values are legible in mono at projected size.
- Rehearse the final flow under the expected room/projector lighting and record
  any contrast/type adjustments in `docs/RUNBOOK.md`.

---

## 5. API and trace contract

### Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /health` | Backend availability and enabled-model modes; never exposes secrets |
| `POST /api/ingest` | Validate/upload one image and return metadata + an image id |
| `POST /api/jobs` | Create an analysis job from image id(s) and natural-language query |
| `GET /api/jobs/{id}` | Poll job status and fetch final structured result |
| `GET /api/jobs/{id}/trace` | Fetch the immutable execution trace |
| `GET /api/jobs/{id}/artifacts/{name}` | Fetch preview, change mask, GeoJSON or report |

### Required trace properties

`ObservableExecutionTrace` must include:

- trace ID, timestamps, task classification and input summary;
- ordered tool steps, their safe parameters, latency and confidence where
  available;
- render recipe used for a VLM input (for example, `B4/B3/B2` or a documented
  false-colour mapping);
- outputs/artifact references and the final answer;
- explicit limitations and fallback/model mode (`mock`, `local`, `modal`);
- a per-result confidence labelled as model-provided, rule-derived, or
  unavailable—never invented.

The router may select only names from a Python `Enum`/Pydantic `Literal` tool
registry. It cannot emit shell commands, Python code, arbitrary URLs or raw SQL.

---

## 6. Execution phases

Each phase is a vertical slice. Do not begin the next phase until its exit
criteria pass. All model adapters must offer a deterministic/mock mode so tests
do not require GPU access or model downloads.

### Phase 0 — Scaffold and contracts

Build the repository layout, FastAPI `/health`, Next.js landing page, shared API
types, `.env.example` files, `.gitignore`, and ADR documents 001–012. Configure
two documented demo modes: local/offline (`Next.js → localhost FastAPI`) and
remote-public-sample (`Vercel Next.js → temporary Cloudflare Tunnel → laptop
FastAPI`). The latter is never used for restricted imagery.

Implement SQLite/filesystem job persistence, the job state machine
`RECEIVED → VALIDATED → ROUTING → EXECUTING → COMPLETED|REJECTED|FAILED`, and
tests for legal/illegal state transitions.

**Exit criteria**

- Backend starts locally and `/health` returns enabled modes.
- Next.js starts locally and renders a backend health indicator.
- The UI does not contain a model token or backend secret.
- State transition tests pass.
- `docs/RUNBOOK.md` states exactly which demo mode will be used during judging.

### Phase 1 — GeoTIFF ingestion and deterministic EO tools

Implement content-validated GeoTIFF/TIFF/PNG/JPEG ingestion. GeoTIFF/TIFF is
the general geospatial input path. PNG/JPEG is accepted **only** when the caller
explicitly marks it as a prescribed benchmark fixture/dataset input; it is not a
general geospatial upload format. For a GeoTIFF, extract CRS, affine transform,
GSD, extent, band count, dtype, nodata, sensor tags and SHA-256 checksum. For a
two-image job, verify CRS compatibility and spatial overlap; return specific
rejection reasons.

Implement RGB/false-colour preview generation, NDVI/MNDWI/NDBI, pixel-to-WGS84
bounding-box conversion, polygon area, change-area calculation and the Nyquist
guardrail. The guardrail must trigger only when target size is below roughly
2–3× input GSD; it must not fire for a vehicle/structure-sized target at
Cartosat-2S-scale 0.65 m GSD. Implement the SAR calibration/despeckle interface,
but require calibration factor and incidence angle to be supplied from metadata;
never hardcode product constants. Keep any SAR water backscatter threshold
unset/configurable until a Sentinel-1/RISAT/NISAR water-detection source has
been recorded in `docs/OPEN_ITEMS.md`; no unverified −18 dB rule is allowed.

**Exit criteria**

- Uploading a seed GeoTIFF returns CRS, GSD, extent, bands and checksum.
- Preview output records its exact band mapping.
- Spectral and geodesy functions have known-value unit tests.
- A random PNG/JPEG upload is rejected; a benchmark-labelled fixture is accepted.
- Guardrail tests cover both its 2–3× trigger condition and its required
  non-trigger Cartosat-2S case.
- Invalid/non-georeferenced inputs and incompatible pairs are rejected safely.

### Phase 2 — Open remote-sensing adapters + required M1 adaptation gate

Create the `models/base.py` interface with `caption`, `answer`, `ground`, and
`detect_change` capabilities. Add:

- `GeoChatAdapter`, accepting only documented 3-channel preview files;
- `ChangeFormerAdapter`, accepting a validated co-registered preview pair;
- `MockModelAdapter`, returning fixture outputs for local tests and demos when
  no GPU/model is available.

Pin model source, checkpoint revision and licence status in `docs/STATUS.md`.
Do not assume a code repository licence applies to model weights or datasets.
Treat the GeoChat checkpoint as `licence-unverified` until its model card and
all material upstream dependencies (including any Vicuna-derived weights) have
been checked for local-use, redistribution and commercial-use terms.

**Required M1 deliverable — do not start Phase 3 until this is complete:**

1. Take a deterministic, documented 2,000–5,000 sample subset of
   BigEarthNet.txt (or another PS-permitted open RS dataset), with a held-out
   split. Record source revision, sample IDs and the split seed.
2. Run LoRA/QLoRA on GeoChat's projection/language layers; freeze the vision
   backbone when VRAM is constrained. Use one short Modal A10/A100 session if
   available. This is a team adaptation run, distinct from upstream GeoChat.
3. Save the adapter/checkpoint reference and complete a before/after evaluation
   on one held-out RSVQA-LR or VRSBench slice (minimum 100 examples). Record the
   exact command, random seed, GPU, runtime, prompts, metrics and limitations.
4. If the free GPU path fails before training completes, resolve it before Phase
   3 by using a different free GPU session or reducing the subset/model layers.
   Do not replace this deliverable with a promise to run it later.

**Exit criteria**

- Adapter contract tests pass in mock mode without internet/GPU.
- A model-disabled backend produces a clear `model_unavailable` result rather
  than a 500 error.
- GeoChat receives a preview only; a test proves raw raster arrays cannot cross
  its adapter boundary.
- ChangeFormer output is saved as a mask artifact and converted to a
  deterministic area when georeferencing is available.
- The M1 run has a reproducibility record, pinned LoRA checkpoint and an honest
  before/after table for its held-out slice. This is a hard gate for Phase 3.

### Phase 3 — Typed router, executor and trace

Implement a deterministic query classifier and router. Embed the incoming query
with a local `sentence-transformers` model, compare it to versioned canonical
templates using a fixed similarity threshold, then select a fixed DAG. Below the
threshold or near a tie, reject the query as unsupported and show supported
examples; do not guess. This preserves zero probabilistic routing while handling
normal paraphrases better than keywords alone. It maps supported query types to
fixed tool DAGs, for example:

| Query type | Initial DAG |
|---|---|
| water/vegetation/urban question | preview → relevant spectral index → GeoChat VQA → geodesy if region exists |
| caption or scene question | preview → GeoChat caption/VQA |
| object/region request | preview → GeoChat grounding → geodesy |
| before/after change | compatibility check → previews → ChangeFormer → change area → optional GeoChat summary |
| optical + SAR water request | SAR calibration → despeckle → MNDWI → consistency rule → GeoChat summary |

The executor runs only registered tools, records latency/errors and persists an
immutable Pydantic-validated trace. Query text and parsed metadata are the only
inputs to the router; it never sees pixels or files. The trace records the
canonical template ID, similarity score, threshold and deterministic router
version. The defense statement is: **“Our orchestrator has zero probabilistic
components—routing is deterministic by construction.”**

**Exit criteria**

- Each supported query generates a schema-valid trace in mock mode.
- A tool failure transitions the job to `FAILED`, preserves prior step details,
  and never returns a fabricated answer.
- A repeated job request is idempotent for a short configurable window.
- Paraphrase fixtures verify that expected variants select the same canonical
  template; unsupported/ambiguous inputs are rejected rather than misrouted.

### Phase 4 — Next.js/Vercel evidence UI

Implement the design-system contract in §4 before composing the page. Configure
dark-default tokens in `app/globals.css`, load Inter and JetBrains Mono with
`next/font`, add Lucide, and use shadcn/ui primitives only where they preserve
the instrument-panel treatment. Build the UI in `frontend/`:

- upload form with clear direct-to-backend upload status;
- metadata card: format, CRS, GSD, band count, extent and sensor;
- query form and polling job-state indicator;
- evidence viewer for RGB/false-colour preview, masks and bounding boxes;
- trace panel and simple DAG timeline, not a chat transcript;
- guardrail/refusal display and GeoJSON download link;
- visibly labelled model mode and known limitations.

Add MapLibre only for the evidence viewer/map interactions; it must function
without a third-party basemap. Add Recharts only after real chart data exists.
Apply cyan optical and violet SAR markers consistently to evidence, trace rows,
legends and chart series, always paired with text labels. Preserve scientific
raster ramps and add legends—never recolour them to the app accent colours.

Configure Vercel only with `NEXT_PUBLIC_API_BASE_URL`. Use CORS on the FastAPI
backend for the deployed Vercel URL and local development origin. Test direct
browser upload; do not create a Next.js route that relays raster bytes.

**Exit criteria**

- The full seed-fixture flow works: upload → metadata → query → trace → artifact.
- The frontend is deployable to Vercel with no model/GDAL dependency.
- A large-file rejection is shown before a misleading failed job state.
- The visual acceptance criteria in §4 pass in a desktop screenshot review and
  a projector-lighting rehearsal; no consumer-SaaS treatment slips into the UI.

### Phase 5 — Optional Modal inference integration

The Phase 2 M1 training run may already have used Modal. This phase implements
optional end-to-end Modal *inference* only after the local/mock vertical slice
works. `modal_worker/app.py` must call the same adapter contract as the backend,
use an explicit `MODEL_MODE=modal` setting, have a timeout, and release
resources after each job. Cache weights only if within the free-tier allowance.

Start with one short GeoChat or ChangeFormer inference against a public sample.
Log GPU runtime and status, but never publish unmeasured accuracy claims. If a
payment method, credits or GPU allocation is unavailable, the application must
remain usable in mock/local mode.

**Exit criteria**

- One public-sample model job completes through the Modal adapter, or the
  limitation is documented without blocking all other phases.
- Backend/UI work unchanged when `MODEL_MODE=mock`.
- No Modal credential is committed or exposed to the browser.

### Phase 6 — Evaluation and handoff

Add lightweight loaders/fixtures for VRSBench, RSVQA and CDVQA. The required
M1 adaptation experiment was completed in Phase 2; this phase broadens
evaluation only when free GPU time permits. Run a GSD ladder or larger benchmark
slice only when the result can be retained with its exact model/checkpoint,
dataset split, command and hardware metadata.

Write `docs/KNOWN_LIMITATIONS.md`, including:

- existing open-model integration is not SatCore;
- GeoChat/ChangeFormer preview limitations and no raw multispectral/SAR neural
  input;
- which claims are mock-tested, locally tested, or Modal-tested;
- Vercel/Modal are prototype hosting only and do not support the final sovereign
  deployment claim;
- adaptation and benchmark status, with no fabricated numbers.

**Exit criteria**

- README provides local backend, local UI and Vercel deployment instructions.
- Tests cover upload validation, deterministic tools, router output, failure
  states and the mock end-to-end path.
- Demo uses public seed imagery and can run with no paid service.

---

## 7. Claims and USP status

Only claim an item when its stated evidence exists. The table is deliberately
stricter than the master plan's aspirational USP list.

| Claim / USP | Status after this plan | Evidence required before it may appear in the demo |
|---|---|---|
| Wavelength-keyed native band adapter | Deferred | A tested SatCore implementation and results; do not imply GeoChat provides this. |
| Team RS adaptation / M1 | Required Phase 2 gate | Pinned LoRA checkpoint plus reproducible before/after held-out results. |
| Indian NISAR/Bhoonidhi validation | Deferred | Successful authenticated request and retained validation results. |
| GSD degradation curve | Deferred | Saved run metadata and measured six-point curve. |
| Typed observable execution trace | Live once Phase 3 passes | Pydantic-valid trace and end-to-end test. |
| Metadata-driven SAR calibration chain | MVP prototype | A documented sensor metadata mapping; otherwise label as parameterised, not validated. |
| No foreign **model API** | Live | No OpenAI, Gemini, Claude, or similar model API in source/dependency configuration. |
| Sovereign/no foreign inference deployment | Deferred | It cannot be claimed while a Vercel, Cloudflare Tunnel, or Modal route handles real inputs/inference. Demonstrate locally with public data only. |

---

## 8. Security and reliability rules

- Validate upload content with Rasterio/Pillow, not file extension alone; cap
  size and dimensions before processing.
- Never use `subprocess`, `eval()` or `exec()` with user-derived values.
- Store uploads and artifacts under generated IDs, never user-provided paths.
- Validate every tool step against the fixed registry before execution.
- Return stable, actionable `REJECTED` messages for input problems and `FAILED`
  messages with a request ID for system problems.
- Keep all keys in backend/Modal environment variables. `NEXT_PUBLIC_*` values
  are public by definition and must never contain secrets.
- Do not log imagery, raw pixel arrays, tokens, or full sensitive coordinates.
- Use public imagery for any Vercel/Modal prototype demo.

---

## 9. Definition of MVP success

The MVP is complete when a user can upload a public GeoTIFF, see validated EO
metadata, ask a supported query, receive visual/deterministic evidence, inspect
a typed execution trace, and download a GeoJSON artifact through the Next.js UI.

The strongest honest demo statement is:

> “This prototype combines open remote-sensing models with deterministic native
> GeoTIFF, SAR and geodesy tools. Every result has an observable execution trace.
> SatCore adaptation and full benchmark validation are the next measured phase.”
