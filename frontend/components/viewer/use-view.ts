"use client";

import { useCallback, useEffect, useRef, useState, type RefObject } from "react";
import { prefersReducedMotion } from "@/lib/utils";

/** screen = (x, y) + k · imagePixel, relative to the pane's top-left. */
export interface View {
  k: number;
  x: number;
  y: number;
}

export interface Size {
  w: number;
  h: number;
}

const PAD = 24;
const MIN_FACTOR = 0.5;
const MAX_FACTOR = 40;
/** Don't fight the user: evidence focus won't move the view within this window of a manual zoom/pan. */
export const USER_GRACE_MS = 5000;

export function fitView(pane: Size, img: Size): View {
  const k = Math.min((pane.w - PAD * 2) / img.w, (pane.h - PAD * 2) / img.h);
  return { k, x: (pane.w - img.w * k) / 2, y: (pane.h - img.h * k) / 2 };
}

/** Fit a normalised bbox to about `fraction` of the pane. */
export function fitBox(pane: Size, img: Size, bbox: [number, number, number, number], fraction = 0.6): View {
  const [x0, y0, x1, y1] = bbox;
  const bw = Math.max((x1 - x0) * img.w, 1);
  const bh = Math.max((y1 - y0) * img.h, 1);
  const base = fitView(pane, img).k;
  const k = clamp(Math.min((pane.w * fraction) / bw, (pane.h * fraction) / bh), base * MIN_FACTOR, base * MAX_FACTOR);
  const cx = ((x0 + x1) / 2) * img.w;
  const cy = ((y0 + y1) / 2) * img.h;
  return { k, x: pane.w / 2 - cx * k, y: pane.h / 2 - cy * k };
}

function clamp(v: number, lo: number, hi: number) {
  return Math.min(hi, Math.max(lo, v));
}

export function useElementSize<T extends HTMLElement>(ref: RefObject<T | null>): Size {
  const [size, setSize] = useState<Size>({ w: 0, h: 0 });
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      setSize((s) => (Math.abs(s.w - width) < 0.5 && Math.abs(s.h - height) < 0.5 ? s : { w: width, h: height }));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref]);
  return size;
}

