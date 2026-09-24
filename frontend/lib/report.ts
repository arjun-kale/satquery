/*
 * Self-contained HTML report (UX brief §F7), built in the browser from the same trace the UI
 * shows. Light theme, printable. Every figure in it is copied from the trace or computed from
 * the evidence geometry — the report adds no claims of its own.
 */

import { CIRCLED, deriveAnswer, deriveEvidence, deriveTimeline, splitModelQuantities, type Evidence } from "./analysis";
import { previewUrl } from "./api";
import { CONFIDENCE_BANDS, CONFIDENCE_METHOD, DASH } from "./confidence";
import { formatArea, formatDate, formatLonLat, formatSeconds, pixelToLonLat } from "./geo";
import type { RasterMetadata } from "./types";
import { MODALITY_LABEL, ROLE, SCENE_SET, TASK } from "./vocabulary";
import type { Analysis, SceneSet } from "@/components/workspace/store";

const esc = (s: unknown) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);

function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error(`Couldn't load ${url}`));
    img.src = url;
  });
}

/** Quick-look with the evidence drawn the same way the viewer draws it (brackets, outlines, markers). */
async function evidenceImage(imageId: string, meta: RasterMetadata, evidence: Evidence[]): Promise<string> {
  const img = await loadImage(previewUrl(imageId));
  const W = 900;
  const H = Math.round((W * meta.height) / meta.width);
  const canvas = document.createElement("canvas");
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d")!;
  ctx.drawImage(img, 0, 0, W, H);

  for (const e of evidence) {
    const [x0, y0, x1, y1] = [e.bbox[0] * W, e.bbox[1] * H, e.bbox[2] * W, e.bbox[3] * H];
    const color = e.tone === "change" ? "#fb923c" : "#f8fafc";
    const path = new Path2D();
    if (e.kind === "box" || !e.rings) {
      const L = Math.max(6, Math.min(18, Math.min(x1 - x0, y1 - y0) * 0.28));
      path.moveTo(x0, y0 + L); path.lineTo(x0, y0); path.lineTo(x0 + L, y0);
      path.moveTo(x1 - L, y0); path.lineTo(x1, y0); path.lineTo(x1, y0 + L);
      path.moveTo(x1, y1 - L); path.lineTo(x1, y1); path.lineTo(x1 - L, y1);
      path.moveTo(x0 + L, y1); path.lineTo(x0, y1); path.lineTo(x0, y1 - L);
    } else {
      for (const ring of e.rings) {
        ring.forEach(([u, v], i) => (i ? path.lineTo(u * W, v * H) : path.moveTo(u * W, v * H)));
        path.closePath();
      }
    }
    ctx.lineJoin = "round";
    ctx.setLineDash([]);
    ctx.strokeStyle = "rgba(0,0,0,0.75)";
    ctx.lineWidth = e.kind === "box" ? 4 : 3.5;
    ctx.stroke(path);
    ctx.strokeStyle = color;
    ctx.lineWidth = e.kind === "box" ? 2 : 1.5;
    ctx.setLineDash(DASH[e.line]?.split(" ").map(Number) ?? []);
    ctx.stroke(path);

    const mx = Math.max(11, x0 - 12);
    const my = Math.max(11, y0 - 12);
    ctx.setLineDash([]);
    ctx.beginPath();
    ctx.arc(mx, my, 9.5, 0, Math.PI * 2);
    ctx.fillStyle = "#0a0e14";
    ctx.fill();
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.stroke();
    ctx.fillStyle = color;
    ctx.font = "600 11px 'JetBrains Mono', monospace";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(String(e.n), mx, my + 0.5);
  }
  return canvas.toDataURL("image/png");
}

