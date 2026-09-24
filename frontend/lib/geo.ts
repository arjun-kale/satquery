/*
 * Geo helpers. Pixel → lon/lat is bilinear across the four corner coordinates the backend
 * derives from the GeoTIFF transform (RasterMetadata.corners_wgs84); for scene-sized UTM
 * crops the error is well under a pixel.
 */

export type Corners = [number, number][];

/** (u, v) in [0, 1] of the scene (x right, y down) → [lon, lat]. */
export function pixelToLonLat(corners: Corners, u: number, v: number): [number, number] {
  const [ul, ur, lr, ll] = corners;
  const top = [ul[0] + (ur[0] - ul[0]) * u, ul[1] + (ur[1] - ul[1]) * u];
  const bottom = [ll[0] + (lr[0] - ll[0]) * u, ll[1] + (lr[1] - ll[1]) * u];
  return [top[0] + (bottom[0] - top[0]) * v, top[1] + (bottom[1] - top[1]) * v];
}

export function formatLonLat([lon, lat]: [number, number], digits = 5): string {
  const ns = lat >= 0 ? "N" : "S";
  const ew = lon >= 0 ? "E" : "W";
  return `${Math.abs(lat).toFixed(digits)}° ${ns}  ${Math.abs(lon).toFixed(digits)}° ${ew}`;
}

/** Areas are always deterministic (pixel counts × GSD²); format them without false precision. */
export function formatArea(m2: number | null | undefined): string | null {
  if (m2 == null || Number.isNaN(m2)) return null;
  if (m2 >= 100_000) return `${(m2 / 1_000_000).toLocaleString(undefined, { maximumFractionDigits: 2 })} km²`;
  return `${Math.round(m2).toLocaleString()} m²`;
}

export function formatPercent(fraction: number, digits = 1): string {
  return `${(fraction * 100).toFixed(digits)}%`;
}

/** A scale bar of about `targetPx` screen pixels with a round length (1, 2 or 5 × 10ⁿ m). */
export function scaleBar(metresPerScreenPx: number, targetPx = 96): { px: number; label: string } | null {
  if (!Number.isFinite(metresPerScreenPx) || metresPerScreenPx <= 0) return null;
  const raw = metresPerScreenPx * targetPx;
  const pow = 10 ** Math.floor(Math.log10(raw));
  const nice = [1, 2, 5, 10].map((m) => m * pow).reduce((best, m) => (Math.abs(m - raw) < Math.abs(best - raw) ? m : best));
  const label = nice >= 1000 ? `${nice / 1000} km` : `${nice} m`;
  return { px: nice / metresPerScreenPx, label };
}

export function formatDate(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = new Date(`${iso.slice(0, 10)}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" });
}

export function formatSeconds(ms: number | null | undefined): string {
  if (ms == null) return "";
  return ms < 1000 ? `${(ms / 1000).toFixed(2)} s` : `${(ms / 1000).toFixed(1)} s`;
}
