"use client";

import { Download, FileSearch, Info, RotateCcw, ScanEye, ImagePlus, Loader2, Check } from "lucide-react";
import { CIRCLED, deriveAnswer, deriveEvidence, runPhase, splitModelQuantities, type Evidence } from "@/lib/analysis";
import { CONFIDENCE_METHOD } from "@/lib/confidence";
import { formatArea } from "@/lib/geo";
import { cn } from "@/lib/utils";
import { TASK, tasksFor, toolLabel } from "@/lib/vocabulary";
import { Button, ConfidenceMeter, Tag, Tip } from "@/components/ui/primitives";
import { useDispatch, useWorkspace, type Analysis, type SceneSet } from "@/components/workspace/store";
import type { TaskType } from "@/lib/types";

interface Props {
  analysis: Analysis;
  set: SceneSet;
  isActive: boolean;
  onAsk: (q: string, task?: TaskType) => void;
  onRetry: () => void;
  onReport: () => void;
  reportState: "idle" | "preparing" | "done";
}

/** What the run produced — or, when it didn't produce an answer, exactly why and what to do next. */
export function Outcome(props: Props) {
  const { analysis } = props;
  const phase = runPhase(analysis.status, analysis.trace);
  if (analysis.submitError) return <CouldNotStart {...props} />;
  if (phase === "rejected") return analysis.trace?.rejection === "needs_pair" ? <NeedsPair {...props} /> : <RouterUnsure {...props} />;
  if (phase === "completed") return <AnswerCard {...props} />;
  if (phase === "failed" || phase === "stopped") return <Failed {...props} stopped={phase === "stopped"} />;
  // Running: evidence may already be on the image; show it as it arrives.
  const evidence = deriveEvidence(analysis.trace);
  return evidence.length ? <EvidenceChips evidence={evidence} partial /> : null;
}

/* ------------------------------------------------------------------ Answer */

