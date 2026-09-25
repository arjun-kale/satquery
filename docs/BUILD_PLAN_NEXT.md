# SatQuery AI: build plan for the next coding session

> Handoff written 2026-09-24. Read this file first, then `SATQUERY_UX_BRIEF.md` (the product spec)
> and `elite_ui_ux_design_system_for_coding_agents.md` (the design doctrine). `docs/OPEN_ITEMS.md`
> has the running list of known gaps. The brief wins over this plan where they disagree.

---

## 0. Rules that must not be broken

These are the product's core promise (brief §0, §12 "Honesty") and the reason judges will trust it.

1. **Never show data the backend didn't produce.** No fake progress, invented confidence, simulated
   steps presented as real, or numbers written by a language model presented as measurements.
2. **Numbers come from pixels.** Areas and percentages are pixel counts × pixel ground area. Model
   text that contains numbers is marked "stated by the model, not measured" (`splitModelQuantities`).
3. **Label what actually ran.** Every step records the weights it used (`outputs.weights`). The UI
   credits the M2 adapter only where it was used. Do not relabel base-model output as M2.
4. **Boxes are brackets, masks are outlines, the evidence is never covered** (Evidence Lens, brief §7).
5. **Colour discipline:** cyan = optical, violet = SAR, yellow = focused evidence only,
   orange = change only. Filled buttons use `--color-action` (#2563EB); `--color-accent` (#3B82F6)
   is for focus rings and non-text marks. Faint text is #808A99 (≥ 4.5:1).
6. **Mock mode is a developer fallback, never a demo state.** The default is real models.

---

## 1. Where things stand

### 1.1 Git

- Branch `main`. **10 commits are ahead of `origin/main` and not pushed** (`git push origin main`).
- Working tree clean. Commit style: conventional commits, one line, no co-author/tool trailers.

### 1.2 What is real

| Step (tool name) | Status | Where |
|---|---|---|
| `preview` quick-looks (2–98 % stretch, 512 px; SAR in dB, fixed −25…0) | Real | `app/ingestion/preview.py` |
| `compatibility` (same CRS, overlap) | Real | `dispatcher.py`, `ingestion/compatibility.py` |
| `spectral_index` (NDVI / NDWI / MNDWI from **declared** band names) + outlines | Real, rule | `dispatcher.py` |
| `index_change` (water gained/lost, MNDWI or NDWI T1 vs T2) | Real, rule | `dispatcher._index_change` |
| `changeformer` (ChangeFormer V6, DSIFN weights, local CPU ~5 s) | Real model | `app/models/changeformer.py` |
| `change_area`, `geodesy` | Real | `dispatcher.py`, `tools/geodesy.py` |
| `sar_calibrate` (skips if the file declares calibrated; applies with metadata; else fails) | Real | `dispatcher.py` |
| `sar_despeckle` (Lee filter 5×5), `sar_water` (VV < −18 dB) | Real, rule | `dispatcher.py`, `tools/sar.py` |
| `cross_modal_fusion` | Real but trivial (SAR as a red overlay) | `tools/fusion.py` |
| `geochat_vqa`, `geochat_grounding` | Real, Modal GPU, **M2 adapter** | `modal_worker/infer.py` |
| `geochat_caption` | Real, Modal GPU, **base weights** (M2 adapter off) | `modal_worker/infer.py` |
| `change_vqa` | Real, but the VLM sees **only the T1 quick-look** | `dispatcher.py` |

### 1.3 Architecture in one screen

```text
Next.js 15 (frontend/)                                  FastAPI (backend/)
useChat + DefaultChatTransport ──POST /api/chat──▶ app/api/chat.py  (UI Message Stream v1, SSE)
   onData(data-job, data-trace) → reducer             │  runs DAGExecutor in a thread; on_trace hook
trace polling (fallback / reload)  ◀─GET /api/jobs/{id}/trace
uploads  ──POST /api/ingest──▶  app/api/ingest.py  (+ /api/images/{id}, /preview.png, /window.png)
scene checks ─POST /api/scene-sets/validate─▶ app/api/scene_sets.py
samples  ──GET /api/samples, POST /api/samples/{id}/load──▶ app/api/samples.py
                                                       │
                          router.py (MiniLM templates, v1.1.0) → fixed DAG per task
                          dispatcher.py → tools / adapters → artifacts/<job>/trace.json
                          GeoChat (+M2 LoRA) on Modal: app `satquery-m1-infer`, class `GeoChatInfer`
                          ChangeFormer V6 local CPU: data/models/changeformer/
```

Frontend map:

| Area | Files |
|---|---|
| State (reducer, selectors) | `components/workspace/store.tsx` |
| Health, persistence, polling, job actions | `components/workspace/effects.ts` |
| AI SDK streaming (ask/stop/retry) | `components/workspace/stream.ts` |
| Shell, hotkeys, report, toast | `components/workspace/workspace.tsx` |
| Empty state + samples, upload flow, rail, top bar | `empty-state.tsx`, `scene-composer.tsx`, `scene-rail.tsx`, `top-bar.tsx` |
| Viewer, pan/zoom, lens, layers | `components/viewer/*` |
| Thread, timeline, answer, prompt | `components/conversation/*` |
| Trace drawer (Steps / Layers / JSON) | `components/trace/trace-drawer.tsx` |
| Trace → view model (evidence, answer, layers, timeline) | `lib/analysis.ts` |
| Vocabulary, confidence mapping, geo, report, API types | `lib/vocabulary.ts`, `lib/confidence.ts`, `lib/geo.ts`, `lib/report.ts`, `lib/types.ts`, `lib/api.ts` |

---

## 2. Running it

```bash
# backend (real models are the default; needs Modal credentials for VLM steps)
cd backend && .venv/bin/uvicorn app.main:app --port 8000 --reload --reload-dir app
# free UI development: labelled placeholders, no GPU
cd backend && SATQUERY_MODEL_MODE=mock .venv/bin/uvicorn app.main:app --port 8000 --reload --reload-dir app

# one-time data (gitignored)
cd backend && .venv/bin/python scripts/fetch_samples.py        # Sentinel-2/1 sample scenes
cd backend && .venv/bin/python scripts/fetch_changeformer.py   # ~1 GB download → 164 MB weights

# frontend
cd frontend && npx next dev -p 3000

# checks
cd backend && .venv/bin/pytest -q            # 87 tests
cd frontend && npx tsc --noEmit -p . && npm run lint
cd frontend && npm run build                 # ONLY while `next dev` is stopped (see §6)
```

---

## 3. Remaining work, in priority order

Each item: why it matters → what to do → how to know it's done.

### P0: before any demo

**P0.1 Push and tag.** `git push origin main`, then tag the demo build (`git tag demo-sih-2026`).

**P0.2 Commit the browser end-to-end tests into the repo.** The Playwright scripts used this session
lived in a temporary scratch folder and are gone. Recreate them under `frontend/e2e/` with
`@playwright/test` (Chromium is already installed at `~/.cache/ms-playwright/chromium-1234`).
Cover, against a **mock-mode** backend:
- F0: empty state renders, three samples load.
- Sample → Enter → answer, with **one `/api/chat` response, `x-vercel-ai-ui-message-stream: v1`,
  and zero `/trace` polls during the run**.
- Chip hover ↔ region highlight; key `1` zooms to region ①; `T` opens the trace; `L` loupe shows
  "native pixels".
- Failures: CRS-mismatch pair shows the failing check; PNG upload shows the benchmark rule; backend
  offline (route-abort `localhost:8000`) shows "Backend offline".
- Reload restores the analysis; mobile 390×844 and tablet 900×1100 screenshots.
- `reducedMotion: "reduce"`: flicker paused, "Space to switch" visible.

Done when `npx playwright test` passes locally and is documented in the README.

**P0.3 Demo-day Modal warm-up.** Cold start is 30–50 s. For a judging window, set `min_containers=1`
in `modal_worker/infer.py` and redeploy, then set it back to `0` afterwards: an A10G costs ≈ $1.10/h
kept warm. **Ask the owner before any GPU spend and give a dollar estimate.**

**P0.4 Delete the dead adapter.** `backend/app/models/modal_adapter.py` doesn't import (it references
a non-existent `VLMAdapter`) and contains fabricated `0.95` confidence defaults. Nothing uses it;
remove it.

