"use client";

import { ArrowLeftRight, FileUp, RotateCcw, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, uploadRaster } from "@/lib/api";
import { formatDate } from "@/lib/geo";
import type { SceneRole, SceneSetKind, ValidateResponse } from "@/lib/types";
import { cn } from "@/lib/utils";
import { MODALITY_LABEL, ROLE, SCENE_SET } from "@/lib/vocabulary";
import { Button, StatusIcon, Tag } from "@/components/ui/primitives";
import { useActions } from "./effects";
import { ACCEPT, Samples } from "./empty-state";
import { useDispatch, useWorkspace, type Scene } from "./store";

interface Upload {
  key: string;
  file: File | null;
  sent: number;
  total: number;
  status: "uploading" | "done" | "error";
  error?: string;
  scene?: Omit<Scene, "role">;
}

function friendlyUploadError(e: unknown): string {
  if (!(e instanceof ApiError)) return "The upload failed.";
  // The backend's message names the scene's size and the limit, and says to crop.
  if (e.code === "RASTER_TOO_LARGE") return e.message;
  if (e.status === 413) return "This file is over the 500 MB limit.";
  if (e.code === "INVALID_FORMAT" && /benchmark_fixture/.test(e.message))
    return "PNG is accepted only for benchmark images. Upload the GeoTIFF to keep georeferencing.";
  if (e.code === "INVALID_FORMAT") return `This file isn't a readable raster. ${e.message}`;
  return e.message;
}

/** Suggest roles from metadata — but only suggest; the user confirms. */
function propose(scenes: Omit<Scene, "role">[]): { kind: SceneSetKind; order: number[]; why: string } | null {
  if (scenes.length === 1) return { kind: "single", order: [0], why: "One image" };
  const [a, b] = scenes.map((s) => s.metadata);
  if (a.modality !== b.modality && [a.modality, b.modality].includes("sar") && [a.modality, b.modality].includes("optical"))
    return { kind: "optical_sar", order: a.modality === "optical" ? [0, 1] : [1, 0], why: "One file declares optical, the other SAR" };
  if (a.acquired_at && b.acquired_at && a.acquired_at !== b.acquired_at)
    return { kind: "bitemporal", order: a.acquired_at < b.acquired_at ? [0, 1] : [1, 0], why: "The acquisition dates differ; the earlier one is T1" };
  return null;
}

