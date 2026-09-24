"use client";

import { CIRCLED, type Evidence } from "@/lib/analysis";
import { DASH } from "@/lib/confidence";
import { formatArea } from "@/lib/geo";
import { cn } from "@/lib/utils";
import { toolLabel } from "@/lib/vocabulary";
import { ConfidenceMeter } from "@/components/ui/primitives";
import type { Size, View } from "./use-view";

/*
 * The Evidence Lens (UX brief §7): attention without occlusion.
 *  - Spotlight, not fill: a scrim dims everything *outside* the active region; the region
 *    itself is never covered.
 *  - Boxes are drawn as four corner brackets, masks as outlines — never the other way round.
 *  - Confidence is carried by line style (solid / dashed / dotted), so it survives greyscale.
 *  - Every stroke has a dark halo so it reads on water, desert, cloud and vegetation alike.
 *  - Numbered markers sit outside the region's top-left corner, matching the answer's chips.
 * Geometry is drawn in screen space so stroke widths and dash patterns stay constant at any zoom.
 */

interface LensProps {
  evidence: Evidence[];
  view: View;
  img: Size;
  pane: Size;
  /** Region the lens is on (hover wins over focus). */
  lens: number | null;
  showAll: boolean;
  fill: boolean;
  runKey: string;
  crosshair?: { u: number; v: number } | null;
  onHover: (n: number | null) => void;
  onSelect: (n: number) => void;
  interactive?: boolean;
}

const HALO = "var(--color-halo)";

export function EvidenceLens({ evidence, view, img, pane, lens, showAll, fill, runKey, crosshair, onHover, onSelect, interactive = true }: LensProps) {
  const sx = (u: number) => view.x + u * img.w * view.k;
  const sy = (v: number) => view.y + v * img.h * view.k;
  const imageRect = { x: sx(0), y: sy(0), w: img.w * view.k, h: img.h * view.k };
  const target = lens != null && !showAll ? evidence.find((e) => e.n === lens) ?? null : null;

  const shapePath = (e: Evidence) =>
    e.kind === "box" || !e.rings
      ? rectPath(sx(e.bbox[0]), sy(e.bbox[1]), sx(e.bbox[2]), sy(e.bbox[3]))
      : e.rings.map((ring) => ring.map(([u, v], i) => `${i ? "L" : "M"}${sx(u).toFixed(1)},${sy(v).toFixed(1)}`).join("") + "Z").join("");

  return (
    <>
      <svg className="pointer-events-none absolute inset-0 size-full overflow-visible" aria-hidden="true">
        {/* Spotlight scrim: outer image rectangle minus the active region (even-odd). */}
        <path
          d={rectPath(imageRect.x, imageRect.y, imageRect.x + imageRect.w, imageRect.y + imageRect.h) + (target ? shapePath(target) : "")}
          fillRule="evenodd"
          fill="var(--color-scrim)"
          className="transition-opacity duration-(--duration-base) ease-(--ease-out)"
          opacity={target ? 1 : 0}
        />

        {evidence.map((e) => {
          const active = target?.n === e.n || lens === e.n;
          const opacity = showAll ? 0.6 : target ? (active ? 1 : 0.3) : 0.9;
          const color = active ? "var(--color-evidence-active)" : e.tone === "change" ? "var(--color-change)" : "var(--color-evidence)";
          const dash = DASH[e.line];
          const x0 = sx(e.bbox[0]);
          const y0 = sy(e.bbox[1]);
          const x1 = sx(e.bbox[2]);
          const y1 = sy(e.bbox[3]);
          const low = e.confidence.available && e.confidence.band.steps <= 2;
          // Regions entirely outside the pane draw nothing — a marker pinned to the edge would point nowhere.
          if (x1 < 0 || y1 < 0 || x0 > pane.w || y0 > pane.h) return null;
          const marker = { x: Math.max(imageRect.x + 11, x0 - 12), y: Math.max(imageRect.y + 11, y0 - 12) };
          return (
            <g
              key={`${runKey}-${e.n}`}
              opacity={opacity}
              className="evidence-arrive transition-opacity duration-(--duration-base)"
              style={{ transformOrigin: `${(x0 + x1) / 2}px ${(y0 + y1) / 2}px` }}
            >
              {e.kind === "box" ? (
                <>
                  <path d={bracketPath(x0, y0, x1, y1)} fill="none" stroke={HALO} strokeWidth={4} strokeLinecap="square" />
                  <path d={bracketPath(x0, y0, x1, y1)} fill="none" stroke={color} strokeWidth={2} strokeDasharray={dash} strokeLinecap="square" />
                </>
              ) : (
                <>
                  {fill && <path d={shapePath(e)} fill={color} fillOpacity={0.15} fillRule="evenodd" stroke="none" />}
                  <path d={shapePath(e)} fill="none" stroke={HALO} strokeWidth={3.5} strokeLinejoin="round" />
                  <path d={shapePath(e)} fill="none" stroke={color} strokeWidth={1.5} strokeDasharray={dash} strokeLinejoin="round" />
                </>
              )}
              <circle cx={marker.x} cy={marker.y} r={9.5} fill="var(--color-base)" stroke={HALO} strokeWidth={3} />
              <circle cx={marker.x} cy={marker.y} r={9.5} fill="var(--color-base)" stroke={color} strokeWidth={1.5} />
              <text x={marker.x} y={marker.y} dy="0.36em" textAnchor="middle" fontSize={11} fontWeight={600} fill={color} className="font-mono">
                {e.n}
              </text>
              {low && (
                <text x={marker.x + 15} y={marker.y} dy="0.36em" fontSize={11} fill={color} stroke={HALO} strokeWidth={3} paintOrder="stroke">
                  Needs review
                </text>
              )}
            </g>
          );
        })}

        {crosshair && (
          <g>
            <path d={`M${sx(crosshair.u)},${sy(0)}V${sy(1)}M${sx(0)},${sy(crosshair.v)}H${sx(1)}`} stroke={HALO} strokeWidth={3} />
            <path d={`M${sx(crosshair.u)},${sy(0)}V${sy(1)}M${sx(0)},${sy(crosshair.v)}H${sx(1)}`} stroke="var(--color-evidence)" strokeWidth={1} strokeDasharray="4 4" />
          </g>
        )}
      </svg>

      {/* Hit targets live in their own layer so hovering a region lights its chip (two-way linking). */}
      {interactive && (
        <svg className="pointer-events-none absolute inset-0 size-full" aria-hidden="true">
          {evidence.map((e) => (
            <path
              key={e.n}
              d={shapePath(e)}
              fill="transparent"
              stroke="transparent"
              strokeWidth={12}
              fillRule="evenodd"
              className="pointer-events-auto cursor-pointer"
              onPointerEnter={() => onHover(e.n)}
              onPointerLeave={() => onHover(null)}
              onClick={() => onSelect(e.n)}
            >
              <title>{`${CIRCLED[e.n - 1]} ${e.title}${e.areaM2 != null ? ` · ${formatArea(e.areaM2)}` : ""} — ${e.honesty}`}</title>
            </path>
          ))}
        </svg>
      )}

      {target && <LensCard e={target} rect={{ x0: sx(target.bbox[0]), y0: sy(target.bbox[1]), x1: sx(target.bbox[2]), y1: sy(target.bbox[3]) }} pane={pane} />}
    </>
  );
}

