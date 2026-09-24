"use client";

/*
 * Asking a question = one AI SDK chat turn (UX brief §8). `useChat` posts to FastAPI's
 * /api/chat through DefaultChatTransport and receives the UI Message Stream: every recorded
 * run event arrives as a `data-trace` part (reconciled in place by job id), plus tool and text
 * parts. `stop()` aborts the stream and the backend cancels the job before its next step.
 *
 * If the stream drops mid-run, the analysis falls back to trace polling (useTracePolling),
 * which resumes from the backend's own record — the "reconnecting" path.
 */

import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport, type UIMessage } from "ai";
import { useCallback, useMemo, useRef } from "react";
import { api, API_BASE } from "@/lib/api";
import type { TaskType, TraceResponse } from "@/lib/types";
import { newId } from "@/lib/utils";
import type { useActions } from "./effects";
import { activeSceneSet, useDispatch, useWorkspace, type WorkspaceState } from "./store";

type StreamMeta = { jobId: string; localId: string | null };
export type SatQueryMessage = UIMessage<StreamMeta, { job: StreamMeta; trace: TraceResponse }>;

export function useStreamingAnalysis(fallback: ReturnType<typeof useActions>) {
  const state = useWorkspace();
  const dispatch = useDispatch();
  const stateRef = useRef<WorkspaceState>(state);
  stateRef.current = state;
  const jobToLocal = useRef(new Map<string, string>());

  const transport = useMemo(() => new DefaultChatTransport<SatQueryMessage>({ api: `${API_BASE}/api/chat` }), []);
  const chat = useChat<SatQueryMessage>({
    id: "satquery-workspace",
    transport,
    onData: (part) => {
      if (part.type === "data-job" && part.data.localId) {
        jobToLocal.current.set(part.data.jobId, part.data.localId);
        dispatch({ type: "analysis/created", localId: part.data.localId, jobId: part.data.jobId });
      } else if (part.type === "data-trace") {
        const localId = jobToLocal.current.get(part.data.job_id);
        if (localId) dispatch({ type: "analysis/trace", localId, response: part.data });
      }
    },
  });
  const chatRef = useRef(chat);
  chatRef.current = chat;

  const ask = useCallback(
    async (question: string, task?: TaskType) => {
      const set = activeSceneSet(stateRef.current);
      if (!set || !question.trim()) return;
      // One stream at a time: a second concurrent question (another scene set) uses the job API.
      if (chatRef.current.status === "streaming" || chatRef.current.status === "submitted") {
        return fallback.ask(question, task);
      }
      const localId = newId();
      dispatch({
        type: "analysis/submit",
        analysis: {
          localId,
          jobId: null,
          sceneSetId: set.id,
          question: question.trim(),
          forcedTask: task,
          createdAt: Date.now(),
          status: "SUBMITTING",
          trace: null,
          schemaVersion: null,
          failureReason: null,
          submitError: null,
          connection: "ok",
          stopRequested: false,
          streaming: true,
        },
      });
      try {
        await chatRef.current.sendMessage(
          { text: question.trim() },
          { body: { image_ids: set.scenes.map((s) => s.imageId), scene_set_kind: set.kind, task, local_id: localId } },
        );
      } catch {
        /* handled below from the recorded state */
      } finally {
        const a = stateRef.current.analyses.find((x) => x.localId === localId);
        if (a && !a.jobId) {
          dispatch({ type: "analysis/submitFailed", localId, message: chatRef.current.error?.message ?? "Can't reach the SatQuery backend." });
        }
        // Stream over (finished, aborted or dropped): polling now owns anything still running.
        dispatch({ type: "analysis/streaming", localId, value: false });
      }
    },
    [dispatch, fallback],
  );

  const stop = useCallback(
    async (localId: string) => {
      const a = stateRef.current.analyses.find((x) => x.localId === localId);
      if (!a) return;
      if (a.streaming) {
        dispatch({ type: "analysis/stopRequested", localId });
        await chatRef.current.stop();
        // The abort reaches FastAPI as a disconnect; the explicit cancel makes it certain.
        if (a.jobId) await api.cancel(a.jobId).catch(() => undefined);
      } else {
        await fallback.stop(localId);
      }
    },
    [dispatch, fallback],
  );

  const retry = useCallback(
    (localId: string) => {
      const a = stateRef.current.analyses.find((x) => x.localId === localId);
      if (a) ask(a.question, a.forcedTask);
    },
    [ask],
  );

  return { ask, stop, retry };
}