function AnswerCard({ analysis, set, isActive, onAsk, onReport, reportState }: Props) {
  const dispatch = useDispatch();
  const answer = deriveAnswer(analysis.trace);
  const evidence = deriveEvidence(analysis.trace);
  const totalArea = evidence.reduce((s, e) => s + (e.areaM2 ?? 0), 0);
  const followUps = nextQuestions(analysis, set, evidence);

  return (
    <div className="flex flex-col gap-3">
      {answer.isMock && (
        <p className="flex items-start gap-2 rounded-sm border border-warning/30 bg-warning/10 px-3 py-2 text-sm text-warning">
          <Info className="mt-0.5 size-4 shrink-0" />
          The backend is in mock mode: the text and any model boxes or masks below are placeholders, not a real reading of these images. Measured numbers are still computed from the pixels.
        </p>
      )}

      {answer.lead && (
        <div className="flex flex-col gap-1">
          <p className="text-lg leading-relaxed text-fg">{answer.lead}</p>
          <span className="text-xs text-fg-faint">Measured from pixels — every number above comes from the rasters, not from a model.</span>
        </div>
      )}
      {answer.lead ? (
        answer.text && (
          <div className="flex flex-col gap-1.5 rounded-sm border border-line bg-base/50 px-3 py-2">
            <span className="text-xs font-medium tracking-wide text-fg-faint uppercase">
              Model description{answer.note ? ` · ${answer.note}` : ""}
            </span>
            <ModelText text={answer.text} fromModel size="base" />
          </div>
        )
      ) : (
        <>
          {answer.text ? (
            <ModelText text={answer.text} fromModel={!!answer.tool && answer.tool !== "cross_modal_fusion"} />
          ) : !answer.tool && answer.measured.length ? (
            <p className="text-lg text-fg">
              <span className="text-fg-muted">{answer.measured[0].label}:</span>{" "}
              <span className="font-mono tabular">{answer.measured[0].value}</span>
              <span className="ml-2 align-middle text-xs text-fg-faint">measured from pixels, no model text for this question</span>
            </p>
          ) : (
            <p className="text-lg text-fg-muted">Unable to determine an answer from these images.</p>
          )}
          {answer.note && <p className="-mt-1 text-xs text-fg-faint">{answer.text ? `Model input: ${answer.note}` : answer.note}</p>}
        </>
      )}

      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
        <ConfidenceLine answer={answer} />
        {evidence.length > 0 && (
          <span className="text-fg-muted">
            Evidence: {evidence.length} region{evidence.length > 1 ? "s" : ""}
            {totalArea > 0 && <span className="font-mono text-xs text-fg tabular"> · {formatArea(totalArea)}</span>}
          </span>
        )}
      </div>

      {evidence.length > 0 && <EvidenceChips evidence={evidence} disabled={!isActive} onActivate={() => !isActive && dispatch({ type: "analysis/activate", localId: analysis.localId })} />}

      {answer.measured.length > 0 && (
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 rounded-sm border border-line bg-base/60 px-3 py-2 text-sm">
          <dt className="col-span-2 mb-0.5 text-xs font-medium tracking-wide text-fg-faint uppercase">Measured from pixels</dt>
          {answer.measured.map((m) => (
            <div key={m.label} className="contents">
              <dt className="text-fg-muted">{m.label}</dt>
              <dd className="flex items-center gap-1.5 font-mono text-xs text-fg tabular">
                {m.value}
                <Tip content={m.method}>
                  <button aria-label={`How ${m.label} is computed`} className="text-fg-faint hover:text-fg">
                    <Info className="size-3.5" />
                  </button>
                </Tip>
              </dd>
            </div>
          ))}
        </dl>
      )}

      <div className="flex flex-wrap gap-2">
        {evidence.length > 1 && (
          <Button size="sm" onClick={() => { dispatch({ type: "analysis/activate", localId: analysis.localId }); dispatch({ type: "evidence/showAll", value: true }); }}>
            <ScanEye /> Show all evidence
          </Button>
        )}
        <Tip content="Steps, parameters, layers and the raw trace" shortcut="T">
          <Button size="sm" onClick={() => { dispatch({ type: "analysis/activate", localId: analysis.localId }); dispatch({ type: "trace/open" }); }}>
            <FileSearch /> View trace
          </Button>
        </Tip>
        <Button size="sm" onClick={() => { dispatch({ type: "analysis/activate", localId: analysis.localId }); onReport(); }} disabled={reportState === "preparing"}>
          {reportState === "preparing" ? <Loader2 className="animate-spin" /> : reportState === "done" ? <Check /> : <Download />}
          {reportState === "preparing" ? "Preparing report…" : reportState === "done" ? "Downloaded" : "Download report"}
        </Button>
      </div>

      {followUps.length > 0 && isActive && (
        <div className="flex flex-wrap items-center gap-1.5 text-sm">
          <span className="text-fg-faint">Ask next:</span>
          {followUps.map((q) => (
            <button key={q} onClick={() => onAsk(q)} className="rounded-full border border-line px-2.5 py-0.5 text-fg-muted transition-colors hover:border-line-strong hover:text-fg">
              {q}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/** Model prose, with any quantities it states marked as the model's wording rather than measurements. */
function ModelText({ text, fromModel, size = "lg" }: { text: string; fromModel: boolean; size?: "lg" | "base" }) {
  const segments = fromModel ? splitModelQuantities(text) : [{ text, quantity: false }];
  const stated = segments.some((s) => s.quantity);
  return (
    <div className="flex flex-col gap-1.5">
      <p className={cn("leading-relaxed text-fg", size === "lg" ? "text-lg" : "text-base")}>
        {segments.map((s, i) =>
          s.quantity ? (
            <Tip key={i} content="Stated by the model, not measured. Measured values are under “Measured from pixels”.">
              <span tabIndex={0} className="cursor-help rounded-[2px] text-fg-muted underline decoration-warning decoration-dotted decoration-2 underline-offset-4">
                {s.text}
              </span>
            </Tip>
          ) : (
            <span key={i}>{s.text}</span>
          ),
        )}
      </p>
      {stated && (
        <p className="flex items-start gap-1.5 text-xs text-warning">
          <Info className="mt-px size-3.5 shrink-0" />
          Underlined numbers are the model&apos;s own wording, not measurements.
        </p>
      )}
    </div>
  );
}

function ConfidenceLine({ answer }: { answer: ReturnType<typeof deriveAnswer> }) {
  const c = answer.confidence;
  // With a measured lead, the only model output rated here is the secondary description.
  const of = answer.lead && answer.text ? "Model description: " : "";
  if (!c.available) return <span className="text-fg-faint">{of}{c.reason}</span>;
  return (
    <Tip content={`${c.value.toFixed(2)} — ${CONFIDENCE_METHOD} It reflects how sure the model was of its wording, not whether the answer is true.`}>
      <span tabIndex={0} className="flex items-center gap-2 rounded-sm text-fg">
        {of && <span className="text-fg-muted">{of}</span>}
        <span className="font-medium">{c.band.word}</span>
        <ConfidenceMeter steps={c.band.steps} />
      </span>
    </Tip>
  );
}

/** Evidence chips ①②… — hovering or focusing one puts the lens on its region, and vice versa. */
export function EvidenceChips({ evidence, partial, disabled, onActivate }: { evidence: Evidence[]; partial?: boolean; disabled?: boolean; onActivate?: () => void }) {
  const state = useWorkspace();
  const dispatch = useDispatch();
  const lit = state.evidence.hovered ?? state.evidence.focused;
  return (
    <div className="flex flex-col gap-1.5">
      {partial && <span className="text-xs text-fg-faint">Evidence so far (the run is still going)</span>}
      <ul className="flex flex-wrap gap-1.5" aria-label="Evidence">
        {evidence.map((e) => {
          const on = !disabled && lit === e.n;
          const pressed = !disabled && state.evidence.focused === e.n;
          return (
            <li key={e.n}>
              <Tip content={`${e.honesty}${e.confidence.available ? ` · ${e.confidence.band.word}` : ""}`} shortcut={String(e.n)}>
                <button
                  aria-pressed={pressed}
                  onPointerEnter={() => !disabled && dispatch({ type: "evidence/hover", n: e.n })}
                  onPointerLeave={() => !disabled && dispatch({ type: "evidence/hover", n: null })}
                  onFocus={() => !disabled && dispatch({ type: "evidence/hover", n: e.n })}
                  onBlur={() => !disabled && dispatch({ type: "evidence/hover", n: null })}
                  onClick={() => {
                    onActivate?.();
                    dispatch({ type: "evidence/focus", n: pressed ? null : e.n });
                  }}
                  className={cn(
                    "flex min-h-8 items-center gap-1.5 rounded-sm border px-2 text-sm transition-colors",
                    on
                      ? "border-evidence-active bg-evidence-active/10 text-evidence-active"
                      : "border-line text-fg hover:border-line-strong",
                  )}
                >
                  <span className={cn("font-mono", !on && (e.tone === "change" ? "text-change" : "text-evidence"))}>{CIRCLED[e.n - 1]}</span>
                  <span className="max-w-40 truncate">{e.title}</span>
                  {e.areaM2 != null && <span className="font-mono text-xs text-fg-muted tabular">{formatArea(e.areaM2)}</span>}
                  {e.confidence.available && e.confidence.band.steps <= 2 && <Tag tone="warning">Needs review</Tag>}
                </button>
              </Tip>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function nextQuestions(analysis: Analysis, set: SceneSet, evidence: Evidence[]): string[] {
  const task = analysis.trace?.canonical_template_id;
  const qs: string[] = [];
  if (set.kind === "single") {
    if (task !== "CAPTION_SCENE") qs.push("Describe this scene");
    if (task !== "SPECTRAL_WATER_VEGETATION") qs.push("Calculate the water index for this region");
    if (task === "SPECTRAL_WATER_VEGETATION") qs.push("Analyze the vegetation health");
  }
  if (set.kind === "bitemporal" && evidence.length) qs.push("Describe what changed between these dates");
  return qs.slice(0, 2);
}

/* ------------------------------------------------------------------ Not an answer */

function RouterUnsure({ analysis, set, onAsk }: Props) {
  const allowed = tasksFor(set.kind, set.scenes[0].metadata.modality);
  const candidates = (analysis.trace?.candidates ?? []).filter((c) => allowed.includes(c.task));
  const choices: TaskType[] = candidates.length ? candidates.map((c) => c.task) : allowed;
  const scoreOf = (t: TaskType) => analysis.trace?.candidates.find((c) => c.task === t)?.score;
  return (
    <div className="flex flex-col gap-2.5 rounded-md border border-line bg-raised/50 p-3">
      <p className="text-base text-fg">I&apos;m not sure what kind of question this is.</p>
      <p className="text-sm text-fg-muted">Pick what you meant and I&apos;ll run it — or rephrase your question.</p>
      <div className="flex flex-wrap gap-2">
        {choices.slice(0, 3).map((t) => (
          <Button key={t} size="sm" onClick={() => onAsk(analysis.question, t)}>
            {TASK[t].question}
            {scoreOf(t) != null && <span className="font-mono text-[11px] text-fg-faint tabular">{scoreOf(t)!.toFixed(2)}</span>}
          </Button>
        ))}
      </div>
    </div>
  );
}

function NeedsPair({ set }: Props) {
  const dispatch = useDispatch();
  return (
    <div className="flex flex-col gap-2.5 rounded-md border border-line bg-raised/50 p-3">
      <p className="text-base text-fg">Change questions need two dates. You have one image.</p>
      <div>
        <Button size="sm" variant="primary" onClick={() => dispatch({ type: "composer/open", kind: "bitemporal", seed: { ...set.scenes[0], role: "T1" } })}>
          <ImagePlus /> Add a second date
        </Button>
      </div>
    </div>
  );
}

function Failed({ analysis, onRetry, stopped }: Props & { stopped: boolean }) {
  const failedStep = analysis.trace?.steps.find((s) => s.status === "FAILED");
  const unavailable = /unavailable|not loaded|ModelUnavailable/i.test(failedStep?.error ?? analysis.failureReason ?? "");
  const evidence = deriveEvidence(analysis.trace);
  return (
    <div className="flex flex-col gap-2.5">
      <div className={cn("flex flex-col gap-2 rounded-md border p-3", stopped ? "border-line bg-raised/50" : "border-critical/30 bg-critical/5")}>
        <p className="text-base text-fg">
          {stopped
            ? "Stopped by you. Steps that finished are kept; anything below is partial."
            : unavailable
              ? `The analysis engine isn't reachable, so “${toolLabel(failedStep?.tool_name ?? "").toLowerCase()}” couldn't run.`
              : failedStep
                ? `“${toolLabel(failedStep.tool_name)}” failed. The steps before it finished and are kept.`
                : "The run failed before it could start its steps."}
        </p>
        <div>
          <Button size="sm" onClick={onRetry}>
            <RotateCcw /> {stopped ? "Run again" : "Retry run"}
          </Button>
        </div>
      </div>
      {evidence.length > 0 && <EvidenceChips evidence={evidence} partial={false} />}
    </div>
  );
}

function CouldNotStart({ analysis, onRetry }: Props) {
  return (
    <div className="flex flex-col gap-2 rounded-md border border-critical/30 bg-critical/5 p-3">
      <p className="text-base text-fg">The analysis couldn&apos;t start: {analysis.submitError}</p>
      <p className="text-sm text-fg-muted">Your question is kept.</p>
      <div>
        <Button size="sm" onClick={onRetry}>
          <RotateCcw /> Retry
        </Button>
      </div>
    </div>
  );
}
