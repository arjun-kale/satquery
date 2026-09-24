/*
 * Pure derivations from a backend trace to what the UI shows. Nothing here invents data:
 * every row, number, box and outline is read from a step's recorded outputs.
 */

import { confidenceView, type ConfidenceView, type LineStyle } from "./confidence";
import { formatArea, formatPercent } from "./geo";
import type {
  ExecutionStep,
  GroundingBoxOut,
  JobStatus,
  ModelMode,
  OrchestratorTrace,
  RegionOut,
} from "./types";
import { modelName, TOOL, toolLabel } from "./vocabulary";

const MOCK_PREFIX = /^\s*\[MOCK\]\s*/;
const BOX_ONLY = /^\s*(\{\s*<-?\d+>\s*<-?\d+>\s*<-?\d+>\s*<-?\d+>\s*(\|\s*<-?\d+>)?\s*\}\s*)+$/;

function stepOf(trace: OrchestratorTrace | null, tool: string): { step: ExecutionStep; index: number } | null {
  if (!trace) return null;
  const index = trace.steps.findIndex((s) => s.tool_name === tool && s.status === "SUCCESS");
  return index === -1 ? null : { step: trace.steps[index], index };
}

const str = (v: unknown): string | null => (typeof v === "string" && v.trim() ? v : null);
const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);

/* ------------------------------------------------------------------ evidence */

export type EvidenceKind = "box" | "contour";

export interface Evidence {
  /** ① … ⑨ — the same number appears on the chip and next to the region. */
  n: number;
  kind: EvidenceKind;
  tone: "evidence" | "change";
  title: string;
  /** Honest geometry: what this shape actually is. */
  honesty: string;
  bbox: [number, number, number, number];
  rings?: [number, number][][];
  areaM2: number | null;
  confidence: ConfidenceView;
  line: LineStyle;
  producedBy: { index: number; tool: string };
  isMock: boolean;
}

export const CIRCLED = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨"];

