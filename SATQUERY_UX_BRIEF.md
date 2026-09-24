# SatQuery AI: End-User Experience Brief for Claude Code

> **Read this whole file before writing UI code.** It is the design context, user flows, system states and acceptance criteria for redesigning the SatQuery AI web app (SIH 2026, PS 26167, ISRO/SAC).
> Governing doctrine: `elite_ui_ux_design_system_for_coding_agents.md`. Where this brief is silent, follow the doctrine.
> Core rule for this product: **the image is the answer's evidence, and the interface must never hide the evidence it is pointing at.**

---

## 0. Before you touch the UI: read the repo

This brief describes the target experience. It does **not** know your code, so map it onto reality first:

1. Read the router (`router.py`), the tool modules (`tools/`, including `tools/sar.py` and `tools/fusion.py`), the execution-trace schema, and the FastAPI chat/analysis endpoints.
2. Write a short list of **which capabilities actually exist**: which tools, what each one returns (box, mask, text, number), and whether a confidence value is computed and how.
3. Build the UI **only on top of what exists**. If this brief asks for something the backend does not produce (for example a confidence value), either (a) add it to the backend as a separate, clearly-scoped task with a real computation, or (b) render the honest fallback state ("Confidence not available for this tool"). **Never fabricate data in the UI.**

Known facts about the backend (verify them):

| Component | What it really outputs | UI consequence |
|---|---|---|
| GeoChat-7B (QLoRA-adapted) | Text answers and captions; grounding as **axis-aligned boxes** | Draw boxes as boxes. Never draw them as polygons or masks. |
| ChangeFormer (pre-trained) | **Binary change mask** (no text) | Convert the mask to vector contours; text comes from another step |
| SAR / fusion tools | Deterministic calibration and consistency-rule outputs | Show them as rule checks with their values, not as "AI reasoning" |
| Router | Embedding-similarity task classification (SentenceTransformer) plus a fixed tool registry | Show the chosen task and its score, and the runner-up |
| Execution trace | Schema-validated record: task, tools, parameters, outputs | This is the thing ISRO scores. Make it one click away, always. |

---

## 1. The outcome we are designing for

```text
BEFORE  A disaster, agriculture or planning officer has satellite images but no GIS/SAR skills.
        They can't tell what changed, where, or how sure anyone is.
        An ISRO analyst can do it, but only across 3–5 separate tools (GIS, SNAP, scripts).
                ↓
SATQUERY  One question, typed in plain language, about the images they already have.
                ↓
AFTER   They get a direct answer, the exact region on the image that supports it,
        how sure the system is, and an auditable record of what ran.
        They can act on it, or hand it to an analyst who can verify it in under a minute.
```

**Success, measured:**
- Time to first useful action on the empty screen: under 10 s. A sample is one click away.
- The user can point to where the answer came from on the image, without help.
- An analyst can go from the answer to the model, parameters and raw layer in 2 clicks or fewer.
- The UI never shows progress, reasoning or confidence that the backend did not emit.

---

## 2. Who uses it (two people, one interface)

| | **Primary: the Asker** | **Secondary: the Verifier** |
|---|---|---|
| Who | District disaster cell, agriculture or water officer, urban planner, student | ISRO/SAC scientist, RS analyst, **the SIH judges** |
| Knows | The place and the question | Sensors, SAR physics, CRS, GSD, model behaviour |
| Wants | "Just tell me, and show me where" | "Show me what ran, with what parameters, on what pixels" |
| Fears | Being misled; jargon | Hallucination; hidden preprocessing; overclaimed precision |
| Needs first | Answer + highlighted evidence | Trace + parameters + raw layers + metadata |

Design rule: the **Asker's path is the default view**, and the **Verifier's path is always one click deeper**. That is progressive disclosure, and it is never hidden. The judges are Verifiers, so the Verifier path must be excellent, not an afterthought.

---

## 3. What these users use today, and the gaps

