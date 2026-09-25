"use client";

import { Loader2, Upload } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { Sample, SceneSetKind } from "@/lib/types";
import { cn } from "@/lib/utils";
import { SCENE_SET } from "@/lib/vocabulary";
import { Tip } from "@/components/ui/primitives";
import { useActions } from "./effects";
import { useDispatch, useWorkspace } from "./store";

export const ACCEPT = ".tif,.tiff,.png,.jpg,.jpeg";

/** F0 — the first screen is the tool: three scene-set drop zones and one-click samples. */
export function EmptyState() {
  const state = useWorkspace();
  return (
    <div className="h-full overflow-y-auto scrollbar-thin">
      <div className="mx-auto flex min-h-full w-full max-w-3xl flex-col justify-center px-4 py-10 sm:px-8">
        <h1 className="text-2xl font-semibold tracking-tight text-fg">Ask questions about satellite images.</h1>
        <p className="mt-1 text-lg text-fg-muted">Upload a GeoTIFF, or try a sample.</p>

        <div className="mt-8 grid gap-3 sm:grid-cols-3">
          {(Object.keys(SCENE_SET) as SceneSetKind[]).map((k) => (
            <DropTile key={k} kind={k} />
          ))}
        </div>

        <Samples offline={state.health.state === "offline"} />

        <p className="mt-10 text-xs leading-relaxed text-fg-faint">
          GeoTIFF up to 500 MB
          {state.health.maxMegapixels != null &&
            ` and ${state.health.maxMegapixels} megapixels per scene (about ${Math.floor(Math.sqrt(state.health.maxMegapixels * 1e6)).toLocaleString()} × ${Math.floor(Math.sqrt(state.health.maxMegapixels * 1e6)).toLocaleString()} px; crop larger scenes to the area of interest)`}
          . PNG and JPEG are accepted only for benchmark images, because they carry no georeferencing.
          Files stay on the SatQuery backend you&apos;re connected to.
        </p>
      </div>
    </div>
  );
}

function Schematic({ kind }: { kind: SceneSetKind }) {
  const box = "h-10 w-10 rounded-[4px] border";
  if (kind === "single") return <span className={cn(box, "border-fg-faint bg-raised")} />;
  if (kind === "bitemporal")
    return (
      <span className="flex items-center gap-1.5">
        <span className={cn(box, "grid place-items-center border-fg-faint bg-raised font-mono text-[10px] text-fg-muted")}>T1</span>
        <span className={cn(box, "grid place-items-center border-fg-faint bg-raised font-mono text-[10px] text-fg-muted")}>T2</span>
      </span>
    );
  return (
    <span className="flex items-center gap-1.5">
      <span className={cn(box, "grid place-items-center border-optical/60 bg-optical/5 text-[10px] text-optical")}>OPT</span>
      <span className={cn(box, "grid place-items-center border-sar/60 bg-sar/5 text-[10px] text-sar")}>SAR</span>
    </span>
  );
}

function DropTile({ kind }: { kind: SceneSetKind }) {
  const dispatch = useDispatch();
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const meta = SCENE_SET[kind];
  const open = (files?: File[]) => dispatch({ type: "composer/open", kind, files });

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        e.stopPropagation();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        e.stopPropagation();
        setOver(false);
        const files = [...e.dataTransfer.files];
        if (files.length) open(files);
      }}
    >
      <button
        onClick={() => input.current?.click()}
        className={cn(
          "group flex h-full w-full flex-col items-start gap-4 rounded-lg border border-dashed p-4 text-left transition-colors",
          over ? "border-accent bg-accent/10" : "border-line-strong bg-panel hover:border-fg-faint hover:bg-raised",
        )}
      >
        <Schematic kind={kind} />
        <span className="flex flex-col gap-0.5">
          <span className="text-base font-medium text-fg">{meta.label}</span>
          <span className="text-sm text-fg-muted">{meta.teach}</span>
        </span>
        <span className="mt-auto flex items-center gap-1.5 text-sm text-fg-faint group-hover:text-fg-muted">
          <Upload className="size-4" /> Drop {meta.roles.length > 1 ? "2 files" : "a file"} or browse
        </span>
      </button>
      <input
        ref={input}
        type="file"
        hidden
        multiple={meta.roles.length > 1}
        accept={ACCEPT}
        onChange={(e) => {
          const files = [...(e.target.files ?? [])];
          e.target.value = "";
          if (files.length) open(files);
        }}
      />
    </div>
  );
}

export function Samples({ offline }: { offline: boolean }) {
  const { loadSample } = useActions();
  const dispatch = useDispatch();
  const [samples, setSamples] = useState<Sample[] | null>(null);
  const [loading, setLoading] = useState<string | null>(null);

  useEffect(() => {
    if (offline) return;
    api.samples().then(setSamples).catch(() => setSamples([]));
  }, [offline]);

  if (offline)
    return (
      <p className="mt-6 rounded-md border border-critical/30 bg-critical/5 px-3 py-2 text-sm text-fg-muted">
        The SatQuery backend isn&apos;t reachable. Start it with{" "}
        <code className="font-mono text-xs text-fg">uvicorn app.main:app --port 8000</code> in <code className="font-mono text-xs text-fg">backend/</code>.
      </p>
    );

  return (
    <div className="mt-6 flex flex-wrap items-center gap-2 text-sm">
      <span className="text-fg-muted">Try a sample:</span>
      {samples === null && <span className="text-fg-faint">loading…</span>}
      {samples?.length === 0 && (
        <span className="text-fg-faint">
          none on this backend — run <code className="font-mono text-xs">scripts/fetch_samples.py</code>
        </span>
      )}
      {samples?.map((s) => (
        <Tip key={s.id} content={`${s.description} Source: ${s.source}. ${s.license}.`}>
          <button
            disabled={!!loading}
            onClick={async () => {
              setLoading(s.id);
              try {
                await loadSample(s.id);
              } catch (e) {
                dispatch({ type: "toast", tone: "critical", message: `Couldn't load the sample: ${e instanceof ApiError ? e.message : "unknown error"}` });
              } finally {
                setLoading(null);
              }
            }}
            className="flex h-8 items-center gap-1.5 rounded-full border border-line-strong px-3 text-fg transition-colors hover:border-accent hover:bg-accent/10 disabled:opacity-60"
          >
            {loading === s.id && <Loader2 className="size-3.5 animate-spin" />}
            {s.title}
          </button>
        </Tip>
      ))}
    </div>
  );
}
