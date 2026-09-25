"use client";

import { useCallback, useEffect, useRef } from "react";
import { api, ApiError } from "@/lib/api";
import { TERMINAL_STATUSES, type LoadedSample, type SceneSetKind, type TaskType } from "@/lib/types";
import { newId } from "@/lib/utils";
import { SCENE_SET } from "@/lib/vocabulary";
import {
  activeSceneSet,
  useDispatch,
  useWorkspace,
  type Analysis,
  type Scene,
  type SceneSet,
  type WorkspaceState,
} from "./store";

/* ------------------------------------------------------------------ health */

export function useHealth() {
  const dispatch = useDispatch();
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    const controller = new AbortController();
    const check = async () => {
      try {
        const h = await api.health(controller.signal);
        dispatch({ type: "health", state: "online", modelMode: h.model_mode, maxMegapixels: h.max_raster_megapixels });
      } catch {
        if (!controller.signal.aborted) dispatch({ type: "health", state: "offline" });
      }
      timer = setTimeout(check, 15_000);
    };
    check();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [dispatch]);
}

/* ------------------------------------------------------------------ persistence */

const STORAGE_KEY = "satquery.workspace.v1";
const MAX_ANALYSES = 40;

interface Persisted {
  v: 1;
  sceneSets: (Omit<SceneSet, "scenes" | "validation"> & { scenes: { role: Scene["role"]; imageId: string }[] })[];
  activeSceneSetId: string | null;
  analyses: Pick<Analysis, "localId" | "jobId" | "sceneSetId" | "question" | "forcedTask" | "createdAt">[];
  activeAnalysisId: string | null;
}

function readPersisted(): Persisted | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? (JSON.parse(raw) as Persisted) : null;
    return parsed?.v === 1 ? parsed : null;
  } catch {
    return null;
  }
}

/**
 * Only ids and questions live in the browser; scenes, validation and traces are re-read from
 * the backend on reload, so a restored analysis shows exactly what the backend recorded.
 */
export function usePersistence() {
  const state = useWorkspace();
  const dispatch = useDispatch();

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const saved = readPersisted();
      if (!saved) {
        dispatch({ type: "restore", sceneSets: {}, activeSceneSetId: null, analyses: [], activeAnalysisId: null });
        return;
      }
      const sceneSets: Record<string, SceneSet> = {};
      await Promise.all(
        saved.sceneSets.map(async (s) => {
          try {
            const metas = await Promise.all(s.scenes.map((sc) => api.imageMetadata(sc.imageId)));
            const validation = await api.validate(s.kind, s.scenes.map((sc) => sc.imageId)).catch(() => null);
            sceneSets[s.id] = {
              ...s,
              scenes: s.scenes.map((sc, i) => ({ ...sc, metadata: metas[i] })),
              validation,
            };
          } catch {
            /* scene files are gone from the backend: drop the set */
          }
        }),
      );
      const analyses: Analysis[] = [];
      for (const a of saved.analyses) {
        if (!sceneSets[a.sceneSetId] || !a.jobId) continue;
        try {
          const r = await api.trace(a.jobId);
          analyses.push({
            ...a,
            status: r.status,
            trace: r.trace,
            schemaVersion: r.schema_version,
            failureReason: r.failure_reason,
            submitError: null,
            connection: "ok",
            stopRequested: false,
          });
        } catch {
          /* job no longer on the backend */
        }
      }
      if (cancelled) return;
      const activeSceneSetId = saved.activeSceneSetId && sceneSets[saved.activeSceneSetId] ? saved.activeSceneSetId : null;
      const activeAnalysisId = analyses.some((a) => a.localId === saved.activeAnalysisId) ? saved.activeAnalysisId : null;
      dispatch({ type: "restore", sceneSets, activeSceneSetId, analyses, activeAnalysisId });
    })();
    return () => {
      cancelled = true;
    };
  }, [dispatch]);

  useEffect(() => {
    if (!state.restored) return;
    const data: Persisted = {
      v: 1,
      sceneSets: Object.values(state.sceneSets).map((s) => ({
        id: s.id,
        kind: s.kind,
        title: s.title,
        sampleId: s.sampleId,
        suggestedQuestion: s.suggestedQuestion,
        source: s.source,
        scenes: s.scenes.map((sc) => ({ role: sc.role, imageId: sc.imageId })),
      })),
      activeSceneSetId: state.activeSceneSetId,
      analyses: state.analyses
        .filter((a) => a.jobId)
        .slice(-MAX_ANALYSES)
        .map(({ localId, jobId, sceneSetId, question, forcedTask, createdAt }) => ({
          localId,
          jobId,
          sceneSetId,
          question,
          forcedTask,
          createdAt,
        })),
      activeAnalysisId: state.activeAnalysisId,
    };
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    } catch {
      /* storage unavailable (private mode): the session still works, it just won't survive reload */
    }
  }, [state.restored, state.sceneSets, state.activeSceneSetId, state.analyses, state.activeAnalysisId]);
}

