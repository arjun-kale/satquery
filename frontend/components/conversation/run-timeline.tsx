"use client";

import { ChevronRight, Loader2, Square, WifiOff } from "lucide-react";
import { useState } from "react";
import { deriveTimeline, expertCount, isActivePhase, runPhase, type TimelineRow } from "@/lib/analysis";
import { formatSeconds } from "@/lib/geo";
import { cn } from "@/lib/utils";
import { SCENE_SET, TASK } from "@/lib/vocabulary";
import { Button, StatusIcon, Tag } from "@/components/ui/primitives";
import type { Analysis, SceneSet } from "@/components/workspace/store";
import { useNow } from "./use-now";

/** A step that sits on a GPU call this long may be waiting for a cold worker. */
const COLD_START_HINT_MS = 15_000;
const SLOW_RUN_MS = 120_000;

/*
 * "See the agent work" (UX brief §F3). Every row is a real backend record:
 *   row 1 — the scene-set validation the user already passed,
 *   row 2 — the router's recorded decision (task, score, runner-up),
 *   rows 3+ — the router's planned DAG, resolving as the executor writes each step.
 * Timers are real elapsed time. There is no percentage bar because the backend reports none.
 */
export function RunTimeline({ analysis, set, onStop }: { analysis: Analysis; set: SceneSet; onStop: () => void }) {
  const trace = analysis.trace;
  const phase = runPhase(analysis.status, trace);
  const active = isActivePhase(phase);
  const now = useNow(active);
  const rows = deriveTimeline(trace, phase === "stopped");
  const hasProblem = rows.some((r) => r.status === "failed" || r.simulated) || phase === "stopped" || phase === "rejected";
  const [open, setOpen] = useState<boolean | null>(null);
  const expanded = open ?? (active || hasProblem);

  const elapsed = trace?.total_latency_ms ?? (active ? now - analysis.createdAt : null);
  const experts = expertCount(trace, trace?.model_mode ?? null);
  const [slowDismissed, setSlowDismissed] = useState(false);

  if (!expanded) {
    return (
      <button
        onClick={() => setOpen(true)}
        aria-expanded={false}
        className="flex w-full items-center gap-2 rounded-sm py-1 text-left text-sm text-fg-muted transition-colors hover:text-fg"
      >
        <ChevronRight className="size-4" />
        <span>
          Run · {trace?.steps.length ?? 0} steps · {experts} expert{experts === 1 ? "" : "s"}
        </span>
        <span className="font-mono text-xs tabular">{formatSeconds(elapsed)}</span>
      </button>
    );
  }

  const checks = set.validation?.checks ?? [];
  const passed = checks.filter((c) => c.status === "pass").length;
  const warn = checks.filter((c) => c.status === "warn").length;

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <button
          onClick={() => setOpen(false)}
          disabled={active}
          aria-expanded
          className="flex items-center gap-2 text-sm font-medium text-fg disabled:cursor-default"
        >
          {!active && <ChevronRight className="size-4 rotate-90 text-fg-muted" />}
          {active ? (
            <span className="flex items-center gap-2">
              <span className="size-1.5 rounded-full bg-accent animate-pulse-dot" />
              {analysis.stopRequested ? "Stopping after the current step…" : "Running"}
            </span>
          ) : phase === "stopped" ? (
            "Stopped by you"
          ) : phase === "failed" ? (
            "Run failed"
          ) : phase === "rejected" ? (
            "Run not started"
          ) : (
            "Run"
          )}
          <span className="font-mono text-xs font-normal text-fg-muted tabular">{formatSeconds(elapsed)}</span>
        </button>
        {active && analysis.jobId && (
          <Button size="sm" variant="danger" className="ml-auto" onClick={onStop} disabled={analysis.stopRequested} title="Stops before the next step; a step already running finishes first">
            {analysis.stopRequested ? <Loader2 className="animate-spin" /> : <Square className="fill-current" />}
            {analysis.stopRequested ? "Stopping after current step…" : "Stop"}
          </Button>
        )}
      </div>

      {analysis.connection === "lost" && (
        <p role="status" className="flex items-center gap-2 text-sm text-warning">
          <WifiOff className="size-4" /> Connection lost — reconnecting. The run continues on the server.
        </p>
      )}

      <ol className="flex flex-col" aria-label="Run steps">
        <Row
          status="done"
          label="Checked your images"
          detail={`${passed} checks passed${warn ? ` · ${warn} warning${warn > 1 ? "s" : ""}` : ""}`}
          mono={`scene set · ${SCENE_SET[set.kind].label.toLowerCase()}`}
        />
        <RoutingRow analysis={analysis} active={active} />
        {rows.map((r) => (
          <StepRow key={r.key} row={r} now={now} coldStartPossible={trace?.model_mode === "modal"} />
        ))}
      </ol>

      {active && elapsed != null && elapsed > SLOW_RUN_MS && !slowDismissed && (
        <div role="status" className="flex flex-wrap items-center gap-2 rounded-sm border border-warning/30 bg-warning/10 px-3 py-2 text-sm text-warning">
          Taking longer than expected. It is still running.
          <span className="ml-auto flex gap-2">
            <Button size="sm" variant="ghost" onClick={() => setSlowDismissed(true)}>
              Keep waiting
            </Button>
            <Button size="sm" variant="danger" onClick={onStop}>
              Stop
            </Button>
          </span>
        </div>
      )}
    </div>
  );
}

