import { useCallback, useEffect, useState } from "react";
import { FileSignature, ShieldCheck, ShieldAlert, Copy } from "lucide-react";
import { api, ApiError, type ManifestKeyInfo, type ManifestRow, type ManifestVerification } from "../lib/api";
import { Panel, PanelHeader, StatusBadge } from "./ui";

function Check({ ok, label }: { ok: boolean; label: string }) {
  return (
    <li className="flex items-center gap-2 text-[12px]">
      {ok ? <ShieldCheck size={14} className="text-brand" aria-hidden /> : <ShieldAlert size={14} className="text-[#A23B32]" aria-hidden />}
      <span className="text-ink">{label}</span>
      <span className="sr-only">{ok ? "passed" : "failed"}</span>
    </li>
  );
}

export default function ManifestPanel({ incidentId }: { incidentId: string }) {
  const [rows, setRows] = useState<ManifestRow[]>([]);
  const [key, setKey] = useState<ManifestKeyInfo | null>(null);
  const [result, setResult] = useState<ManifestVerification | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setRows(await api.listManifests(incidentId));
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load manifests.");
    }
    try {
      setKey(await api.getManifestKey());
    } catch {
      setKey(null); // signing may be unconfigured; the create button will explain
    }
  }, [incidentId]);

  useEffect(() => { void load(); }, [load]);

  const sign = async () => {
    setBusy("sign"); setError(null); setResult(null);
    try {
      await api.createManifest(incidentId, false);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Signing failed.");
    } finally { setBusy(null); }
  };

  const verify = async (id: string) => {
    setBusy(id); setError(null);
    try {
      setResult(await api.verifyManifest(incidentId, id));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Verification failed.");
    } finally { setBusy(null); }
  };

  const v = result?.verification;
  return (
    <Panel className="p-5 sm:p-6">
      <PanelHeader
        title="Signed integrity manifest"
        subtitle="An Ed25519 signature over every media, evidence and source hash in this case"
        right={<StatusBadge tone={key ? "green" : "gray"}>{key ? `Key ${key.key_id}` : "Signing key unavailable"}</StatusBadge>}
      />
      <div className="flex flex-wrap items-center gap-3">
        <button type="button" onClick={sign} disabled={busy !== null}
          className="inline-flex items-center gap-2 rounded-xl bg-brand text-white px-4 py-2.5 text-[12.5px] font-semibold hover:bg-brandDark transition disabled:opacity-60">
          <FileSignature size={15} aria-hidden /> {busy === "sign" ? "Signing…" : "Sign current evidence"}
        </button>
        {key && (
          <button type="button" onClick={() => navigator.clipboard?.writeText(key.public_key_pem)}
            className="inline-flex items-center gap-2 rounded-xl border border-border px-4 py-2.5 text-[12px] font-semibold hover:bg-soft transition">
            <Copy size={14} aria-hidden /> Copy public key
          </button>
        )}
      </div>
      <p className="text-[11.5px] text-muted mt-3 leading-relaxed">
        A signature proves these hashes were recorded by this deployment at this time. It supports an investigation; it does not by itself make evidence admissible.
      </p>
      {error && <p role="alert" className="text-[12px] text-[#A23B32] mt-3">{error}</p>}

      <div className="mt-4 divide-y divide-border/50">
        {rows.length === 0 && <p className="text-[12px] text-muted py-2">No manifests signed yet.</p>}
        {rows.map((r) => (
          <div key={r.id} className="flex flex-wrap items-center justify-between gap-3 py-2.5">
            <div className="min-w-0">
              <p className="text-[12px] font-semibold text-ink">{new Date(r.created_at).toLocaleString()}{r.has_timestamp ? " · trusted timestamp" : ""}</p>
              <p className="font-mono text-[10px] text-muted break-all">{r.manifest_sha256}</p>
            </div>
            <button type="button" onClick={() => verify(r.id)} disabled={busy !== null}
              className="rounded-xl border border-border px-3 py-2 text-[11.5px] font-semibold hover:bg-soft transition disabled:opacity-60">
              {busy === r.id ? "Verifying…" : "Verify"}
            </button>
          </div>
        ))}
      </div>

      {result && v && (
        <div className="mt-4 rounded-xl border border-border bg-bg p-4" role="status" aria-live="polite">
          <p className="text-[12px] font-semibold text-ink mb-2">Verification result</p>
          <ul className="space-y-1.5">
            <Check ok={v.signature_valid} label="Signature is valid for this deployment's key" />
            <Check ok={v.key_matches_embedded} label="Key matches the one embedded in the manifest" />
            <Check ok={v.manifest_sha256_matches} label="Manifest digest matches" />
            <Check ok={v.entries_digest_matches} label="Entry list digest matches" />
          </ul>
          <p className="text-[12px] text-ink mt-3">
            {result.case_drift_since_signing.unchanged
              ? "No evidence has been added, removed or altered since signing."
              : `Since signing: ${result.case_drift_since_signing.added.length} added, ${result.case_drift_since_signing.removed.length} removed, ${result.case_drift_since_signing.hash_changed.length} with a changed hash.`}
          </p>
          <p className="text-[11px] text-muted mt-1">{result.note}</p>
        </div>
      )}
    </Panel>
  );
}
