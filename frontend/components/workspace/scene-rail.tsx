"use client";

import { ChevronDown, Plus } from "lucide-react";
import { useState } from "react";
import { isActivePhase, runPhase } from "@/lib/analysis";
import { previewUrl } from "@/lib/api";
import { formatDate } from "@/lib/geo";
import { cn } from "@/lib/utils";
import { MODALITY_LABEL, ROLE, SCENE_SET } from "@/lib/vocabulary";
import { Button, SectionLabel, StatusIcon, Tag } from "@/components/ui/primitives";
import { activeSceneSet, useDispatch, useWorkspace, type Analysis, type Scene } from "./store";

export function SceneRail() {
  const state = useWorkspace();
  const dispatch = useDispatch();
  const set = activeSceneSet(state);
  const checks = set?.validation?.checks ?? [];
  const [checksOpen, setChecksOpen] = useState(false);

  return (
    <nav aria-label="Scenes and history" className="flex h-full min-h-0 flex-col bg-panel">
      <div className="min-h-0 flex-1 overflow-y-auto p-3 scrollbar-thin">
        {set && (
          <section className="flex flex-col gap-2">
            <SectionLabel>Scene set</SectionLabel>
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-fg">{SCENE_SET[set.kind].label}</span>
              {checks.length > 0 && (
                <button
                  onClick={() => setChecksOpen((o) => !o)}
                  aria-expanded={checksOpen}
                  className="ml-auto flex items-center gap-1 rounded-sm text-xs text-fg-muted hover:text-fg"
                >
                  <StatusIcon status={checks.some((c) => c.status === "warn") ? "warn" : "pass"} className="size-3.5" />
                  {checks.length} checks
                  <ChevronDown className={cn("size-3.5 transition-transform", checksOpen && "rotate-180")} />
                </button>
              )}
            </div>
            {checksOpen && (
              <ul className="flex flex-col gap-1 rounded-sm border border-line bg-base/60 p-2">
                {checks.map((c) => (
                  <li key={c.id} className="flex items-center gap-2 text-xs">
                    <StatusIcon status={c.status} className="size-3.5" />
                    <span className="text-fg-muted">{c.label}</span>
                    <span className="ml-auto truncate font-mono text-[11px] text-fg tabular" title={c.reason ?? undefined}>
                      {c.value}
                    </span>
                  </li>
                ))}
              </ul>
            )}
            <ul className="flex flex-col gap-2">
              {set.scenes.map((s) => (
                <SceneCard key={s.imageId} scene={s} />
              ))}
            </ul>
          </section>
        )}

        <Button size="sm" className="mt-3 w-full" onClick={() => dispatch({ type: "composer/open", kind: null })}>
          <Plus /> Add scenes
        </Button>

        <History />
      </div>
    </nav>
  );
}

/** Metadata is one click (or focus + Enter) away — sensor, CRS, GSD and bands for the Verifier. */
function SceneCard({ scene }: { scene: Scene }) {
  const [open, setOpen] = useState(false);
  const m = scene.metadata;
  const tone = m.modality === "sar" ? "sar" : m.modality === "optical" ? "optical" : "neutral";
  const sensor = m.sensor_tags.sensor ?? m.sensor_tags.SENSOR ?? m.sensor_tags.satellite;
  return (
    <li className="overflow-hidden rounded-md border border-line bg-base/40">
      <button onClick={() => setOpen((o) => !o)} aria-expanded={open} className="flex w-full items-center gap-2.5 p-2 text-left hover:bg-hover">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={previewUrl(scene.imageId)} alt="" crossOrigin="anonymous" className="size-11 shrink-0 rounded-[4px] border border-line object-cover" />
        <span className="flex min-w-0 flex-col gap-1">
          <span className="flex items-center gap-1.5">
            <Tag tone={tone}>{ROLE[scene.role].label}</Tag>
            <span className="font-mono text-xs text-fg tabular">{formatDate(m.acquired_at) ?? "date unknown"}</span>
          </span>
          <span className="truncate text-xs text-fg-muted">{m.filename}</span>
        </span>
        <ChevronDown className={cn("ml-auto size-3.5 shrink-0 text-fg-faint transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 border-t border-line px-2.5 py-2 font-mono text-[11px]">
          <Meta k="sensor" v={sensor ?? "not declared"} />
          <Meta k="type" v={MODALITY_LABEL[m.modality]} />
          <Meta k="crs" v={m.crs ?? "none"} />
          <Meta k="gsd" v={m.gsd_m ? `${m.gsd_m} m` : "unknown"} />
          <Meta k="bands" v={`${m.band_count} · ${m.dtype}`} />
          {m.sensor_tags.bands && <Meta k="names" v={m.sensor_tags.bands} />}
          <Meta k="size" v={`${m.width} × ${m.height} px`} />
          {m.sensor_tags.polarisation && <Meta k="pol" v={m.sensor_tags.polarisation} />}
          <Meta k="sha256" v={`${m.checksum_sha256.slice(0, 12)}…`} />
        </dl>
      )}
    </li>
  );
}

function Meta({ k, v }: { k: string; v: string }) {
  return (
    <>
      <dt className="text-fg-faint">{k}</dt>
      <dd className="truncate text-fg-muted" title={v}>
        {v}
      </dd>
    </>
  );
}

function History() {
  const state = useWorkspace();
  const dispatch = useDispatch();
  const items = [...state.analyses].reverse();
  if (!items.length) return null;

  const open = (a: Analysis) => {
    if (a.sceneSetId !== state.activeSceneSetId) dispatch({ type: "sceneSet/activate", id: a.sceneSetId });
    dispatch({ type: "analysis/activate", localId: a.localId });
  };

  return (
    <section className="mt-6 flex flex-col gap-1.5">
      <SectionLabel>History</SectionLabel>
      <ul className="flex flex-col">
        {items.map((a) => {
          const phase = runPhase(a.status, a.trace);
          const set = state.sceneSets[a.sceneSetId];
          const active = a.localId === state.activeAnalysisId;
          return (
            <li key={a.localId}>
              <button
                onClick={() => open(a)}
                aria-current={active ? "true" : undefined}
                className={cn(
                  "flex w-full items-start gap-2 rounded-sm px-2 py-1.5 text-left transition-colors",
                  active ? "bg-hover text-fg" : "text-fg-muted hover:bg-hover hover:text-fg",
                )}
              >
                <StatusIcon
                  className="mt-0.5 size-3.5"
                  status={isActivePhase(phase) ? "active" : phase === "completed" ? "pass" : phase === "failed" ? "fail" : "warn"}
                />
                <span className="flex min-w-0 flex-col">
                  <span className="line-clamp-2 text-sm">{a.question}</span>
                  {set && a.sceneSetId !== state.activeSceneSetId && <span className="truncate text-xs text-fg-faint">{set.title}</span>}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