export function deriveEvidence(trace: OrchestratorTrace | null): Evidence[] {
  if (!trace) return [];
  const out: Omit<Evidence, "n">[] = [];
  const mode = trace.model_mode;

  const change = stepOf(trace, "changeformer");
  if (change) {
    const isMock = change.step.outputs.model_mode === "mock" || mode === "mock";
    const conf = confidenceView(change.step.outputs.confidence, change.step.outputs.confidence_source, isMock);
    const trainedOn = str(change.step.outputs.training_note);
    for (const r of (change.step.outputs.change_regions as RegionOut[] | undefined) ?? []) {
      out.push({
        kind: "contour",
        tone: "change",
        title: "Changed region (model)",
        honesty: isMock
          ? "Change mask outline (mock model — placeholder mask)"
          : `ChangeFormer mask outline${trainedOn ? ` — trained on ${trainedOn.split(",")[0].replace(/\(.*$/, "").trim()}, 2 m imagery` : ""}`,
        bbox: r.bbox,
        rings: r.rings,
        areaM2: r.area_m2,
        confidence: conf,
        line: conf.available ? conf.band.line : "dashdot",
        producedBy: { index: change.index, tool: "changeformer" },
        isMock,
      });
    }
  }

  const ic = stepOf(trace, "index_change");
  if (ic) {
    const name = str(ic.step.outputs.index_type) ?? "water index";
    for (const [key, title] of [["gained_regions", "Water gained"], ["lost_regions", "Water lost"]] as const) {
      for (const r of (ic.step.outputs[key] as RegionOut[] | undefined) ?? []) {
        out.push(ruleRegion(r, title, `Rule outline: ${name} T1 → T2 (water = ${name} > 0)`, "change", ic.index, "index_change"));
      }
    }
  }

  const sar = stepOf(trace, "sar_water");
  if (sar) {
    const rule = str(sar.step.outputs.rule) ?? "SAR threshold rule";
    for (const r of (sar.step.outputs.sar_water_regions as RegionOut[] | undefined) ?? []) {
      out.push(ruleRegion(r, "Water (SAR)", `Rule outline: ${rule}`, "evidence", sar.index, "sar_water"));
    }
  }

  const index = stepOf(trace, "spectral_index");
  if (index) {
    const rule = str(index.step.outputs.rule) ?? "threshold rule";
    const target = str(index.step.outputs.target) ?? "target";
    for (const r of (index.step.outputs.index_regions as RegionOut[] | undefined) ?? []) {
      out.push({
        kind: "contour",
        tone: "evidence",
        title: target[0].toUpperCase() + target.slice(1),
        honesty: `Rule outline: ${rule}`,
        bbox: r.bbox,
        rings: r.rings,
        areaM2: r.area_m2,
        confidence: { available: false, reason: "Rule output — a measurement, not a model guess" },
        line: "solid",
        producedBy: { index: index.index, tool: "spectral_index" },
        isMock: false,
      });
    }
  }

  const ground = stepOf(trace, "geochat_grounding");
  if (ground) {
    const isMock = mode === "mock";
    for (const b of (ground.step.outputs.grounding_boxes as GroundingBoxOut[] | undefined) ?? []) {
      const conf = confidenceView(b.confidence, isMock ? "unavailable" : "model-provided", isMock);
      out.push({
        kind: "box",
        tone: "evidence",
        title: b.label.replace(MOCK_PREFIX, ""),
        honesty: isMock ? "Approximate box (mock model — placeholder)" : "Approximate box (model output)",
        bbox: [b.x_min, b.y_min, b.x_max, b.y_max],
        areaM2: null,
        confidence: conf,
        line: conf.available ? conf.band.line : "dashdot",
        producedBy: { index: ground.index, tool: "geochat_grounding" },
        isMock,
      });
    }
  }

  // Largest first across all sources, so the nine numbered slots go to the regions that matter most.
  return out
    .map((e, i) => ({ e, i }))
    .sort((x, y) => (y.e.areaM2 ?? 0) - (x.e.areaM2 ?? 0) || x.i - y.i)
    .slice(0, CIRCLED.length)
    .map(({ e }, i) => ({ ...e, n: i + 1 }));
}

function ruleRegion(r: RegionOut, title: string, honesty: string, tone: "evidence" | "change", index: number, tool: string): Omit<Evidence, "n"> {
  return {
    kind: "contour",
    tone,
    title,
    honesty,
    bbox: r.bbox,
    rings: r.rings,
    areaM2: r.area_m2,
    confidence: { available: false, reason: "Rule output — a measurement, not a model guess" },
    line: "solid",
    producedBy: { index, tool },
    isMock: false,
  };
}

/* ------------------------------------------------------------------ answer */

export interface Measurement {
  label: string;
  value: string;
  method: string;
}

export interface AnswerView {
  text: string | null;
  tool: string | null;
  isMock: boolean;
  confidence: ConfidenceView;
  measured: Measurement[];
  note: string | null;
}

const ANSWER_TOOLS: { tool: string; key: string }[] = [
  { tool: "change_vqa", key: "change_description" },
  { tool: "geochat_vqa", key: "vqa_answer" },
  { tool: "geochat_caption", key: "caption" },
];

export function deriveAnswer(trace: OrchestratorTrace | null): AnswerView {
  const measured = deriveMeasurements(trace);
  for (const { tool, key } of ANSWER_TOOLS) {
    const hit = stepOf(trace, tool);
    const raw = hit ? str(hit.step.outputs[key]) : null;
    if (hit && raw) {
      const isMock = hit.step.outputs.model_mode === "mock" || MOCK_PREFIX.test(raw);
      // The model sometimes answers with only its location-token syntax, e.g. {<0><0><100><100>|<90>}.
      // That is not an answer; never show raw tokens as prose.
      if (BOX_ONLY.test(raw)) {
        return {
          text: null,
          tool,
          isMock,
          confidence: { available: false, reason: "No text answer to rate" },
          measured,
          note: `The model replied with a location box (${raw.trim()}) instead of a sentence. Try rephrasing the question.`,
        };
      }
      return {
        text: raw.replace(MOCK_PREFIX, ""),
        tool,
        isMock,
        confidence: confidenceView(hit.step.outputs.confidence, hit.step.outputs.confidence_source, isMock),
        measured,
        note: str(hit.step.outputs.vlm_input),
      };
    }
  }

  const ground = stepOf(trace, "geochat_grounding");
  if (ground) {
    const boxes = (ground.step.outputs.grounding_boxes as GroundingBoxOut[] | undefined) ?? [];
    const isMock = trace?.model_mode === "mock";
    return {
      text: boxes.length
        ? `Found ${boxes.length} approximate location${boxes.length > 1 ? "s" : ""} for “${trace?.query}”.`
        : `No location was returned for “${trace?.query}”.`,
      tool: "geochat_grounding",
      isMock,
      confidence: confidenceView(boxes[0]?.confidence, isMock ? "unavailable" : "model-provided", isMock),
      measured,
      note: null,
    };
  }

  const fusion = stepOf(trace, "cross_modal_fusion");
  if (fusion) {
    return {
      text: str(fusion.step.outputs.fusion_description),
      tool: "cross_modal_fusion",
      isMock: false,
      confidence: { available: false, reason: "Confidence not available for this tool" },
      measured,
      note: null,
    };
  }

  return {
    text: null,
    tool: null,
    isMock: false,
    confidence: { available: false, reason: "Confidence not available" },
    measured,
    note: null,
  };
}

function deriveMeasurements(trace: OrchestratorTrace | null): Measurement[] {
  const out: Measurement[] = [];

  const ic = stepOf(trace, "index_change");
  if (ic) {
    const o = ic.step.outputs;
    const name = str(o.index_type) ?? "index";
    const method = `Pixels with ${name} > 0 × pixel ground area`;
    const pair = (a: unknown, f: unknown) => [formatArea(num(a)), num(f) != null ? `${formatPercent(num(f)!)} of scene` : null].filter(Boolean).join(" · ");
    out.push({ label: "Water at T1", value: pair(o.water_area_t1_m2, o.water_fraction_t1), method });
    out.push({ label: "Water at T2", value: pair(o.water_area_t2_m2, o.water_fraction_t2), method });
    const gained = formatArea(num(o.gained_area_m2));
    const lost = formatArea(num(o.lost_area_m2));
    if (gained) out.push({ label: "Water gained", value: gained, method: "Dry at T1 and water at T2" });
    if (lost) out.push({ label: "Water lost", value: lost, method: "Water at T1 and dry at T2" });
  }

  const sar = stepOf(trace, "sar_water");
  if (sar) {
    const o = sar.step.outputs;
    const frac = num(o.target_fraction);
    if (frac != null)
      out.push({
        label: `Water (VV < ${num(o.threshold_db) ?? -18} dB)`,
        value: [formatPercent(frac), formatArea(num(o.target_area_m2))].filter(Boolean).join(" · "),
        method: "Despeckled SAR pixels below the dB threshold × pixel ground area",
      });
  }

  const index = stepOf(trace, "spectral_index");
  if (index) {
    const o = index.step.outputs;
    const frac = num(o.target_fraction);
    const area = formatArea(num(o.target_area_m2));
    if (frac != null) {
      out.push({
        label: `${str(o.target) ?? "Target"} (${str(o.rule)?.split("→")[0].trim() ?? "rule"})`,
        value: [formatPercent(frac), area].filter(Boolean).join(" · "),
        method: "Pixels above the index threshold × pixel ground area",
      });
    }
    const mean = num(o.index_mean);
    if (mean != null) {
      out.push({
        label: `Mean ${str(o.index_type) ?? "index"}`,
        value: mean.toFixed(3),
        method: `Averaged over valid pixels · ${Object.entries((o.bands_used as Record<string, string>) ?? {})
          .map(([k, v]) => `${k} = ${v}`)
          .join(", ")}`,
      });
    }
  }

  const changeArea = stepOf(trace, "change_area");
  const change = stepOf(trace, "changeformer");
  if (changeArea) {
    const area = formatArea(num(changeArea.step.outputs.change_area_m2));
    const ratio = change ? num(change.step.outputs.change_ratio) : null;
    if (area || ratio != null) {
      out.push({
        label: "Changed area",
        value: [area, ratio != null ? `${formatPercent(ratio)} of scene` : null].filter(Boolean).join(" · "),
        method: "Changed mask pixels × ground area of one mask pixel",
      });
    }
  }

  const geo = stepOf(trace, "geodesy");
  if (geo) {
    const area = formatArea(num(geo.step.outputs.area_m2));
    if (area) out.push({ label: "Scene footprint", value: area, method: "Width × height × pixel area from the GeoTIFF transform" });
  }
  return out;
}

/* ------------------------------------------------------------------ layers */

export interface JobLayer {
  id: string;
  label: string;
  url: string;
  producedBy: { index: number; tool: string };
  tone: "change" | "evidence" | "sar";
  legend?: string;
}

export function deriveJobLayers(trace: OrchestratorTrace | null): JobLayer[] {
  const out: JobLayer[] = [];
  const index = stepOf(trace, "spectral_index");
  const mask = index && str(index.step.outputs.mask_url);
  if (index && mask)
    out.push({
      id: "index",
      label: `${str(index.step.outputs.index_type) ?? "Index"} raster`,
      url: mask,
      producedBy: { index: index.index, tool: "spectral_index" },
      tone: "evidence",
      legend: "Red → green: low → high (2–98 % stretch)",
    });
  const ic = stepOf(trace, "index_change");
  const icu = ic && str(ic.step.outputs.change_raster_url);
  if (ic && icu)
    out.push({
      id: "index-change",
      label: "Water change raster",
      url: icu,
      producedBy: { index: ic.index, tool: "index_change" },
      tone: "change",
      legend: "Solid orange: water gained · faint orange: water lost",
    });
  const sarw = stepOf(trace, "sar_water");
  const sw = sarw && str(sarw.step.outputs.mask_url);
  if (sarw && sw)
    out.push({
      id: "sar-water",
      label: "SAR water mask",
      url: sw,
      producedBy: { index: sarw.index, tool: "sar_water" },
      tone: "sar",
      legend: "Blue: despeckled VV below the dB threshold",
    });
  const change = stepOf(trace, "changeformer");
  const cm = change && str(change.step.outputs.change_mask_url);
  if (change && cm)
    out.push({
      id: "change-mask",
      label: "Change mask (raw)",
      url: cm,
      producedBy: { index: change.index, tool: "changeformer" },
      tone: "change",
    });
  const fusion = stepOf(trace, "cross_modal_fusion");
  const fu = fusion && str(fusion.step.outputs.fused_preview_url);
  if (fusion && fu)
    out.push({
      id: "fused",
      label: "Fused optical + SAR",
      url: fu,
      producedBy: { index: fusion.index, tool: "cross_modal_fusion" },
      tone: "sar",
      legend: "SAR intensity as a red overlay on optical",
    });
  return out;
}

/* ------------------------------------------------------------------ run timeline */

export type RowStatus = "pending" | "active" | "done" | "failed" | "skipped";

export interface TimelineRow {
  key: string;
  label: string;
  tool: string;
  model: string | null;
  detail: string | null;
  status: RowStatus;
  ms: number | null;
  startedAt: string | null;
  simulated: boolean;
  /** A step that decided not to act says why (e.g. input already calibrated). */
  reason: string | null;
  error: string | null;
}

export function deriveTimeline(trace: OrchestratorTrace | null, stopped: boolean): TimelineRow[] {
  if (!trace) return [];
  return trace.planned_steps.map((tool, i) => {
    const step = trace.steps[i];
    const status: RowStatus = !step
      ? stopped
        ? "skipped"
        : "pending"
      : step.status === "RUNNING"
        ? "active"
        : step.status === "SUCCESS"
          ? "done"
          : step.status === "FAILED"
            ? "failed"
            : "skipped";
    return {
      key: `${i}-${tool}`,
      label: toolLabel(tool),
      tool,
      model: modelName(tool, trace.model_mode, step?.outputs?.weights),
      detail: TOOL[tool]?.detail ?? null,
      status,
      ms: step?.latency_ms ?? null,
      startedAt: step?.start_time ?? null,
      simulated: step?.outputs?.simulated === true,
      reason: typeof step?.outputs?.reason === "string" ? step.outputs.reason : null,
      error: step?.error ?? null,
    };
  });
}

export type RunPhase = "submitting" | "routing" | "running" | "completed" | "rejected" | "failed" | "stopped";

export function runPhase(status: JobStatus | "SUBMITTING", trace: OrchestratorTrace | null): RunPhase {
  if (status === "SUBMITTING") return "submitting";
  if (trace?.cancelled) return "stopped";
  if (status === "COMPLETED") return "completed";
  if (status === "REJECTED") return "rejected";
  if (status === "FAILED") return "failed";
  if (status === "EXECUTING") return "running";
  return "routing";
}

export function isActivePhase(phase: RunPhase): boolean {
  return phase === "submitting" || phase === "routing" || phase === "running";
}

export function expertCount(trace: OrchestratorTrace | null, mode: ModelMode | null): number {
  if (!trace) return 0;
  return new Set(trace.steps.map((s) => modelName(s.tool_name, mode, s.outputs?.weights)).filter(Boolean)).size;
}

/* ------------------------------------------------------------------ model-stated quantities */

/*
 * Numbers with units inside model-generated text. The language model is never a source of
 * measurements (UX brief §F4), so these are marked as the model's own wording; the measured
 * values live in "Measured from pixels".
 */
const QUANTITY =
  /(?:~\s*|≈\s*|about\s+|approximately\s+|around\s+|nearly\s+|over\s+|less than\s+)?\d[\d,]*(?:\.\d+)?\s*(?:%|percent\b|km²|km2\b|sq\.?\s?km\b|square\s+kilomet(?:er|re)s?\b|m²|m2\b|sqm\b|sq\.?\s?m\b|square\s+met(?:er|re)s?\b|hectares?\b|ha\b|acres?\b|kilomet(?:er|re)s?\b|km\b|met(?:er|re)s?\b)/gi;

export type TextSegment = { text: string; quantity: boolean };

export function splitModelQuantities(text: string): TextSegment[] {
  const out: TextSegment[] = [];
  let last = 0;
  for (const m of text.matchAll(QUANTITY)) {
    const i = m.index ?? 0;
    if (i > last) out.push({ text: text.slice(last, i), quantity: false });
    out.push({ text: m[0], quantity: true });
    last = i + m[0].length;
  }
  if (last < text.length) out.push({ text: text.slice(last), quantity: false });
  return out;
}
