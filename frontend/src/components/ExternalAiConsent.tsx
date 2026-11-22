import { useEffect, useState } from "react";
import { api } from "../lib/api";

/** Per-investigation consent to send case facts to an external language model (Anthropic).
 *  Off by default. While off, the Copilot answers from the investigation records only and reports use the
 *  built-in template. The server enforces this; this control only records the choice. */
export default function ExternalAiConsent({ incidentId }: { incidentId: string | null }) {
  const [granted, setGranted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!incidentId) return;
    let active = true;
    api.listConsents(incidentId)
      .then((rows) => {
        // newest first: the first row for this purpose is the current choice
        const latest = rows.find((r) => r.purpose === "external_llm_processing");
        if (active) setGranted(!!latest?.granted);
      })
      .catch(() => { if (active) setGranted(false); });
    return () => { active = false; };
  }, [incidentId]);

  async function toggle(next: boolean) {
    if (!incidentId) return;
    setBusy(true); setError(null);
    try {
      await api.recordConsent(incidentId, "external_llm_processing", next);
      setGranted(next);
    } catch (e: any) {
      setError(e?.message ?? "Could not save this choice.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <label className="flex items-start gap-3 text-[12px] leading-relaxed text-ink/80">
      <input type="checkbox" className="mt-0.5" checked={granted} disabled={busy || !incidentId}
        onChange={(e) => toggle(e.target.checked)} />
      <span>
        I am authorized to let this investigation's facts (sources, timeline, findings) be sent to an external language model
        (Anthropic) to draft Copilot answers and report summaries. Leave this off to use records-only answers.
        {error && <span className="block text-red-700">{error}</span>}
      </span>
    </label>
  );
}