export function useView(pane: Size, img: Size) {
  const [view, setView] = useState<View | null>(null);
  const lastUserAt = useRef(0);
  const anim = useRef<number | null>(null);
  const viewRef = useRef<View | null>(null);
  viewRef.current = view;

  const ready = pane.w > 0 && pane.h > 0 && img.w > 0 && img.h > 0;

  // Fit when a new image arrives. When only the pane resizes (rail toggled, toolbar reflowed),
  // keep the same image point centred at the same relative zoom — never discard the user's view.
  const prev = useRef<{ pane: Size; img: Size } | null>(null);
  useEffect(() => {
    if (!ready) return;
    const last = prev.current;
    prev.current = { pane, img };
    setView((v) => {
      if (!v || !last || last.img.w !== img.w || last.img.h !== img.h) return fitView(pane, img);
      const ratio = fitView(pane, img).k / fitView(last.pane, img).k;
      const cx = (last.pane.w / 2 - v.x) / v.k;
      const cy = (last.pane.h / 2 - v.y) / v.k;
      const k = v.k * ratio;
      return { k, x: pane.w / 2 - cx * k, y: pane.h / 2 - cy * k };
    });
  }, [ready, pane.w, pane.h, img.w, img.h]); // eslint-disable-line react-hooks/exhaustive-deps

  const cancelAnim = () => {
    if (anim.current != null) cancelAnimationFrame(anim.current);
    anim.current = null;
  };

  const animateTo = useCallback((target: View, ms = 300) => {
    cancelAnim();
    const from = viewRef.current;
    if (!from || prefersReducedMotion()) {
      setView(target);
      return;
    }
    const start = performance.now();
    const ease = (t: number) => 1 - Math.pow(1 - t, 3);
    const step = (now: number) => {
      const t = Math.min(1, (now - start) / ms);
      const e = ease(t);
      // Interpolate zoom geometrically so the motion feels uniform.
      const k = from.k * Math.pow(target.k / from.k, e);
      // Keep the pane-centre point moving linearly in image space.
      const fc = { x: (pane.w / 2 - from.x) / from.k, y: (pane.h / 2 - from.y) / from.k };
      const tc = { x: (pane.w / 2 - target.x) / target.k, y: (pane.h / 2 - target.y) / target.k };
      const c = { x: fc.x + (tc.x - fc.x) * e, y: fc.y + (tc.y - fc.y) * e };
      setView({ k, x: pane.w / 2 - c.x * k, y: pane.h / 2 - c.y * k });
      if (t < 1) anim.current = requestAnimationFrame(step);
      else anim.current = null;
    };
    anim.current = requestAnimationFrame(step);
  }, [pane.w, pane.h]);

  const zoomAt = useCallback(
    (factor: number, px: number, py: number) => {
      cancelAnim();
      lastUserAt.current = Date.now();
      setView((v) => {
        if (!v) return v;
        const base = fitView(pane, img).k;
        const k = clamp(v.k * factor, base * MIN_FACTOR, base * MAX_FACTOR);
        const f = k / v.k;
        return { k, x: px - (px - v.x) * f, y: py - (py - v.y) * f };
      });
    },
    [pane, img],
  );

  const panBy = useCallback((dx: number, dy: number) => {
    cancelAnim();
    lastUserAt.current = Date.now();
    setView((v) => (v ? { ...v, x: v.x + dx, y: v.y + dy } : v));
  }, []);

  const reset = useCallback(() => {
    if (ready) animateTo(fitView(pane, img), 240);
  }, [ready, pane, img, animateTo]);

  const focusBox = useCallback(
    (bbox: [number, number, number, number], force = false) => {
      if (!ready) return;
      if (!force && Date.now() - lastUserAt.current < USER_GRACE_MS) return;
      animateTo(fitBox(pane, img, bbox));
    },
    [ready, pane, img, animateTo],
  );

  useEffect(() => cancelAnim, []);

  return { view, zoomAt, panBy, reset, focusBox, lastUserAt };
}

/** Pointer + wheel + keyboard navigation for a pane. */
export function useNavigation(
  el: RefObject<HTMLElement | null>,
  nav: Pick<ReturnType<typeof useView>, "zoomAt" | "panBy" | "reset">,
) {
  const { zoomAt, panBy } = nav;
  useEffect(() => {
    const node = el.current;
    if (!node) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const r = node.getBoundingClientRect();
      const delta = e.deltaMode === 1 ? e.deltaY * 16 : e.deltaY;
      zoomAt(Math.exp(-delta * 0.0015), e.clientX - r.left, e.clientY - r.top);
    };
    node.addEventListener("wheel", onWheel, { passive: false });
    return () => node.removeEventListener("wheel", onWheel);
  }, [el, zoomAt]);

  const drag = useRef<{ x: number; y: number; id: number; moved: boolean } | null>(null);
  const endedDragAt = useRef(0);

  return {
    onPointerDown: (e: React.PointerEvent) => {
      if (e.button !== 0) return;
      drag.current = { x: e.clientX, y: e.clientY, id: e.pointerId, moved: false };
    },
    onPointerMove: (e: React.PointerEvent) => {
      const d = drag.current;
      if (!d || d.id !== e.pointerId) return;
      const dx = e.clientX - d.x;
      const dy = e.clientY - d.y;
      if (!d.moved && Math.hypot(dx, dy) < 3) return;
      if (!d.moved) (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
      d.moved = true;
      d.x = e.clientX;
      d.y = e.clientY;
      panBy(dx, dy);
    },
    onPointerUp: (e: React.PointerEvent) => {
      if (drag.current?.id !== e.pointerId) return;
      if (drag.current.moved) endedDragAt.current = performance.now();
      drag.current = null;
    },
    onDoubleClick: (e: React.MouseEvent) => {
      const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
      zoomAt(e.shiftKey ? 0.5 : 2, e.clientX - r.left, e.clientY - r.top);
    },
    /** True right after a pan, so the click that ends a drag isn't treated as a selection. */
    justDragged: () => performance.now() - endedDragAt.current < 50,
  };
}
