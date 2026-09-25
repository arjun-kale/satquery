"use client";

import { createContext, useContext, useReducer, type Dispatch, type ReactNode } from "react";
import type {
  JobStatus,
  ModelMode,
  OrchestratorTrace,
  RasterMetadata,
  SceneRole,
  SceneSetKind,
  TaskType,
  TraceResponse,
  ValidateResponse,
} from "@/lib/types";

export interface Scene {
  role: SceneRole;
  imageId: string;
  metadata: RasterMetadata;
}

export interface SceneSet {
  id: string;
  kind: SceneSetKind;
  title: string;
  scenes: Scene[];
  validation: ValidateResponse | null;
  sampleId?: string;
  suggestedQuestion?: string;
  source?: string;
}

export interface Analysis {
  localId: string;
  jobId: string | null;
  sceneSetId: string;
  question: string;
  forcedTask?: TaskType;
  createdAt: number;
  status: JobStatus | "SUBMITTING";
  trace: OrchestratorTrace | null;
  schemaVersion: string | null;
  failureReason: string | null;
  /** The job never started (backend unreachable / rejected the request). */
  submitError: string | null;
  connection: "ok" | "lost";
  stopRequested: boolean;
  /** Receiving live events over the AI SDK stream; polling skips it until the stream ends. */
  streaming?: boolean;
}

export type ViewerMode = "swipe" | "side" | "flicker" | "blend";
export type TraceTab = "steps" | "layers" | "json";

export interface WorkspaceState {
  health: { state: "checking" | "online" | "offline"; modelMode: ModelMode | null; maxMegapixels: number | null };
  sceneSets: Record<string, SceneSet>;
  activeSceneSetId: string | null;
  analyses: Analysis[];
  activeAnalysisId: string | null;
  evidence: { focused: number | null; hovered: number | null; showAll: boolean };
  /** Layer visibility overrides; layers not listed use their own default. */
  viewer: { mode: ViewerMode; loupe: boolean; layers: Record<string, boolean>; sarOpacity: number; outlineFill: boolean };
  trace: { open: boolean; tab: TraceTab };
  railOpen: boolean;
  /** Set while the add-scenes flow is open (replaces the viewer). */
  composer: { kind: SceneSetKind | null; seed?: Scene; files?: File[] } | null;
  toast: { id: number; message: string; tone: "neutral" | "critical" } | null;
  restored: boolean;
}

export const initialState: WorkspaceState = {
  health: { state: "checking", modelMode: null, maxMegapixels: null },
  sceneSets: {},
  activeSceneSetId: null,
  analyses: [],
  activeAnalysisId: null,
  evidence: { focused: null, hovered: null, showAll: false },
  viewer: { mode: "swipe", loupe: false, layers: {}, sarOpacity: 0.6, outlineFill: false },
  trace: { open: false, tab: "steps" },
  railOpen: true,
  composer: null,
  toast: null,
  restored: false,
};

export type Action =
  | { type: "health"; state: WorkspaceState["health"]["state"]; modelMode?: ModelMode | null; maxMegapixels?: number | null }
  | { type: "restore"; sceneSets: Record<string, SceneSet>; activeSceneSetId: string | null; analyses: Analysis[]; activeAnalysisId: string | null }
  | { type: "sceneSet/add"; sceneSet: SceneSet }
  | { type: "sceneSet/activate"; id: string }
  | { type: "composer/open"; kind: SceneSetKind | null; seed?: Scene; files?: File[] }
  | { type: "composer/close" }
  | { type: "analysis/submit"; analysis: Analysis }
  | { type: "analysis/created"; localId: string; jobId: string }
  | { type: "analysis/submitFailed"; localId: string; message: string }
  | { type: "analysis/trace"; localId: string; response: TraceResponse }
  | { type: "analysis/connection"; localId: string; connection: "ok" | "lost" }
  | { type: "analysis/stopRequested"; localId: string }
  | { type: "analysis/streaming"; localId: string; value: boolean }
  | { type: "analysis/activate"; localId: string }
  | { type: "evidence/focus"; n: number | null }
  | { type: "evidence/hover"; n: number | null }
  | { type: "evidence/showAll"; value?: boolean }
  | { type: "viewer/mode"; mode: ViewerMode }
  | { type: "viewer/loupe"; value?: boolean }
  | { type: "viewer/layer"; id: string; visible: boolean }
  | { type: "viewer/sarOpacity"; value: number }
  | { type: "viewer/outlineFill"; value?: boolean }
  | { type: "toast"; message: string | null; tone?: "neutral" | "critical" }
  | { type: "trace/open"; tab?: TraceTab }
  | { type: "trace/close" }
  | { type: "trace/tab"; tab: TraceTab }
  | { type: "rail/toggle"; value?: boolean };

const resetEvidence = { focused: null, hovered: null, showAll: false };

function patchAnalysis(state: WorkspaceState, localId: string, patch: (a: Analysis) => Partial<Analysis>): WorkspaceState {
  return {
    ...state,
    analyses: state.analyses.map((a) => (a.localId === localId ? { ...a, ...patch(a) } : a)),
  };
}

