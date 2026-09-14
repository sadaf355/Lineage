import { useState } from "react";
import { Download, Share2, FileText, CheckCircle2 } from "lucide-react";
import { incidentReport, caseInfo, sources, detectionResult } from "../data/caseData";
import { Panel, PanelHeader, ConfidenceBar, StatusBadge, DemoBadge } from "../components/ui";

export default function IncidentReport() {
  const [shared, setShared] = useState(false);

  return (
    <div className="space-y-6 max-w-[1400px] mx-auto">
      {/* Header bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-card border border-border rounded-2xl p-5 sm:p-6 shadow-card">
        <div>
          <h2 className="text-xl font-semibold tracking-[-.02em] text-ink">Incident Report</h2>
          <p className="text-[13px] text-muted mt-1 leading-relaxed">
            Review the structured report before exporting or sharing.
          </p>
        </div>
        <div className="flex flex-wrap gap-2.5">
          <button
            onClick={() => setShared(true)}
            className="rounded-xl border border-border px-4 py-2.5 text-[12.5px] font-medium hover:bg-soft transition flex items-center gap-2"
          >
            <Share2 size={14} />
            {shared ? "Shared" : "Share Report"}
          </button>
          <button
            onClick={() => window.print()}
            className="rounded-xl bg-brand text-white px-4 py-2.5 text-[12.5px] font-semibold hover:bg-brandDark transition flex items-center gap-2 shadow-sm"
          >
            <Download size={14} /> Download PDF
          </button>
        </div>
      </div>

      <div className="grid xl:grid-cols-[1fr_340px] gap-5">
        <Panel className="p-0 overflow-hidden border border-border">
          <div className="p-7 md:p-10 bg-white min-h-[900px] space-y-8">
            {/* Document Header */}
            <div className="flex justify-between items-start border-b border-border pb-6">
              <div>
                <div className="font-display text-[22px] tracking-[.15em] font-semibold text-ink">LINEAGE</div>
                <p className="text-[9px] tracking-[.18em] text-muted mt-1 uppercase font-semibold">TRACE TRUTH. PROTECT PEOPLE.</p>
              </div>
              <div className="text-right">
                <p className="font-semibold text-[13.5px] text-ink">Incident Report</p>
                <p className="text-[11px] text-muted mt-0.5">Generated {incidentReport.generatedAt}</p>
                <p className="text-[11px] font-mono text-muted">{caseInfo.id}</p>
              </div>
            </div>

            <div>
              <h2 className="font-display text-[30px] sm:text-[34px] font-semibold tracking-[-.02em] text-ink">Incident Report</h2>
              <p className="text-[13px] text-muted mt-1">AI-Powered Synthetic Identity Abuse Investigation Platform</p>
            </div>

            <ReportSection n="1" title="Executive Summary">
              <p className="text-[13px] text-ink/90 leading-relaxed pb-1">{incidentReport.summary}</p>
            </ReportSection>

            <ReportSection n="2" title="Media Analysis">
              <div className="grid sm:grid-cols-2 gap-5">
                <div className="rounded-2xl bg-soft p-6 border border-brand/20 flex flex-col justify-between">
                  <div>
                    <p className="text-[12px] text-muted font-medium">Manipulation likelihood</p>
                    <b className="text-4xl block mt-2 font-semibold text-ink">87%</b>
                  </div>
                  <p className="text-[12px] text-muted mt-3 font-medium">High likelihood · face manipulation</p>
                </div>

                <div className="space-y-3 text-[12.5px] justify-center flex flex-col">
                  {[
                    ["Detection confidence", "87%"],
                    ["Detected region", detectionResult.detectedRegion],
                    ["Likely technique", detectionResult.likelyTechnique],
                    ["Media", "Riya_video.mp4"],
                  ].map(([a, b]) => (
                    <div className="flex justify-between border-b border-border/40 pb-2.5 last:border-0 last:pb-0" key={a}>
                      <span className="text-muted">{a}</span>
                      <b className="text-right text-ink font-semibold ml-2">{b}</b>
                    </div>
                  ))}
                </div>
              </div>
            </ReportSection>

            <ReportSection n="3" title="Evidence Summary">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                {[
                  ["Sources", String(sources.length)],
                  ["Evidence items", "5"],
                  ["Matching sources", "4"],
                  ["Highest similarity", "96%"],
                ].map(([a, b]) => (
                  <div className="rounded-xl border border-border p-4 sm:p-5 bg-[#FAFBF9]" key={a}>
                    <p className="text-[11.5px] text-muted font-medium">{a}</p>
                    <b className="text-2xl sm:text-3xl mt-2 block font-semibold text-ink">{b}</b>
                  </div>
                ))}
              </div>
            </ReportSection>

            <ReportSection n="4" title="Platforms Involved">
              <div className="flex flex-wrap gap-2.5">
                {sources.map((s) => (
                  <StatusBadge tone="gray" key={s.id}>
                    {s.platform}
                  </StatusBadge>
                ))}
              </div>
            </ReportSection>

            <ReportSection n="5" title="Attribution Assessment">
              <div className="grid sm:grid-cols-2 gap-5">
                <div className="rounded-2xl bg-soft p-6 border border-brand/25 flex flex-col justify-between space-y-3 shadow-xs">
                  <div>
                    <b className="text-[14px] font-semibold text-ink">Established</b>
                    <p className="text-[12.5px] text-ink/90 mt-2.5 leading-relaxed">
                      The media is likely manipulated and similar versions appear across the observed sources.
                    </p>
                  </div>
                </div>

                <div className="rounded-2xl bg-[#F8F1EC] p-6 border border-[#E8D9CD] flex flex-col justify-between space-y-3 shadow-xs">
                  <div>
                    <b className="text-[14px] font-semibold text-[#663A2E]">Unresolved</b>
                    <p className="text-[12.5px] text-[#7A4B3F] mt-2.5 leading-relaxed">
                      Real-world identity and original creation cannot be established from available evidence.
                    </p>
                  </div>
                </div>
              </div>
            </ReportSection>

            <ReportSection n="6" title="Recommended Next Actions">
              <ol className="space-y-3 text-[12.5px] text-muted list-decimal pl-5">
                {incidentReport.recommendedActions.slice(0, 4).map((a) => (
                  <li key={a.title} className="leading-relaxed">
                    <b className="text-ink font-semibold">{a.title}.</b> {a.detail}
                  </li>
                ))}
              </ol>
            </ReportSection>
          </div>
        </Panel>

        {/* Sidebar Controls & Metadata */}
        <div className="space-y-5">
          <Panel className="p-5 sm:p-6">
            <PanelHeader title="Report Actions" />
            <button
              onClick={() => window.print()}
              className="w-full rounded-xl bg-brand text-white py-3 text-[12.5px] font-semibold hover:bg-brandDark transition shadow-sm flex items-center justify-center gap-2"
            >
              <Download size={14} /> Download PDF
            </button>
            <button className="w-full rounded-xl border border-border py-3 mt-2 text-[12.5px] font-medium hover:bg-soft transition flex items-center justify-center gap-2">
              <FileText size={14} /> Download JSON
            </button>
            <button
              onClick={() => setShared(true)}
              className="w-full rounded-xl border border-border py-3 mt-2 text-[12.5px] font-medium hover:bg-soft transition flex items-center justify-center gap-2"
            >
              <Share2 size={14} /> Share Report
            </button>
            {shared && (
              <p className="text-[11.5px] text-brand font-medium mt-3 flex items-center gap-1">
                <CheckCircle2 size={14} /> Share link prepared (demo).
              </p>
            )}
          </Panel>

          <Panel className="p-5 sm:p-6">
            <PanelHeader title="Confidence Breakdown" />
            <div className="space-y-3.5 mt-2">
              <ConfidenceBar label="Manipulation detection" value={87} />
              <ConfidenceBar label="Media similarity" value={93} />
              <ConfidenceBar label="Propagation relationship" value={88} />
              <ConfidenceBar label="Real-world attribution" value={0} tone="red" note="Not established" />
            </div>
          </Panel>

          <Panel className="p-5 sm:p-6">
            <PanelHeader title="Report Contents" />
            <div className="space-y-3 text-[12px] mt-2">
              {[
                "Executive Summary",
                "Media Analysis",
                "Evidence Summary",
                "Platforms Involved",
                "Attribution Assessment",
                "Recommended Next Actions",
                "Appendix / Evidence Details",
              ].map((x, i) => (
                <div className="flex justify-between border-b border-border/40 pb-2.5 last:border-0 last:pb-0" key={x}>
                  <span className="text-ink font-medium">
                    {i + 1}. {x}
                  </span>
                  <span className="text-muted">Page {Math.min(6, Math.floor(i / 2) + 1)}</span>
                </div>
              ))}
            </div>
            <div className="mt-5">
              <DemoBadge />
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}

function ReportSection({ n, title, children }: { n: string; title: string; children: any }) {
  return (
    <section className="border-t border-border mt-8 pt-6">
      <h3 className="text-[15px] font-semibold text-ink">
        {n}. {title}
      </h3>
      <div className="mt-4">{children}</div>
    </section>
  );
}
