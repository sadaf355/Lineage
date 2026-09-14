import { useState } from "react";
import { Download, Search, Filter, X, ExternalLink, Database, FileImage, Link2, Clock } from "lucide-react";
import { sources, evidenceItems } from "../data/caseData";
import { Panel, PanelHeader, DemoBadge, StatCard, StatusBadge } from "../components/ui";

export default function EvidenceLocker() {
  const [selected, setSelected] = useState(sources[0]);

  return (
    <div className="space-y-6">
      {/* Header bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-card border border-border rounded-2xl p-5 sm:p-6 shadow-card">
        <div>
          <h2 className="text-xl font-semibold tracking-[-.02em] text-ink">Evidence Locker</h2>
          <p className="text-[13px] text-muted mt-1 leading-relaxed">
            All discovered and preserved instances of this content across sources.
          </p>
        </div>
        <button className="rounded-xl bg-brand text-white px-5 py-3 text-[12.5px] font-semibold hover:bg-brandDark transition shrink-0 shadow-sm flex items-center gap-2">
          <Download size={15} /> Export Bundle
        </button>
      </div>

      {/* Quick stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <StatCard label="Total Sources" value="5" icon={Database} />
        <StatCard label="Evidence Items" value="5" icon={FileImage} />
        <StatCard label="Matching Sources" value="4" icon={Link2} />
        <StatCard label="Highest Similarity" value="96%" icon={Clock} />
      </div>

      {/* Preserved Sources Table */}
      <Panel className="p-5 sm:p-6">
        <PanelHeader title="Preserved Sources" right={<DemoBadge />} />
        <div className="flex flex-wrap gap-2.5 mb-5">
          <div className="relative flex-1 min-w-[240px]">
            <Search size={16} className="absolute left-3.5 top-3 text-faint" />
            <input
              placeholder="Search sources, platforms, or keywords..."
              className="w-full h-10 rounded-xl border border-border pl-10 pr-3 text-[12.5px] bg-bg focus:bg-card focus:outline-none focus:border-brand transition"
            />
          </div>
          <button className="h-10 px-4 rounded-xl border border-border text-[12.5px] font-medium hover:bg-soft transition flex items-center gap-2">
            <Filter size={14} /> Filter
          </button>
          <button className="h-10 px-4 rounded-xl border border-border text-[12.5px] font-medium hover:bg-soft transition">
            Sort: Date ↓
          </button>
        </div>

        <div className="overflow-x-auto -mx-5 sm:-mx-6 px-5 sm:px-6">
          <table className="w-full min-w-[780px] text-left">
            <thead>
              <tr className="bg-[#F4F6F3] text-[10.5px] uppercase tracking-wide text-faint border-b border-border">
                {["#", "Source", "Platform", "Account / Identifier", "Observed On", "Similarity", "Status", ""].map((x) => (
                  <th className="px-3.5 py-3 font-medium" key={x}>
                    {x}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sources.map((s, i) => (
                <tr
                  onClick={() => setSelected(s)}
                  key={s.id}
                  className={`border-b border-border/60 text-[12.5px] cursor-pointer hover:bg-soft/40 transition ${
                    selected?.id === s.id ? "bg-soft/60" : ""
                  }`}
                >
                  <td className="px-3.5 py-4 font-mono text-muted">{String(i + 1).padStart(2, "0")}</td>
                  <td className="px-3.5 py-4">
                    <b className="text-ink">{s.id}</b>
                    <p className="text-[11px] text-muted mt-0.5">{s.relationship}</p>
                  </td>
                  <td className="px-3.5 py-4 font-semibold text-ink">{s.platform}</td>
                  <td className="px-3.5 py-4 text-muted">{s.account}</td>
                  <td className="px-3.5 py-4 text-muted">{s.observedAt}</td>
                  <td className="px-3.5 py-4">
                    <span className="rounded-full bg-soft px-3 py-1 font-semibold text-brand text-[11.5px]">{s.similarity}%</span>
                  </td>
                  <td className="px-3.5 py-4">
                    <StatusBadge tone="blue">Seeded</StatusBadge>
                  </td>
                  <td className="px-3.5 py-4 text-muted font-medium">•••</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-[11.5px] text-muted mt-4">
          Showing 1–5 of 5 sources · Evidence is preserved as a structured investigative record.
        </p>
      </Panel>

      {/* Evidence Items & Detail Drawer */}
      <div className="grid lg:grid-cols-[1fr_340px] gap-5">
        <Panel className="p-5 sm:p-6">
          <PanelHeader title="Evidence Items" subtitle="Preserved artifacts linked to source observations" />
          <div className="grid md:grid-cols-2 gap-3.5 mt-4">
            {evidenceItems.map((ev) => (
              <div key={ev.id} className="border border-border/70 rounded-xl p-4 hover:bg-soft/40 transition flex flex-col justify-between">
                <div>
                  <div className="flex justify-between items-center">
                    <span className="h-9 w-9 rounded-lg bg-soft text-brand flex items-center justify-center shrink-0">
                      <FileImage size={17} />
                    </span>
                    <StatusBadge tone="green">Preserved</StatusBadge>
                  </div>
                  <p className="text-[13px] font-semibold text-ink mt-4">{ev.type}</p>
                  <p className="text-[11px] text-muted mt-1">
                    {ev.id} · linked to {ev.sourceId}
                  </p>
                </div>
                <p className="text-[11px] text-muted mt-3 pt-2 border-t border-border/40">{ev.capturedAt}</p>
              </div>
            ))}
          </div>
        </Panel>

        <Panel className="p-5 sm:p-6 relative">
          {selected ? (
            <>
              <button onClick={() => setSelected(null as any)} className="absolute right-4 top-4 text-muted hover:text-ink transition p-1">
                <X size={18} />
              </button>
              <p className="text-[11px] uppercase tracking-wide font-semibold text-brand">Evidence Detail</p>
              <div className="h-36 rounded-xl bg-brandDark mt-4 flex items-center justify-center text-white/70 shadow-inner">
                <FileImage size={36} />
              </div>
              <h3 className="text-[18px] font-semibold text-ink mt-4">{selected.id}</h3>
              <div className="mt-4 space-y-2.5 text-[12px]">
                {[
                  ["Platform", selected.platform],
                  ["Account", selected.account],
                  ["Observed", selected.observedAt],
                  ["Similarity", `${selected.similarity}%`],
                  ["URL", selected.url],
                ].map(([a, b]) => (
                  <div className="flex justify-between gap-4 border-b border-border/40 pb-2 last:border-0" key={a}>
                    <span className="text-muted">{a}</span>
                    <span className="font-semibold text-ink text-right break-all">{b}</span>
                  </div>
                ))}
              </div>
              <div className="rounded-xl bg-soft/70 p-3.5 mt-5 border border-brand/20">
                <p className="text-[12px] font-semibold text-ink">AI Analysis Note</p>
                <p className="text-[11.5px] text-muted mt-1 leading-relaxed">
                  High similarity detected with minor cropping and re-encoding. Treat this as an investigative lead, not proof of origin.
                </p>
              </div>
              <button className="text-[12px] font-semibold text-brand mt-4 hover:underline flex items-center gap-1.5">
                <ExternalLink size={14} /> Open preserved source
              </button>
            </>
          ) : (
            <div className="py-20 text-center text-[12.5px] text-muted">Select an evidence item to view details.</div>
          )}
        </Panel>
      </div>
    </div>
  );
}
