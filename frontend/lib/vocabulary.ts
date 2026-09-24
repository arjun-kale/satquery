/*
 * The product's vocabulary (UX brief §4). One word per concept, used everywhere:
 * Scene · Scene set · Analysis · Evidence · Run · Trace.
 * Plain English first; the real tool/model name is always shown second, in mono.
 */

import type { ModelMode, Modality, SceneRole, SceneSetKind, TaskType } from "./types";

export const SCENE_SET: Record<SceneSetKind, { label: string; teach: string; roles: SceneRole[] }> = {
  single: { label: "Single image", teach: "Ask what's in one scene", roles: ["image"] },
  bitemporal: { label: "Two dates", teach: "Ask what changed between two dates", roles: ["T1", "T2"] },
  optical_sar: { label: "Optical + SAR", teach: "Combine an optical and a radar scene", roles: ["optical", "sar"] },
};

export const ROLE: Record<SceneRole, { label: string; long: string }> = {
  image: { label: "Scene", long: "Scene" },
  T1: { label: "T1", long: "Earlier date (T1)" },
  T2: { label: "T2", long: "Later date (T2)" },
  optical: { label: "Optical", long: "Optical scene" },
  sar: { label: "SAR", long: "SAR scene" },
};

export const MODALITY_LABEL: Record<Modality, string> = {
  optical: "Optical",
  sar: "SAR",
  unknown: "Modality not declared",
};

export const TASK: Record<TaskType, { label: string; question: string }> = {
  SPECTRAL_WATER_VEGETATION: { label: "Water or vegetation index", question: "Measure water or vegetation" },
  CAPTION_SCENE: { label: "Describe the scene", question: "Describe what's in the scene" },
  OBJECT_GROUNDING: { label: "Find objects", question: "Locate objects on the image" },
  CHANGE_DETECTION: { label: "Change between dates", question: "Find what changed" },
  SAR_WATER: { label: "Water from SAR", question: "Find water in the radar scene" },
  CROSS_MODAL: { label: "Optical + SAR together", question: "Combine optical and SAR" },
};

/** Tasks a scene set can actually run — used to filter suggestions and intent choices. */
export function tasksFor(kind: SceneSetKind, modality: Modality): TaskType[] {
  if (kind === "bitemporal") return ["CHANGE_DETECTION"];
  if (kind === "optical_sar") return ["CROSS_MODAL"];
  if (modality === "sar") return ["SAR_WATER", "CAPTION_SCENE"];
  return ["SPECTRAL_WATER_VEGETATION", "CAPTION_SCENE", "OBJECT_GROUNDING"];
}

type ModelKind = "vlm" | "change" | null;

export const TOOL: Record<string, { label: string; detail?: string; model: ModelKind }> = {
  compatibility: { label: "Checking the pair lines up", detail: "same CRS · shared footprint", model: null },
  preview: { label: "Rendering quick-looks", detail: "2–98 % stretch · 512 px", model: null },
  spectral_index: { label: "Measuring the index", detail: "from declared bands", model: null },
  geochat_vqa: { label: "Answering the question", model: "vlm" },
  geochat_caption: { label: "Describing the scene", model: "vlm" },
  geochat_grounding: { label: "Locating objects", model: "vlm" },
  geodesy: { label: "Placing it on the ground", detail: "footprint · area", model: null },
  changeformer: { label: "Finding what changed", model: "change" },
  change_area: { label: "Measuring the changed area", detail: "mask pixels × GSD²", model: null },
  change_vqa: { label: "Describing the change", detail: "sees the T1 quick-look", model: "vlm" },
  sar_calibrate: { label: "Calibrating the SAR scene", model: null },
  sar_despeckle: { label: "Reducing SAR speckle", model: null },
  mndwi: { label: "Water index", model: null },
  cross_modal_fusion: { label: "Fusing optical and SAR", detail: "SAR intensity as red overlay", model: null },
  geochat_summary: { label: "Summarising", model: "vlm" },
};

export function toolLabel(tool: string): string {
  return TOOL[tool]?.label ?? tool.replaceAll("_", " ");
}

/** The model that actually serves a tool in this backend mode — never a nicer-sounding one. */
export function modelName(tool: string, mode: ModelMode | null): string | null {
  const kind = TOOL[tool]?.model;
  if (!kind) return null;
  if (mode === "mock") return "mock adapter";
  return kind === "vlm" ? "GeoChat-7B · M2 LoRA" : "ChangeFormer";
}

export const MODEL_MODE_LABEL: Record<ModelMode, string> = {
  mock: "Mock models",
  local: "Local models",
  modal: "GeoChat on Modal GPU",
};
