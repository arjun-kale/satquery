"use client";

import { X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { deriveEvidence, isActivePhase, runPhase } from "@/lib/analysis";
import { buildReport } from "@/lib/report";
import { cn, isTypingTarget } from "@/lib/utils";
import { IconButton, TooltipProvider } from "@/components/ui/primitives";
import { ConversationPanel, type ReportControl } from "@/components/conversation/conversation-panel";
import { PROMPT_ID } from "@/components/conversation/prompt-box";
import { TraceDrawer } from "@/components/trace/trace-drawer";
import { EvidenceViewer } from "@/components/viewer/evidence-viewer";
import { useActions, useHealth, usePersistence, useTracePolling } from "./effects";
import { useStreamingAnalysis } from "./stream";
import { EmptyState } from "./empty-state";
import { SceneComposer } from "./scene-composer";
import { SceneRail } from "./scene-rail";
import { activeAnalysis, activeSceneSet, useDispatch, useWorkspace, WorkspaceProvider, type ViewerMode } from "./store";
import { TopBar } from "./top-bar";

export function Workspace() {
  return (
    <WorkspaceProvider>
      <TooltipProvider delay={350}>
        <Shell />
      </TooltipProvider>
    </WorkspaceProvider>
  );
}

/** Esc stops a long run only when pressed twice, so a stray key can't throw away 10+ seconds of work. */
const STOP_CONFIRM_AFTER_MS = 10_000;

function Shell() {
  useHealth();
  usePersistence();
  useTracePolling();
  const state = useWorkspace();
  const dispatch = useDispatch();
  const jobActions = useActions();
  const actions = useStreamingAnalysis(jobActions);
  const set = activeSceneSet(state);
  const report = useReport();
  useHotkeys(actions.stop);
  usePageDrop();

  const main = state.composer ? <SceneComposer /> : !state.restored ? <Restoring /> : set ? <EvidenceViewer /> : <EmptyState />;

  return (
    <div className="flex h-dvh flex-col overflow-hidden">
      <a href={`#${PROMPT_ID}`} className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded-sm focus:bg-action focus:px-3 focus:py-1.5 focus:text-white">
        Skip to the question box
      </a>
      <TopBar report={report} />
      <div className="relative flex min-h-0 flex-1 flex-col md:flex-row">
        {set && state.railOpen && (
          <>
            {/* Tablet and below: the rail is a drawer over the viewer. */}
            <div className="fixed inset-0 z-30 bg-black/50 lg:hidden" onClick={() => dispatch({ type: "rail/toggle", value: false })} aria-hidden="true" />
            <div className="fixed inset-y-0 left-0 z-40 w-[280px] border-r border-line shadow-2xl lg:static lg:z-auto lg:w-60 lg:shrink-0 lg:shadow-none">
              <div className="flex h-12 items-center justify-end border-b border-line bg-panel px-2 lg:hidden">
                <IconButton label="Close scenes" onClick={() => dispatch({ type: "rail/toggle", value: false })}>
                  <X />
                </IconButton>
              </div>
              <div className="h-[calc(100%-3rem)] lg:h-full">
                <SceneRail />
              </div>
            </div>
          </>
        )}
        <main className={cn("relative min-w-0 border-line md:flex-1", set && !state.composer ? "h-[55dvh] shrink-0 border-b md:h-auto md:border-b-0" : "min-h-0 flex-1")}>
          {main}
        </main>
        <div className={cn("relative min-h-0 flex-1 flex-col border-line md:flex md:w-[360px] md:flex-none md:border-l xl:w-[400px]", set || state.composer ? "flex" : "hidden")}>
          <ConversationPanel onAsk={actions.ask} onStop={actions.stop} onRetry={actions.retry} report={report} />
        </div>
        <TraceDrawer />
      </div>
      <Toast />
    </div>
  );
}

function Restoring() {
  return (
    <div className="grid h-full place-items-center text-sm text-fg-muted" role="status">
      Restoring your workspace…
    </div>
  );
}

/* ------------------------------------------------------------------ report */

function useReport(): ReportControl {
  const state = useWorkspace();
  const dispatch = useDispatch();
  const [status, setStatus] = useState<ReportControl["state"]>("idle");
  const stateRef = useRef(state);
  stateRef.current = state;

  const run = useCallback(async () => {
    const s = stateRef.current;
    const analysis = activeAnalysis(s);
    const set = analysis ? s.sceneSets[analysis.sceneSetId] : null;
    if (!analysis?.trace || !set) return;
    setStatus("preparing");
    try {
      const blob = await buildReport(analysis, set);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `satquery-report-${analysis.jobId}.html`;
      a.click();
      URL.revokeObjectURL(url);
      setStatus("done");
      setTimeout(() => setStatus("idle"), 2000);
    } catch (e) {
      setStatus("idle");
      dispatch({
        type: "toast",
        tone: "critical",
        message: `The report couldn't be generated (${e instanceof Error ? e.message : "unknown error"}). The analysis is untouched — try again.`,
      });
    }
  }, [dispatch]);

  return { state: status, run };
}

/* ------------------------------------------------------------------ keyboard */

const MODE_KEYS: Record<string, ViewerMode> = { s: "swipe", d: "side", f: "flicker", b: "blend" };

function useHotkeys(stop: (localId: string) => void) {
  const state = useWorkspace();
  const dispatch = useDispatch();
  const ref = useRef(state);
  ref.current = state;
  const escArmedAt = useRef(0);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const s = ref.current;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const typing = isTypingTarget(e.target);
      const set = activeSceneSet(s);
      const analysis = activeAnalysis(s);
      const running = analysis && isActivePhase(runPhase(analysis.status, analysis.trace)) ? analysis : null;

      if (e.key === "Escape") {
        if (s.trace.open) return dispatch({ type: "trace/close" });
        if (running?.jobId && !running.stopRequested) {
          const long = Date.now() - running.createdAt > STOP_CONFIRM_AFTER_MS;
          if (!long || Date.now() - escArmedAt.current < 3000) {
            escArmedAt.current = 0;
            dispatch({ type: "toast", message: null });
            return stop(running.localId);
          }
          escArmedAt.current = Date.now();
          return dispatch({ type: "toast", message: "Press Esc again to stop the run." });
        }
        if (s.evidence.focused != null || s.evidence.showAll) {
          dispatch({ type: "evidence/focus", n: null });
          dispatch({ type: "evidence/showAll", value: false });
        }
        return;
      }
      if (typing) return;

      if (e.key === "/") {
        e.preventDefault();
        document.getElementById(PROMPT_ID)?.focus();
        return;
      }
      if (!set || s.composer) return;
      const key = e.key.toLowerCase();
      if (/^[1-9]$/.test(e.key)) {
        const n = Number(e.key);
        if (deriveEvidence(analysis?.trace ?? null).some((ev) => ev.n === n)) dispatch({ type: "evidence/focus", n: s.evidence.focused === n ? null : n });
        return;
      }
      if (key in MODE_KEYS && set.scenes.length === 2) {
        if (MODE_KEYS[key] === "blend" && set.kind !== "optical_sar") return;
        return dispatch({ type: "viewer/mode", mode: MODE_KEYS[key] });
      }
      if (key === "l") return dispatch({ type: "viewer/loupe" });
      if (key === "a") return dispatch({ type: "evidence/showAll" });
      if (key === "t") return dispatch(s.trace.open ? { type: "trace/close" } : { type: "trace/open" });
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [dispatch, stop]);
}