export function reducer(state: WorkspaceState, action: Action): WorkspaceState {
  switch (action.type) {
    case "health":
      return {
        ...state,
        health: {
          state: action.state,
          modelMode: action.modelMode ?? state.health.modelMode,
          maxMegapixels: action.maxMegapixels ?? state.health.maxMegapixels,
        },
      };
    case "restore": {
      const { sceneSets, activeSceneSetId, analyses, activeAnalysisId } = action;
      return {
        ...state,
        sceneSets,
        activeSceneSetId,
        analyses,
        activeAnalysisId,
        restored: true,
        railOpen: typeof window === "undefined" || window.innerWidth >= 1024,
      };
    }
    case "sceneSet/add": {
      const s = action.sceneSet;
      return {
        ...state,
        sceneSets: { ...state.sceneSets, [s.id]: s },
        activeSceneSetId: s.id,
        activeAnalysisId: null,
        composer: null,
        evidence: resetEvidence,
        viewer: { ...state.viewer, mode: s.kind === "optical_sar" ? "blend" : "swipe", layers: {} },
      };
    }
    case "sceneSet/activate": {
      const last = [...state.analyses].reverse().find((a) => a.sceneSetId === action.id);
      return {
        ...state,
        activeSceneSetId: action.id,
        activeAnalysisId: last?.localId ?? null,
        composer: null,
        evidence: resetEvidence,
      };
    }
    case "composer/open":
      return { ...state, composer: { kind: action.kind, seed: action.seed, files: action.files }, trace: { ...state.trace, open: false } };
    case "composer/close":
      return { ...state, composer: null };
    case "analysis/submit":
      return {
        ...state,
        analyses: [...state.analyses, action.analysis],
        activeAnalysisId: action.analysis.localId,
        evidence: resetEvidence,
        // Scenes step back once there's an answer to look at, on screens under 1440 px.
        railOpen: typeof window !== "undefined" && window.innerWidth < 1440 ? false : state.railOpen,
      };
    case "analysis/created":
      return patchAnalysis(state, action.localId, () => ({ jobId: action.jobId, status: "RECEIVED" }));
    case "analysis/submitFailed":
      return patchAnalysis(state, action.localId, () => ({ submitError: action.message, status: "FAILED" }));
    case "analysis/trace":
      return patchAnalysis(state, action.localId, () => ({
        status: action.response.status,
        trace: action.response.trace,
        schemaVersion: action.response.schema_version,
        failureReason: action.response.failure_reason,
        connection: "ok",
      }));
    case "analysis/connection":
      return patchAnalysis(state, action.localId, () => ({ connection: action.connection }));
    case "analysis/streaming":
      return patchAnalysis(state, action.localId, () => ({ streaming: action.value }));
    case "analysis/stopRequested":
      return patchAnalysis(state, action.localId, () => ({ stopRequested: true }));
    case "analysis/activate":
      return { ...state, activeAnalysisId: action.localId, evidence: resetEvidence };
    case "evidence/focus":
      return { ...state, evidence: { ...state.evidence, focused: action.n, showAll: action.n == null ? state.evidence.showAll : false } };
    case "evidence/hover":
      return { ...state, evidence: { ...state.evidence, hovered: action.n } };
    case "evidence/showAll": {
      const value = action.value ?? !state.evidence.showAll;
      return { ...state, evidence: { focused: value ? null : state.evidence.focused, hovered: null, showAll: value } };
    }
    case "viewer/mode":
      return { ...state, viewer: { ...state.viewer, mode: action.mode } };
    case "viewer/loupe":
      return { ...state, viewer: { ...state.viewer, loupe: action.value ?? !state.viewer.loupe } };
    case "viewer/layer":
      return { ...state, viewer: { ...state.viewer, layers: { ...state.viewer.layers, [action.id]: action.visible } } };
    case "viewer/sarOpacity":
      return { ...state, viewer: { ...state.viewer, sarOpacity: action.value } };
    case "viewer/outlineFill":
      return { ...state, viewer: { ...state.viewer, outlineFill: action.value ?? !state.viewer.outlineFill } };
    case "toast":
      return {
        ...state,
        toast: action.message ? { id: Date.now(), message: action.message, tone: action.tone ?? "neutral" } : null,
      };
    case "trace/open":
      return { ...state, trace: { open: true, tab: action.tab ?? state.trace.tab } };
    case "trace/close":
      return { ...state, trace: { ...state.trace, open: false } };
    case "trace/tab":
      return { ...state, trace: { ...state.trace, tab: action.tab } };
    case "rail/toggle":
      return { ...state, railOpen: action.value ?? !state.railOpen };
  }
}

const StateContext = createContext<WorkspaceState | null>(null);
const DispatchContext = createContext<Dispatch<Action> | null>(null);

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState);
  return (
    <StateContext.Provider value={state}>
      <DispatchContext.Provider value={dispatch}>{children}</DispatchContext.Provider>
    </StateContext.Provider>
  );
}

export function useWorkspace(): WorkspaceState {
  const ctx = useContext(StateContext);
  if (!ctx) throw new Error("useWorkspace must be used inside WorkspaceProvider");
  return ctx;
}

export function useDispatch(): Dispatch<Action> {
  const ctx = useContext(DispatchContext);
  if (!ctx) throw new Error("useDispatch must be used inside WorkspaceProvider");
  return ctx;
}

/* ---- selectors ---- */

export function activeSceneSet(state: WorkspaceState): SceneSet | null {
  return state.activeSceneSetId ? state.sceneSets[state.activeSceneSetId] ?? null : null;
}

export function activeAnalysis(state: WorkspaceState): Analysis | null {
  return state.analyses.find((a) => a.localId === state.activeAnalysisId) ?? null;
}

export function analysesFor(state: WorkspaceState, sceneSetId: string | null): Analysis[] {
  return state.analyses.filter((a) => a.sceneSetId === sceneSetId);
}

export function layerVisible(state: WorkspaceState, id: string, fallback: boolean): boolean {
  return state.viewer.layers[id] ?? fallback;
}
