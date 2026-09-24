"use client";

import { ArrowRight, CheckCheck, CircleAlert } from "lucide-react";
import { useEffect, useRef } from "react";
import { isActivePhase, runPhase } from "@/lib/analysis";
import { cn } from "@/lib/utils";
import type { TaskType } from "@/lib/types";
import { activeSceneSet, analysesFor, useDispatch, useWorkspace, type Analysis, type SceneSet } from "@/components/workspace/store";
import { Outcome } from "./answer-card";
import { PromptBox } from "./prompt-box";
import { RunTimeline } from "./run-timeline";

export interface ReportControl {
  state: "idle" | "preparing" | "done";
  run: () => void;
}

export function ConversationPanel({
  onAsk,
  onStop,
  onRetry,
  report,
}: {
  onAsk: (q: string, task?: TaskType) => void;
  onStop: (localId: string) => void;
  onRetry: (localId: string) => void;
  report: ReportControl;
}) {
  const state = useWorkspace();
  const set = activeSceneSet(state);
  const thread = analysesFor(state, set?.id ?? null);
  const running = thread.find((a) => isActivePhase(runPhase(a.status, a.trace)));
  const otherSetsHaveAnalyses = state.analyses.some((a) => a.sceneSetId !== set?.id);

  const scroller = useRef<HTMLDivElement>(null);
  const lastCount = useRef(0);
  useEffect(() => {
    const el = scroller.current;
    if (!el) return;
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 160;
    if (thread.length !== lastCount.current || nearBottom) el.scrollTo({ top: el.scrollHeight, behavior: thread.length !== lastCount.current ? "smooth" : "auto" });
    lastCount.current = thread.length;
  });

  const disabledReason =
    state.health.state === "offline" ? "The backend is offline — questions can't run until it's back." : state.composer ? "Finish adding scenes first." : null;

  return (
    <section aria-label="Conversation" className="flex h-full min-h-0 flex-col bg-panel">
      <div ref={scroller} className="min-h-0 flex-1 overflow-y-auto scrollbar-thin" aria-live="polite" aria-relevant="additions">
        {!set ? (
          <HowItWorks />
        ) : (
          <div className="flex flex-col gap-1 p-4">
            {otherSetsHaveAnalyses && thread.length === 0 && (
              <p className="mb-2 text-xs text-fg-faint">New scene set — starting a new analysis.</p>
            )}
            <SceneSetReady set={set} />
            {thread.map((a) => (
              <Turn
                key={a.localId}
                analysis={a}
                set={set}
                isActive={a.localId === state.activeAnalysisId}
                onAsk={onAsk}
                onStop={() => onStop(a.localId)}
                onRetry={() => onRetry(a.localId)}
                report={report}
              />
            ))}
          </div>
        )}
      </div>
      <PromptBox
        set={set}
        hasAnalyses={thread.length > 0}
        running={!!running}
        disabledReason={disabledReason}
        onAsk={(q) => onAsk(q)}
        onStop={() => running && onStop(running.localId)}
      />
    </section>
  );
}

function Turn({
  analysis,
  set,
  isActive,
  onAsk,
  onStop,
  onRetry,
  report,
}: {
  analysis: Analysis;
  set: SceneSet;
  isActive: boolean;
  onAsk: (q: string, task?: TaskType) => void;
  onStop: () => void;
  onRetry: () => void;
  report: ReportControl;
}) {
  const dispatch = useDispatch();
  return (
    <article className="mt-4 flex flex-col gap-3 animate-fade-up" aria-label={`Analysis: ${analysis.question}`}>
      <div className="flex flex-col items-end gap-1">
        <span className="text-xs text-fg-faint">You</span>
        <p className="max-w-[90%] rounded-md rounded-tr-sm bg-raised px-3 py-2 text-base text-fg">{analysis.question}</p>
      </div>
      <div
        className={cn(
          "flex flex-col gap-3 border-l-2 pl-3 transition-colors",
          isActive ? "border-accent" : "cursor-pointer border-line hover:border-line-strong",
        )}
        onClick={(e) => {
          if (!isActive && !(e.target as HTMLElement).closest("button,a,input")) dispatch({ type: "analysis/activate", localId: analysis.localId });
        }}
      >
        {!isActive && <span className="text-xs text-fg-faint">Click to show this analysis on the image</span>}
        <RunTimeline analysis={analysis} set={set} onStop={onStop} />
        <Outcome
          analysis={analysis}
          set={set}
          isActive={isActive}
          onAsk={onAsk}
          onRetry={onRetry}
          onReport={report.run}
          reportState={isActive ? report.state : "idle"}
        />
      </div>
    </article>
  );
}

function SceneSetReady({ set }: { set: SceneSet }) {
  const checks = set.validation?.checks ?? [];
  const warnings = checks.filter((c) => c.status === "warn");
  return (
    <div className="flex flex-col gap-1.5 rounded-md border border-line bg-base/50 px-3 py-2.5 text-sm">
      <div className="flex items-center gap-2 text-fg">
        {warnings.length ? <CircleAlert className="size-4 text-warning" /> : <CheckCheck className="size-4 text-success" />}
        <span>
          Scenes checked · {checks.filter((c) => c.status === "pass").length} passed
          {warnings.length > 0 && `, ${warnings.length} warning${warnings.length > 1 ? "s" : ""}`}
        </span>
      </div>
      {warnings.map((w) => (
        <p key={w.id} className="text-xs text-warning">
          {w.label}: {w.reason}
        </p>
      ))}
      {set.source && <p className="text-xs text-fg-faint">Source: {set.source}</p>}
    </div>
  );
}

/** The mental model, in the product's own words (UX brief §4). */
function HowItWorks() {
  const steps = [
    ["Your images", "GeoTIFFs you already have — one scene, two dates, or optical + SAR"],
    ["Checked", "Format, georeferencing, and that a pair covers the same ground"],
    ["The assistant picks the right experts", "Your question is matched to a fixed, auditable pipeline"],
    ["Experts analyse", "Remote-sensing models and deterministic measurements run step by step"],
    ["Answer + proof", "The answer, the region on the image, how sure it is, and the full trace"],
  ];
  return (
    <div className="flex flex-col gap-4 p-5">
      <h2 className="text-base font-medium text-fg">How SatQuery answers</h2>
      <ol className="flex flex-col">
        {steps.map(([title, body], i) => (
          <li key={title} className="flex gap-3">
            <div className="flex flex-col items-center">
              <span className="grid size-6 place-items-center rounded-full border border-line-strong font-mono text-xs text-fg-muted">{i + 1}</span>
              {i < steps.length - 1 && <span className="w-px flex-1 bg-line" />}
            </div>
            <div className="pb-4">
              <p className="text-sm font-medium text-fg">{title}</p>
              <p className="text-sm text-fg-muted">{body}</p>
            </div>
          </li>
        ))}
      </ol>
      <p className="flex items-center gap-1.5 text-sm text-fg-faint">
        <ArrowRight className="size-4" /> Start by adding images, or try a sample.
      </p>
    </div>
  );
}
