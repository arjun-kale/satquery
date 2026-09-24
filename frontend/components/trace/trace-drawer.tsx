"use client";

import { Tabs } from "@base-ui/react/tabs";
import { Check, ChevronRight, Copy, Download, X } from "lucide-react";
import { useMemo, useState } from "react";
import { deriveEvidence, deriveTimeline, runPhase } from "@/lib/analysis";
import { CONFIDENCE_BANDS, CONFIDENCE_METHOD, DASH } from "@/lib/confidence";
import { formatSeconds } from "@/lib/geo";
import { cn } from "@/lib/utils";
import { TASK } from "@/lib/vocabulary";
import { Button, IconButton, StatusIcon, Tag } from "@/components/ui/primitives";
import { LayerList } from "@/components/viewer/layer-list";
import { activeAnalysis, activeSceneSet, analysesFor, useDispatch, useWorkspace, type Analysis } from "@/components/workspace/store";
import type { ExecutionStep, OrchestratorTrace } from "@/lib/types";

export function traceDocument(a: Analysis) {
  return {
    schema_version: a.schemaVersion,
    job_id: a.jobId,
    status: a.status,
    failure_reason: a.failureReason,
    trace: a.trace,
  };
}

export function TraceDrawer() {
  const state = useWorkspace();
  const dispatch = useDispatch();
  const set = activeSceneSet(state);
  const analysis = activeAnalysis(state);
  if (!state.trace.open || !set) return null;
  const n = analysis ? analysesFor(state, set.id).findIndex((a) => a.localId === analysis.localId) + 1 : 0;

  return (
    <aside
      aria-label="Trace"
      className="absolute inset-y-0 right-0 z-30 flex w-full max-w-[560px] flex-col border-l border-line-strong bg-panel shadow-2xl shadow-black/60 animate-fade-up"
    >
      <header className="flex items-start gap-3 border-b border-line px-4 py-3">
        <div className="min-w-0">
          <h2 className="text-base font-medium text-fg">Trace{n ? ` · Analysis ${n}` : ""}</h2>
          {analysis && <p className="truncate text-sm text-fg-muted">“{analysis.question}”</p>}
        </div>
        <IconButton label="Close trace" shortcut="T" className="ml-auto" onClick={() => dispatch({ type: "trace/close" })}>
          <X />
        </IconButton>
      </header>

      {!analysis ? (
        <p className="p-4 text-sm text-fg-muted">Ask a question to produce a trace.</p>
      ) : (
        <Tabs.Root value={state.trace.tab} onValueChange={(v) => dispatch({ type: "trace/tab", tab: v as "steps" | "layers" | "json" })} className="flex min-h-0 flex-1 flex-col">
          <Tabs.List className="relative flex gap-1 border-b border-line px-3">
            {(["steps", "layers", "json"] as const).map((t) => (
              <Tabs.Tab
                key={t}
                value={t}
                className="h-10 px-2.5 text-sm text-fg-muted capitalize transition-colors hover:text-fg data-[selected]:text-fg"
              >
                {t === "json" ? "JSON" : t}
              </Tabs.Tab>
            ))}
            <Tabs.Indicator className="absolute bottom-0 left-0 h-0.5 w-(--active-tab-width) translate-x-(--active-tab-left) bg-accent transition-all duration-(--duration-base)" />
          </Tabs.List>
          <Tabs.Panel value="steps" className="min-h-0 flex-1 overflow-y-auto p-4 scrollbar-thin">
            <StepsTab analysis={analysis} />
          </Tabs.Panel>
          <Tabs.Panel value="layers" className="min-h-0 flex-1 overflow-y-auto p-4 scrollbar-thin">
            <LayerList set={set} trace={analysis.trace} evidence={deriveEvidence(analysis.trace)} />
          </Tabs.Panel>
          <Tabs.Panel value="json" className="flex min-h-0 flex-1 flex-col">
            <JsonTab analysis={analysis} />
          </Tabs.Panel>
        </Tabs.Root>
      )}
    </aside>
  );
}

/* ------------------------------------------------------------------ Steps */

