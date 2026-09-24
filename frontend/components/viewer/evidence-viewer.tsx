"use client";

import { Popover } from "@base-ui/react/popover";
import { Columns2, Layers, Maximize, Pause, Play, Search, SplitSquareHorizontal, Blend as BlendIcon, Repeat, ScanEye } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { deriveEvidence, deriveJobLayers, deriveTimeline, isActivePhase, runPhase } from "@/lib/analysis";
import { previewUrl, assetUrl } from "@/lib/api";
import { formatDate, formatLonLat, pixelToLonLat, scaleBar } from "@/lib/geo";
import { cn, isTypingTarget, prefersReducedMotion } from "@/lib/utils";
import { ROLE } from "@/lib/vocabulary";
import { Button, IconButton, Kbd, Tag, Tip } from "@/components/ui/primitives";
import {
  activeAnalysis,
  activeSceneSet,
  layerVisible,
  useDispatch,
  useWorkspace,
  type Scene,
  type ViewerMode,
} from "@/components/workspace/store";
import { EvidenceLens } from "./evidence-lens";
import { EVIDENCE_LAYER, LayerList } from "./layer-list";
import { useElementSize, useNavigation, useView, type Size, type View } from "./use-view";

const FLICKER_MS = 600;
const QUICKLOOK_PX = 512; // backend preview size (app/ingestion/preview.py)
const LOUPE = { size: 168, scale: 6 };

interface Cursor {
  u: number;
  v: number;
  /** Position within the viewer area, for the loupe. */
  ax: number;
  ay: number;
  pane: 0 | 1;
}

