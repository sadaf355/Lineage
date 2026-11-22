import { Image, AudioLines, ScanFace, Layers3, CheckCircle2, ShieldCheck, Copy, Check, Trash2 } from "lucide-react";
import { useState } from "react";
import { api } from "../lib/api";
import { Panel, PanelHeader } from "../components/ui";
import { useCase } from "../context/CaseContext";
import { toDisplaySources, parseFaceEmbedding } from "../lib/adapters";
import HashGrid from "../components/HashGrid";
import { AnimatedNumber, Reveal, Stagger, StaggerItem } from "../components/motion";

export default function FingerprintScreen() {
  const { fingerprint: fpSlice, media, sources: sourcesSlice, incidentId, refreshAll } = useCase();
  const fp = fpSlice.data;
  const sources = toDisplaySources(sourcesSlice.data).filter((source) => source.platform !== "User upload");
  const face = parseFaceEmbedding(fp?.face_embedding_json ?? null);
  const [integrity, setIntegrity] = useState<{verified:boolean;stored_sha256:string|null;actual_sha256:string}|null>(null);
  const [integrityBusy, setIntegrityBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const [reverseSearch, setReverseSearch] = useState<any>(null);
  const [reverseBusy, setReverseBusy] = useState(false);
  async function verifyIntegrity(){ if(!media.data || !incidentId) return; setIntegrityBusy(true); try{ setIntegrity(await api.verifyMediaIntegrity(incidentId, media.data.id)); } finally { setIntegrityBusy(false); } }

  const keyframeCount = (() => {
    if (!fp?.keyframe_hashes_json) return null;
    try { return (JSON.parse(fp.keyframe_hashes_json) as unknown[]).length; } catch { return null; }
  })();

  const cards = [
    [Image, "Visual Fingerprint", "pHash + dHash + aHash", fp?.perceptual_hash ? `${fp.perceptual_hash} · ${fp.difference_hash ?? "—"}` : fp?.average_hash ?? "—"],
    [AudioLines, "Audio Fingerprint", "Spectrogram provenance", fp?.audio_fingerprint ?? (media.data?.kind === "audio" ? "Available after fingerprinting" : "Not applicable")],
    [
      ScanFace,
      "Face Embedding",
      face.foundFace ? `Real ${face.dims}-dim vector` : "Facial Feature Vector",
      face.foundFace ? face.preview : fp ? "No face detected in this media" : "—",
    ],
    [
      Layers3,
      "Key Frame Fingerprints",
      "Extracted key frames",
      keyframeCount != null ? <><AnimatedNumber value={keyframeCount} /> {keyframeCount === 1 ? "frame" : "frames"} extracted</> : "Single frame",
    ],
  ];

  return (
    <div className="space-y-6">
      {/* Action Header */}
      <Reveal className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-card border border-border rounded-2xl p-5 sm:p-6 shadow-card">
        <div>
          <h2 className="text-xl font-semibold tracking-[-.02em] text-ink">Content Fingerprinting</h2>
          <p className="text-[13px] text-muted mt-1 leading-relaxed">
            Fingerprints describe this upload. External similarity is not automatically calculated in this build.
          </p>
        </div>
        <span className="text-[11.5px] text-muted">Generated automatically after upload</span>
      </Reveal>


      <Reveal delay={0.05}>
      <Panel className="p-5 sm:p-6 border-brand/20 bg-gradient-to-br from-card to-soft/35">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-5">
          <div className="flex items-start gap-4">
            <div className="h-11 w-11 rounded-2xl bg-soft text-brand flex items-center justify-center shrink-0"><ShieldCheck size={21}/></div>
            <div><p className="text-[15px] font-semibold text-ink">Original file integrity</p><p className="text-[11.5px] text-muted mt-1">SHA-256 is calculated on upload and can be re-verified against the stored bytes.</p></div>
          </div>
          <div className="flex items-center gap-2">
            {media.data?.sha256 && <button onClick={async()=>{await navigator.clipboard?.writeText(media.data!.sha256!);setCopied(true);setTimeout(()=>setCopied(false),1200)}} className="h-10 px-3 rounded-xl border border-border bg-card text-[11px] font-medium inline-flex items-center gap-2"><Copy size={14}/>{copied?"Copied":"Copy hash"}</button>}
            <button onClick={verifyIntegrity} disabled={integrityBusy || !media.data} className="h-10 px-4 rounded-xl bg-brand text-white text-[11px] font-semibold disabled:opacity-50">{integrityBusy?"Verifying…":"Verify integrity"}</button>
            {media.data && <button onClick={async()=>{ if(!incidentId || !window.confirm("Delete this media and its encrypted file? This cannot be undone.")) return; await api.deleteMedia(incidentId, media.data!.id); await refreshAll(); }} className="h-10 px-3 rounded-xl border border-[#E9D4D0] text-[#8A4138] text-[11px] font-semibold inline-flex items-center gap-2"><Trash2 size={14}/> Delete file</button>}
          </div>
        </div>
        {media.data?.sha256 && <div className="mt-4 rounded-xl border border-border bg-card/70 p-3 font-mono text-[10px] break-all text-muted">{media.data.sha256}</div>}
        {integrity && <div className={`mt-3 rounded-xl p-3 text-[11px] font-semibold ${integrity.verified?"bg-soft text-brand":"bg-red text-[#8A4138]"}`}>{integrity.verified?<><Check size={14} className="inline mr-1"/>Integrity verified — stored bytes match the original SHA-256.</>:"Integrity mismatch — do not rely on this file without review."}</div>}
      </Panel>
      </Reveal>

      {fp && (fp.perceptual_hash || fp.difference_hash || fp.average_hash) && (
        <Reveal delay={0.1}>
          <Panel className="p-5 sm:p-6">
            <PanelHeader title="Visual hash, bit by bit" subtitle="Each square is one bit of the real hash stored for this upload. Similar images differ in few bits." />
            <div className="mt-5 grid grid-cols-3 gap-4 sm:gap-8">
              <HashGrid label="pHash" hex={fp.perceptual_hash} />
              <HashGrid label="dHash" hex={fp.difference_hash} />
              <HashGrid label="aHash" hex={fp.average_hash} />
            </div>
          </Panel>
        </Reveal>
      )}

      {/* Fingerprint Cards Grid */}
      <Stagger className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        {cards.map(([I, t, s, v]: any) => (
          <StaggerItem key={t} className="[&>*]:h-full"><Panel className="p-5 sm:p-6 flex flex-col justify-between">
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
              <div className={`flex items-center gap-2 font-medium text-[11.5px] mt-4 ${t === "Audio Fingerprint" && !fp?.audio_fingerprint ? "text-muted" : "text-brand"}`}>
                {t === "Audio Fingerprint" && !fp?.audio_fingerprint ? null : <CheckCircle2 size={15} />}
                {t === "Audio Fingerprint" ? (fp?.audio_fingerprint ? "Computed from this upload" : "Available for audio media") : fp ? "Computed from this upload" : fpSlice.loading ? "Computing…" : "Not computed"}
              </div>
            </div>
          </Panel></StaggerItem>
        ))}
      </Stagger>

      {media.data?.kind === "image" && (
        <Panel className="p-5 sm:p-6">
          <PanelHeader title="Licensed reverse-image search" subtitle="Optional provider integration. Results are candidates only and require investigator confirmation." />
          <button disabled={reverseBusy} onClick={async()=>{ if(!incidentId || !media.data) return; setReverseBusy(true); try { setReverseSearch(await api.reverseSearch(incidentId, media.data.id)); } finally { setReverseBusy(false); } }} className="mt-4 rounded-xl bg-brand text-white px-4 py-2.5 text-[12px] font-semibold disabled:opacity-50">{reverseBusy?"Searching…":"Run licensed reverse search"}</button>
          {reverseSearch && <div className="mt-4 rounded-xl bg-soft/50 border border-border p-4 text-[12px]">{reverseSearch.configured ? <><p className="font-semibold text-ink">Provider: {reverseSearch.provider}</p><p className="text-muted mt-1">{reverseSearch.message}</p><div className="mt-3 space-y-2">{(reverseSearch.pages||[]).slice(0,8).map((p:any)=><a key={p.url} href={p.url} target="_blank" rel="noreferrer" className="block text-brand hover:underline">{p.title || p.url}</a>)}</div></> : <p className="text-muted">No licensed provider is configured. Set REVERSE_SEARCH_PROVIDER=google_vision and cloud credentials to enable it.</p>}</div>}
        </Panel>
      )}

      {/* Similarity Matches & Details */}
      <div className="grid xl:grid-cols-[1.2fr_.8fr] gap-5">
        <Panel className="p-5 sm:p-6">
          <PanelHeader title="External Sources" subtitle="External pages can now be traced from a pasted URL. Automatic matches are labeled separately from investigator-entered estimates." />
          <div className="space-y-2.5 mt-4">
            {sources.length === 0 && <p className="text-[12.5px] text-muted">No external sources have been added. The uploaded file is the reference media, not a match against itself. Use Trace URL in Add Source to inspect a public page automatically.</p>}
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
                  <div className="w-40 text-right">
                    <p className="text-[11.5px] font-semibold text-ink">{s.similarity != null ? `${s.similarity}% investigator estimate` : "Not scored"}</p>
                    <p className="text-[10.5px] text-muted mt-1">{s.similarity != null ? "Entered manually; not calculated by LINEAGE" : "No score provided"}</p>
                  </div>
                  {s.url && <a href={s.url} target="_blank" rel="noopener noreferrer" className="text-[11.5px] font-medium border border-border rounded-lg px-3.5 py-1.5 hover:bg-soft transition">Open</a>}
                </div>
              </div>
            ))}
          </div>
        </Panel>

        <div className="space-y-5">
          <Panel className="p-5 sm:p-6">
            <PanelHeader title="Fingerprint Details" />
            <div className="space-y-2.5 text-[12.5px] mt-4">
              {[
                ["File Name", media.data?.original_filename ?? "—"],
                ["File Type", media.data ? (media.data.kind === "video" ? "Video" : "Image") : "—"],
                ["File Size", media.data ? `${Math.round(media.data.file_size_bytes / 1024)} KB` : "—"],
                ["Resolution", media.data?.width && media.data?.height ? `${media.data.width} × ${media.data.height}` : "—"],
                ["Face detected", fp ? (face.foundFace ? `Yes (${Math.round((face.confidence ?? 0) * 100)}% confidence)` : "No") : "—"],
                ["Fingerprint Status", fp ? "Complete" : fpSlice.loading ? "Running…" : "Not yet run"],
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
              LINEAGE generates multiple visual hashes plus a face embedding when a face is detected. Pasted public URLs can be inspected for matching page images; audio media receives a deterministic spectrogram fingerprint, while audio deepfake scoring remains optional and model-dependent.
            </p>
            <div className="mt-4">
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}