function StepsTab({ analysis }: { analysis: Analysis }) {
  const t = analysis.trace;
  if (!t) return <p className="text-sm text-fg-muted">Waiting for the backend to record the run…</p>;
  const rows = deriveTimeline(t, runPhase(analysis.status, t) === "stopped");
  return (
    <div className="flex flex-col gap-5">
      <Routing t={t} />
      <section className="flex flex-col gap-2">
        <h3 className="text-xs font-medium tracking-wide text-fg-faint uppercase">Steps · model mode {t.model_mode ?? "unknown"}</h3>
        <ol className="flex flex-col gap-1.5">
          {rows.map((r, i) => (
            <StepDetail key={r.key} index={i} step={t.steps[i]} label={r.label} model={r.model} status={r.status} tool={r.tool} simulated={r.simulated} />
          ))}
        </ol>
        {t.total_latency_ms != null && <p className="font-mono text-xs text-fg-muted">total {formatSeconds(t.total_latency_ms)}</p>}
      </section>
      <ConfidenceMapping />
    </div>
  );
}

function Routing({ t }: { t: OrchestratorTrace }) {
  const rows: [string, string][] = [
    ["task", t.canonical_template_id ? `${t.canonical_template_id} (${TASK[t.canonical_template_id].label})` : "none"],
    [
      "chosen by",
      t.routing_mode === "scene_set_rule" ? `scene-set rule (${t.scene_set_kind})` : t.routing_mode === "user_choice" ? "the user, after the router was unsure" : "embedding similarity",
    ],
    ["similarity", `${t.similarity_score?.toFixed(3) ?? "–"} (threshold ${t.similarity_threshold.toFixed(2)})`],
    ["runner-up", t.runner_up ? `${t.runner_up.task} ${t.runner_up.score.toFixed(3)}` : "–"],
    ["router", `${t.router_version} · all-MiniLM-L6-v2 templates`],
  ];
  if (t.rejection) rows.push(["rejected", t.rejection]);
  return (
    <section className="flex flex-col gap-2">
      <h3 className="text-xs font-medium tracking-wide text-fg-faint uppercase">Routing</h3>
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 rounded-md border border-line bg-base/50 p-3 font-mono text-xs">
        {rows.map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="text-fg-faint">{k}</dt>
            <dd className="break-words text-fg">{v}</dd>
          </div>
        ))}
      </dl>
      {t.candidates.length > 0 && (
        <p className="font-mono text-[11px] text-fg-faint">
          candidates: {t.candidates.map((c) => `${c.task} ${c.score.toFixed(2)}`).join(" · ")}
        </p>
      )}
    </section>
  );
}

function StepDetail({
  index,
  step,
  label,
  model,
  status,
  tool,
  simulated,
}: {
  index: number;
  step: ExecutionStep | undefined;
  label: string;
  model: string | null;
  status: string;
  tool: string;
  simulated: boolean;
}) {
  const [open, setOpen] = useState(status === "failed");
  const icon = status === "done" ? (simulated ? "warn" : "pass") : status === "failed" ? "fail" : status === "active" ? "active" : status === "skipped" ? "skipped" : "pending";
  return (
    <li className="rounded-md border border-line">
      <button onClick={() => setOpen((o) => !o)} aria-expanded={open} disabled={!step} className="flex w-full items-center gap-2 px-3 py-2 text-left disabled:cursor-default">
        <ChevronRight className={cn("size-3.5 shrink-0 text-fg-faint transition-transform", open && "rotate-90", !step && "opacity-0")} />
        <StatusIcon status={icon} />
        <span className="font-mono text-xs text-fg-faint">{index + 1}</span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm text-fg">{label}</span>
          <span className="block truncate font-mono text-[11px] text-fg-faint">{[tool, model].filter(Boolean).join(" · ")}</span>
        </span>
        {simulated && <Tag tone="warning">placeholder</Tag>}
        <span className="font-mono text-xs text-fg-muted tabular">{formatSeconds(step?.latency_ms)}</span>
      </button>
      {open && step && (
        <div className="flex flex-col gap-2 border-t border-line px-3 py-2">
          {step.error && <Block title="Error" tone="critical" value={step.error} />}
          <Block title="Output" value={step.outputs} />
          <Block title="Input — run context passed to this step" value={step.inputs} />
          <p className="font-mono text-[11px] text-fg-faint">
            {step.start_time} → {step.end_time ?? "running"}
          </p>
        </div>
      )}
    </li>
  );
}