export function EvidenceViewer() {
  const state = useWorkspace();
  const dispatch = useDispatch();
  const set = activeSceneSet(state)!;
  const analysisRaw = activeAnalysis(state);
  const analysis = analysisRaw?.sceneSetId === set.id ? analysisRaw : null;
  const trace = analysis?.trace ?? null;

  const evidence = useMemo(() => deriveEvidence(trace), [trace]);
  const jobLayers = useMemo(() => deriveJobLayers(trace), [trace]);
  const phase = analysis ? runPhase(analysis.status, trace) : null;
  const running = phase ? isActivePhase(phase) : false;
  const activeStep = running ? deriveTimeline(trace, false).find((r) => r.status === "active") : null;

  const [a, b] = set.scenes;
  const img: Size = { w: a.metadata.width, h: a.metadata.height };
  const isPair = set.scenes.length === 2;
  const allowBlend = set.kind === "optical_sar";
  const mode: ViewerMode | "single" = !isPair ? "single" : state.viewer.mode === "blend" && !allowBlend ? "swipe" : state.viewer.mode;

  const areaRef = useRef<HTMLDivElement>(null);
  const area = useElementSize(areaRef);
  const pane: Size = mode === "side" ? { w: Math.max(0, (area.w - 1) / 2), h: area.h } : area;
  const { view, zoomAt, panBy, reset, focusBox } = useView(pane, img);
  const nav = useNavigation(areaRef, { zoomAt, panBy, reset });

  /* ---- evidence focus → fit (unless the user just zoomed) ---- */
  const focused = state.evidence.focused;
  useEffect(() => {
    if (focused == null) return;
    const e = evidence.find((x) => x.n === focused);
    if (e) focusBox(e.bbox, false);
  }, [focused]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (state.evidence.showAll) reset();
  }, [state.evidence.showAll]); // eslint-disable-line react-hooks/exhaustive-deps

  /* ---- comparison modes ---- */
  const [swipe, setSwipe] = useState(0.5);
  const [flickerShowB, setFlickerShowB] = useState(true);
  const [flickerPaused, setFlickerPaused] = useState(false);
  useEffect(() => setFlickerPaused(prefersReducedMotion()), []);
  useEffect(() => {
    if (mode !== "flicker" || flickerPaused) return;
    const t = setInterval(() => setFlickerShowB((v) => !v), FLICKER_MS);
    return () => clearInterval(t);
  }, [mode, flickerPaused]);
  useEffect(() => {
    if (mode !== "flicker") return;
    const onKey = (e: KeyboardEvent) => {
      if (e.code !== "Space" || isTypingTarget(e.target) || (e.target as HTMLElement)?.tagName === "BUTTON") return;
      e.preventDefault();
      setFlickerPaused(true);
      setFlickerShowB((v) => !v);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [mode]);

  /* ---- cursor readout + loupe ---- */
  const [cursor, setCursor] = useState<Cursor | null>(null);
  const onPointerMoveArea = (e: React.PointerEvent<HTMLDivElement>) => {
    nav.onPointerMove(e);
    if (!view) return;
    const r = e.currentTarget.getBoundingClientRect();
    const ax = e.clientX - r.left;
    const ay = e.clientY - r.top;
    const inSecond = mode === "side" && ax > pane.w + 1;
    const px = inSecond ? ax - pane.w - 1 : ax;
    const u = (px - view.x) / (view.k * img.w);
    const v = (ay - view.y) / (view.k * img.h);
    setCursor(u >= 0 && u <= 1 && v >= 0 && v <= 1 ? { u, v, ax, ay, pane: inSecond ? 1 : 0 } : null);
  };

  const showEvidence = layerVisible(state, EVIDENCE_LAYER, true);
  const lens = state.evidence.hovered ?? state.evidence.focused;
  const runKey = analysis?.localId ?? "none";
  const onHover = useCallback((n: number | null) => dispatch({ type: "evidence/hover", n }), [dispatch]);
  const onSelect = useCallback(
    (n: number) => {
      if (nav.justDragged()) return;
      dispatch({ type: "evidence/focus", n: state.evidence.focused === n ? null : n });
    },
    [dispatch, nav, state.evidence.focused],
  );

  const visibleRasters = jobLayers.filter((l) => layerVisible(state, l.id, false));

  /** Which scene the user sees at the cursor — the loupe must magnify exactly that. */
  const sceneAtCursor = (c: Cursor): Scene => {
    if (!isPair) return a;
    if (mode === "side") return c.pane === 0 ? a : b;
    if (mode === "swipe") return c.ax >= swipe * pane.w ? b : a;
    if (mode === "flicker") return flickerShowB ? b : a;
    return state.viewer.sarOpacity >= 0.5 ? b : a;
  };

  const renderPane = (index: 0 | 1, scenes: { scene: Scene; opacity?: number; clipLeft?: number }[]) =>
    view && (
      <div className="absolute inset-y-0 overflow-hidden" style={{ left: index === 0 ? 0 : pane.w + 1, width: pane.w }}>
        {scenes.map(({ scene, opacity = 1, clipLeft }) => (
          <div
            key={scene.imageId}
            className="absolute inset-0"
            style={{ opacity, clipPath: clipLeft != null ? `inset(0 0 0 ${clipLeft}px)` : undefined }}
          >
            <Stage url={previewUrl(scene.imageId)} view={view} img={img} alt={`${ROLE[scene.role].long} quick-look`} />
          </div>
        ))}
        {visibleRasters.map((l) => (
          <div key={l.id} className="absolute inset-0" style={{ opacity: 0.85 }}>
            <Stage url={assetUrl(l.url)} view={view} img={img} alt={l.label} />
          </div>
        ))}
        {showEvidence && evidence.length > 0 && (
          <EvidenceLens
            evidence={evidence}
            view={view}
            img={img}
            pane={pane}
            lens={lens}
            showAll={state.evidence.showAll}
            fill={state.viewer.outlineFill}
            runKey={runKey}
            crosshair={mode === "side" && cursor && cursor.pane !== index ? cursor : null}
            onHover={onHover}
            onSelect={onSelect}
          />
        )}
        {mode === "side" && !(showEvidence && evidence.length) && cursor && cursor.pane !== index && (
          <EvidenceLens evidence={[]} view={view} img={img} pane={pane} lens={null} showAll={false} fill={false} runKey={runKey} crosshair={cursor} onHover={onHover} onSelect={onSelect} interactive={false} />
        )}
      </div>
    );

  const bar = view && a.metadata.gsd_m ? scaleBar(a.metadata.gsd_m / view.k) : null;

  return (
    <section aria-label="Evidence viewer" className="flex h-full min-h-0 flex-col bg-base">
      <div
        ref={areaRef}
        tabIndex={0}
        aria-label="Image. Drag or use arrow keys to pan; scroll, + and − to zoom; 0 to fit."
        className="relative min-h-0 flex-1 cursor-grab touch-none overflow-hidden select-none active:cursor-grabbing focus-visible:outline-offset-[-2px]"
        onPointerDown={nav.onPointerDown}
        onPointerMove={onPointerMoveArea}
        onPointerUp={nav.onPointerUp}
        onPointerLeave={() => setCursor(null)}
        onDoubleClick={nav.onDoubleClick}
        onKeyDown={(e) => {
          const step = 48;
          const keys: Record<string, () => void> = {
            ArrowLeft: () => panBy(step, 0),
            ArrowRight: () => panBy(-step, 0),
            ArrowUp: () => panBy(0, step),
            ArrowDown: () => panBy(0, -step),
            "+": () => zoomAt(1.25, pane.w / 2, pane.h / 2),
            "=": () => zoomAt(1.25, pane.w / 2, pane.h / 2),
            "-": () => zoomAt(0.8, pane.w / 2, pane.h / 2),
            "0": () => reset(),
          };
          const fn = keys[e.key];
          if (fn) {
            e.preventDefault();
            fn();
          }
        }}
      >
        {mode === "single" && renderPane(0, [{ scene: a }])}
        {mode === "swipe" && renderPane(0, [{ scene: a }, { scene: b, clipLeft: swipe * pane.w }])}
        {mode === "flicker" && renderPane(0, [{ scene: a }, { scene: b, opacity: flickerShowB ? 1 : 0 }])}
        {mode === "blend" && renderPane(0, [{ scene: a }, { scene: b, opacity: state.viewer.sarOpacity }])}
        {mode === "side" && (
          <>
            {renderPane(0, [{ scene: a }])}
            <div className="absolute inset-y-0 w-px bg-line-strong" style={{ left: pane.w }} />
            {renderPane(1, [{ scene: b }])}
          </>
        )}

        {mode === "swipe" && <SwipeHandle x={swipe * pane.w} width={pane.w} onChange={setSwipe} />}

        <SceneLabels
          mode={mode}
          scenes={set.scenes}
          pane={pane}
          flickerShowB={flickerShowB}
          sarOpacity={state.viewer.sarOpacity}
        />

        {running && (
          <div className="pointer-events-none absolute top-3 left-1/2 flex -translate-x-1/2 items-center gap-2 rounded-full border border-line-strong bg-panel/90 px-3 py-1 text-sm shadow-lg shadow-black/40">
            <span className="size-1.5 rounded-full bg-accent animate-pulse-dot" />
            <span className="text-fg-muted">
              {activeStep ? activeStep.label : "Starting the run"} — evidence appears as each step finishes
            </span>
          </div>
        )}

        {bar && (
          <div className="pointer-events-none absolute right-3 bottom-3 flex flex-col items-end gap-1" aria-label={`Scale: ${bar.label}`}>
            <span className="font-mono text-xs text-fg [text-shadow:0_0_3px_#000,0_0_2px_#000]">{bar.label}</span>
            <span className="block h-1.5 border-x-2 border-b-2 border-evidence shadow-[0_1px_0_#000,0_-1px_0_#000]" style={{ width: bar.px }} />
          </div>
        )}

        {state.viewer.loupe && cursor && view && (
          <Loupe scene={sceneAtCursor(cursor)} cursor={cursor} area={area} />
        )}
      </div>

      <ViewerToolbar
        mode={mode}
        allowBlend={allowBlend}
        hasEvidence={evidence.length > 0}
        flickerPaused={flickerPaused}
        onFlickerPause={() => setFlickerPaused((p) => !p)}
        onFit={reset}
        cursor={cursor}
        scene={a}
        layerContent={<LayerList set={set} trace={trace} evidence={evidence} dense />}
      />
    </section>
  );
}

/* ------------------------------------------------------------------ Stage */

function Stage({ url, view, img, alt }: { url: string; view: View; img: Size; alt: string }) {
  // Past ~3 screen pixels per quick-look pixel, show the pixels as pixels rather than smoothing them.
  const pixelated = (view.k * img.w) / QUICKLOOK_PX > 3;
  return (
    <div
      className="absolute top-0 left-0 origin-top-left will-change-transform"
      style={{ width: img.w, height: img.h, transform: `translate(${view.x}px, ${view.y}px) scale(${view.k})` }}
    >
      {/* eslint-disable-next-line @next/next/no-img-element -- raw backend rasters, not optimisable assets */}
      <img
        src={url}
        alt={alt}
        crossOrigin="anonymous"
        draggable={false}
        className="block size-full select-none"
        style={{ imageRendering: pixelated ? "pixelated" : "auto" }}
      />
    </div>
  );
}

/* ------------------------------------------------------------------ Swipe */

function SwipeHandle({ x, width, onChange }: { x: number; width: number; onChange: (f: number) => void }) {
  const dragging = useRef(false);
  const set = (clientX: number, el: HTMLElement) => {
    const r = el.parentElement!.getBoundingClientRect();
    onChange(Math.min(0.98, Math.max(0.02, (clientX - r.left) / width)));
  };
  return (
    <div
      role="slider"
      tabIndex={0}
      aria-label="Swipe divider between the two scenes"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round((x / Math.max(width, 1)) * 100)}
      className="group absolute inset-y-0 z-10 -ml-3 flex w-6 cursor-ew-resize justify-center focus-visible:outline-none"
      style={{ left: x }}
      onPointerDown={(e) => {
        e.stopPropagation();
        dragging.current = true;
        e.currentTarget.setPointerCapture(e.pointerId);
      }}
      onPointerMove={(e) => {
        if (!dragging.current) return;
        e.stopPropagation();
        set(e.clientX, e.currentTarget);
      }}
      onPointerUp={(e) => {
        dragging.current = false;
        e.stopPropagation();
      }}
      onDoubleClick={(e) => e.stopPropagation()}
      onKeyDown={(e) => {
        const f = x / Math.max(width, 1);
        if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
          e.preventDefault();
          e.stopPropagation();
          onChange(Math.min(0.98, Math.max(0.02, f + (e.key === "ArrowLeft" ? -0.05 : 0.05))));
        }
      }}
    >
      <span className="h-full w-0.5 bg-evidence shadow-[0_0_0_1px_rgb(0_0_0/0.6)]" />
      <span className="absolute top-1/2 grid size-8 -translate-y-1/2 place-items-center rounded-full border-2 border-evidence bg-base/90 shadow-lg shadow-black/60 group-focus-visible:border-accent group-focus-visible:ring-2 group-focus-visible:ring-accent">
        <SplitSquareHorizontal className="size-4 text-evidence" />
      </span>
    </div>
  );
}

