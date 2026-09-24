"use client";

import { deriveJobLayers, type Evidence } from "@/lib/analysis";
import { formatDate } from "@/lib/geo";
import { cn } from "@/lib/utils";
import { ROLE, toolLabel } from "@/lib/vocabulary";
import { Tag } from "@/components/ui/primitives";
import { layerVisible, useDispatch, useWorkspace, type SceneSet } from "@/components/workspace/store";
import type { OrchestratorTrace } from "@/lib/types";

export const EVIDENCE_LAYER = "evidence";

/** Every layer the viewer can show, with where it came from. Shared by the viewer and the trace drawer. */
export function LayerList({ set, trace, evidence, dense }: { set: SceneSet; trace: OrchestratorTrace | null; evidence: Evidence[]; dense?: boolean }) {
  const state = useWorkspace();
  const dispatch = useDispatch();
  const jobLayers = deriveJobLayers(trace);

  return (
    <div className={cn("flex flex-col", dense ? "gap-3" : "gap-5")}>
      <Group title="Scenes">
        {set.scenes.map((s) => (
          <Row
            key={s.imageId}
            label={
              <span className="flex items-center gap-2">
                <Tag tone={s.metadata.modality === "sar" ? "sar" : s.metadata.modality === "optical" ? "optical" : "neutral"}>{ROLE[s.role].label}</Tag>
                <span className="truncate">{formatDate(s.metadata.acquired_at) ?? s.metadata.filename}</span>
              </span>
            }
            detail={s.metadata.modality === "sar" ? "Band 1 in dB · fixed stretch −25 to 0 dB" : "Quick-look · 2–98 % stretch · first three bands"}
            provenance="uploaded"
          />
        ))}
      </Group>

      <Group title="Evidence">
        <Toggle
          id="layer-evidence"
          checked={layerVisible(state, EVIDENCE_LAYER, true)}
          onChange={(v) => dispatch({ type: "viewer/layer", id: EVIDENCE_LAYER, visible: v })}
          label="Evidence outlines"
          detail={evidence.length ? `${evidence.length} region${evidence.length > 1 ? "s" : ""} · brackets for boxes, outlines for masks` : "No evidence in this analysis yet"}
        />
        <Toggle
          id="layer-fill"
          checked={state.viewer.outlineFill}
          onChange={(v) => dispatch({ type: "viewer/outlineFill", value: v })}
          label="Fill outlines at 15 %"
          detail="Off by default so the pixels inside stay visible"
        />
      </Group>

      <Group title="Intermediate rasters">
        {jobLayers.length === 0 && <p className="text-sm text-fg-faint">This run produced no raster layers.</p>}
        {jobLayers.map((l) => (
          <Toggle
            key={l.id}
            id={`layer-${l.id}`}
            checked={layerVisible(state, l.id, false)}
            onChange={(v) => dispatch({ type: "viewer/layer", id: l.id, visible: v })}
            label={l.label}
            detail={l.legend}
            provenance={`step ${l.producedBy.index + 1} · ${toolLabel(l.producedBy.tool).toLowerCase()}`}
          />
        ))}
      </Group>
    </div>
  );
}

function Group({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-2">
      <h3 className="text-xs font-medium tracking-wide text-fg-faint uppercase">{title}</h3>
      {children}
    </section>
  );
}

function Row({ label, detail, provenance }: { label: React.ReactNode; detail?: string; provenance?: string }) {
  return (
    <div className="flex flex-col gap-0.5 text-sm">
      <div className="flex items-center justify-between gap-2">
        {label}
        {provenance && <span className="shrink-0 font-mono text-[11px] text-fg-faint">{provenance}</span>}
      </div>
      {detail && <span className="text-xs text-fg-muted">{detail}</span>}
    </div>
  );
}

function Toggle({
  id,
  checked,
  onChange,
  label,
  detail,
  provenance,
}: {
  id: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
  detail?: string;
  provenance?: string;
}) {
  return (
    <label htmlFor={id} className="flex cursor-pointer items-start gap-2.5 rounded-sm text-sm">
      <input
        id={id}
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-0.5 size-4 shrink-0 cursor-pointer accent-(--color-accent)"
      />
      <span className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="flex items-center justify-between gap-2">
          <span className="text-fg">{label}</span>
          {provenance && <span className="shrink-0 font-mono text-[11px] text-fg-faint">{provenance}</span>}
        </span>
        {detail && <span className="text-xs text-fg-muted">{detail}</span>}
      </span>
    </label>
  );
}
