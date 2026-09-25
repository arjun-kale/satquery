"use client";

import { ChevronRight, Download, FlaskConical, Loader2, PanelLeft, Check } from "lucide-react";
import { isActivePhase, runPhase } from "@/lib/analysis";
import { cn } from "@/lib/utils";
import { MODEL_MODE_LABEL } from "@/lib/vocabulary";
import { Button, IconButton, Tag, Tip } from "@/components/ui/primitives";
import { activeAnalysis, activeSceneSet, analysesFor, useDispatch, useWorkspace } from "./store";
import type { ReportControl } from "@/components/conversation/conversation-panel";

export function TopBar({ report }: { report: ReportControl }) {
  const state = useWorkspace();
  const dispatch = useDispatch();
  const set = activeSceneSet(state);
  const analysis = activeAnalysis(state);
  const thread = analysesFor(state, set?.id ?? null);
  const analysisIndex = analysis ? thread.findIndex((a) => a.localId === analysis.localId) + 1 : 0;
  const running = state.analyses.some((a) => isActivePhase(runPhase(a.status, a.trace)));
  const canExport = !!analysis && runPhase(analysis.status, analysis.trace) === "completed";

  const status =
    state.health.state === "checking"
      ? { label: "Connecting…", dot: "bg-fg-faint", pulse: true }
      : state.health.state === "offline"
        ? { label: "Backend offline", dot: "bg-critical", pulse: false }
        : running
          ? { label: "Running", dot: "bg-accent", pulse: true }
          : { label: "Ready", dot: "bg-success", pulse: false };

  return (
    <header className="flex h-12 shrink-0 items-center gap-2 border-b border-line bg-panel px-2 sm:px-3">
      {set && (
        <IconButton label={state.railOpen ? "Hide scenes" : "Show scenes"} pressed={state.railOpen} onClick={() => dispatch({ type: "rail/toggle" })}>
          <PanelLeft />
        </IconButton>
      )}
      <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-1.5 overflow-hidden text-sm">
        <span className="flex shrink-0 items-center gap-2 font-semibold text-fg">
          <Logo />
          SatQuery
        </span>
        {set && (
          <span className="hidden min-w-0 items-center gap-1.5 md:flex">
            <ChevronRight className="size-3.5 shrink-0 text-fg-faint" />
            <span className="text-fg-muted">Workspace</span>
            <ChevronRight className="size-3.5 shrink-0 text-fg-faint" />
            <span className="truncate text-fg-muted" title={set.title}>
              {set.title}
            </span>
          </span>
        )}
        {analysisIndex > 0 && (
          <>
            <ChevronRight className="size-3.5 shrink-0 text-fg-faint" />
            <span aria-current="page" className="shrink-0 whitespace-nowrap text-fg">
              Analysis {analysisIndex}
            </span>
          </>
        )}
      </nav>

      <div className="ml-auto flex shrink-0 items-center gap-2 sm:gap-3">
        {state.health.modelMode === "mock" && (
          <Tip content="The backend is running with mock models: answers, boxes and change masks are placeholders. Measurements are still computed from the pixels.">
            <span tabIndex={0}>
              <Tag tone="warning">
                <FlaskConical className="size-3" />
                <span className="hidden sm:inline">{MODEL_MODE_LABEL.mock}</span>
                <span className="sm:hidden">Mock</span>
              </Tag>
            </span>
          </Tip>
        )}
        {(state.health.modelMode === "modal" || state.health.modelMode === "hf") && (
          <Tag tone="neutral" className="hidden md:inline-flex">
            {MODEL_MODE_LABEL[state.health.modelMode]}
          </Tag>
        )}
        <span role="status" className="flex items-center gap-2 text-sm text-fg-muted">
          <span className={cn("size-2 rounded-full", status.dot, status.pulse && "animate-pulse-dot")} />
          <span className="hidden sm:inline">{status.label}</span>
        </span>
        <Button size="sm" onClick={report.run} disabled={!canExport || report.state === "preparing"} title={canExport ? undefined : "Available once an analysis completes"}>
          {report.state === "preparing" ? <Loader2 className="animate-spin" /> : report.state === "done" ? <Check /> : <Download />}
          <span className="hidden md:inline">{report.state === "preparing" ? "Preparing report…" : report.state === "done" ? "Downloaded" : "Export report"}</span>
        </Button>
      </div>
    </header>
  );
}

/** A minimal mark: a scene frame with a corner bracket — the product's own evidence grammar. */
function Logo() {
  return (
    <svg viewBox="0 0 20 20" className="size-5" aria-hidden="true">
      <rect x="2.5" y="2.5" width="15" height="15" rx="2.5" fill="none" stroke="var(--color-line-strong)" strokeWidth="1.5" />
      <path d="M7 11V7h4M13 9v4H9" fill="none" stroke="var(--color-fg)" strokeWidth="1.75" strokeLinecap="square" />
    </svg>
  );
}
