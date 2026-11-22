import { useEffect, useState } from "react";
import { Download, FileCheck2, ShieldCheck, Sparkles, HeartHandshake, ExternalLink } from "lucide-react";
import { api } from "../lib/api";
import { Panel, PanelHeader, StatusBadge } from "./ui";

export default function Phase2Actions({ incidentId }: { incidentId: string }) {
  const [footprints, setFootprints] = useState<any | null>(null);
  const [drafts, setDrafts] = useState<any[]>([]);
  const [manifest, setManifest] = useState<any | null>(null);
  const [verifyAll, setVerifyAll] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([api.getFootprints(incidentId), api.getTakedownDrafts(incidentId), api.getHashManifest(incidentId)])
      .then(([f, d, m]) => { if (active) { setFootprints(f); setDrafts(d.drafts); setManifest(m); } })
      .catch((e) => active && setError(e?.message ?? "Could not load Phase 2 tools."));
    return () => { active = false; };
  }, [incidentId]);

  async function verify() {
    setLoading(true); setError(null);
    try { setVerifyAll(await api.verifyAllEvidenceIntegrity(incidentId)); }
    catch (e: any) { setError(e?.message ?? "Verification failed."); }
    finally { setLoading(false); }
  }

  async function downloadPack() {
    const blob = await api.downloadRequestPack(incidentId);
    const url = URL.createObjectURL(blob); const a = document.createElement("a"); a.href = url; a.download = "lineage-request-pack.pdf"; a.click(); URL.revokeObjectURL(url);
  }

  return <div className="space-y-5">
    {error && <div className="rounded-xl border border-red/50 bg-red/30 p-3 text-[12px] text-[#8A4138]">{error}</div>}
    <Panel className="p-5 sm:p-6">
      <PanelHeader title="Evidence & action pack" subtitle="Integrity verification, exportable hashes, and reviewable complaint material." />
      <div className="grid md:grid-cols-3 gap-3 mt-4">
        <button onClick={verify} disabled={loading} className="rounded-xl border border-border bg-card p-4 text-left hover:border-brand transition">
          <ShieldCheck size={18} className="text-brand"/><p className="text-[13px] font-semibold mt-3">Verify all evidence</p><p className="text-[11px] text-muted mt-1">Re-hash every stored evidence file.</p>
        </button>
        <button onClick={downloadPack} className="rounded-xl border border-border bg-card p-4 text-left hover:border-brand transition">
          <Download size={18} className="text-brand"/><p className="text-[13px] font-semibold mt-3">Request pack</p><p className="text-[11px] text-muted mt-1">URLs, hashes, timestamps and hosting details.</p>
        </button>
        <button onClick={() => manifest && navigator.clipboard?.writeText(JSON.stringify(manifest, null, 2))} className="rounded-xl border border-border bg-card p-4 text-left hover:border-brand transition">
          <FileCheck2 size={18} className="text-brand"/><p className="text-[13px] font-semibold mt-3">Copy hash manifest</p><p className="text-[11px] text-muted mt-1">Exportable JSON-ready integrity record.</p>
        </button>
      </div>
      {verifyAll && <div className="mt-4 rounded-xl bg-soft p-3 flex items-center gap-2 text-[12px]"><StatusBadge tone={verifyAll.verified ? "green" : "red"}>{verifyAll.verified ? "ALL VERIFIED" : "REVIEW REQUIRED"}</StatusBadge>{verifyAll.results.length} evidence file(s) checked.</div>}
    </Panel>

    <Panel className="p-5 sm:p-6">
      <PanelHeader title="Footprints" subtitle="Metadata and hosting observations. Hosting information identifies the server, not the creator." />
      <div className="grid lg:grid-cols-2 gap-4 mt-4">
        <div className="rounded-xl border border-border p-4">
          <p className="text-[11px] uppercase tracking-wide font-semibold text-faint">Media metadata</p>
          <div className="space-y-3 mt-3">{(footprints?.media ?? []).map((m: any) => <div key={m.media_id} className="rounded-lg bg-soft/50 p-3"><p className="text-[12px] font-semibold">{m.filename}</p><p className="text-[11px] text-muted mt-1">Camera: {m.camera ?? "not recorded"} · Software: {m.software ?? "not recorded"}</p><p className="text-[11px] text-muted">Original timestamp: {m.timestamp ?? "not recorded"} · C2PA: {m.c2pa_present ? "present" : "not detected"}</p><p className="text-[10.5px] text-muted mt-1">{m.metadata_stripped ? "Metadata stripped / unavailable" : "Metadata fields available"}</p></div>)}</div>
        </div>
        <div className="rounded-xl border border-border p-4">
          <p className="text-[11px] uppercase tracking-wide font-semibold text-faint">Hosting footprint</p>
          <div className="space-y-3 mt-3">{(footprints?.hosting ?? []).map((h: any, i: number) => <div key={i} className="rounded-lg bg-soft/50 p-3"><p className="text-[12px] font-semibold">{h.domain || "Unknown domain"}</p><p className="text-[11px] text-muted mt-1">IP: {h.server_ips?.join(", ") || "not resolved"}</p><p className="text-[11px] text-muted">Country: {h.country}</p><p className="text-[10.5px] text-amber-700 mt-1">{h.label}</p></div>)}</div>
        </div>
      </div>
      <div className="mt-4 rounded-xl border border-amber/40 bg-amber/30 p-3 text-[11.5px] text-[#78571A]">{footprints?.attribution_gap ?? "Creator IP or account identity requires platform disclosure via a legal request."}</div>
    </Panel>

    <Panel className="p-5 sm:p-6">
      <PanelHeader title="Platform takedown drafts" subtitle="Generated from accepted sources. Nothing is sent automatically." />
      {drafts.length === 0 ? <p className="text-[12px] text-muted mt-3">No accepted live sources yet.</p> : <div className="space-y-3 mt-4">{drafts.map((d: any) => <div key={d.source_id} className="rounded-xl border border-border p-4"><div className="flex items-center justify-between gap-3"><div><p className="text-[12.5px] font-semibold">{d.platform}</p><p className="text-[11px] text-muted break-all">{d.url}</p></div><Sparkles size={16} className="text-brand"/></div><p className="text-[11.5px] text-ink mt-3 whitespace-pre-line">{d.body}</p></div>)}</div>}
    </Panel>

    <Panel className="p-5 sm:p-6">
      <PanelHeader title="Victim support" subtitle="Safety-first guidance; these links are informational and do not automatically contact anyone." />
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3 mt-4">{[["StopNCII", "https://stopncii.org/"],["Take It Down", "https://takeitdown.ncmec.org/"],["Cybercrime India", "https://cybercrime.gov.in/"],["Emergency", "tel:1930"]].map(([name,url]) => <a key={name} href={url} target={url.startsWith("http") ? "_blank" : undefined} rel="noreferrer" className="rounded-xl border border-border p-4 hover:border-brand transition"><HeartHandshake size={17} className="text-brand"/><p className="text-[12px] font-semibold mt-3">{name}</p><ExternalLink size={12} className="text-faint mt-2"/></a>)}</div>
    </Panel>
  </div>;
}