| Tool family | Examples | What it does well | Gap SatQuery fills |
|---|---|---|---|
| Desktop GIS / SAR toolboxes | ArcGIS Pro, QGIS, ESA SNAP | Full analytical power | Needs expert skills and many manual steps; no question → answer |
| GIS + VLM add-ons | ArcGIS Pro VLM tools (Image Interrogation, Grounding DINO, TextSAM) | Prompt-driven description and detection inside GIS | Esri states these VLMs work **only with natural-colour imagery**; SAR/multispectral need separate task-specific models. No agentic choice between them. |
| Map + chat assistants | Microsoft Earth Copilot / Planetary Explorer; Google Earth AI with Gemini | Natural-language search over data catalogues; results as map overlays | Built to find and show data at catalogue or planet scale, not to reason over *my* co-registered pair with an auditable trace |
| EO browsers / geoportals | Sentinel Hub EO Browser, ISRO Bhuvan, NRSC Bhoonidhi | Find, view and download scenes | View only; no answers, no change reasoning |
| RS VLM research demos | GeoChat (Gradio), GeoPixel | Chat with one image; boxes or masks drawn on it | No input validation, no change or SAR pairing, no trace, no confidence |

### The highlighting failure we must beat

In current tools, a detected region is drawn as a **filled, semi-transparent box or mask laid over the object**. So:
1. It **covers the exact pixels** the user needs to see to believe the answer.
2. Every detection looks equally certain.
3. Nothing links the **words** in the answer to the **regions** on the image.
4. A coarse box is often drawn as if it were a precise outline.

SatQuery's answer is the **Evidence Lens** (section 7).

---

## 4. Mental model (what the user should believe is happening)

Show the user this model, in these words, in the UI:

```text
Your images  →  checked  →  the assistant picks the right experts  →  experts analyse  →  answer + proof
```

The real system is: upload → validation gate → embedding router → specialist tools → fusion → trace. Keep the words simple. Let the Verifier expand any step to see the real names (`ChangeFormer`, `geochat_vqa`, parameters, timings).

