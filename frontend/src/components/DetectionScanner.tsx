import { ReactNode } from "react";
import { useCase } from "../context/CaseContext";

/**
 * Scanner overlay for the media preview. It is shown ONLY while the server is genuinely working, i.e. while
 * `analysisStage` is uploading / detection / fingerprinting or the detection request is in flight.
 * It is deliberately indeterminate: the API reports stages, not percentages, so no progress number is drawn.
 */
const STAGE_TEXT: Record<string, string> = {
  uploading: "Encrypting and hashing the upload",
  detection: "Detection model running on the server",
  fingerprinting: "Computing fingerprints",
};

export function useScannerStatus(): { active: boolean; label: string } {
  const { analysisStage, detection, fingerprint, media } = useCase();
  if (analysisStage && STAGE_TEXT[analysisStage]) return { active: true, label: STAGE_TEXT[analysisStage] };
  if (media.loading) return { active: true, label: STAGE_TEXT.uploading };
  if (detection.loading) return { active: true, label: STAGE_TEXT.detection };
  if (fingerprint.loading) return { active: true, label: STAGE_TEXT.fingerprinting };
  return { active: false, label: "" };
}

export default function DetectionScanner({ children }: { children: ReactNode }) {
  const { active, label } = useScannerStatus();
  return (
    <div className="relative">
      {children}
      {active && (
        <div className="pointer-events-none absolute inset-0 overflow-hidden rounded-xl" data-testid="detection-scanner">
          <div className="scan-sweep absolute inset-x-0 top-0 h-1/4 bg-gradient-to-b from-transparent via-[#5fe0a0]/35 to-transparent border-b border-[#5fe0a0]/70" aria-hidden="true" />
          {["left-2 top-2 border-l-2 border-t-2", "right-2 top-2 border-r-2 border-t-2", "left-2 bottom-2 border-l-2 border-b-2", "right-2 bottom-2 border-r-2 border-b-2"].map((c) => (
            <span key={c} aria-hidden="true" className={`absolute h-5 w-5 border-[#5fe0a0] ${c}`} />
          ))}
          <p role="status" className="absolute bottom-3 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-full bg-black/70 px-3 py-1 text-[11px] font-medium text-white">
            {label}…
          </p>
        </div>
      )}
    </div>
  );
}
