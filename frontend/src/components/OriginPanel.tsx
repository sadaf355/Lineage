import { useState } from "react";
import { Fingerprint, FileDown, PackageOpen, ShieldAlert, ShieldCheck, HelpCircle } from "lucide-react";
import { api, ApiError, type LegalPackRequest, type OriginReport, type TamperVerdict } from "../lib/api";
import { Panel, PanelHeader, StatusBadge } from "./ui";

const VERDICT_LABEL: Record<TamperVerdict, { text: string; tone: "green" | "amber" | "red" | "gray" }> = {
  no_signals: { text: "No inconsistency found", tone: "green" },
  cannot_judge: { text: "Cannot judge", tone: "gray" },
  inconsistent_single: { text: "Inconsistent (one sign)", tone: "amber" },
  inconsistent_multiple: { text: "Inconsistent (several signs)", tone: "red" },
};

const REGIMES: { value: LegalPackRequest["regime"]; label: string }[] = [
  { value: "preservation", label: "Preservation request (keep logs incl. uploader IP)" },
  { value: "it_rules", label: "Removal notice: India IT Rules" },
  { value: "tida", label: "Removal request: US TAKE IT DOWN Act" },
  { value: "ncrp", label: "Complaint summary: cybercrime.gov.in" },
];

function save(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = name; a.click();
  URL.revokeObjectURL(url);
}

