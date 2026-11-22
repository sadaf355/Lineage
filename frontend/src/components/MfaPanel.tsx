import { useEffect, useState } from "react";
import { api, ApiError } from "../lib/api";
import { StatusBadge } from "./ui";

/** TOTP enrolment with one-time recovery codes. The secret is shown as text and as an otpauth:// link; no QR library is bundled. */
export default function MfaPanel({ required = false }: { required?: boolean }) {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [remaining, setRemaining] = useState(0);
  const [mandatory, setMandatory] = useState(required);
  const [setup, setSetup] = useState<{ secret: string; otpauth_uri: string } | null>(null);
  const [codes, setCodes] = useState<string[] | null>(null);
  const [code, setCode] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = () => api.mfaStatus().then((s) => { setEnabled(s.enabled); setRemaining(s.recovery_codes_remaining); setMandatory(s.required); }).catch(() => undefined);
  useEffect(() => { void refresh(); }, []);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true); setMsg(null);
    try { await fn(); } catch (e) { setMsg(e instanceof ApiError ? e.message : "Something went wrong."); } finally { setBusy(false); }
  };

  return (
    <div className="rounded-xl border border-border/60 bg-soft/40 p-4">
      <p className="text-[13.5px] font-semibold text-ink">Two-factor authentication (TOTP)</p>
      <p className="text-[12px] text-muted mt-1">Use an authenticator app. Once enabled, sign-in asks for a 6-digit code. Each code works once.</p>
      {mandatory && enabled === false && <p className="mt-2 text-[12px] font-medium text-red-700">Your organisation requires two-factor. Turn it on to continue using LINEAGE.</p>}
      <div className="flex flex-wrap gap-2 mt-2">
        {enabled === true && <StatusBadge tone="green">Enabled · {remaining} recovery codes left</StatusBadge>}
        {enabled === false && <StatusBadge tone="gray">Not enabled</StatusBadge>}
      </div>
      {!setup && enabled === false && (
        <button disabled={busy} className="mt-3 rounded-lg border border-brand text-brand px-3 py-1.5 text-[12px]"
          onClick={() => run(async () => { setSetup(await api.mfaSetup()); })}>Set up</button>
      )}
      {setup && (
        <div className="mt-3 space-y-2 text-[12px]">
          <p>Add this key in your authenticator app: <code className="break-all">{setup.secret}</code></p>
          <p><a className="text-brand underline" href={setup.otpauth_uri}>Open in authenticator app</a></p>
          <input value={code} onChange={(e) => setCode(e.target.value)} inputMode="numeric" maxLength={6} placeholder="6-digit code"
            className="h-9 rounded-lg border border-border px-3 text-[12px]" />
          <button disabled={busy || code.length !== 6} className="ml-2 rounded-lg bg-brand text-white px-3 py-1.5 text-[12px]"
            onClick={() => run(async () => { const r = await api.mfaEnable(code); setCodes(r.recovery_codes); setEnabled(true); setRemaining(r.recovery_codes.length); setSetup(null); setCode(""); })}>Turn on</button>
        </div>
      )}
      {codes && (
        <div className="mt-3 rounded-lg border border-amber-300 bg-amber-50 p-3 text-[12px]">
          <p className="font-semibold">Save these recovery codes now. They are shown only once.</p>
          <p className="mt-1 text-muted">If you lose your phone, each code signs you in one time.</p>
          <pre className="mt-2 font-mono text-[12.5px] leading-6 select-all">{codes.join("\n")}</pre>
          <button className="mt-2 rounded-lg border border-border px-3 py-1.5" onClick={() => setCodes(null)}>I have saved them</button>
        </div>
      )}
      {enabled === true && !setup && !codes && (
        <div className="mt-3 text-[12px] space-x-2">
          <input value={code} onChange={(e) => setCode(e.target.value)} inputMode="numeric" maxLength={11} placeholder="Current code"
            className="h-9 rounded-lg border border-border px-3 text-[12px]" />
          <button disabled={busy || code.length < 6} className="rounded-lg border border-border px-3 py-1.5"
            onClick={() => run(async () => { const r = await api.mfaNewRecoveryCodes(code); setCodes(r.recovery_codes); setRemaining(r.recovery_codes.length); setCode(""); })}>New recovery codes</button>
          {!mandatory && <button disabled={busy || code.length < 6} className="rounded-lg border border-border px-3 py-1.5"
            onClick={() => run(async () => { await api.mfaDisable(code); setEnabled(false); setCode(""); setMsg("Two-factor is now off."); })}>Turn off</button>}
        </div>
      )}
      {msg && <p className="mt-2 text-[12px] text-muted">{msg}</p>}
    </div>
  );
}