export function SceneComposer() {
  const state = useWorkspace();
  const dispatch = useDispatch();
  const { addSceneSet } = useActions();
  const composer = state.composer!;

  const [kind, setKind] = useState<SceneSetKind | null>(composer.kind);
  const [uploads, setUploads] = useState<Upload[]>(() =>
    composer.seed
      ? [{ key: composer.seed.imageId, file: null, sent: 1, total: 1, status: "done", scene: { imageId: composer.seed.imageId, metadata: composer.seed.metadata } }]
      : [],
  );
  const [order, setOrder] = useState<number[] | null>(null);
  const [confirmed, setConfirmed] = useState(composer.kind != null);
  const [validation, setValidation] = useState<ValidateResponse | null>(null);
  const [validating, setValidating] = useState(false);
  const [tooMany, setTooMany] = useState(false);
  const started = useRef(false);

  const startUpload = useCallback((file: File, replaceKey?: string) => {
    const key = replaceKey ?? `${file.name}-${file.size}-${Math.random()}`;
    const entry: Upload = { key, file, sent: 0, total: file.size, status: "uploading" };
    setUploads((u) => (replaceKey ? u.map((x) => (x.key === replaceKey ? entry : x)) : [...u, entry]));
    setValidation(null);
    uploadRaster(file, (sent, total) => setUploads((u) => u.map((x) => (x.key === key ? { ...x, sent, total } : x))))
      .then((res) =>
        setUploads((u) => u.map((x) => (x.key === key ? { ...x, status: "done", sent: x.total, scene: { imageId: res.image_id, metadata: res.metadata } } : x))),
      )
      .catch((e) => setUploads((u) => u.map((x) => (x.key === key ? { ...x, status: "error", error: friendlyUploadError(e) } : x))));
  }, []);

  const addFiles = useCallback(
    (files: File[]) => {
      const room = 2 - uploads.length;
      setTooMany(files.length > room);
      files.slice(0, Math.max(room, 0)).forEach((f) => startUpload(f));
    },
    [uploads.length, startUpload],
  );

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    if (composer.files?.length) addFiles(composer.files);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const done = uploads.filter((u) => u.status === "done");
  const allDone = uploads.length > 0 && done.length === uploads.length;
  const needed = kind ? SCENE_SET[kind].roles.length : uploads.length === 1 ? 1 : 2;

  // Once every file is in, propose roles (unless the tile already fixed them).
  useEffect(() => {
    if (!allDone || order) return;
    if (kind && confirmed) {
      setOrder(done.map((_, i) => i));
      return;
    }
    const p = propose(done.map((u) => u.scene!));
    if (p) {
      setKind(p.kind);
      setOrder(p.order);
      if (p.kind === "single") setConfirmed(true);
    } else if (done.length === 2) {
      setOrder([0, 1]);
    }
  }, [allDone, order, kind, confirmed, done]);

  const roles: SceneRole[] = kind ? SCENE_SET[kind].roles : [];
  const ordered = order && allDone ? order.map((i) => done[i]) : [];
  const ready = !!kind && confirmed && allDone && ordered.length === roles.length && roles.length === uploads.length;

  // Validate once roles are confirmed; continue automatically when nothing fails.
  useEffect(() => {
    if (!ready || validation || validating) return;
    setValidating(true);
    const scenes: Scene[] = ordered.map((u, i) => ({ role: roles[i], ...u.scene! }));
    api
      .validate(kind!, scenes.map((s) => s.imageId))
      .then((v) => {
        setValidation(v);
        if (v.passed) addSceneSet(kind!, scenes, v);
      })
      .catch((e) => dispatch({ type: "toast", tone: "critical", message: e instanceof ApiError ? e.message : "Validation failed." }))
      .finally(() => setValidating(false));
  }, [ready, validation, validating]); // eslint-disable-line react-hooks/exhaustive-deps

  const cancel = () => dispatch({ type: "composer/close" });
  const proposal = allDone && !confirmed && uploads.length === 2 ? propose(done.map((u) => u.scene!)) : null;

  return (
    <div className="h-full overflow-y-auto scrollbar-thin" onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); addFiles([...e.dataTransfer.files]); }}>
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-6 px-4 py-8 sm:px-8">
        <header className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold text-fg">Add scenes</h1>
            <p className="text-sm text-fg-muted">
              {kind ? `${SCENE_SET[kind].label}: ${SCENE_SET[kind].teach.toLowerCase()}.` : "Drop one or two GeoTIFFs. Roles are proposed from their metadata for you to confirm."}
            </p>
          </div>
          <Button variant="ghost" size="sm" onClick={cancel}>
            <X /> Cancel
          </Button>
        </header>

        {/* Kind switcher: the user always has the final word on what the scenes are. */}
        <div role="radiogroup" aria-label="Scene set type" className="flex flex-wrap gap-2">
          {(Object.keys(SCENE_SET) as SceneSetKind[]).map((k) => (
            <button
              key={k}
              role="radio"
              aria-checked={kind === k}
              onClick={() => {
                setKind(k);
                setConfirmed(true);
                setValidation(null);
                setOrder(done.length ? done.map((_, i) => i) : null);
              }}
              className={cn(
                "h-8 rounded-full border px-3 text-sm transition-colors",
                kind === k ? "border-accent bg-accent/10 text-fg" : "border-line text-fg-muted hover:text-fg",
              )}
            >
              {SCENE_SET[k].label}
            </button>
          ))}
        </div>

        {proposal && (
          <div className="flex flex-col gap-2 rounded-md border border-accent/40 bg-accent/5 p-3 text-sm">
            <p className="text-fg">
              These look like <strong className="font-medium">{SCENE_SET[proposal.kind].label}</strong> — {proposal.why.toLowerCase()}.
            </p>
            <div className="flex flex-wrap gap-2">
              <Button size="sm" variant="primary" onClick={() => setConfirmed(true)}>
                Use as {SCENE_SET[proposal.kind].label.toLowerCase()}
              </Button>
              <Button size="sm" onClick={() => setOrder((o) => (o ? [o[1], o[0]] : o))}>
                <ArrowLeftRight /> Swap {SCENE_SET[proposal.kind].roles.map((r) => ROLE[r].label).join(" / ")}
              </Button>
            </div>
          </div>
        )}
        {allDone && !proposal && !confirmed && uploads.length === 2 && (
          <p className="rounded-md border border-line bg-raised/50 p-3 text-sm text-fg-muted">
            The metadata doesn&apos;t say whether these are two dates or optical + SAR. Choose the type above, then check the order below.
          </p>
        )}

        <ol className="flex flex-col gap-2">
          {Array.from({ length: Math.max(needed, uploads.length, 1) }).map((_, i) => {
            const u = ordered.length ? ordered[i] : uploads[i];
            const role = roles[i];
            return (
              <SlotCard
                key={u?.key ?? `empty-${i}`}
                role={role}
                upload={u}
                onPick={(f) => (u ? startUpload(f, u.key) : addFiles([f]))}
              />
            );
          })}
        </ol>
        {uploads.length === 0 && <Samples offline={state.health.state === "offline"} />}
        {tooMany && <p className="text-sm text-warning">A scene set holds at most two scenes; extra files were left out.</p>}
        {ordered.length === 2 && confirmed && (
          <div>
            <Button size="sm" variant="ghost" onClick={() => { setOrder((o) => (o ? [o[1], o[0]] : o)); setValidation(null); }}>
              <ArrowLeftRight /> Swap {roles.map((r) => ROLE[r].label).join(" and ")}
            </Button>
          </div>
        )}

        {(validating || validation) && (
          <section aria-label="Checks" className="flex flex-col gap-2">
            <h2 className="text-sm font-medium text-fg">{validating ? "Checking your images…" : validation?.passed ? "All checks passed" : "A check failed"}</h2>
            <ul className="flex flex-col divide-y divide-line rounded-md border border-line">
              {validation?.checks.map((c) => (
                <li key={c.id} className="flex flex-col gap-0.5 px-3 py-2">
                  <div className="flex items-center gap-2.5 text-sm">
                    <StatusIcon status={c.status} />
                    <span className="text-fg">{c.label}</span>
                    {c.value && <span className="ml-auto font-mono text-xs text-fg-muted tabular">{c.value}</span>}
                  </div>
                  {c.reason && <p className={cn("pl-6.5 text-sm", c.status === "fail" ? "text-critical" : "text-warning")}>{c.reason}</p>}
                </li>
              ))}
            </ul>
            {validation && !validation.passed && (
              <p className="text-sm text-fg-muted">Your files are kept. Replace the file that doesn&apos;t match, or change the scene set type.</p>
            )}
          </section>
        )}
      </div>
    </div>
  );
}