export default function OriginPanel({ incidentId }: { incidentId: string }) {
  const [report, setReport] = useState<OriginReport | null>(null);
  const [lang, setLang] = useState<"en" | "hi">("en");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [regime, setRegime] = useState<LegalPackRequest["regime"]>("preservation");
  const [platform, setPlatform] = useState("");
  const [track, setTrack] = useState<NonNullable<LegalPackRequest["track"]>>("high_risk_complaint");
  const [startedAt, setStartedAt] = useState("");
  const [withFiles, setWithFiles] = useState(false);
  const [compare, setCompare] = useState<Record<string, string>>({});

  const run = async (label: string, fn: () => Promise<void>) => {
    setBusy(label); setError(null);
    try { await fn(); }
    catch (e) { setError(e instanceof ApiError ? e.message : "Something went wrong."); }
    finally { setBusy(null); }
  };

  const load = (l: "en" | "hi") => run("origin", async () => { setLang(l); setReport(await api.getOrigin(incidentId, l)); });
  const pack = () => run("pack", async () => {
    const timed = regime === "it_rules" || regime === "tida";
    save(await api.downloadLegalPack(incidentId, {
      regime, platform: platform.trim() || undefined,
      ...(timed && startedAt ? { order_received_at: new Date(startedAt).toISOString() } : {}),
      ...(regime === "it_rules" ? { track } : {}),
    }), `lineage-${regime}.pdf`);
  });
  const bundle = () => run("bundle", async () => { save(await api.downloadCaseBundle(incidentId, withFiles), "lineage-case-bundle.zip"); });

  return (
    <Panel className="p-5 sm:p-6">
      <PanelHeader
        title="Origin and metadata check"
        subtitle={lang === "hi" ? "मेटाडेटा की तुलना केवल सुरक्षित पुराने snapshot से की जाती है। पुराना snapshot न हो तो बदलाव का दावा नहीं किया जाता। संकेत हैं, निर्णय नहीं।" : "Metadata is compared with a preserved earlier snapshot. Without one, LINEAGE will not claim a change. Signals, not verdicts."}
        right={<StatusBadge tone="blue">Draft tools</StatusBadge>}
      />
      <div className="flex flex-wrap items-center gap-3">
        <button type="button" onClick={() => load(lang)} disabled={busy !== null}
          className="inline-flex items-center gap-2 rounded-xl bg-brand text-white px-4 py-2.5 text-[12.5px] font-semibold hover:bg-brandDark transition disabled:opacity-60">
          <Fingerprint size={15} aria-hidden /> {busy === "origin" ? "Analysing…" : report ? "Re-run origin report" : "Run origin report"}
        </button>
        <label className="text-[12px] text-ink flex items-center gap-2">
          Language
          <select value={lang} onChange={(e) => load(e.target.value as "en" | "hi")} disabled={busy !== null || !report}
            className="rounded-lg border border-border bg-card px-2 py-1.5 text-[12px]">
            <option value="en">English</option>
            <option value="hi">हिन्दी (draft wording)</option>
          </select>
        </label>
      </div>
      {error && <p role="alert" className="text-[12px] text-[#A23B32] mt-3">{error}</p>}

      {report && (
        <div className="mt-4 space-y-4" aria-live="polite">
          <div className="rounded-xl border border-border bg-bg p-4">
            <p className="text-[12px] font-semibold text-ink flex items-center gap-2"><HelpCircle size={14} aria-hidden /> {lang === "hi" ? "यह सामग्री कहाँ से आई?" : "Where did this content come from?"}</p>
            <p className="text-[12px] text-ink mt-1 leading-relaxed">{report.creator_ip.reason}</p>
            <p className="text-[12px] text-muted mt-1 leading-relaxed">{report.creator_ip.how_to_obtain}</p>
          </div>

          <div>
            <p className="text-[12px] font-semibold text-ink mb-2">{lang === "hi" ? "मेटाडेटा तुलना" : "Metadata comparison"}</p>
            <p className="text-[11px] text-muted mb-2">{lang === "hi" ? "Changed का अर्थ तभी है जब पहले का सुरक्षित snapshot मौजूद हो। मेटाडेटा हटना अपने-आप में छेड़छाड़ का प्रमाण नहीं है।" : "‘Changed’ is reported only against a preserved earlier snapshot. Missing metadata alone is not proof of tampering."}</p>
            {report.layers.tamper.length === 0 && <p className="text-[12px] text-muted">No media in this case yet.</p>}
            <ul className="space-y-3">
              {report.layers.tamper.map((t) => {
                const v = t.verdict ? VERDICT_LABEL[t.verdict] : { text: "Not analysed", tone: "gray" as const };
                const Icon = t.verdict === "no_signals" ? ShieldCheck : ShieldAlert;
                return (
                  <li key={t.media_id} className="rounded-xl border border-border p-3">
                    <div className="flex flex-wrap items-center gap-2 justify-between">
                      <span className="text-[12px] font-semibold text-ink flex items-center gap-2"><Icon size={14} aria-hidden /> {t.filename}</span>
                      <StatusBadge tone={v.tone}>{v.text}</StatusBadge>
                    </div>
                    {t.description && <p className="text-[12px] text-ink mt-2 whitespace-pre-line leading-relaxed">{t.description}</p>}
                    <label className="block text-[11px] text-muted mt-2">
                      Compare a later copy with the preserved snapshot
                      <input type="file" accept="image/*" className="mt-1 block text-[11px]"
                        onChange={(e) => { const f = e.target.files?.[0]; if (f) run("compare", async () => { const r = await api.compareMetadata(incidentId, t.media_id, f); setCompare((c) => ({ ...c, [t.media_id]: r.state + ": " + r.reason + (r.changed_fields?.length ? " (" + r.changed_fields.join(", ") + ")" : "") })); }); }} />
                    </label>
                    {compare[t.media_id] && <p className="text-[12px] text-ink mt-1" role="status">{compare[t.media_id]}</p>}
                  </li>
                );
              })}
            </ul>
          </div>

          <div>
            <p className="text-[12px] font-semibold text-ink mb-2">Hosting of traced pages (the server, not the creator)</p>
            {report.layers.hosting.length === 0 && <p className="text-[12px] text-muted">No traced pages yet.</p>}
            <ul className="space-y-1">
              {report.layers.hosting.map((h, i) => (
                <li key={`${h.domain}-${i}`} className="text-[12px] text-ink">
                  {h.domain}: {(h.server_ips ?? []).join(", ") || "not resolved"}{h.country ? ` · ${h.country}` : ""}
                  <span className="text-muted"> ({h.label})</span>
                </li>
              ))}
            </ul>
          </div>

          {report.signals_found.length > 0 && (
            <ul className="list-disc pl-5 text-[12px] text-ink space-y-1">
              {report.signals_found.map((s, i) => <li key={i}>{s}</li>)}
            </ul>
          )}
          <p className="text-[11px] text-muted leading-relaxed">{report.limits.join(" ")}</p>
        </div>
      )}

      <div className="mt-6 border-t border-border pt-4 grid md:grid-cols-2 gap-5">
        <div>
          <p className="text-[12px] font-semibold text-ink mb-2">Draft legal pack (PDF)</p>
          <select aria-label="Pack type" value={regime} onChange={(e) => setRegime(e.target.value as LegalPackRequest["regime"])}
            className="w-full rounded-lg border border-border bg-card px-2 py-2 text-[12px] mb-2">
            {REGIMES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
          </select>
          {regime === "it_rules" && (
            <select aria-label="What started the request" value={track} onChange={(e) => setTrack(e.target.value as NonNullable<LegalPackRequest["track"]>)}
              className="w-full rounded-lg border border-border bg-card px-2 py-2 text-[12px] mb-2">
              <option value="high_risk_complaint">My complaint about intimate, nude, impersonating or morphed content (2 h)</option>
              <option value="individual_complaint">Other complaint by an individual (36 h)</option>
              <option value="order">Court order or government notice (3 h)</option>
            </select>
          )}
          {(regime === "it_rules" || regime === "tida") && (
            <label className="block text-[11px] text-muted mb-2">Request sent or order received (optional, for a planning deadline)
              <input type="datetime-local" value={startedAt} onChange={(e) => setStartedAt(e.target.value)}
                className="mt-1 w-full rounded-lg border border-border bg-card px-3 py-2 text-[12px]" />
            </label>
          )}
          {regime === "tida" && <p className="text-[11px] text-muted mb-2">Intimate imagery only. A US law that applies to covered platforms.</p>}
          <input aria-label="Platform name" value={platform} onChange={(e) => setPlatform(e.target.value)} placeholder="Platform (optional)"
            className="w-full rounded-lg border border-border bg-card px-3 py-2 text-[12px] mb-2" />
          <button type="button" onClick={pack} disabled={busy !== null}
            className="inline-flex items-center gap-2 rounded-xl border border-border px-4 py-2.5 text-[12px] font-semibold hover:bg-soft transition disabled:opacity-60">
            <FileDown size={14} aria-hidden /> {busy === "pack" ? "Preparing…" : "Download draft"}
          </button>
          <p className="text-[11px] text-muted mt-2">Drafts only. Have a lawyer review before sending. Not legal advice.</p>
        </div>
        <div>
          <p className="text-[12px] font-semibold text-ink mb-2">Signed case bundle (zip)</p>
          <label className="flex items-start gap-2 text-[12px] text-ink mb-2">
            <input type="checkbox" checked={withFiles} onChange={(e) => setWithFiles(e.target.checked)} className="mt-0.5" />
            <span>Include the original files (sensitive; only if the recipient needs them)</span>
          </label>
          <button type="button" onClick={bundle} disabled={busy !== null}
            className="inline-flex items-center gap-2 rounded-xl border border-border px-4 py-2.5 text-[12px] font-semibold hover:bg-soft transition disabled:opacity-60">
            <PackageOpen size={14} aria-hidden /> {busy === "bundle" ? "Building…" : "Download bundle"}
          </button>
          <p className="text-[11px] text-muted mt-2">Includes the latest signed manifest. Sign the evidence first for the bundle to carry a signature.</p>
        </div>
      </div>
    </Panel>
  );
}
