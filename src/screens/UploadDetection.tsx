import { Play, CheckCircle2 } from "lucide-react";
import { mediaItem, detectionResult } from "../data/caseData";
import { Panel, PanelHeader, ConfidenceBar, Notice, StatusBadge } from "../components/ui";
import UploadDropzone from "../components/UploadDropzone";
import { useUpload } from "../context/UploadContext";

export default function UploadDetection() {
  const { result } = useUpload();
  const live = !!result;

  return (
    <div className="space-y-6">
      {/* Description header section */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-card border border-border rounded-2xl p-5 sm:p-6 shadow-card">
        <div>
          <h2 className="text-xl font-semibold tracking-[-.02em] text-ink">Detection Analysis</h2>
          <p className="text-[13px] text-muted mt-1 leading-relaxed">
            Assess manipulation likelihood with an explanation — never a bare fake/real verdict.
          </p>
        </div>
        <div className="shrink-0">
          <StatusBadge tone="amber">Evidence Building</StatusBadge>
        </div>
      </div>

      <UploadDropzone />

      <div className="grid xl:grid-cols-[.9fr_1.2fr_.8fr] gap-5">
        <Panel className="p-5 sm:p-6 flex flex-col justify-between">
          <div>
            <PanelHeader title={live ? "Your Upload" : "Uploaded Media"} subtitle={live ? result!.fileName : mediaItem.filename} />
            <div className="h-[320px] sm:h-[360px] rounded-xl bg-brandDark relative flex items-center justify-center overflow-hidden shadow-inner">
              {live ? (
                <img src={result!.previewUrl} className="w-full h-full object-cover" alt="Uploaded frame" />
              ) : (
                <>
                  <div className="h-20 w-20 rounded-full border border-white/20 flex items-center justify-center bg-black/20 backdrop-blur-xs">
                    <Play className="text-white/80 ml-1" size={30} />
                  </div>
                  <p className="absolute bottom-4 text-[11.5px] text-white/70 bg-black/40 backdrop-blur-md px-3 py-1 rounded-lg">
                    Sample media · 00:{String(mediaItem.durationSec).padStart(2, "0")}
                  </p>
                </>
              )}
            </div>
          </div>
          <div className="mt-5 space-y-2.5 text-[12.5px] pt-4 border-t border-border/60">
            {[
              ["File type", live ? result!.kind : "MP4 (Video)"],
              ["File size", live ? `${result!.fileSizeKB} KB` : "12.4 MB"],
              ["Dimensions", live ? `${result!.width} × ${result!.height}` : "1920 × 1080"],
              ...(!live || result!.frameTimestamp ? [["Frame analyzed", live ? result!.frameTimestamp : "Sample timeline"]] : []),
            ].map(([a, b]) => (
              <div className="flex justify-between border-b border-border/40 pb-2 last:border-0" key={a}>
                <span className="text-muted">{a}</span>
                <span className="font-semibold text-ink">{b}</span>
              </div>
            ))}
          </div>
        </Panel>

        <Panel className="p-5 sm:p-6 flex flex-col justify-between">
          <div>
            <PanelHeader
              title="Manipulation Analysis"
              subtitle={live ? "Live heuristic — not a trained classifier" : "Seeded demonstration result"}
            />
            <div className="flex flex-col sm:flex-row items-center gap-6 mb-7 bg-soft/40 p-4 rounded-xl border border-border/50">
              <div
                className="h-36 w-36 rounded-full flex items-center justify-center shrink-0 shadow-xs"
                style={{
                  background: `conic-gradient(#B96255 ${live ? result!.signalScore : detectionResult.manipulationLikelihood}%, #E9EDE8 0)`,
                }}
              >
                <div className="h-28 w-28 bg-card rounded-full flex flex-col items-center justify-center shadow-xs">
                  <b className="text-[34px] font-semibold text-ink leading-none">
                    {live ? result!.signalScore : detectionResult.manipulationLikelihood}%
                  </b>
                  <span className="text-[10px] text-muted font-medium mt-1">likelihood</span>
                </div>
              </div>
              <div>
                <StatusBadge tone="red">High likelihood</StatusBadge>
                <p className="text-[12.5px] text-ink leading-relaxed mt-3">
                  {live
                    ? "This browser-only score combines pixel edge irregularity and compression density."
                    : "Facial blending inconsistency detected around the jawline, with temporal artifacts across frames."}
                </p>
              </div>
            </div>

            {live ? (
              <div className="space-y-4">
                <ConfidenceBar label="Edge irregularity" value={result!.edgeIrregularity} tone="amber" />
                <ConfidenceBar label="Compression density anomaly" value={result!.compressionDensity} tone="amber" />
                <ConfidenceBar label="Combined signal score" value={result!.signalScore} tone="red" />
              </div>
            ) : (
              <div className="space-y-4">
                <ConfidenceBar label="Manipulation likelihood" value={87} tone="red" />
                <div className="grid grid-cols-2 gap-4 mt-6 pt-4 border-t border-border/60 text-[12px]">
                  <div>
                    <p className="text-muted font-medium">Detection confidence</p>
                    <b className="block mt-1 text-ink">87%</b>
                  </div>
                  <div>
                    <p className="text-muted font-medium">Likely technique</p>
                    <b className="block mt-1 text-ink">Face manipulation</b>
                  </div>
                  <div>
                    <p className="text-muted font-medium">Detected region</p>
                    <b className="block mt-1 text-ink">Face / jawline</b>
                  </div>
                  <div>
                    <p className="text-muted font-medium">Model</p>
                    <b className="block mt-1 text-ink">Pretrained detector</b>
                  </div>
                </div>
              </div>
            )}
          </div>
        </Panel>

        <div className="space-y-5">
          <Panel className="p-5 sm:p-6">
            <PanelHeader title="Frame Analysis" />
            <div className="grid grid-cols-4 gap-2.5">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="aspect-square rounded-xl bg-soft border border-border/60 flex items-center justify-center text-brand font-semibold shadow-xs">
                  <span className="text-[11px] font-mono">F{i}</span>
                </div>
              ))}
            </div>
            <p className="text-[11.5px] text-muted mt-3">Key frames extracted for deep heuristic inspection.</p>
          </Panel>

          <Panel className="p-5 sm:p-6">
            <PanelHeader title="Next Steps" />
            <div className="space-y-3 text-[12.5px]">
              {["Fingerprinting completed", "Add related sources to build evidence", "Review attribution gap analysis", "Generate incident report"].map(
                (x, i) => (
                  <div className="flex items-center gap-3" key={x}>
                    <CheckCircle2 size={16} className={i === 0 ? "text-brand shrink-0" : "text-border shrink-0"} />
                    <span className={i === 0 ? "font-semibold text-ink" : "text-muted"}>{x}</span>
                  </div>
                )
              )}
            </div>
          </Panel>

          <Notice tone="info">
            <b>Important Notice</b>
            <br />
            This analysis provides an indication of likelihood, not definitive proof. Review the evidence and recommended next steps.
          </Notice>
        </div>
      </div>
    </div>
  );
}