function SlotCard({ role, upload, onPick }: { role?: SceneRole; upload?: Upload; onPick: (f: File) => void }) {
  const input = useRef<HTMLInputElement>(null);
  const m = upload?.scene?.metadata;
  const pct = upload && upload.total ? Math.round((upload.sent / upload.total) * 100) : 0;
  const tone = m?.modality === "sar" ? "sar" : m?.modality === "optical" ? "optical" : "neutral";
  return (
    <li className="flex flex-col gap-2 rounded-md border border-line bg-panel p-3">
      <div className="flex items-center gap-2.5">
        {role ? <Tag tone={role === "sar" ? "sar" : role === "optical" ? "optical" : "neutral"}>{ROLE[role].long}</Tag> : <Tag>Scene</Tag>}
        {upload ? (
          <span className="min-w-0 truncate text-sm text-fg">{upload.file?.name ?? m?.filename}</span>
        ) : (
          <span className="text-sm text-fg-faint">Empty</span>
        )}
        <span className="ml-auto flex items-center gap-2">
          {upload?.status === "uploading" && <span className="font-mono text-xs text-fg-muted tabular">{pct}%</span>}
          {upload?.status === "done" && <StatusIcon status="pass" />}
          {upload?.status === "error" && <StatusIcon status="fail" />}
          <Button size="sm" variant={upload ? "ghost" : "secondary"} onClick={() => input.current?.click()} disabled={upload?.status === "uploading"}>
            {upload ? <RotateCcw /> : <FileUp />}
            {upload ? "Replace" : "Choose file"}
          </Button>
        </span>
      </div>
      {upload?.status === "uploading" && (
        <div
          role="progressbar"
          aria-label={`Uploading ${upload.file?.name}`}
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
          className="h-1 overflow-hidden rounded-full bg-line"
        >
          <div className="h-full bg-accent transition-[width] duration-(--duration-fast)" style={{ width: `${pct}%` }} />
        </div>
      )}
      {upload?.status === "uploading" && (
        <span className="font-mono text-[11px] text-fg-faint tabular">
          {(upload.sent / 1e6).toFixed(1)} / {(upload.total / 1e6).toFixed(1)} MB
        </span>
      )}
      {upload?.status === "error" && <p className="text-sm text-critical">{upload.error}</p>}
      {m && (
        <dl className="flex flex-wrap gap-x-4 gap-y-1 font-mono text-xs text-fg-muted">
          <Meta k="date" v={formatDate(m.acquired_at) ?? "not in metadata"} />
          <Meta k="type" v={MODALITY_LABEL[m.modality]} tone={tone} />
          <Meta k="crs" v={m.crs ?? "none"} />
          <Meta k="gsd" v={m.gsd_m ? `${m.gsd_m} m` : "unknown"} />
          <Meta k="bands" v={String(m.band_count)} />
          <Meta k="size" v={`${m.width}×${m.height}`} />
        </dl>
      )}
      <input
        ref={input}
        type="file"
        hidden
        accept={ACCEPT}
        onChange={(e) => {
          const f = e.target.files?.[0];
          e.target.value = "";
          if (f) onPick(f);
        }}
      />
    </li>
  );
}

function Meta({ k, v, tone }: { k: string; v: string; tone?: "optical" | "sar" | "neutral" }) {
  return (
    <div className="flex gap-1.5">
      <dt className="text-fg-faint">{k}</dt>
      <dd className={cn(tone === "optical" && "text-optical", tone === "sar" && "text-sar")}>{v}</dd>
    </div>
  );
}