/** Files dropped anywhere open the add-scenes flow; roles are then proposed, never guessed silently. */
function usePageDrop() {
  const dispatch = useDispatch();
  useEffect(() => {
    const over = (e: DragEvent) => {
      if (e.dataTransfer?.types.includes("Files")) e.preventDefault();
    };
    const drop = (e: DragEvent) => {
      const files = [...(e.dataTransfer?.files ?? [])];
      if (!files.length) return;
      e.preventDefault();
      dispatch({ type: "composer/open", kind: null, files });
    };
    window.addEventListener("dragover", over);
    window.addEventListener("drop", drop);
    return () => {
      window.removeEventListener("dragover", over);
      window.removeEventListener("drop", drop);
    };
  }, [dispatch]);
}

/* ------------------------------------------------------------------ toast */

function Toast() {
  const { toast } = useWorkspace();
  const dispatch = useDispatch();
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => dispatch({ type: "toast", message: null }), toast.tone === "critical" ? 8000 : 3000);
    return () => clearTimeout(t);
  }, [toast, dispatch]);
  return (
    <div aria-live="assertive" className="pointer-events-none fixed inset-x-0 bottom-4 z-50 flex justify-center px-4">
      {toast && (
        <div
          key={toast.id}
          className={cn(
            "pointer-events-auto flex max-w-lg items-start gap-3 rounded-md border bg-raised px-3 py-2 text-sm shadow-2xl shadow-black/60 animate-fade-up",
            toast.tone === "critical" ? "border-critical/40 text-fg" : "border-line-strong text-fg",
          )}
        >
          {toast.message}
          <button onClick={() => dispatch({ type: "toast", message: null })} aria-label="Dismiss" className="text-fg-muted hover:text-fg">
            <X className="size-4" />
          </button>
        </div>
      )}
    </div>
  );
}
