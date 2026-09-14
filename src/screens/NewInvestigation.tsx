import { useRef, useState } from "react";
import { UploadCloud, Link2, Search, Fingerprint, FileText, Lock, ArrowRight, CheckCircle2 } from "lucide-react";
import { ScreenKey } from "../components/Sidebar";
import { Panel, SectionTitle, PrimaryButton } from "../components/ui";
import { useUpload } from "../context/UploadContext";

export default function NewInvestigation({ onNavigate }: { onNavigate: (k: ScreenKey) => void }) {
  const { upload, isAnalyzing, result, error } = useUpload();
  const [mode, setMode] = useState<"file" | "url">("file");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const ref = useRef<HTMLInputElement>(null);

  const submit = () => {
    if (result) onNavigate("overview");
    else if (!isAnalyzing) onNavigate("detection");
  };

  return (
    <div className="max-w-[1250px] mx-auto space-y-6">
      <SectionTitle
        eyebrow="Investigation"
        title="Start a New Investigation"
        description="Upload suspicious media or provide a source link. LINEAGE will analyze the content and create an evidence trail."
      />

      <div className="flex items-center mb-8 max-w-3xl overflow-x-auto pb-2">
        <Step n="01" t="Upload Media" active />
        <Line />
        <Step n="02" t="Analysis" />
        <Line />
        <Step n="03" t="Evidence Building" />
        <Line />
        <Step n="04" t="Review & Report" />
      </div>

      <div className="grid xl:grid-cols-[1.5fr_1fr] gap-6 items-start">
        {/* Left Column: Form & Dropzone */}
        <Panel className="p-6 sm:p-8 space-y-6">
          <div>
            <h2 className="text-lg font-semibold text-ink">Case Information</h2>
            <p className="text-[12.5px] text-muted mt-1">Provide details to identify and organize this investigation.</p>
          </div>

          <div>
            <label className="block text-[12.5px] font-semibold text-ink mb-2">
              Incident Title <span className="text-[#B96255]">*</span>
            </label>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Riya's Case"
              className="w-full h-11 rounded-xl border border-border bg-card px-4 text-[13px] outline-none focus:ring-2 focus:ring-brand/20 transition"
            />
          </div>

          <div>
            <label className="block text-[12.5px] font-semibold text-ink mb-2">
              Description <span className="text-muted font-normal">(Optional)</span>
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Add any details you want to include (where you found the content, when you saw it, etc.)"
              className="w-full min-h-[110px] rounded-xl border border-border bg-card px-4 py-3 text-[13px] outline-none resize-none focus:ring-2 focus:ring-brand/20 transition leading-relaxed"
            />
          </div>

          <div className="pt-4 border-t border-border/60">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-ink">Add Media</h3>
              <span className="text-[11.5px] text-muted font-medium">Max 500 MB</span>
            </div>

            <div className="flex gap-2 border-b border-border/60 pb-px mb-5">
              <button
                onClick={() => setMode("file")}
                className={`px-4 py-2.5 text-[12.5px] font-medium border-b-2 transition ${
                  mode === "file" ? "border-brand text-brand font-semibold" : "border-transparent text-muted hover:text-ink"
                }`}
              >
                <UploadCloud size={15} className="inline mr-2" />
                Upload File
              </button>
              <button
                onClick={() => setMode("url")}
                className={`px-4 py-2.5 text-[12.5px] font-medium border-b-2 transition ${
                  mode === "url" ? "border-brand text-brand font-semibold" : "border-transparent text-muted hover:text-ink"
                }`}
              >
                <Link2 size={15} className="inline mr-2" />
                Paste URL
              </button>
            </div>

            {mode === "file" ? (
              <div
                onClick={() => ref.current?.click()}
                className="min-h-[240px] rounded-2xl border-2 border-dashed border-[#BAC4BB] bg-[#FAFBF9] p-6 flex flex-col items-center justify-center text-center hover:bg-soft/50 transition cursor-pointer group shadow-xs"
              >
                <input
                  ref={ref}
                  type="file"
                  accept="image/*,video/*,audio/*"
                  className="hidden"
                  onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
                />
                {isAnalyzing ? (
                  <>
                    <div className="h-14 w-14 rounded-full bg-soft flex items-center justify-center text-brand">
                      <Search size={24} className="animate-pulse" />
                    </div>
                    <p className="font-semibold text-ink text-[15px] mt-4">Analyzing media…</p>
                    <p className="text-[12.5px] text-muted mt-1">Preparing your evidence trail</p>
                  </>
                ) : result ? (
                  <>
                    <div className="h-14 w-14 rounded-full bg-soft flex items-center justify-center text-brand">
                      <CheckCircle2 size={26} />
                    </div>
                    <p className="font-semibold text-ink text-[15px] mt-4">{result.fileName}</p>
                    <p className="text-[12.5px] text-muted mt-1">Analysis ready — continue to review</p>
                  </>
                ) : (
                  <>
                    <div className="h-14 w-14 rounded-full bg-soft flex items-center justify-center text-brand group-hover:scale-105 transition-transform">
                      <UploadCloud size={26} />
                    </div>
                    <p className="font-semibold text-ink text-[15px] mt-4">Drag & drop your file here</p>
                    <p className="text-[12.5px] text-muted mt-1">Supports images, videos and audio files</p>
                    <span className="my-3 text-[11.5px] text-faint font-medium">or</span>
                    <span className="rounded-xl bg-brand text-white px-5 py-2.5 text-[12.5px] font-semibold hover:bg-brandDark transition shadow-xs">
                      Browse Files
                    </span>
                    <p className="text-[11px] text-faint mt-4">JPG, PNG, MP4, MOV, AVI, MP3, WAV</p>
                  </>
                )}
              </div>
            ) : (
              <div className="p-4 rounded-xl border border-border bg-[#FAFBF9] space-y-3">
                <div className="flex gap-3 items-center">
                  <Link2 className="text-brand shrink-0" size={20} />
                  <input
                    placeholder="https://example.com/source"
                    className="flex-1 h-11 rounded-xl border border-border bg-card px-4 text-[13px] outline-none focus:ring-2 focus:ring-brand/20 transition"
                  />
                </div>
                <p className="text-[11.5px] text-muted leading-relaxed">
                  A source URL is stored as an investigation lead; this prototype does not perform live cross-platform discovery.
                </p>
              </div>
            )}

            {error && <p className="text-[12.5px] font-medium text-[#8A4138] mt-3">{error}</p>}
          </div>
        </Panel>

        {/* Right Column: "What happens next?" & Privacy */}
        <div className="space-y-5">
          {/* What happens next Card */}
          <Panel className="p-6 sm:p-7 space-y-5">
            <h2 className="text-lg font-semibold text-ink pb-2 border-b border-border/50">What happens next?</h2>

            <div className="space-y-4">
              {[
                [Search, "AI Analysis", "Detect manipulation and return a likelihood score with an explanation."],
                [Fingerprint, "Fingerprinting", "Generate digital signatures for similarity matching."],
                [FileText, "Evidence Building", "Preserve sources and organize evidence."],
                [CheckCircle2, "Review & Report", "Understand the attribution gap and generate a structured report."],
              ].map(([I, t, d]: any, i) => (
                <div key={t} className="flex gap-3.5 items-start pb-3.5 border-b border-border/40 last:border-0 last:pb-0">
                  <div className="h-10 w-10 shrink-0 rounded-full bg-soft flex items-center justify-center text-brand mt-0.5 shadow-xs">
                    <I size={18} />
                  </div>
                  <div>
                    <p className="text-[13.5px] font-semibold text-ink">
                      {i + 1}. {t}
                    </p>
                    <p className="text-[12.5px] text-muted leading-relaxed mt-1">{d}</p>
                  </div>
                </div>
              ))}
            </div>
          </Panel>

          {/* Privacy Matters Card */}
          <Panel className="p-6 sm:p-7 bg-[#F8F1EC] border-[#E8D8CE]">
            <div className="flex gap-4 items-start">
              <div className="h-10 w-10 rounded-xl bg-[#E8D8CE]/60 text-[#765A4D] flex items-center justify-center shrink-0 mt-0.5">
                <Lock size={20} />
              </div>
              <div>
                <h3 className="text-[15px] font-semibold text-[#5A4339]">Your Privacy Matters</h3>
                <p className="text-[12.5px] text-[#765A4D] leading-relaxed mt-1.5">
                  Your identity is pseudonymous by default. Evidence is handled securely and only included in exports you explicitly request.
                </p>
              </div>
            </div>
          </Panel>

          {/* Action Button */}
          <div className="pt-2 space-y-3">
            <PrimaryButton className="w-full py-3.5 text-[14px] shadow-sm" onClick={submit}>
              {result ? "Continue Investigation" : "Begin Analysis"}
            </PrimaryButton>
            <p className="text-center text-[11.5px] text-muted font-medium">Safe. Secure. Supportive.</p>
          </div>
        </div>
      </div>
    </div>
  );
}

function Step({ n, t, active = false }: { n: string; t: string; active?: boolean }) {
  return (
    <div className="flex flex-col items-center min-w-[85px] shrink-0">
      <div
        className={`h-9 w-9 rounded-full flex items-center justify-center text-[11.5px] font-semibold border transition ${
          active ? "bg-brand text-white border-brand shadow-xs" : "bg-card text-muted border-border"
        }`}
      >
        {n}
      </div>
      <span className={`mt-2 text-[11px] text-center ${active ? "font-semibold text-ink" : "text-muted font-medium"}`}>{t}</span>
    </div>
  );
}

function Line() {
  return <div className="h-px flex-1 bg-border/70 min-w-[20px] mt-4 mx-1.5" />;
}
