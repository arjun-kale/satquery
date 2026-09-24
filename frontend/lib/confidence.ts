/*
 * The single mapping from a confidence number to words (UX brief §F4). Shown verbatim in the
 * trace drawer so the Verifier can see exactly how "Likely" was decided.
 *
 * The VLM's confidence is the geometric-mean probability of its generated tokens under greedy
 * decoding (modal_worker/infer.py). It measures how sure the model was of its own wording, not
 * whether the answer is true — the UI says so wherever the number appears.
 */

import type { ConfidenceSource } from "./types";

export type ConfidenceWord = "High confidence" | "Likely" | "Needs review" | "Unable to determine";

/** Line style on the image carries confidence, so it survives greyscale and colour blindness. */
export type LineStyle = "solid" | "dashed" | "dotted" | "dashdot";

export interface ConfidenceBand {
  min: number;
  word: ConfidenceWord;
  steps: 1 | 2 | 3 | 4;
  line: LineStyle;
}

export const CONFIDENCE_BANDS: ConfidenceBand[] = [
  { min: 0.8, word: "High confidence", steps: 4, line: "solid" },
  { min: 0.6, word: "Likely", steps: 3, line: "dashed" },
  { min: 0.4, word: "Needs review", steps: 2, line: "dotted" },
  { min: 0, word: "Unable to determine", steps: 1, line: "dotted" },
];

export const CONFIDENCE_METHOD = "Geometric-mean token probability of the model's own output (greedy decoding).";

export type ConfidenceView =
  | { available: true; value: number; band: ConfidenceBand; source: ConfidenceSource }
  | { available: false; reason: string };

export function confidenceView(value: unknown, source: unknown, isMock: boolean): ConfidenceView {
  if (isMock) return { available: false, reason: "Confidence not available — mock model" };
  if (source !== "model-provided" && source !== "rule-derived")
    return { available: false, reason: "Confidence not available for this tool" };
  if (typeof value !== "number" || Number.isNaN(value))
    return { available: false, reason: "Confidence not available for this tool" };
  const band = CONFIDENCE_BANDS.find((b) => value >= b.min) ?? CONFIDENCE_BANDS[CONFIDENCE_BANDS.length - 1];
  return { available: true, value, band, source };
}

export const DASH: Record<LineStyle, string | undefined> = {
  solid: undefined,
  dashed: "7 4",
  dotted: "1.5 3.5",
  dashdot: "8 3 1.5 3",
};
