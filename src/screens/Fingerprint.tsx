import { Image, AudioLines, ScanFace, Layers3, Copy, CheckCircle2 } from "lucide-react";
import { fingerprint, sources, mediaItem } from "../data/caseData";
import { Panel, PanelHeader, DemoBadge } from "../components/ui";
import { useUpload } from "../context/UploadContext";

export default function FingerprintScreen() {
  const { result } = useUpload();
  const live = !!result;

  const cards = [
    [Image, "Visual Fingerprint", "Perceptual Hash", live ? result!.averageHash : fingerprint.perceptualHash],
    [AudioLines, "Audio Fingerprint", "Acoustic Hash", fingerprint.audioFingerprint],
    [ScanFace, "Face Embedding", "Facial Feature Vector", fingerprint.faceEmbeddingPreview],
    [Layers3, "Key Frame Fingerprints", "Extracted key frames", "6 frames extracted"],
  ];

  return (
    <div className="space-y-6">
      {/* Action Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-card border border-border rounded-2xl p-5 sm:p-6 shadow-card">
        <div>
          <h2 className="text-xl font-semibold tracking-[-.02em] text-ink">Content Fingerprinting</h2>
          <p className="text-[13px] text-muted mt-1 leading-relaxed">
            Generate digital fingerprints to identify matching or similar content across sources.
          </p>
        </div>
        <button className="rounded-xl bg-brand text-white px-5 py-3 text-[12.5px] font-semibold hover:bg-brandDark transition shrink-0 shadow-sm">
          ＋ Generate Fingerprints
        </button>
      </div>

      {/* Fingerprint Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        {cards.map(([I, t, s, v]: any) => (
          <Panel key={t} className="p-5 sm:p-6 flex flex-col justify-between">
            <div>
              <div className="h-10 w-10 rounded-xl bg-soft text-brand flex items-center justify-center shadow-xs">
                <I size={20} />
              </div>
              <p className="text-[15px] font-semibold text-ink mt-4">{t}</p>
              <p className="text-[11.5px] text-muted mt-1">{s}</p>
            </div>
            <div>
              <div className="mt-4 rounded-xl bg-[#FAFBF9] border border-border/70 p-3 min-h-[74px] flex items-center">
                <span className="font-mono text-[11px] text-ink/90 break-all leading-tight">{v}</span>
              </div>
              <div className="flex items-center gap-2 text-brand font-medium text-[11.5px] mt-4">
                <CheckCircle2 size={15} /> Fingerprint generated
              </div>
            </div>
          </Panel>
        ))}
      </div>

      {/* Similarity Matches & Details */}
      <div className="grid xl:grid-cols-[1.2fr_.8fr] gap-5">
        <Panel className="p-5 sm:p-6">
          <PanelHeader title="Similarity Matches" subtitle="Matching content found across the seeded sources" />
          <div className="space-y-2.5 mt-4">
            {sources.map((s) => (
              <div
                className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-3.5 rounded-xl border border-border/50 hover:bg-soft/40 transition"
                key={s.id}
              >
                <div className="flex items-center gap-3.5">
                  <div className="h-10 w-10 rounded-lg bg-soft flex items-center justify-center text-brand text-[11px] font-bold shrink-0">
                    {s.platform.slice(0, 2)}
                  </div>
                  <div>
                    <p className="text-[13px] font-semibold text-ink">{s.platform}</p>
                    <p className="text-[11px] text-muted">
                      {s.account} · {s.observedAt}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <div className="w-32">
                    <div className="flex justify-between text-[11.5px]">
                      <b className="text-ink">{s.similarity}%</b>
                      <span className="text-muted">match</span>
                    </div>
                    <div className="h-1.5 bg-[#EEF1ED] rounded-full mt-1 overflow-hidden">
                      <div className="h-full bg-brand rounded-full" style={{ width: `${s.similarity}%` }} />
                    </div>
                  </div>
                  <button className="text-[11.5px] font-medium border border-border rounded-lg px-3.5 py-1.5 hover:bg-soft transition">
                    View
                  </button>
                </div>
              </div>
            ))}
          </div>
        </Panel>

        <div className="space-y-5">
          <Panel className="p-5 sm:p-6">
            <PanelHeader
              title="Fingerprint Details"
              right={
                <button className="text-[11.5px] border border-border rounded-lg px-3 py-1.5 hover:bg-soft transition flex items-center gap-1.5">
                  <Copy size={12} /> Raw Data
                </button>
              }
            />
            <div className="space-y-2.5 text-[12.5px] mt-4">
              {[
                ["File Name", live ? result!.fileName : mediaItem.filename],
                ["File Type", "MP4 (Video)"],
                ["File Size", live ? `${result!.fileSizeKB} KB` : "12.4 MB"],
                ["Resolution", live ? `${result!.width} × ${result!.height}` : "1920 × 1080"],
                ["Duration", "00:24"],
                ["Video Codec", "H.264"],
                ["Audio Codec", "AAC"],
                ["Frame Rate", "30 fps"],
                ["Fingerprint Status", "Complete"],
              ].map(([a, b]) => (
                <div className="flex justify-between border-b border-border/40 pb-2 last:border-0" key={a}>
                  <span className="text-muted">{a}</span>
                  <span className="font-semibold text-ink text-right">{b}</span>
                </div>
              ))}
            </div>
          </Panel>

          <Panel className="p-5 sm:p-6">
            <PanelHeader title="How it works?" />
            <p className="text-[12.5px] text-muted leading-relaxed">
              LINEAGE generates unique digital fingerprints from visual, audio, structural and facial features, then compares those signatures against known or observed sources.
            </p>
            <div className="mt-4">
              <DemoBadge />
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}