function RoutingRow({ analysis, active }: { analysis: Analysis; active: boolean }) {
  const t = analysis.trace;
  if (!t) {
    return <Row status={active ? "active" : "pending"} label="Understanding the question" detail={analysis.status === "SUBMITTING" ? "Sending your question" : undefined} />;
  }
  const task = t.canonical_template_id ? TASK[t.canonical_template_id].label : null;
  const score = t.similarity_score != null ? t.similarity_score.toFixed(2) : "–";
  if (t.rejection) {
    return (
      <Row
        status="warn"
        label="Understood the question"
        detail={t.rejection === "needs_pair" ? `${task} — needs two scenes` : "Not sure what kind of question this is"}
        mono={`best match ${score} · threshold ${t.similarity_threshold.toFixed(2)}`}
      />
    );
  }
  const how =
    t.routing_mode === "scene_set_rule"
      ? `chosen by the scene set · question similarity ${score}`
      : t.routing_mode === "user_choice"
        ? `chosen by you · similarity ${score}`
        : `similarity ${score}`;
  return (
    <Row
      status="pass"
      label="Understood the question"
      detail={task ?? undefined}
      mono={`${how}${t.runner_up ? ` · runner-up: ${TASK[t.runner_up.task].label} ${t.runner_up.score.toFixed(2)}` : ""}`}
    />
  );
}

function StepRow({ row, now, coldStartPossible }: { row: TimelineRow; now: number; coldStartPossible: boolean }) {
  const liveMs = row.status === "active" && row.startedAt ? Math.max(0, now - Date.parse(row.startedAt)) : null;
  const ms = row.ms ?? liveMs;
  const status = row.status === "done" ? (row.simulated ? "warn" : "pass") : row.status === "failed" ? "fail" : row.status === "active" ? "active" : row.status === "skipped" ? "skipped" : "pending";
  return (
    <Row
      status={status}
      label={row.label}
      shimmer={row.status === "active"}
      detail={row.simulated ? "Placeholder step — no computation ran" : row.reason ?? row.detail ?? undefined}
      mono={[row.model, row.tool].filter(Boolean).join(" · ")}
      time={ms != null ? formatSeconds(ms) : undefined}
      error={row.error}
      faint={row.status === "pending" || row.status === "skipped"}
      note={
        row.status === "active" && row.model && coldStartPossible && liveMs != null && liveMs > COLD_START_HINT_MS
          ? "The GPU worker may be starting — a first run can take a minute or two."
          : undefined
      }
    />
  );
}

function Row({
  status,
  label,
  detail,
  mono,
  time,
  error,
  shimmer,
  faint,
  note,
}: {
  status: "pass" | "warn" | "fail" | "active" | "pending" | "skipped" | "done";
  label: string;
  detail?: string;
  mono?: string;
  time?: string;
  error?: string | null;
  shimmer?: boolean;
  faint?: boolean;
  note?: string;
}) {
  return (
    <li className="relative flex gap-2.5 py-1.5 pl-0.5 animate-fade-up">
      <span className="mt-0.5">
        <StatusIcon status={status === "done" ? "pass" : status} />
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <div className="flex items-baseline gap-2">
          <span className={cn("min-w-0 flex-1 text-sm", faint ? "text-fg-faint" : "text-fg", shimmer && "shimmer-text")}>{label}</span>
          {time && <span className="shrink-0 font-mono text-xs text-fg-muted tabular">{time}</span>}
        </div>
        {(detail || mono) && (
          <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
            {detail && <span className={cn("text-xs", status === "warn" ? "text-warning" : "text-fg-muted")}>{detail}</span>}
            {mono && <span className="min-w-0 font-mono text-[11px] break-words text-fg-faint">{mono}</span>}
          </div>
        )}
        {note && <span className="text-xs text-warning">{note}</span>}
        {error && (
          <span className="mt-1 rounded-sm border border-critical/30 bg-critical/10 px-2 py-1 font-mono text-xs break-words text-critical">
            {error}
          </span>
        )}
      </div>
    </li>
  );
}

export function RunSummaryTag({ analysis }: { analysis: Analysis }) {
  const phase = runPhase(analysis.status, analysis.trace);
  if (phase === "completed") return null;
  return <Tag tone={phase === "failed" ? "critical" : phase === "rejected" || phase === "stopped" ? "warning" : "accent"}>{phase}</Tag>;
}
