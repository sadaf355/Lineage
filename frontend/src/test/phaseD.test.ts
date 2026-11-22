import { describe, it, expect } from "vitest";
import { deriveCaseProgress, progressSummary } from "../lib/caseProgress";
import { hexToBits, gridColumns, popcount } from "../lib/hashBits";
import { connectedIds, nodeOpacity, edgeState } from "../lib/graphFocus";
import { filterCommands, score } from "../lib/commandSearch";

const s = <T,>(data: T) => ({ data, loading: false, error: null as string | null });
const empty: any = { analysisStage: null, media: s(null), detection: s(null), fingerprint: s(null), sources: s([] as any[]), evidence: s([] as any[]), attributionGap: s([] as any[]), report: s(null) };

describe("case progress is derived only from real state", () => {
  it("marks nothing done when nothing exists", () => {
    expect(deriveCaseProgress(empty).map((x) => x.state)).toEqual(Array(7).fill("pending"));
  });
  it("follows the live pipeline stage", () => {
    const steps = deriveCaseProgress({ ...empty, analysisStage: "detection", media: s({ kind: "image" }) });
    expect(steps.map((x) => x.state).slice(0, 3)).toEqual(["done", "active", "pending"]);
  });
  it("does not count the investigator's own upload as an external trace", () => {
    const steps = deriveCaseProgress({ ...empty, media: s({ kind: "image" }), sources: s([{ platform: "User upload" }]) });
    expect(steps[3].state).toBe("pending");
  });
  it("skips detection for audio and excludes it from the total", () => {
    const steps = deriveCaseProgress({ ...empty, media: s({ kind: "audio" }) });
    expect(steps[1].state).toBe("skipped");
    expect(progressSummary(steps).total).toBe(6);
  });
  it("surfaces slice errors and report-job status verbatim", () => {
    expect(deriveCaseProgress({ ...empty, detection: { data: null, loading: false, error: "boom" } })[1]).toMatchObject({ state: "failed", detail: "boom" });
    expect(deriveCaseProgress({ ...empty, reportJobStatus: "running" })[6]).toMatchObject({ state: "active", detail: "Report job running" });
  });
});

describe("hash bits", () => {
  it("expands hex to bits and rejects non-hex", () => {
    expect(hexToBits("a5")).toEqual([1, 0, 1, 0, 0, 1, 0, 1]);
    expect(hexToBits("xyz")).toBeNull();
    expect(hexToBits(null)).toBeNull();
    expect(gridColumns(64)).toBe(8);
    expect(popcount(hexToBits("ff00")!)).toBe(8);
  });
});

describe("graph focus", () => {
  const edges = [{ id: "1", fromId: "a", toId: "b" }, { id: "2", fromId: "c", toId: "d" }];
  it("dims everything unrelated to the focused node and nothing when unfocused", () => {
    expect(connectedIds(null, edges)).toBeNull();
    const c = connectedIds("a", edges)!;
    expect([...c].sort()).toEqual(["a", "b"]);
    expect(nodeOpacity("c", c)).toBe(0.25);
    expect(nodeOpacity("b", c)).toBe(1);
    expect(edgeState(edges[0], "a")).toBe("focused");
    expect(edgeState(edges[1], "a")).toBe("dimmed");
    expect(edgeState(edges[1], null)).toBe("idle");
  });
});

describe("command search", () => {
  const cmds = ["Evidence Locker", "Lineage / Propagation", "Settings", "New Investigation"].map((label, i) => ({ id: String(i), label, group: "g", run() {} }));
  it("ranks prefix and word matches first, drops non-matches", () => {
    expect(filterCommands(cmds, "evi")[0].label).toBe("Evidence Locker");
    expect(filterCommands(cmds, "ni")[0].label).toBe("New Investigation");
    expect(filterCommands(cmds, "zzz")).toHaveLength(0);
    expect(filterCommands(cmds, "")).toHaveLength(4);
    expect(score("lp", "Lineage / Propagation")).toBeGreaterThan(0);
  });
});