function Block({ title, value, tone }: { title: string; value: unknown; tone?: "critical" }) {
  const text = useMemo(() => (typeof value === "string" ? value : JSON.stringify(value, compact, 2)), [value]);
  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs text-fg-faint">{title}</span>
      <pre className={cn("max-h-64 overflow-auto rounded-sm bg-base p-2 font-mono text-[11px] leading-relaxed whitespace-pre-wrap break-words scrollbar-thin", tone === "critical" ? "text-critical" : "text-fg-muted")}>
        {text}
      </pre>
    </div>
  );
}

/** Long coordinate arrays are summarised here; the JSON tab always has the full, untouched trace. */
function compact(_key: string, value: unknown) {
  if (Array.isArray(value) && value.length > 6 && value.every((v) => Array.isArray(v) || typeof v === "number")) {
    return [...value.slice(0, 3), `… ${value.length - 3} more (full values in the JSON tab)`];
  }
  return value;
}

function ConfidenceMapping() {
  return (
    <section className="flex flex-col gap-2">
      <h3 className="text-xs font-medium tracking-wide text-fg-faint uppercase">How confidence is worded</h3>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-fg-faint">
            <th className="py-1 font-normal">Value</th>
            <th className="py-1 font-normal">Words</th>
            <th className="py-1 font-normal">Line on the image</th>
          </tr>
        </thead>
        <tbody>
          {CONFIDENCE_BANDS.map((b, i) => (
            <tr key={b.word} className="border-t border-line">
              <td className="py-1.5 font-mono text-xs text-fg-muted">
                {i === 0 ? `≥ ${b.min.toFixed(2)}` : `${b.min.toFixed(2)} – ${CONFIDENCE_BANDS[i - 1].min.toFixed(2)}`}
              </td>
              <td className="py-1.5 text-fg">{b.word}</td>
              <td className="py-1.5">
                <svg width="56" height="8" aria-label={b.line}>
                  <line x1="0" y1="4" x2="56" y2="4" stroke="var(--color-fg)" strokeWidth="2" strokeDasharray={DASH[b.line]} />
                </svg>
              </td>
            </tr>
          ))}
          <tr className="border-t border-line">
            <td className="py-1.5 font-mono text-xs text-fg-muted">none</td>
            <td className="py-1.5 text-fg">Confidence not available</td>
            <td className="py-1.5">
              <svg width="56" height="8" aria-label="dash-dot">
                <line x1="0" y1="4" x2="56" y2="4" stroke="var(--color-fg)" strokeWidth="2" strokeDasharray={DASH.dashdot} />
              </svg>
            </td>
          </tr>
        </tbody>
      </table>
      <p className="text-xs text-fg-muted">{CONFIDENCE_METHOD} Rule outlines (index thresholds) are measurements and are always drawn solid.</p>
    </section>
  );
}

/* ------------------------------------------------------------------ JSON */

function JsonTab({ analysis }: { analysis: Analysis }) {
  const doc = useMemo(() => JSON.stringify(traceDocument(analysis), null, 2), [analysis]);
  const [copied, setCopied] = useState(false);
  const download = () => {
    const url = URL.createObjectURL(new Blob([doc], { type: "application/json" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `satquery-trace-${analysis.jobId}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };
  return (
    <>
      <div className="flex items-center gap-2 border-b border-line px-4 py-2">
        <Tag mono>schema {analysis.schemaVersion ?? "unversioned"}</Tag>
        <span className="truncate font-mono text-[11px] text-fg-faint">{analysis.jobId}</span>
        <span className="ml-auto flex gap-1.5">
          <Button
            size="sm"
            onClick={async () => {
              try {
                await navigator.clipboard.writeText(doc);
                setCopied(true);
                setTimeout(() => setCopied(false), 1500);
              } catch {
                /* clipboard blocked; download still works */
              }
            }}
          >
            {copied ? <Check /> : <Copy />} {copied ? "Copied" : "Copy"}
          </Button>
          <Button size="sm" onClick={download}>
            <Download /> Download
          </Button>
        </span>
      </div>
      <pre className="min-h-0 flex-1 overflow-auto p-4 font-mono text-[11px] leading-relaxed text-fg-muted scrollbar-thin">{doc}</pre>
    </>
  );
}
