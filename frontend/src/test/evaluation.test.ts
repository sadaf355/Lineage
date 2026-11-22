import { describe, expect, it } from "vitest";
import { conditionLabel, formatAuc, weakestCondition } from "../lib/evaluation";
import type { DetectorMetrics, DetectorModelReport } from "../lib/api";

const m = (f1: number): DetectorMetrics => ({
  samples: 10, accuracy: f1, precision: f1, recall: f1, f1, roc_auc: 0.9,
  true_positive: 1, true_negative: 1, false_positive: 0, false_negative: 0, confusion_matrix: [[1, 0], [0, 1]],
});

describe("detector evaluation helpers", () => {
  it("finds the weakest condition from measured data", () => {
    const model: DetectorModelReport = { rows_total: 30, unscored: 0, by_condition: { original: m(95), jpeg_q50: m(71), crop_80: m(88) } };
    expect(weakestCondition(model)).toEqual({ condition: "jpeg_q50", f1: 71 });
  });
  it("returns null when there is no per-condition breakdown", () => {
    expect(weakestCondition({ rows_total: 0, unscored: 0 })).toBeNull();
  });
  it("formats a missing AUC as n/a instead of 0", () => {
    expect(formatAuc(null)).toBe("n/a");
    expect(formatAuc(0.91234)).toBe("0.912");
  });
  it("falls back to the raw key for unknown conditions", () => {
    expect(conditionLabel("screenshot")).toBe("Screenshot-style re-encode");
    expect(conditionLabel("night_mode")).toBe("night_mode");
  });
});