/* ------------------------------------------------------------------ Scene labels */

function sceneTag(s: Scene) {
  const tone = s.metadata.modality === "sar" ? "sar" : s.metadata.modality === "optical" ? "optical" : "neutral";
  return (
    <span className="flex items-center gap-1.5 rounded-sm border border-line-strong bg-base/85 px-2 py-1 text-sm shadow-lg shadow-black/40">
      <Tag tone={tone}>{ROLE[s.role].label}</Tag>
      <span className="font-mono text-xs text-fg tabular">{formatDate(s.metadata.acquired_at) ?? s.metadata.filename}</span>
    </span>
  );
}

function SceneLabels({ mode, scenes, pane, flickerShowB, sarOpacity }: { mode: ViewerMode | "single"; scenes: Scene[]; pane: Size; flickerShowB: boolean; sarOpacity: number }) {
  const [a, b] = scenes;
  const pos = "pointer-events-none absolute top-3 z-[5]";
  if (mode === "single") return <div className={cn(pos, "left-3")}>{sceneTag(a)}</div>;
  if (mode === "swipe" || mode === "side")
    return (
      <>
        <div className={cn(pos, "left-3")}>{sceneTag(a)}</div>
        <div className={pos} style={{ right: mode === "side" ? undefined : 12, left: mode === "side" ? pane.w + 13 : undefined }}>
          {sceneTag(b)}
        </div>
      </>
    );
  if (mode === "flicker") return <div className={cn(pos, "left-3")} aria-live="off">{sceneTag(flickerShowB ? b : a)}</div>;
  return (
    <div className={cn(pos, "left-3 flex gap-2")}>
      {sceneTag(a)}
      <span className="flex items-center gap-1.5 rounded-sm border border-line-strong bg-base/85 px-2 py-1 text-sm">
        <Tag tone="sar">SAR</Tag>
        <span className="font-mono text-xs text-fg tabular">{Math.round(sarOpacity * 100)}% over optical</span>
      </span>
    </div>
  );
}