### P1: answer quality (the judges read this)

**P1.1 The change VLM only sees T1.** `change_vqa` sends only `preview.png` to a single-image model.
Options: (a) send a side-by-side composite (T1 | T2 with labels) and prompt "left is before, right is
after"; (b) drop `change_vqa` from the CHANGE DAG and rely on the measured lead sentence
(`lib/analysis.ts` `measuredLead`). Try (a) on the reservoir sample. If the text still says "cannot
determine", do (b). Record the choice in `docs/OPEN_ITEMS.md`.

**P1.2 Router misses plain phrasing.** "Where is the water?" scores 0.56–0.58 (threshold 0.60), so
users see "I'm not sure what kind of question this is". Add natural templates to
`CANONICAL_TEMPLATES` in `app/orchestration/router.py` (e.g. "where is the water", "show me the
water", "how much water is there", "is there vegetation", "what is in this picture", "find the
buildings"), bump `ROUTER_VERSION` to `v1.2.0`, and add a paraphrase test set
(`tests/orchestration/test_router.py`) of about 30 real questions with expected tasks. Keep the tie
rule. Done when every paraphrase in the set routes correctly and the existing tests still pass.

**P1.3 M2 weaknesses (needs GPU budget, ask first).** From `docs/STATUS.md` and this session:
- Captions overfit to the BigEarthNet Lithuania/Summer template (which is why captions now use base
  weights).
- Referring-expression grounding is not learned: the model returns a whole-image box.
- Base weights hallucinate US-centric objects ("baseball diamonds").

Plan: a new training round on more regions and seasons, including Indian scenes, with the staged
pipeline in `modal_worker/train_m2.py`. Measure on a held-out Indian set before switching `caption`
back to the adapter. The rate measured last time was ~2.5 s per example (≈ $1.50/GPU-hour).

**P1.4 Flag whole-image boxes.** When a grounding box covers ≥ 90 % of the image, show it as
"Needs review — the model returned the whole image" (`deriveEvidence` in `lib/analysis.ts`) instead
of a normal region.

**P1.5 ChangeFormer domain gap.** DSIFN was trained on 2 m imagery; on 10 m Sentinel-2 it misses
large water change. Options: fine-tune on the OSCD dataset (Sentinel-2, 13 bands, 10 m) on Modal
(GPU budget; ask first), or keep it as a secondary land-cover signal. Its outlines already carry
"trained on DSIFN-CD, 2 m imagery".

### P2: brief items not yet built

| Brief § | Gap | Plan |
|---|---|---|
| §8.2 | No `data-progress` (e.g. ChangeFormer tile 3/4) or cold-start `data-status` transient parts | Add a progress callback in `ChangeFormerAdapter.detect_change` → executor → `chat.py` emits `{type:"data-progress", id: toolCallId, data:{done,total,unit:"tiles"}, transient:true}`; UI shows `3/4 tiles` on the active row only when present. For cold start, time the Modal call's first-token wait server-side and emit `data-status {phase:"cold-start", sinceMs}` only if Modal reports a new container (use `modal` container lifecycle info); otherwise keep the current "may be starting" hint. |
| §8.5 | Stop is between steps; an in-flight Modal call runs to completion | Use `modal` function-call handles (`.spawn()` + `FunctionCall.cancel()`) in `GeoChatAdapter._remote`; register the handle in `orchestration/cancel.py` so `request_cancel` can cancel it. Keep the "Stopping after current step…" label until cancellation is confirmed. |
| §8.5 | Persistence is ids in `localStorage` | SQLite `analyses` table (job id, scene-set id, question, created_at) + `GET /api/analyses`; restore from it on load, keep localStorage only for UI conveniences. |
| §F4 | Evidence chips are listed under the answer, not inline in the sentence | Only possible for the measured lead: have `measuredLead` return segments with evidence refs (e.g. "became water ①") and render chips inline. Do not ask the VLM for markers. |
| §F5 / §10 | Cursor readout has no pixel values / σ⁰ | `GET /api/images/{id}/pixel?col=&row=` returning raw band values (and dB for SAR); throttle to ~10 Hz in the viewer toolbar. |
| §F0 | Brief asks for a "Flood — two dates" sample | Add a Sentinel-1 before/after flood pair (e.g. Assam or Kerala monsoon) to `scripts/fetch_samples.py`; the SAR water rule works on it. Needs a SAR two-date path: route "bitemporal" + SAR modality to a new `sar_change` (water difference in dB). |
| §F7 | Report is HTML only | Add "Print / Save as PDF" (the report already has print CSS), or render a PDF server-side. |
| §8.1 | Types are hand-written mirrors of Pydantic | Generate `lib/types.ts` from FastAPI's OpenAPI (`openapi-typescript`) in a `npm run gen:types` script; commit the output. |
| §8.4 | AI Elements not used | Optional. The custom components already meet the behaviour; switching adds risk. |

### P3: product and deployment

- **P3.1 Vercel UI deploy.** The UI is static-ish (client-only workspace). Set
  `NEXT_PUBLIC_API_BASE_URL` to the public backend URL. Add the Vercel origin to
  `SATQUERY_CORS_ORIGINS`. The backend stays on the demo laptop behind a Cloudflare Tunnel
  (`docs/RUNBOOK.md`). Never route rasters through Vercel.
- **P3.2 GeoChat licence.** Still unverified (`docs/OPEN_ITEMS.md`). Resolve before any public demo.
  The UI names the model "SatQuery VLM"; the trace keeps the exact weights string as the audit
  record. Don't remove that from the trace.
- **P3.3 Fusion is a red overlay.** Replace with something defensible (e.g. RGB = optical R, G and
  SAR VV dB as blue, or an agreement map: optical water index vs SAR water) and label the method.
- **P3.4 Accessibility pass.** Keyboard-only F0→F5 works. Still to do: a screen-reader pass (NVDA or
  VoiceOver) over the run timeline's live region and the lens caption, plus a 200 % zoom check.

---

## 4. Contracts to keep stable

- **Trace schema** `app/orchestration/schema.py` (`TRACE_SCHEMA_VERSION = "1.1"`). If you add
  fields, bump the version and mirror them in `frontend/lib/types.ts`.
- **Stream parts** (`app/api/chat.py`): `start` (metadata `jobId`, `localId`), `data-job`,
  `data-trace` (id = job id, replaced in place), dynamic `tool-input-available` /
  `tool-output-available` / `tool-output-error` (`toolCallId = "<job>:<step index>"`),
  `text-start/-delta/-end` (answer text, sent whole), `finish`, `[DONE]`. **No `reasoning-*` parts.**
  The protocol tests are in `tests/test_chat_stream.py`.
- **Evidence geometry** is normalised 0–1 of the scene (x right, y down): `RegionOut.rings`, `bbox`.
- **Confidence words** come only from `lib/confidence.ts` `CONFIDENCE_BANDS`. The trace drawer shows
  that table.
- **Router DAGs** (`router.py` `QUERY_DAGS`). Changing a DAG means bumping `ROUTER_VERSION`.

---

## 5. How to verify a change (the loop used this session)

1. Backend unit and API tests: `pytest -q`. Add tests with synthetic rasters whose answer is known
   exactly (see `tests/orchestration/test_executor.py` `_water_tif`, `_sar_tif`).
2. Type-check and lint the frontend.
3. Run the UI against a **mock** backend in headless Chromium, and screenshot every state touched:
   desktop 1440×900, mobile 390×844, reduced motion.
4. Only then run **one** real-model question, with the owner's OK, and read the trace JSON: step
   times, weights, confidence.
5. Look at every screenshot. Several real bugs this session were only visible in screenshots
   (CORS image cache, marker clamped to the pane corner, raw box tokens shown as the answer).

---

## 6. Pitfalls already hit (don't repeat them)

| Symptom | Cause | Fix |
|---|---|---|
| `__webpack_modules__[moduleId] is not a function` in the browser | `npm run build` while `next dev` was running (both write `.next`) | Stop dev, `rm -rf frontend/.next`, restart. Build only with dev stopped. |
| Images blank in side-by-side; report export fails silently | A backend image loaded once without CORS was cached and reused for a `crossOrigin` request | Every backend `<img>` uses `crossOrigin="anonymous"`; no CSS `background-image` for backend images. |
| `sentence_transformers` import error after `pip install timm` | PyPI `torchvision` doesn't match the CPU `torch` build | `pip install --no-deps torchvision --index-url https://download.pytorch.org/whl/cpu` |
| `pkill -f "uvicorn …"` kills your own shell | The pattern matches the shell's command line | Use a bracket pattern: `pkill -f "[u]vicorn app.main:app --port 8000"` |
| UI runs were silently mock while `/health` said "modal" | `jobs.py` didn't pass `settings.model_mode` | Fixed; keep the mode coming from settings everywhere. |
| Sample question typed after the pre-fill got concatenated | The pre-filled draft wasn't selected | Fixed: the pre-fill is selected on focus. |
| Raw `{<0><0><100><100>\|<90>}` shown as the answer | The VLM replied with a box only | Fixed: `BOX_ONLY` check in `deriveAnswer`. |
| M2 captions describe Lithuania for any image | Training data was Lithuania/Summer only | Captions run on base weights; see P1.3. |
| Zoom lost when changing compare mode | Pane resize triggered a refit | Fixed: `useView` preserves the centre and relative zoom on resize. |

---

## 7. Budget and ownership notes

- **Modal:** ~$30/month credit and tight. Every UI question in `modal` mode costs GPU time
  (cold start ≈ $0.05–0.10, warm questions cents). Develop in mock mode. Ask before training or
  keeping containers warm, and give an estimate.
- **Model credits:** GeoChat-7B base (MBZUAI) + the team's M2 LoRA; ChangeFormer V6 (MIT,
  wgcban/ChangeFormer, DSIFN weights). Keep licences and attribution in the repo
  (`backend/app/models/vendor/changeformer/LICENSE`).
