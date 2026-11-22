import type { DetectorMetrics, DetectorModelReport } from "./api";

export function formatAuc(auc: number | null | undefined): string {
  return auc === null || auc === undefined ? "n/a" : auc.toFixed(3);
}

/** The condition with the lowest F1, computed from the measured data. Null if there is no breakdown. */
export function weakestCondition(model: DetectorModelReport): { condition: string; f1: number } | null {
  const entries = Object.entries(model.by_condition ?? {}) as [string, DetectorMetrics][];
  if (entries.length === 0) return null;
  const [condition, m] = entries.reduce((lo, cur) => (cur[1].f1 < lo[1].f1 ? cur : lo));
  return { condition, f1: m.f1 };
}

/** Plain-language names so the table reads without knowing the file naming. */
export const CONDITION_LABELS: Record<string, string> = {
  original: "Original",
  jpeg_q50: "JPEG quality 50",
  resize_50: "Resized to 50%",
  crop_80: "80% centre crop",
  screenshot: "Screenshot-style re-encode",
};

export function conditionLabel(key: string): string {
  return CONDITION_LABELS[key] ?? key;
}