**Vocabulary (use it everywhere, and don't mix synonyms):**
- **Scene**: one uploaded image.
- **Scene set**: what a question is asked about. Exactly one of: `Single image`, `Two dates` (bi-temporal pair), `Optical + SAR` (cross-modal pair).
- **Analysis**: one question plus its run plus its answer.
- **Evidence**: a region on the image that supports a statement (box, change contour, or whole-scene).
- **Run**: the steps the system executed for an analysis.
- **Trace**: the machine-readable record of the run.

---

## 5. Information architecture

**Inventory, ranked:**

| Priority | Information |
|---|---|
| Critical | Current scene set (what the question applies to), the answer, the evidence on the image, run status |
| Important | Confidence, validation result, dates/sensors of each scene, which experts ran |
| Useful | Coordinates and area of evidence, scale bar, layer toggles, history of analyses |
| Optional | Parameters, timings, model versions, CRS/GSD/band metadata |
| Advanced | Full trace JSON, raw intermediate layers, download of masks and boxes |

**Single workspace, three zones (desktop, ≥1280 px):**

```text
┌ SatQuery ▸ Workspace ▸ Kerala flood — two dates ▸ Analysis 3        ● Ready     [Export report] ┐
│ SCENES (240)      │ EVIDENCE VIEWER (flex, hero)                   │ CONVERSATION (400)        │
│                   │                                                │                           │
│ ▾ Two dates  ✓    │   ┌───────────── T1 │ T2 ─────────────┐        │  You                      │
│   T1  02 Jun 2024 │   │            ⌜      ⌝                │        │  What changed between     │
│   T2  21 Aug 2024 │   │            ⌞  ①   ⌟   ◀ swipe ▶   │        │  these dates, and where?  │
│                   │   │                                    │        │                           │
│ + Add scenes      │   └────────────────────────────────────┘        │  ▸ Run · 5 steps · 11.2 s │
│                   │   [Swipe | Side by side | Flicker]  [Layers]   │  Built-up area increased  │
│ HISTORY           │   10.04°N 76.31°E · 1 km ▬▬              [⌕]   │  in the north-east ①.     │
│   Analysis 2      │                                                │  Likely ▮▮▮▯              │
│   Analysis 1      │                                                │  [Evidence] [Trace]       │
│                   │                                                │ ┌ Scene set: Two dates ──┐│
│                   │                                                │ │ Ask about these dates… ││
└───────────────────┴────────────────────────────────────────────────┴─┴────────────────────────┴┘
```

- The **viewer is the hero**: imagery is the product's truth. The answer text points into it.
- **Conversation on the right**, input at the bottom. This is the chat convention; don't break it.
- **Scenes on the left**, collapsible. Hidden by default after the first analysis on screens under 1440 px.
- Tablet: the scenes rail becomes a drawer. Mobile (<768 px): viewer on top (≥50 vh), conversation as a bottom sheet. Pinch-zoom works, and evidence chips are tap targets ≥44 px.

**Why each zone exists** (the "why does this exist" rule):

| Element | Why it exists | What breaks if removed |
|---|---|---|
| Breadcrumb | "Where am I / which scene set?" | User asks about the wrong images |
| Status dot + label | System status must be visible | User can't tell whether it froze |
| Scene-set pill above input | The question's scope is visible *at the moment of asking* | Change question asked on a single image |
| Swipe/Side/Flicker | Analysts compare dates or modalities in these three real ways | No way to verify a change claim |
| Coordinates + scale bar | Georeferenced truth; judges check GSD | Evidence can't be located on the ground |
| Evidence chips ① in text | Link words to pixels | Answer is unverifiable prose |
| Run summary line | Proof of agentic orchestration, collapsed after completion | Judges can't see orchestration; users see noise |

---

## 6. Primary user flows

Each flow: **Entry → Intent → Input → System response → Progress → Result → Interpretation → Next action**, plus failure and recovery.

### F0: First visit (empty state)

```text
Ask questions about satellite images.
Upload a GeoTIFF, or try a sample.

[ Single image ]   [ Two dates ]   [ Optical + SAR ]      ← drop zones, one per scene-set type
Try a sample:  Flood — two dates · City — single image · Reservoir — optical + SAR
```

- The three tiles *are* the mental model: they teach what the product accepts before anything else.
- Samples come from the prescribed public benchmarks, or other openly licensed scenes (state the source on hover). One click loads the set and pre-fills a suggested question. The user presses Enter.
- No marketing hero, no animation. The first screen is the tool.

### F1: Upload and validate

1. The user drops files on a tile, or anywhere on the page.
   - Dropped on a tile: that tile sets the roles (T1/T2 or Optical/SAR slots).
   - Dropped anywhere: if there are two files, **propose** roles from metadata (dates differ → Two dates; sensor or polarisation differs → Optical + SAR) and ask the user to confirm. If the metadata can't decide, show explicit role slots. Never guess silently.
2. Show **real** upload progress per file (bytes sent / total).
3. Validation checks stream in one by one, each resolving to ✓ or ✕ with the value:
   `✓ 2 scenes · ✓ GeoTIFF · ✓ Optical (4 bands) + SAR (VV) · ✓ Same CRS EPSG:32643 · ✓ Co-registered (offset 0.3 px) · ✓ GSD 10 m / 10 m`
   Show only the checks the backend actually performs, with the values it actually reports.
4. On pass, the scene set appears in the viewer with a quick-look rendering (percentile-stretched optical; SAR in dB with a fixed, labelled stretch). The input focuses, with scene-set-aware suggestions.

**Failure (F1-x):** the ✕ check stays visible with a plain-language reason and a next step:
> ✕ These two images don't overlap the same area (CRS EPSG:32643 vs EPSG:4326).
> Upload a co-registered pair, or [Reproject T2 to match T1].

Offer the fix button **only if the backend implements it**. Uploaded files are kept; nothing is lost. PNG/JPEG outside the benchmark flow: "PNG is accepted only for benchmark images. Upload the GeoTIFF to keep georeferencing." (This is the PS's own rule.)

### F2: Ask (all scene-set types)

- Above the textbox, a pill shows scope: `Scene set: Two dates · 02 Jun 2024 → 21 Aug 2024`.
- The placeholder is specific to the set: *"Ask about these two dates — e.g. What changed, and where?"*
- Suggestions (AI Elements `Suggestion`) show **only questions this scene set supports**. For example, change questions appear only for Two dates. This prevents routing to impossible tasks.
- Enter sends; Shift+Enter makes a new line. While a run is active, the send button becomes **Stop**, which is a real cancel (section 8.5).

### F3: Watch the run (the "see the agent work" experience)

This is where the product earns trust. **Every row is a real backend event. Nothing is animated for its own sake.**

```text
Running · 6.4 s                                                        [Stop]
 ✓ Checked your images        6 checks passed                          0.3 s
 ✓ Understood the question    Change question  ·  score 0.82           0.1 s
                              runner-up: Describe scene · 0.41
 ● Finding what changed       ChangeFormer · 512×512 tiles · 4/9       4.1 s
 ○ Describing the change      GeoChat-7B (adapted)
 ○ Combining evidence
```

- The label is plain English first; the real tool name is second, in mono, muted.
- An active step uses AI Elements `Shimmer` on its label, plus a **real** elapsed timer. Show a count (`4/9 tiles`) only if the backend emits it. **No percentage bars unless they are computed from real work units.**
- **The picture assembles as the agent works**: when the change mask is ready, its contours draw onto the viewer *during* the run, tagged with the step that produced them. Grounding boxes appear when GeoChat returns them. This is the "crazy" moment, and it is 100% honest.
- **Cold start is a first-class state**: if the GPU worker is starting, show `Starting the analysis engine — first run can take longer` with a real elapsed timer. Never show a fake progress bar.
- On completion, the run collapses to a single line: `▸ Run · 5 steps · 3 experts · 11.2 s`. It expands on click. It stays expanded if any step failed or warned.

### F4: Read the answer

The answer layout follows AI-dashboard order: **Answer → Confidence → Evidence → Next actions → Details**.

```text
Built-up area increased in the north-east of the scene ①, mostly along the
river bank ②. No major change detected in the southern farmland.

Likely  ▮▮▮▯        Evidence: 2 regions · 0.84 km² changed
[Show all evidence]  [View trace]  [Download report]
Ask next:  "How large is the change?" · "Show only region ①"
```

- **Evidence chips** (①, ②) are inline, focusable buttons. Hovering or focusing one puts the Evidence Lens on that region in the viewer, pans or zooms if it's off-screen, and highlights the chip. Hovering a region on the image highlights its chip and sentence. **Linking goes both ways.**
- Confidence is shown **in words first** (`High confidence`, `Likely`, `Needs review`, `Unable to determine`), with a 4-step meter and the number on hover. The mapping from number to word is defined once in code and shown in the trace drawer. If the backend gives no confidence for a tool, show `Confidence not available`.
- Areas and lengths are **computed deterministically** from mask pixel counts × GSD² (or the box extent), and labelled that way. The language model is never the source of a number.
- Low confidence or no evidence: say so plainly (`Unable to determine from these images — the SAR scene is heavily speckled in this area`) and suggest a better next step.

### F5: Verify (the Verifier's / judge's path)

- **View trace** opens a right-hand drawer (not a modal; the viewer stays visible). It has three tabs:
  1. **Steps**: each tool call (AI Elements `Tool`) with its real input parameters, output summary, state and duration.
  2. **Layers**: each intermediate raster or vector layer (SAR in dB, change mask, boxes) that can be toggled in the viewer, with provenance ("produced by step 3").
  3. **JSON**: the raw schema-validated trace, with a copy button and a download button. The schema version is shown.
- **Loupe** (press `L` or use the magnifier button) shows native-resolution pixels around the cursor, so the Verifier can check a box edge against the real pixels.
- Scene metadata (sensor, date, CRS, GSD, bands or polarisation) is shown on hover or focus of the scene in the left rail.

### F6: Follow-up questions

The same scene set stays active: the pill stays, and previous evidence dims but stays toggleable. "Show only region ①" style questions reuse existing outputs where the backend supports that; otherwise it's a new run. A different scene set means a new analysis thread, and the UI says so ("New scene set — starting a new analysis").

### F7: Export

`Download report` produces a PDF (or HTML) containing: question, answer, confidence, evidence image with the lens overlays, coordinates and areas, scenes' metadata, and a trace summary with the full JSON attached. The button shows `Preparing report…` → `Downloaded`. If generation fails, the analysis is untouched and a retry is offered.

### F8: Failure and recovery matrix

| Failure | What the user sees | Recovery |
|---|---|---|
| Validation fails | The failing check with value and plain reason | Fix hint; files kept |
| Router unsure (top score low, or top two close) | "I'm not sure what kind of question this is" plus 2–3 intent choices | User picks; run continues |
| Question unsupported for this scene set | "Change questions need two dates. You have one image." | [Add a second date] |
| GPU cold start | Named state + real timer | Wait; can navigate away (run continues) |
| Tool error mid-run | Step shows ✕ with message; completed steps and their layers stay | [Retry step] or [Retry run] |
| Network drop during stream | "Connection lost — reconnecting…" | Resume the stream if implemented; otherwise [Retry], with the question preserved |
| Timeout | "Taking longer than expected" after a set threshold, still running | Keep waiting or [Stop] |
| User pressed Stop | Run marked `Stopped by you` with partial results clearly labelled partial | [Run again] |
| Report export fails | Toast with reason | [Retry] |

---

## 7. The Evidence Lens (highlighting specification)

**Principle: attention without occlusion.** The highlighted pixels stay at full fidelity. Everything else steps back.

1. **Spotlight, not fill.** When evidence is active, a scrim (`rgba(5,8,12,0.55)`) dims everything outside the evidence region. The region itself gets no overlay at all.
2. **Boxes → corner brackets.** A GeoChat box is drawn as four L-shaped corners (2 px stroke, 1 px dark halo so it reads on any terrain), with no edges between them and no fill. The pixels along the box edge stay visible.
3. **Masks → contours.** The ChangeFormer mask is vectorised on the backend (marching squares or rasterio `shapes`), simplified to about half a pixel, and sent as GeoJSON in pixel and geo coordinates. It is drawn as a 1.5 px outline with a halo; fill is off by default, and there is a toggle for a 15% fill.
4. **Confidence is a line style, not a colour:** solid = high, dashed = likely, dotted + `Needs review` tag = low. This is colour-blind-safe, and it leaves colour free for semantics.
5. **Honest geometry.** Box tooltips say `Approximate box (model output)`. Contours say `Change mask outline`. Never label a box as a boundary.
6. **Motion explains arrival.** A new evidence item draws on (brackets extend outwards; contours trace) in 240 ms, easing out, and only on arrival. With `prefers-reduced-motion`, it appears instantly.
7. **Numbered markers** (①②) sit at the top-left corner outside the region, never on top of it, and match the chips in the text.
8. **Focus behaviour.** Selecting evidence fits the region to about 60% of the viewport (animated pan/zoom, 300 ms), unless the user has zoomed in manually within the last 5 s (don't fight the user).
9. **All evidence** view: every region shows its brackets or contour at 60% opacity, with no scrim.

**Comparison modes** (for Two dates and Optical + SAR):
- **Swipe** (default): a vertical divider with a draggable handle, the date or sensor label pinned on each side, and evidence drawn on both halves.
- **Side by side**: synchronised pan and zoom, and a crosshair mirrored in the other panel.
- **Flicker**: alternates every 600 ms (pausable). This is a standard analyst technique for small changes. Disabled under reduced motion; the user presses Space to toggle manually.
- Optical + SAR adds a **SAR opacity** slider (blend). The SAR stretch in dB is labelled, with a legend.

---

## 8. Streaming the agent's work with the Vercel AI SDK UI

Current docs at the time of writing: **AI SDK v7**. The UI uses `useChat` from `@ai-sdk/react` and **AI Elements** components (shadcn/ui-based, installed as source: `npx ai-elements@latest add <component>`). **Check every API name below against the installed version before relying on it.**

### 8.1 Architecture

```text
Next.js (Vercel)                                   FastAPI (Python)
useChat({ transport: DefaultChatTransport({ api }) })  ──POST──▶  /api/chat
  ◀── SSE, UI Message Stream protocol ──────────────────────────  emits parts as the run progresses
```

- Uploads do **not** travel inside chat messages. Upload GeoTIFFs to a separate FastAPI endpoint that returns a `sceneSetId`. Send `sceneSetId` in the chat request body using `DefaultChatTransport`'s `body: () => ({ sceneSetId })`, or `prepareSendMessagesRequest` for full control. The default body is `{ id, messages, trigger, messageId }`; FastAPI must accept it.
- FastAPI must emit the **UI Message Stream protocol**: SSE lines `data: {json}\n\n`, header `x-vercel-ai-ui-message-stream: v1`, ending with `data: [DONE]`. Also set `Content-Type: text/event-stream` and `Cache-Control: no-cache`. If there is a proxy, disable buffering.
- Keep Pydantic as the source of truth. Generate TypeScript types from the Pydantic JSON Schema (for example with `json-schema-to-typescript`), so the tool and data-part types can't drift.

### 8.2 Mapping real backend events to stream parts

| Backend event | Stream part(s) | UI |
|---|---|---|
| Run starts | `start` (with message metadata: `runId`, `sceneSetId`) | Status → Running |
| Engine warming | `data-status` **transient** `{phase:"cold-start", sinceMs}` | Cold-start line (`onData`) |
| Each validation check | `data-validation` with stable `id`, first `{status:"pending"}` then the **same id** `{status:"pass"\|"fail", value, reason}` | Check rows resolve in place (reconciliation by id) |
| Router decision | `data-plan` `{task, score, runnerUp:{task,score}, steps:[…planned tools]}` | "Understood the question" row + the pending step list |
| Tool call begins | `tool-input-available` `{toolCallId, toolName, input}` (the permitted params) | Step becomes active, parameters in `ToolInput` |
| Tool progress (if real) | `data-progress` with `id = toolCallId`, `{done, total, unit}` | `4/9 tiles` |
| Intermediate layer ready | `data-layer` `{id, kind:"mask-contours"\|"boxes"\|"sar-db", url\|geojson, producedBy: toolCallId}` | Viewer adds the layer **immediately** |
| Tool finishes | `tool-output-available` `{toolCallId, output}` or tool error | Step ✓ / ✕ with duration |
| Evidence registered | `data-evidence` `{id:"①", geometry, kind, confidence, areaM2?, label}` | Lens overlay + chip target |
| Answer text | `text-start` / `text-delta` / `text-end`, with evidence markers such as `[[ev:1]]` in the text | Streamed answer; markers render as chips |
| Confidence | `data-confidence` `{value, label, method}` | Meter + words |
| Trace | `data-trace` `{schemaVersion, trace}` | Trace drawer, download |
| Failure | `error` `{errorText}` (plus the failing tool part) | Failure matrix row |
| Stop | `abort` | "Stopped by you" |
| Done | `finish`, then `[DONE]` | Run collapses to its summary line |

- **Do not emit `reasoning-*` parts.** The pipeline produces no model reasoning text, and the PS says internal reasoning is not evaluated. Writing "thoughts" that nothing produced would be fake AI state. If a future LLM controller produces real reasoning, show it collapsed, labelled `Model reasoning (not verified)`.
- The Python tools are not declared in TypeScript, so their parts may arrive as `dynamic-tool`. Either narrow them with the generated types, or declare the tool types on the `UIMessage` generic. Check how v7 types server-declared tools from a non-JS backend.

### 8.3 Typed message

```ts
// types/ui-message.ts — generated tool/data types come from Pydantic JSON Schema
import type { UIMessage } from 'ai';

export type SatQueryData = {
  status:     { phase: 'cold-start' | 'queued'; sinceMs: number };           // transient
  validation: { check: string; status: 'pending' | 'pass' | 'fail'; value?: string; reason?: string };
  plan:       { task: string; score: number; runnerUp?: { task: string; score: number }; steps: string[] };
  progress:   { done: number; total: number; unit: string };
  layer:      { kind: 'mask-contours' | 'boxes' | 'sar-db' | 'optical-rgb'; url?: string; geojson?: unknown; producedBy: string };
  evidence:   { label: string; kind: 'box' | 'contour' | 'scene'; geometry: unknown; confidence?: number; areaM2?: number };
  confidence: { value: number; label: 'High confidence' | 'Likely' | 'Needs review' | 'Unable to determine'; method: string };
  trace:      { schemaVersion: string; trace: unknown };
};

export type SatQueryMessage = UIMessage<{ runId: string; sceneSetId: string }, SatQueryData>;
```

### 8.4 AI Elements to use (restyle them all to the tokens in section 9)

| Need | Component |
|---|---|
| Thread and scroll | `Conversation`, `Message` |
| Input with scene-set pill | `PromptInput` (add the pill as a header slot) |
| Run timeline | `ChainOfThought` + `ChainOfThoughtStep` (`status: complete \| active \| pending`, `label`, `description`) |
| Active step label | `Shimmer` |
| Tool details in the trace drawer | `Tool`, `ToolHeader`, `ToolContent`, `ToolInput`, `ToolOutput` (its state badges map to the real tool-part states) |
| Suggested questions | `Suggestion` |
| Dataset/model provenance | `Sources` / `InlineCitation` (optional) |

Don't add `Confirmation`/approval flows unless there is a real consequential action (for example a reprojection that rewrites data, or a very long GPU job with a real time estimate). Analysis is read-only by default.

### 8.5 Stop, resume, persistence

- `stop()` must cancel the backend run: the client disconnect or abort must reach FastAPI and the GPU call. Partial results stay, and are labelled partial.
- Persist analyses (SQLite) with their parts and trace, so reload restores the full view, including layers.
- If resumable streams are implemented, show `Reconnecting…`. Otherwise show the retry path from F8.

---

## 9. Visual system

**Direction: scientific and instrument-grade. Calm chrome, imagery in charge.** Dark by default, because a neutral dark surround makes imagery contrast read correctly and keeps the UI from competing with the pixels. The light theme is used for exported reports.

```css
:root {
  /* surfaces (neutral, slightly cool; never tinted toward any modality colour) */
  --bg-base:#0A0E14; --bg-panel:#10151D; --bg-raised:#161C26; --border:#232B37;
  --text:#E6EAF0; --text-muted:#9AA4B2; --text-faint:#6B7584;

  /* semantics: each colour means exactly one thing */
  --optical:#22D3EE;   /* optical scene / optical layer tags only */
  --sar:#C084FC;       /* SAR scene / SAR layer tags only */
  --evidence:#F8FAFC;  /* evidence brackets & contours (with --halo) */
  --evidence-active:#FDE047; /* the currently focused evidence */
  --change:#FB923C;    /* change-mask contours */
  --halo:rgba(0,0,0,.75);
  --accent:#3B82F6;    /* primary action, focus ring */
  --success:#22C55E; --warning:#F59E0B; --critical:#EF4444;

  --font-ui:"Inter",system-ui,sans-serif;
  --font-data:"JetBrains Mono",ui-monospace,monospace;   /* numbers, coords, tool names, params */

  --space:4px 8px 12px 16px 24px 32px 48px;   /* use the scale, no magic numbers */
  --radius-sm:6px; --radius-md:10px; --radius-lg:14px;
  --dur-fast:120ms; --dur-base:240ms; --dur-slow:300ms; --ease-out:cubic-bezier(.2,.8,.2,1);
}
```

- **Type scale:** 13 / 14 (body) / 16 / 20 / 24. Numbers use tabular figures (`font-variant-numeric: tabular-nums`) so timers and coordinates don't jitter.
- **Colour discipline:** cyan and violet appear *only* where a scene or layer is optical or SAR. Yellow appears *only* on the focused evidence. Orange appears *only* on change. If you want to use a colour for decoration, don't.
- **No** gradients, glassmorphism, glow or background animation. The one "wow" is the imagery assembling itself from real steps.
- **Contrast:** UI text ≥ 4.5:1 on panels. Evidence strokes always carry the dark halo, so they pass on bright desert, snow, cloud and water.
- **Icons:** Lucide at 16/20 px, always with a text label or tooltip, and never icon-only for primary actions.

---

## 10. Interaction details that make it feel inevitable

- **Keyboard:** `/` focuses the question box · `Esc` stops a run (with confirmation if it has run for more than 10 s) · `1–9` focuses evidence ① to ⑨ · `Tab` cycles evidence chips · `S` / `D` / `F` switch Swipe / Side-by-side / Flicker · `L` toggles the loupe · `T` opens the trace. Shortcuts are shown in tooltips (recognition, not recall).
- **Cursor readout:** lat/lon (from the GeoTIFF transform) and pixel value(s) under the cursor, in mono, bottom-left of the viewer. For SAR, show σ⁰ in dB if the backend provides calibrated values.
- **Scale bar** always visible, computed from GSD and zoom.
- **Hover ↔ focus parity:** everything available on hover is also available on keyboard focus.
- **Latency budget:** first visible feedback within 100 ms of send (the user message appears plus `Checking your images…` from the first real event). INP under 200 ms. Viewer pan/zoom at 60 fps on a 4k quick-look (use a WebGL/canvas image viewer in image-pixel space, such as OpenSeadragon or a deck.gl `OrthographicView`; draw overlays on an SVG layer in the same coordinate space).

---

## 11. Build order for Claude Code

1. **Contract first:** Pydantic models for every data part and tool I/O → JSON Schema → TypeScript types. Then write a recorded SSE fixture of a full "Two dates" run (all parts in section 8.2, in real order).
2. **FastAPI emitter:** a small helper that writes protocol-correct parts (with header and `[DONE]`), wired to the real router, tools and trace events. Test it: the fixture replayed through `useChat` renders without errors.
3. **Workspace shell:** three zones, breadcrumb, status, empty state (F0) with samples.
4. **Upload + validation** (F1), with streamed checks and every failure state.
5. **Viewer:** quick-looks, pan/zoom, scale bar, cursor readout, then Swipe / Side-by-side / Flicker, then the SAR blend.
6. **Evidence Lens** (section 7), with two-way chip ↔ region linking and keyboard support.
7. **Run timeline** (F3) and the collapsed summary; cold start; Stop.
8. **Answer card** (F4) with confidence words and deterministic areas.
9. **Trace drawer** (F5): Steps / Layers / JSON, and the loupe.
10. **Failure matrix** (F8): force every row and screenshot each.
11. **Report export** (F7).
12. **Responsive**, **reduced motion**, and an **accessibility pass**.

---

## 12. Acceptance criteria (don't call it done until every box is true)

**Honesty**
- [ ] Every timeline row, count, timer, confidence and number comes from a backend event. `grep` for hardcoded progress, `setTimeout`-driven fake steps, and invented confidence finds nothing.
- [ ] No `reasoning` parts are emitted or rendered.
- [ ] Boxes are labelled as approximate boxes; nothing is drawn as a polygon unless it came from a mask.

**Evidence Lens**
- [ ] No evidence region is ever covered by a fill by default. The spotlight dims the outside only.
- [ ] Hovering or focusing chip ① lights region ①, and hovering region ① lights chip ①, with mouse and with keyboard.
- [ ] Confidence is distinguishable in greyscale (line style).

**Flows**
- [ ] A new user loads a sample and gets a highlighted answer in 2 clicks + Enter.
- [ ] Each F8 failure can be forced and shows its specified message and recovery. User input and uploads are never lost.
- [ ] Stop cancels the backend job (verify in backend logs).
- [ ] Reload restores the analysis, evidence and trace.

**Verifier path**
- [ ] From the answer: trace, the parameters of any tool, and any intermediate layer are each reachable in 2 clicks or fewer.
- [ ] The trace JSON downloads and validates against the backend schema.

**Quality**
- [ ] Keyboard-only run of F0→F5 is possible, with a visible focus ring everywhere.
- [ ] `prefers-reduced-motion`: no draw-on, no flicker autoplay, no animated pans.
- [ ] Text contrast is ≥ 4.5:1, and evidence strokes are visible on bright, dark, water and vegetation samples (screenshot each).
- [ ] Five-second test on the empty state: a new person can say what it does and what to click.
- [ ] Blur test on the result screen: the image and evidence dominate, then the answer, then everything else.

---

## 13. Sources used for this brief

- Esri, *Talk to Your Imagery: Vision-Language Models for Geospatial Analysis* (ArcGIS Pro VLM tools; natural-colour-only limitation): https://www.esri.com/arcgis-blog/products/arcgis-pro/geoai/vision-language-models-geospatial-analysis
- Microsoft, *Earth Copilot / Planetary Explorer* README (map + chat, multi-agent, pin-drop): https://github.com/microsoft/Earth-Copilot/blob/main/README.md
- Google, *New updates and more access to Google Earth AI*: https://blog.google/innovation-and-ai/technology/research/new-updates-and-more-access-to-google-earth-ai/
- MBZUAI, *GeoChat* (box grounding): https://mbzuai-oryx.github.io/GeoChat/ · *GeoPixel* (pixel-mask grounding): https://mbzuai-oryx.github.io/GeoPixel/
- Vercel AI SDK: UI Message Stream protocol https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol · Streaming custom data https://ai-sdk.dev/docs/ai-sdk-ui/streaming-data · Tool usage https://ai-sdk.dev/docs/ai-sdk-ui/chatbot-tool-usage · useChat https://ai-sdk.dev/docs/ai-sdk-ui/chatbot
- AI Elements: https://elements.ai-sdk.dev/ (Chain of Thought, Tool, and others)
- Design doctrine: `elite_ui_ux_design_system_for_coding_agents.md` (project file)
