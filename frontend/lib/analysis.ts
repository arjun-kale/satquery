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
    for (const r of (change.step.outputs.change_regions as RegionOut[] | undefined) ?? []) {
      out.push({
        kind: "contour",
        tone: "change",
        title: "Changed region",
        honesty: isMock ? "Change mask outline (mock model — placeholder mask)" : "Change mask outline",
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

  return out.slice(0, CIRCLED.length).map((e, i) => ({ ...e, n: i + 1 }));
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
      model: modelName(tool, trace.model_mode),
      detail: TOOL[tool]?.detail ?? null,
      status,
      ms: step?.latency_ms ?? null,
      startedAt: step?.start_time ?? null,
      simulated: step?.outputs?.simulated === true,
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
  return new Set(trace.steps.map((s) => modelName(s.tool_name, mode)).filter(Boolean)).size;
}