/* ------------------------------------------------------------------ Loupe */

function Loupe({ scene, cursor, area }: { scene: Scene; cursor: Cursor; area: Size }) {
  const S = LOUPE.size;
  const bg = QUICKLOOK_PX * LOUPE.scale;
  const left = cursor.ax + 24 + S > area.w ? cursor.ax - 24 - S : cursor.ax + 24;
  const top = Math.min(Math.max(8, cursor.ay - S / 2), area.h - S - 28);
  return (
    <div className="pointer-events-none absolute z-20 flex flex-col items-center gap-1" style={{ left, top }}>
      <div
        className="relative overflow-hidden rounded-full border-2 border-evidence bg-base shadow-[0_0_0_1px_#000,0_10px_30px_rgb(0_0_0/0.6)]"
        style={{ width: S, height: S }}
      >
        {/* An <img> (not a CSS background) so every backend image request is CORS-mode and cache-compatible. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={previewUrl(scene.imageId)}
          alt=""
          crossOrigin="anonymous"
          draggable={false}
          className="absolute max-w-none"
          style={{
            width: bg,
            height: bg,
            left: -(cursor.u * bg - S / 2),
            top: -(cursor.v * bg - S / 2),
            imageRendering: "pixelated",
          }}
        />
        <span className="absolute top-1/2 left-1/2 size-3 -translate-1/2 border border-evidence shadow-[0_0_0_1px_#000]" />
      </div>
      <span className="rounded-sm bg-base/90 px-1.5 font-mono text-[11px] text-fg-muted">
        {ROLE[scene.role].label} · quick-look pixels ×{LOUPE.scale}
      </span>
    </div>
  );
}

/* ------------------------------------------------------------------ Toolbar */

const MODES: { id: ViewerMode; label: string; key: string; icon: React.ReactNode }[] = [
  { id: "swipe", label: "Swipe", key: "S", icon: <SplitSquareHorizontal /> },
  { id: "side", label: "Side by side", key: "D", icon: <Columns2 /> },
  { id: "flicker", label: "Flicker", key: "F", icon: <Repeat /> },
  { id: "blend", label: "Blend", key: "B", icon: <BlendIcon /> },
];

function ViewerToolbar({
  mode,
  allowBlend,
  hasEvidence,
  flickerPaused,
  onFlickerPause,
  onFit,
  cursor,
  scene,
  layerContent,
}: {
  mode: ViewerMode | "single";
  allowBlend: boolean;
  hasEvidence: boolean;
  flickerPaused: boolean;
  onFlickerPause: () => void;
  onFit: () => void;
  cursor: Cursor | null;
  scene: Scene;
  layerContent: React.ReactNode;
}) {
  const state = useWorkspace();
  const dispatch = useDispatch();
  const m = scene.metadata;
  const lonlat = cursor && m.corners_wgs84 ? pixelToLonLat(m.corners_wgs84, cursor.u, cursor.v) : null;

  return (
    <div className="flex min-h-11 flex-wrap items-center gap-x-3 gap-y-1 border-t border-line bg-panel px-2 py-1.5">
      {mode !== "single" && (
        <div role="radiogroup" aria-label="Compare mode" className="flex items-center rounded-sm border border-line bg-base p-0.5">
          {MODES.filter((x) => x.id !== "blend" || allowBlend).map((x) => (
            <Tip key={x.id} content={x.label} shortcut={x.key} side="top">
              <button
                role="radio"
                aria-checked={mode === x.id}
                onClick={() => dispatch({ type: "viewer/mode", mode: x.id })}
                className={cn(
                  "flex h-7 items-center gap-1.5 rounded-[4px] px-2 text-sm text-fg-muted transition-colors [&_svg]:size-3.5",
                  mode === x.id ? "bg-raised text-fg" : "hover:text-fg",
                )}
              >
                {x.icon}
                <span className="hidden lg:inline">{x.label}</span>
              </button>
            </Tip>
          ))}
        </div>
      )}

      {mode === "flicker" && (
        <Button size="sm" variant="ghost" onClick={onFlickerPause} aria-label={flickerPaused ? "Resume flicker" : "Pause flicker"}>
          {flickerPaused ? <Play /> : <Pause />}
          {flickerPaused ? (
            <span className="text-fg-faint">
              <Kbd>Space</Kbd> to switch
            </span>
          ) : (
            "600 ms"
          )}
        </Button>
      )}

      {mode === "blend" && (
        <label className="flex items-center gap-2 text-sm text-fg-muted">
          <span className="text-sar">SAR</span>
          <input
            type="range"
            min={0}
            max={100}
            value={Math.round(state.viewer.sarOpacity * 100)}
            onChange={(e) => dispatch({ type: "viewer/sarOpacity", value: Number(e.target.value) / 100 })}
            aria-label="SAR opacity over optical"
            className="w-24 accent-(--color-sar)"
          />
          <span className="w-9 font-mono text-xs tabular">{Math.round(state.viewer.sarOpacity * 100)}%</span>
        </label>
      )}

      <div className="flex items-center">
        <Popover.Root>
          <Tip content="Layers" side="top">
            <Popover.Trigger render={<Button size="sm" variant="ghost" aria-label="Layers" />}>
              <Layers />
              <span className="hidden sm:inline">Layers</span>
            </Popover.Trigger>
          </Tip>
          <Popover.Portal>
            <Popover.Positioner side="top" sideOffset={8} align="start" className="z-40">
              <Popover.Popup className="max-h-[70vh] w-80 overflow-auto rounded-md border border-line-strong bg-panel p-4 shadow-2xl shadow-black/60 scrollbar-thin">
                {layerContent}
              </Popover.Popup>
            </Popover.Positioner>
          </Popover.Portal>
        </Popover.Root>
        <IconButton label="Loupe — quick-look pixels under the cursor" shortcut="L" side="top" pressed={state.viewer.loupe} onClick={() => dispatch({ type: "viewer/loupe" })}>
          <Search />
        </IconButton>
        <IconButton label="Fit image" shortcut="0" side="top" onClick={onFit}>
          <Maximize />
        </IconButton>
        {hasEvidence && (
          <IconButton label="Show all evidence" shortcut="A" side="top" pressed={state.evidence.showAll} onClick={() => dispatch({ type: "evidence/showAll" })}>
            <ScanEye />
          </IconButton>
        )}
      </div>

      <div className="ml-auto flex min-w-0 items-center gap-3 font-mono text-xs text-fg-muted tabular" aria-live="off">
        {cursor ? (
          <>
            <span>
              x {Math.floor(cursor.u * m.width)} · y {Math.floor(cursor.v * m.height)} px
            </span>
            {lonlat && <span className="text-fg">{formatLonLat(lonlat)}</span>}
          </>
        ) : (
          <span className="hidden font-sans text-fg-faint xl:inline">Scroll to zoom · drag to pan · hover for coordinates</span>
        )}
      </div>
    </div>
  );
}