export async function buildReport(analysis: Analysis, set: SceneSet): Promise<Blob> {
  const trace = analysis.trace!;
  const answer = deriveAnswer(trace);
  const evidence = deriveEvidence(trace);
  const rows = deriveTimeline(trace, false);
  const images = await Promise.all(set.scenes.map((s) => evidenceImage(s.imageId, s.metadata, evidence)));
  const corners = set.scenes[0].metadata.corners_wgs84;
  const conf = answer.confidence;
  const task = trace.canonical_template_id ? TASK[trace.canonical_template_id].label : "–";
  const generated = new Date().toISOString();
  const segments = answer.text && answer.tool !== "cross_modal_fusion" ? splitModelQuantities(answer.text) : null;
  const stated = segments?.some((s) => s.quantity);
  const leadHtml = answer.lead ? `<p class="answer">${esc(answer.lead)}</p><p class="muted" style="font-size:12px">Measured from pixels — every number in this sentence comes from the rasters, not from a model.</p>` : "";
  const answerHtml = answer.text
    ? `<p class="answer">${(segments ?? [{ text: answer.text, quantity: false }]).map((s) => (s.quantity ? `<span class="stated">${esc(s.text)}</span>` : esc(s.text))).join("")}</p>${stated ? `<p class="muted" style="font-size:12px">Dotted-underlined numbers are the model's own wording, not measurements; measured values are listed under “Measured from pixels”.</p>` : ""}`
    : `<p class="answer">Unable to determine an answer from these images.</p>`;

  const evidenceRows = evidence
    .map((e) => {
      const centre = corners ? formatLonLat(pixelToLonLat(corners, (e.bbox[0] + e.bbox[2]) / 2, (e.bbox[1] + e.bbox[3]) / 2)) : "not georeferenced";
      return `<tr><td class="mono">${CIRCLED[e.n - 1]}</td><td>${esc(e.title)}</td><td>${esc(e.honesty)}</td><td class="mono">${esc(formatArea(e.areaM2) ?? "–")}</td><td class="mono">${esc(centre)}</td><td>${esc(e.confidence.available ? `${e.confidence.band.word} (${e.confidence.value.toFixed(2)})` : e.confidence.reason)}</td><td class="mono">step ${e.producedBy.index + 1} · ${esc(e.producedBy.tool)}</td></tr>`;
    })
    .join("");

  const sceneRows = set.scenes
    .map((s) => {
      const m = s.metadata;
      return `<tr><td>${esc(ROLE[s.role].long)}</td><td>${esc(m.filename)}</td><td>${esc(formatDate(m.acquired_at) ?? "–")}</td><td>${esc(MODALITY_LABEL[m.modality])}</td><td class="mono">${esc(m.sensor_tags.sensor ?? "–")}</td><td class="mono">${esc(m.crs ?? "none")}</td><td class="mono">${esc(m.gsd_m ? `${m.gsd_m} m` : "–")}</td><td class="mono">${m.width}×${m.height} · ${m.band_count} bands</td><td class="mono">${esc(m.checksum_sha256.slice(0, 16))}…</td></tr>`;
    })
    .join("");

  const stepRows = rows
    .map((r, i) => `<tr><td class="mono">${i + 1}</td><td>${esc(r.label)}${r.simulated ? " <em>(placeholder — no computation)</em>" : ""}</td><td class="mono">${esc(r.tool)}</td><td class="mono">${esc(r.model ?? "–")}</td><td>${esc(r.status)}</td><td class="mono">${esc(formatSeconds(r.ms))}</td></tr>`)
    .join("");

  const measured = answer.measured.map((m) => `<tr><td>${esc(m.label)}</td><td class="mono">${esc(m.value)}</td><td>${esc(m.method)}</td></tr>`).join("");

  const html = `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>SatQuery report — ${esc(analysis.question)}</title>
<style>
  :root { --fg:#0f172a; --muted:#475569; --faint:#94a3b8; --line:#e2e8f0; --bg:#ffffff; --panel:#f8fafc; --warn:#b45309; }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--fg); font:14px/1.55 Inter, system-ui, sans-serif; }
  main { max-width: 980px; margin: 0 auto; padding: 40px 24px 64px; }
  h1 { font-size:24px; margin:0 0 4px; } h2 { font-size:16px; margin:32px 0 10px; } .muted { color:var(--muted); }
  .mono { font-family: "JetBrains Mono", ui-monospace, monospace; font-size:12px; font-variant-numeric: tabular-nums; }
  .answer { font-size:18px; line-height:1.6; margin: 8px 0; }
  .stated { text-decoration: underline dotted #b45309 2px; text-underline-offset: 4px; color: var(--muted); }
  .warn { border:1px solid #fcd34d; background:#fffbeb; color:var(--warn); padding:8px 12px; border-radius:6px; }
  table { width:100%; border-collapse:collapse; font-size:13px; } th, td { text-align:left; vertical-align:top; padding:6px 8px; border-top:1px solid var(--line); }
  th { color:var(--muted); font-weight:500; font-size:12px; }
  .figs { display:grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap:12px; }
  figure { margin:0; } figure img { width:100%; border-radius:6px; display:block; background:#0a0e14; } figcaption { color:var(--muted); font-size:12px; margin-top:4px; }
  pre { background:var(--panel); border:1px solid var(--line); border-radius:6px; padding:12px; overflow:auto; font-size:11px; max-height:600px; }
  dl { display:grid; grid-template-columns: max-content 1fr; gap:4px 16px; margin:0; } dt { color:var(--muted); }
  @media print { details { display:none; } main { padding:0; } }
</style></head>
<body><main>
  <p class="muted mono">SatQuery AI · analysis report · generated ${esc(generated)}</p>
  <h1>${esc(analysis.question)}</h1>
  <p class="muted">${esc(SCENE_SET[set.kind].label)} · ${esc(set.title)}${set.source ? ` · ${esc(set.source)}` : ""}</p>

  <h2>Answer</h2>
  ${answer.isMock ? `<p class="warn">Produced in mock mode: the answer text and any model boxes or masks are placeholders, not a reading of these images. Measured values are computed from the pixels.</p>` : ""}
  ${leadHtml}${answer.lead && answer.text ? `<h3 style="font-size:13px;margin:16px 0 4px" class="muted">Model description${answer.note ? ` · ${esc(answer.note)}` : ""}</h3>` : ""}${answerHtml}
  <dl>
    <dt>Confidence</dt><dd>${esc(conf.available ? `${conf.band.word} (${conf.value.toFixed(2)})` : conf.reason)}</dd>
    <dt>Question type</dt><dd>${esc(task)} · ${esc(trace.routing_mode)} · similarity ${esc(trace.similarity_score?.toFixed(3) ?? "–")}</dd>
    <dt>Model mode</dt><dd class="mono">${esc(trace.model_mode ?? "unknown")}</dd>
  </dl>

  ${measured ? `<h2>Measured from pixels</h2><table><thead><tr><th>Measure</th><th>Value</th><th>Method</th></tr></thead><tbody>${measured}</tbody></table>` : ""}

  <h2>Evidence</h2>
  <div class="figs">${images.map((src, i) => `<figure><img src="${src}" alt="${esc(ROLE[set.scenes[i].role].long)} with evidence"><figcaption>${esc(ROLE[set.scenes[i].role].long)} · ${esc(formatDate(set.scenes[i].metadata.acquired_at) ?? set.scenes[i].metadata.filename)} · quick-look</figcaption></figure>`).join("")}</div>
  ${evidence.length ? `<table style="margin-top:12px"><thead><tr><th>#</th><th>Region</th><th>What the shape is</th><th>Area</th><th>Centre</th><th>Confidence</th><th>Produced by</th></tr></thead><tbody>${evidenceRows}</tbody></table>` : `<p class="muted">This analysis produced no region-level evidence; the answer refers to the whole scene.</p>`}
  <p class="muted" style="font-size:12px">Line style carries confidence: ${CONFIDENCE_BANDS.map((b) => `${esc(b.word)} = ${b.line}`).join(", ")}; not available = dash-dot. ${esc(CONFIDENCE_METHOD)}</p>

  <h2>Scenes</h2>
  <table><thead><tr><th>Role</th><th>File</th><th>Date</th><th>Type</th><th>Sensor</th><th>CRS</th><th>GSD</th><th>Size</th><th>SHA-256</th></tr></thead><tbody>${sceneRows}</tbody></table>

  <h2>Run</h2>
  <table><thead><tr><th>#</th><th>Step</th><th>Tool</th><th>Model</th><th>Status</th><th>Time</th></tr></thead><tbody>${stepRows}</tbody></table>
  <p class="muted mono">job ${esc(analysis.jobId)} · router ${esc(trace.router_version)} · trace schema ${esc(analysis.schemaVersion ?? "unversioned")} · total ${esc(formatSeconds(trace.total_latency_ms))}</p>

  <details><summary>Full trace (JSON)</summary><pre>${esc(JSON.stringify({ schema_version: analysis.schemaVersion, job_id: analysis.jobId, status: analysis.status, trace }, null, 2))}</pre></details>
</main></body></html>`;

  return new Blob([html], { type: "text/html" });
}
