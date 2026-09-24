import type {
  HealthResponse,
  IngestResponse,
  JobRecord,
  LoadedSample,
  RasterMetadata,
  Sample,
  SceneSetKind,
  TaskType,
  TraceResponse,
  ValidateResponse,
} from "./types";

export const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** Absolute URL for a backend path such as "/api/jobs/…/artifacts/preview.png". */
export function assetUrl(path: string): string {
  return path.startsWith("http") ? path : `${API_BASE}${path}`;
}

export function previewUrl(imageId: string): string {
  return `${API_BASE}/api/images/${imageId}/preview.png`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, init);
  } catch {
    throw new ApiError("Can't reach the SatQuery backend.", 0, "NETWORK");
  }
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(detailMessage(body) ?? `Request failed (${res.status})`, res.status, detailCode(body));
  return body as T;
}

function detailMessage(body: unknown): string | null {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && "message" in detail) return String((detail as { message: unknown }).message);
  return null;
}

function detailCode(body: unknown): string | undefined {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (detail && typeof detail === "object" && "code" in detail) return String((detail as { code: unknown }).code);
  return undefined;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  health: (signal?: AbortSignal) => request<HealthResponse>("/health", { signal }),
  samples: () => request<Sample[]>("/api/samples"),
  loadSample: (id: string) => request<LoadedSample>(`/api/samples/${id}/load`, { method: "POST" }),
  imageMetadata: (id: string) => request<RasterMetadata>(`/api/images/${id}`),
  validate: (kind: SceneSetKind, imageIds: string[]) =>
    request<ValidateResponse>("/api/scene-sets/validate", json({ kind, image_ids: imageIds })),
  createJob: (body: { image_ids: string[]; query: string; scene_set_kind: SceneSetKind; task?: TaskType }) =>
    request<JobRecord>("/api/jobs", json(body)),
  trace: (jobId: string) => request<TraceResponse>(`/api/jobs/${jobId}/trace`),
  cancel: (jobId: string) => request<JobRecord>(`/api/jobs/${jobId}/cancel`, { method: "POST" }),
};

/**
 * Upload one raster with real byte-level progress (fetch can't report upload progress).
 */
export function uploadRaster(
  file: File,
  onProgress: (sent: number, total: number) => void,
  signal?: AbortSignal,
): Promise<IngestResponse> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}/api/ingest`);
    xhr.responseType = "json";
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(e.loaded, e.total);
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve(xhr.response as IngestResponse);
      else reject(new ApiError(detailMessage(xhr.response) ?? `Upload failed (${xhr.status})`, xhr.status, detailCode(xhr.response)));
    };
    xhr.onerror = () => reject(new ApiError("Can't reach the SatQuery backend.", 0, "NETWORK"));
    xhr.onabort = () => reject(new ApiError("Upload cancelled.", 0, "ABORTED"));
    signal?.addEventListener("abort", () => xhr.abort());
    const form = new FormData();
    form.append("file", file);
    xhr.send(form);
  });
}