- **Data:** Copernicus Sentinel-1/2 samples. Attribution is required ("Contains modified Copernicus
  Sentinel data 2024"); it's already shown as the sample source.

---

## 8. Acceptance checklist (brief §12), current status

| Criterion | Status |
|---|---|
| Every row, count, timer, confidence and number comes from a backend event | ✅ grep-checked; no fake timers |
| No reasoning parts | ✅ tested in `test_chat_stream.py` |
| Boxes labelled approximate; polygons only from masks | ✅ |
| Evidence never covered by default; scrim dims the outside | ✅ |
| Chip ↔ region two-way highlight, mouse and keyboard | ✅ |
| Confidence distinguishable in greyscale (line style) | ✅ |
| Sample → highlighted answer in 2 clicks + Enter | ✅ |
| Each F8 failure can be forced and recovers | ✅ mostly; network-drop resume is via polling, not stream resume |
| Stop cancels the backend job | ⚠️ between steps; in-flight Modal call continues (P2) |
| Reload restores analysis, evidence and trace | ✅ (ids in localStorage; P2 moves them to SQLite) |
| Trace, tool params and layers within 2 clicks | ✅ |
| Trace JSON downloads with its schema version | ✅ (no JSON-Schema validation test yet; add one) |
| Keyboard-only F0→F5, visible focus everywhere | ✅ |
| Reduced motion: no draw-on, no flicker autoplay, no animated pans | ✅ |
| Text contrast ≥ 4.5:1 | ✅ after the #808A99 / #2563EB fix |
| Evidence visible on bright, dark, water and vegetation | ✅ halo on every stroke; add screenshots to P0.2 |
| Five-second test and blur test | Not run with real users. Run with 3–5 people before the demo. |
