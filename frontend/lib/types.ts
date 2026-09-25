/*
 * Mirrors of the FastAPI/Pydantic contracts. Source of truth:
 *   backend/app/schemas.py                    RasterMetadata, HealthResponse
 *   backend/app/api/scene_sets.py             ValidationCheck, ValidateResponse
 *   backend/app/api/samples.py                Sample, LoadedSample
 *   backend/app/orchestration/schema.py       OrchestratorTrace, ExecutionStep
 * Keep field names identical so a diff against the Python makes drift obvious.
 */

export type ModelMode = "mock" | "local" | "modal" | "hf";

export interface HealthResponse {
  status: "ok";
  database: "ok";
  model_mode: ModelMode;
  max_raster_megapixels: number;
}

export type Modality = "optical" | "sar" | "unknown";

export interface RasterMetadata {
  image_id: string;
  filename: string;
  checksum_sha256: string;
  format: string;
  width: number;
  height: number;
  band_count: number;
  dtype: string;
  crs: string | null;
  gsd_m: number | null;
  extent_wgs84: [number, number, number, number] | null;
  corners_wgs84: [number, number][] | null;
  modality: Modality;
  acquired_at: string | null;
  nodata: number | null;
  sensor_tags: Record<string, string>;
  preview_band_map: string | null;
  is_georeferenced: boolean;
}

export interface IngestResponse {
  image_id: string;
  metadata: RasterMetadata;
}

export type SceneSetKind = "single" | "bitemporal" | "optical_sar";
export type SceneRole = "image" | "T1" | "T2" | "optical" | "sar";

export type CheckStatus = "pass" | "warn" | "fail";

export interface ValidationCheck {
  id: string;
  label: string;
  status: CheckStatus;
  value: string | null;
  reason: string | null;
}

export interface ValidateResponse {
  kind: SceneSetKind;
  passed: boolean;
  checks: ValidationCheck[];
}

export interface Sample {
  id: string;
  title: string;
  kind: SceneSetKind;
  description: string;
  suggested_question: string;
  source: string;
  license: string;
  files: { role: SceneRole; path: string }[];
}

export interface LoadedSample {
  sample: Sample;
  scenes: { role: SceneRole; image_id: string; metadata: RasterMetadata }[];
}

export type JobStatus =
  | "RECEIVED"
  | "VALIDATED"
  | "ROUTING"
  | "EXECUTING"
  | "COMPLETED"
  | "REJECTED"
  | "FAILED";

export const TERMINAL_STATUSES: JobStatus[] = ["COMPLETED", "REJECTED", "FAILED"];

export interface JobRecord {
  id: string;
  status: JobStatus;
  created_at: string;
  updated_at: string;
  failure_reason: string | null;
}

export type TaskType =
  | "SPECTRAL_WATER_VEGETATION"
  | "CAPTION_SCENE"
  | "OBJECT_GROUNDING"
  | "CHANGE_DETECTION"
  | "SAR_WATER"
  | "CROSS_MODAL";

export type StepStatus = "PENDING" | "RUNNING" | "SUCCESS" | "FAILED" | "SKIPPED";

export interface ExecutionStep {
  tool_name: string;
  status: StepStatus;
  start_time: string | null;
  end_time: string | null;
  latency_ms: number | null;
  inputs: Record<string, unknown>;
  outputs: Record<string, unknown>;
  error: string | null;
}

export interface RouteCandidate {
  task: TaskType;
  score: number;
}

export type RoutingMode = "similarity" | "scene_set_rule" | "user_choice";
export type Rejection = "low_score" | "ambiguous" | "needs_pair";

export interface OrchestratorTrace {
  query: string;
  router_version: string;
  canonical_template_id: TaskType | null;
  similarity_score: number | null;
  similarity_threshold: number;
  routing_mode: RoutingMode;
  runner_up: RouteCandidate | null;
  candidates: RouteCandidate[];
  rejection: Rejection | null;
  scene_set_kind: SceneSetKind | null;
  image_ids: string[];
  model_mode: ModelMode | null;
  planned_steps: string[];
  cancelled: boolean;
  steps: ExecutionStep[];
  total_latency_ms: number | null;
  created_at: string;
}

export interface TraceResponse {
  schema_version: string | null;
  job_id: string;
  status: JobStatus;
  trace: OrchestratorTrace | null;
  failure_reason: string | null;
}

/* ---- Tool outputs the UI reads (subset of each dispatcher branch's return dict) ---- */

export type ConfidenceSource = "model-provided" | "rule-derived" | "unavailable";

export interface GroundingBoxOut {
  label: string;
  confidence: number;
  x_min: number;
  y_min: number;
  x_max: number;
  y_max: number;
}

export interface RegionOut {
  id: number;
  rings: [number, number][][];
  bbox: [number, number, number, number];
  pixel_count: number;
  area_m2: number | null;
}
