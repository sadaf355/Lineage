/**
 * Case-wide progress, derived ONLY from what the backend has actually stored or is actually doing.
 * Nothing here is estimated: a step is "done" when its data exists, "active" when the live pipeline stage
 * (or a slice's own loading flag) says it is running, "failed" when that slice reported an error, and
 * "pending" otherwise. There are no percentages because the API does not report any.
 */
export type StepKey = "upload" | "detect" | "fingerprint" | "trace" | "preserve" | "gap" | "report";
export type StepState = "done" | "active" | "failed" | "pending" | "skipped";

export type ProgressInput = {
  analysisStage: string | null;
  reportJobStatus?: string | null; // BackgroundJob.status while the report job is polled
  media: { data: { kind?: string } | null; loading: boolean; error: string | null };
  detection: { data: unknown | null; loading: boolean; error: string | null };
  fingerprint: { data: unknown | null; loading: boolean; error: string | null };
  sources: { data: { platform: string }[]; loading: boolean; error: string | null };
  evidence: { data: unknown[]; loading: boolean; error: string | null };
  attributionGap: { data: unknown[]; loading: boolean; error: string | null };
  report: { data: unknown | null; loading: boolean; error: string | null };
};

export type ProgressStep = {
  key: StepKey;
  label: string;
  state: StepState;
  detail: string;
  /** Which investigation tab shows this step. */
  screen: "overview" | "detection" | "fingerprint" | "lineage" | "evidence" | "gap" | "report";
};

const STAGE_TO_STEP: Record<string, StepKey> = {
  creating: "upload", uploading: "upload", detection: "detect", fingerprinting: "fingerprint",
  evidence: "preserve", attribution: "gap", report: "report",
};

const UPLOAD_SOURCE = "User upload";

export function deriveCaseProgress(p: ProgressInput): ProgressStep[] {
  const liveStep = p.analysisStage ? STAGE_TO_STEP[p.analysisStage] : undefined;
  const isAudio = p.media.data?.kind === "audio";
  const externalSources = p.sources.data.filter((s) => s.platform !== UPLOAD_SOURCE).length;

  const mk = (
    key: StepKey, label: string, screen: ProgressStep["screen"],
    done: boolean, loading: boolean, error: string | null, detail: { done: string; active: string; pending: string },
    skipped = false,
  ): ProgressStep => {
    let state: StepState;
    if (skipped) state = "skipped";
    else if (error && !done) state = "failed";
    else if (done) state = "done";
    else if (loading || liveStep === key) state = "active";
    else state = "pending";
    const text = state === "done" ? detail.done : state === "active" ? detail.active : state === "failed" ? (error ?? "Failed") : state === "skipped" ? "Not applicable" : detail.pending;
    return { key, label, state, detail: text, screen };
  };

  const reportActive = p.report.loading || (!!p.reportJobStatus && p.reportJobStatus !== "succeeded" && p.reportJobStatus !== "failed");
  return [
    mk("upload", "Upload", "overview", !!p.media.data, p.media.loading, p.media.error,
      { done: "Media stored and hashed", active: "Uploading and encrypting", pending: "No media uploaded" }),
    mk("detect", "Detect", "detection", !!p.detection.data, p.detection.loading, p.detection.error,
      { done: "Detection result recorded", active: "Detection running on the server", pending: "Not yet run" }, isAudio),
    mk("fingerprint", "Fingerprint", "fingerprint", !!p.fingerprint.data, p.fingerprint.loading, p.fingerprint.error,
      { done: "Fingerprints computed", active: "Computing fingerprints", pending: "Not yet run" }),
    mk("trace", "Trace", "lineage", externalSources > 0, p.sources.loading, p.sources.error,
      { done: `${externalSources} external source${externalSources === 1 ? "" : "s"} recorded`, active: "Loading sources", pending: "No external source recorded" }),
    mk("preserve", "Preserve", "evidence", p.evidence.data.length > 0, p.evidence.loading, p.evidence.error,
      { done: `${p.evidence.data.length} evidence item${p.evidence.data.length === 1 ? "" : "s"} preserved`, active: "Recording evidence", pending: "No evidence preserved" }),
    mk("gap", "Attribution", "gap", p.attributionGap.data.length > 0, p.attributionGap.loading, p.attributionGap.error,
      { done: "Attribution gap generated", active: "Analysing attribution gap", pending: "Not generated" }),
    mk("report", "Report", "report", !!p.report.data, reportActive, p.report.error,
      { done: "Report generated", active: p.reportJobStatus ? `Report job ${p.reportJobStatus}` : "Generating report", pending: "Not generated" }),
  ];
}

export function progressSummary(steps: ProgressStep[]): { done: number; total: number; active: ProgressStep | null } {
  const counted = steps.filter((s) => s.state !== "skipped");
  return { done: counted.filter((s) => s.state === "done").length, total: counted.length, active: steps.find((s) => s.state === "active") ?? null };
}