/** The caption for the region under the lens, placed beside it so it never covers it. */
function LensCard({ e, rect, pane }: { e: Evidence; rect: { x0: number; y0: number; x1: number; y1: number }; pane: Size }) {
  const W = 280;
  const H = 112;
  const below = rect.y1 + 12 + H < pane.h;
  const above = rect.y0 - 12 - H > 0;
  const top = below ? rect.y1 + 12 : above ? rect.y0 - 12 - H : Math.min(Math.max(8, rect.y0), pane.h - H - 8);
  const sideways = !below && !above;
  const left = sideways
    ? rect.x1 + 12 + W < pane.w
      ? rect.x1 + 12
      : Math.max(8, rect.x0 - 12 - W)
    : Math.min(Math.max(8, rect.x0), pane.w - W - 8);
  return (
    <div
      role="status"
      className="pointer-events-none absolute z-10 flex flex-col gap-1 rounded-md border border-line-strong bg-panel/95 px-3 py-2 text-sm shadow-xl shadow-black/50 animate-fade-up"
      style={{ left, top, width: W }}
    >
      <div className="flex items-center gap-2 font-medium text-evidence-active">
        <span className="font-mono">{CIRCLED[e.n - 1]}</span>
        <span className="truncate">{e.title}</span>
        {e.areaM2 != null && <span className="ml-auto font-mono text-xs text-fg tabular">{formatArea(e.areaM2)}</span>}
      </div>
      <div className="text-xs leading-snug text-fg-muted">{e.honesty}</div>
      <div className={cn("flex items-center gap-2 text-xs", e.confidence.available ? "text-fg" : "text-fg-faint")}>
        {e.confidence.available ? (
          <>
            <ConfidenceMeter steps={e.confidence.band.steps} />
            <span>{e.confidence.band.word}</span>
          </>
        ) : (
          <span>{e.confidence.reason}</span>
        )}
      </div>
      <div className="font-mono text-[11px] text-fg-faint">
        from step {e.producedBy.index + 1} · {toolLabel(e.producedBy.tool).toLowerCase()}
      </div>
    </div>
  );
}

function rectPath(x0: number, y0: number, x1: number, y1: number) {
  return `M${x0},${y0}H${x1}V${y1}H${x0}Z`;
}

/** Four L-shaped corners and nothing between them: the pixels along the box edge stay visible. */
function bracketPath(x0: number, y0: number, x1: number, y1: number) {
  const L = Math.max(6, Math.min(18, Math.min(x1 - x0, y1 - y0) * 0.28));
  return [
    `M${x0},${y0 + L}V${y0}H${x0 + L}`,
    `M${x1 - L},${y0}H${x1}V${y0 + L}`,
    `M${x1},${y1 - L}V${y1}H${x1 - L}`,
    `M${x0 + L},${y1}H${x0}V${y1 - L}`,
  ].join("");
}