/* ------------------------------------------------------------------ trace polling */

const POLL_MS = 500;
const RETRY_MS = 2000;

/**
 * The executor writes its trace after every step, so polling it is a real event stream:
 * each new row in the UI corresponds to a state change the backend recorded.
 */
export function useTracePolling() {
  const { analyses } = useWorkspace();
  const dispatch = useDispatch();

  useEffect(() => {
    const pending = analyses.filter((a) => a.jobId && !a.streaming && !TERMINAL_STATUSES.includes(a.status as never));
    if (!pending.length) return;
    let cancelled = false;
    const lost = pending.some((a) => a.connection === "lost");
    const timer = setTimeout(() => {
      pending.forEach(async (a) => {
        try {
          const response = await api.trace(a.jobId!);
          if (!cancelled) dispatch({ type: "analysis/trace", localId: a.localId, response });
        } catch {
          if (!cancelled) dispatch({ type: "analysis/connection", localId: a.localId, connection: "lost" });
        }
      });
    }, lost ? RETRY_MS : POLL_MS);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [analyses, dispatch]);
}

/* ------------------------------------------------------------------ actions */

export function useActions() {
  const state = useWorkspace();
  const dispatch = useDispatch();
  const stateRef = useRef<WorkspaceState>(state);
  stateRef.current = state;

  const ask = useCallback(
    async (question: string, forcedTask?: TaskType) => {
      const set = activeSceneSet(stateRef.current);
      if (!set || !question.trim()) return;
      const localId = newId();
      dispatch({
        type: "analysis/submit",
        analysis: {
          localId,
          jobId: null,
          sceneSetId: set.id,
          question: question.trim(),
          forcedTask,
          createdAt: Date.now(),
          status: "SUBMITTING",
          trace: null,
          schemaVersion: null,
          failureReason: null,
          submitError: null,
          connection: "ok",
          stopRequested: false,
        },
      });
      try {
        const job = await api.createJob({
          image_ids: set.scenes.map((s) => s.imageId),
          query: question.trim(),
          scene_set_kind: set.kind,
          task: forcedTask,
        });
        dispatch({ type: "analysis/created", localId, jobId: job.id });
      } catch (e) {
        dispatch({
          type: "analysis/submitFailed",
          localId,
          message: e instanceof ApiError ? e.message : "The analysis couldn't be started.",
        });
      }
    },
    [dispatch],
  );

  const stop = useCallback(
    async (localId: string) => {
      const a = stateRef.current.analyses.find((x) => x.localId === localId);
      if (!a?.jobId) return;
      dispatch({ type: "analysis/stopRequested", localId });
      try {
        await api.cancel(a.jobId);
      } catch {
        /* polling will surface the connection state */
      }
    },
    [dispatch],
  );

  const retry = useCallback(
    (localId: string) => {
      const a = stateRef.current.analyses.find((x) => x.localId === localId);
      if (a) ask(a.question, a.forcedTask);
    },
    [ask],
  );

  const addSceneSet = useCallback(
    (kind: SceneSetKind, scenes: Scene[], validation: SceneSet["validation"], extra?: Partial<SceneSet>) => {
      dispatch({
        type: "sceneSet/add",
        sceneSet: {
          id: newId(),
          kind,
          title: extra?.title ?? defaultTitle(kind, scenes),
          scenes,
          validation,
          ...extra,
        },
      });
    },
    [dispatch],
  );

  const loadSample = useCallback(
    async (sampleId: string): Promise<LoadedSample> => {
      const loaded = await api.loadSample(sampleId);
      const scenes: Scene[] = loaded.scenes.map((s) => ({ role: s.role, imageId: s.image_id, metadata: s.metadata }));
      const validation = await api.validate(loaded.sample.kind, scenes.map((s) => s.imageId));
      addSceneSet(loaded.sample.kind, scenes, validation, {
        title: loaded.sample.title,
        sampleId,
        suggestedQuestion: loaded.sample.suggested_question,
        source: `${loaded.sample.source} · ${loaded.sample.license}`,
      });
      return loaded;
    },
    [addSceneSet],
  );

  return { ask, stop, retry, addSceneSet, loadSample };
}

function defaultTitle(kind: SceneSetKind, scenes: Scene[]): string {
  const name = scenes[0]?.metadata.filename.replace(/\.(tiff?|png|jpe?g)$/i, "") ?? "Scenes";
  return `${name} — ${SCENE_SET[kind].label.toLowerCase()}`;
}
