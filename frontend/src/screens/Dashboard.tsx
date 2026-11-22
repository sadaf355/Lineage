import { Stagger, StaggerItem, AnimatedNumber } from "../components/motion";
import ForensicScene from "../components/visual/ForensicScene";
import {
  FolderOpen,
  Plus,
  ShieldCheck,
  Activity,
  Search,
  ArrowRight,
  Database,
  Lock,
  PieChart,
  BarChart3,
  Server,
  Layers,
} from "lucide-react";
import { Panel, PanelHeader, StatCard, StatusBadge } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { api } from "../lib/api";
import { statusLabel } from "../lib/pipeline";
import { ScreenKey } from "../components/Sidebar";
import DetectorEvaluationPanel from "../components/DetectorEvaluationPanel";


export default function Dashboard({ onNavigate }: { onNavigate: (k: ScreenKey) => void }) {
  const incidents = useAsync(() => api.listIncidents(), []);
  const health = useAsync(() => api.health(), []);
  const all = incidents.data ?? [];

  const openCount = all.filter((i) => i.status !== "closed").length;
  const reportedCount = all.filter((i) => i.status === "report_generated" || i.status === "closed").length;
  const inAnalysis = all.filter((i) => ["analyzing", "fingerprinted", "evidence_building"].includes(i.status)).length;

  // Account-level counts, read from the server. Per-case detection scores and
  // evidence totals live on each investigation rather than being aggregated
  // here — the API exposes them per incident, not as a global rollup.
  const PALETTE = ["#3E503C", "#72846F", "#91A19A", "#9B8BC2", "#C79B42", "#D4DAD5"];
  const statusBreakdown = (() => {
    if (all.length === 0) return [] as { name: string; pct: number; color: string }[];
    const counts = new Map<string, number>();
    all.forEach((i) => counts.set(i.status, (counts.get(i.status) ?? 0) + 1));
    const entries = [...counts.entries()].sort((a, b) => b[1] - a[1]);
    let used = 0;
    return entries.map(([status, n], idx) => {
      const pct = idx === entries.length - 1 ? Math.max(0, 100 - used) : Math.round((n / all.length) * 100);
      used += pct;
      return { name: statusLabel(status as any), pct, color: PALETTE[idx % PALETTE.length] };
    });
  })();

  const stats = [
    ["Total Investigations", incidents.loading ? "…" : String(all.length), "Stored on the server", FolderOpen],
    ["Open Cases", incidents.loading ? "…" : String(openCount), "Not yet archived", Activity],
    ["In Analysis", incidents.loading ? "…" : String(inAnalysis), "Detection or evidence stage", ShieldCheck],
    ["Reports Generated", incidents.loading ? "…" : String(reportedCount), "Ready to export", Database],
  ];

  return (
    <Stagger className="space-y-6 max-w-[1400px] mx-auto">
      {/* Header Banner */}
      <StaggerItem><div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 pb-1">
        <div>
          <p className="text-[11px] uppercase tracking-[.18em] text-brand font-semibold mb-1">SYSTEM OVERVIEW</p>
          <h1 className="font-display text-3xl sm:text-4xl lg:text-[40px] tracking-[-.03em] font-semibold text-ink">
            Investigate with clarity.
          </h1>
          <p className="text-[13.5px] text-muted mt-2 max-w-2xl leading-relaxed">
            High-level platform metrics, global abuse landscape, and active risk monitoring across all cases.
          </p>
        </div>
        <div className="flex items-center gap-2">
        </div>
      </div></StaggerItem>

      <StaggerItem><div className="relative overflow-hidden rounded-[28px] bg-[#0d1711] border border-white/10 shadow-[0_30px_90px_rgba(29,57,39,.16)] min-h-[250px]">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_70%_40%,rgba(95,224,160,.15),transparent_38%)]"/>
        <div className="relative z-10 grid md:grid-cols-[.8fr_1.2fr] min-h-[250px]">
          <div className="p-7 sm:p-9 flex flex-col justify-center">
            <div className="inline-flex items-center gap-2 text-[9px] tracking-[.18em] text-emerald-200/70 font-bold"><span className="h-1.5 w-1.5 rounded-full bg-emerald-300 pulse-dot"/> INVESTIGATION PULSE</div>
            <h2 className="font-display text-3xl sm:text-4xl text-white mt-3">See the evidence connect.</h2>
            <p className="text-[12px] text-white/50 mt-3 max-w-md leading-relaxed">A calm workspace for moving from suspicious media to traceable, reviewable evidence.</p>
          </div>
          <div className="min-h-[250px]"><ForensicScene compact/></div>
        </div>
      </div></StaggerItem>

      {/* Quick Actions Cards */}
      <StaggerItem><div className="grid md:grid-cols-2 gap-5">
        <button
          onClick={() => onNavigate("new")}
          className="bg-brand text-white rounded-2xl p-6 text-left flex items-center justify-between hover:bg-brandDark transition shadow-sm group"
        >
          <div>
            <div className="h-10 w-10 rounded-xl bg-white/10 flex items-center justify-center text-white shrink-0 mb-3">
              <Plus size={22} />
            </div>
            <b className="block text-[17px] font-semibold">Start a New Investigation</b>
            <span className="text-[12.5px] text-white/80 mt-1 block">Upload media or paste a source link to begin detection.</span>
          </div>
          <ArrowRight className="group-hover:translate-x-1.5 transition-transform shrink-0 ml-4" size={20} />
        </button>

        <button
          onClick={() => onNavigate("investigations")}
          className="bg-card border border-border rounded-2xl p-6 text-left flex items-center justify-between hover:bg-soft transition shadow-card group"
        >
          <div>
            <div className="h-10 w-10 rounded-xl bg-soft flex items-center justify-center text-brand shrink-0 mb-3">
              <Search size={20} />
            </div>
            <b className="block text-[17px] font-semibold text-ink">Browse All Investigations</b>
            <span className="text-[12.5px] text-muted mt-1 block">{incidents.loading ? "Loading your cases…" : `View, filter, and manage ${all.length} investigation case${all.length === 1 ? "" : "s"}.`}</span>
          </div>
          <ArrowRight className="text-brand group-hover:translate-x-1.5 transition-transform shrink-0 ml-4" size={20} />
        </button>
      </div></StaggerItem>

      {/* 4 Stat Cards */}
      <StaggerItem><div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-4">
        {stats.map(([l, v, s, I]: any) => (
          <StatCard key={l} label={l} value={v} sub={s} icon={I} />
        ))}
      </div></StaggerItem>

      {/* Global Analytics Section */}
      <StaggerItem><div className="grid lg:grid-cols-2 gap-6">
        {/* Your Investigations */}
        <Panel className="p-6 sm:p-7 flex flex-col justify-between space-y-6">
          <PanelHeader
            title="Your Investigations"
            subtitle="Distribution of your cases by pipeline stage"
            right={
              <div className="h-8 w-8 rounded-xl bg-soft text-brand flex items-center justify-center shrink-0">
                <PieChart size={18} />
              </div>
            }
          />

          <div className="flex flex-col sm:flex-row items-center gap-8 pt-2">
            <div
              className="h-40 w-40 rounded-full shrink-0 shadow-xs relative"
              style={{
                background: statusBreakdown.length
                  ? `conic-gradient(${statusBreakdown.map((x, i) => {
                      const start = statusBreakdown.slice(0, i).reduce((sum, y) => sum + y.pct, 0);
                      return `${x.color} ${start}% ${start + x.pct}%`;
                    }).join(", ")})`
                  : "conic-gradient(#EEF1ED 0 100%)",
              }}
            >
              <div className="h-28 w-28 bg-card rounded-full relative top-6 left-6 flex flex-col items-center justify-center shadow-xs">
                <b className="text-3xl font-semibold text-ink">{incidents.loading ? "…" : <AnimatedNumber value={all.length} />}</b>
                <span className="text-[10.5px] text-muted font-medium">Investigations</span>
              </div>
            </div>

            <div className="space-y-2.5 text-[12.5px] w-full">
              {statusBreakdown.length === 0 && (
                <p className="text-[12.5px] text-muted">No investigations yet.</p>
              )}
              {statusBreakdown.map(({ name, pct, color }) => (
                <div key={name} className="flex justify-between items-center py-1.5 border-b border-border/40 last:border-0">
                  <span className="flex items-center gap-2 text-ink font-medium">
                    <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }} />
                    {name}
                  </span>
                  <span className="font-semibold text-ink">{pct}%</span>
                </div>
              ))}
            </div>
          </div>
        </Panel>

        {/* Global Case Risk & Monthly Trends */}
        <Panel className="p-6 sm:p-7 flex flex-col justify-between space-y-6">
          <PanelHeader
            title="Case Status Breakdown"
            subtitle="Where your investigations currently sit in the pipeline"
            right={
              <div className="h-8 w-8 rounded-xl bg-soft text-brand flex items-center justify-center shrink-0">
                <BarChart3 size={18} />
              </div>
            }
          />

          <div className="space-y-4 pt-2">
            {statusBreakdown.length === 0 && (
              <p className="text-[12.5px] text-muted">
                No investigations yet — case status distribution will appear here once you create one.
              </p>
            )}
            {statusBreakdown.map((x) => (
              <div key={x.name}>
                <div className="flex justify-between text-[12.5px] mb-1.5">
                  <span className="font-medium text-ink flex items-center gap-2">
                    <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: x.color }} /> {x.name}
                  </span>
                  <span className="font-semibold text-ink">{x.pct}%</span>
                </div>
                <div className="h-2.5 bg-[#EEF1ED] rounded-full overflow-hidden">
                  <div className="h-full rounded-full" style={{ width: `${x.pct}%`, backgroundColor: x.color }} />
                </div>
              </div>
            ))}
          </div>

          <div className="p-4 rounded-xl bg-soft/50 border border-border/60 flex items-center justify-between text-[12px]">
            <span className="text-muted">Detection Pipeline Engine</span>
            <StatusBadge tone={health.error ? "red" : health.data?.detector.loaded ? "green" : "amber"}>
              {health.error ? "Unavailable" : health.data?.detector.loaded ? "Pretrained model ready" : "API healthy · model not loaded"}
            </StatusBadge>
          </div>
        </Panel>
      </div></StaggerItem>

      {/* System Health & Security Cards */}
      <StaggerItem><div className="grid md:grid-cols-3 gap-5">
        <Panel className="p-5 sm:p-6 space-y-3">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-xl bg-soft text-brand flex items-center justify-center shrink-0">
              <Server size={18} />
            </div>
            <div>
              <p className="text-[13.5px] font-semibold text-ink">Detector Engine</p>
              <p className="text-[11.5px] text-muted">Pretrained manipulation-detection model</p>
            </div>
          </div>
          <div className="pt-2 border-t border-border/50 flex justify-between items-center text-[12px]">
            <span className="text-muted">Output format</span>
            <span className="font-semibold text-brand">Likelihood score, never binary</span>
          </div>
        </Panel>

        <Panel className="p-5 sm:p-6 space-y-3">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-xl bg-soft text-brand flex items-center justify-center shrink-0">
              <Layers size={18} />
            </div>
            <div>
              <p className="text-[13.5px] font-semibold text-ink">Evidence Vault Storage</p>
              <p className="text-[11.5px] text-muted">Encrypted at rest (AES via Fernet)</p>
            </div>
          </div>
          <div className="pt-2 border-t border-border/50 flex justify-between items-center text-[12px]">
            <span className="text-muted">Cases protected</span>
            <span className="font-semibold text-brand">{incidents.loading ? "…" : all.length}</span>
          </div>
        </Panel>

        <Panel className="p-5 sm:p-6 space-y-3">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-xl bg-soft text-brand flex items-center justify-center shrink-0">
              <Lock size={18} />
            </div>
            <div>
              <p className="text-[13.5px] font-semibold text-ink">Takedown Rule Compliance</p>
              <p className="text-[11.5px] text-muted">2026 IT Intermediary Rules</p>
            </div>
          </div>
          <div className="pt-2 border-t border-border/50 flex justify-between items-center text-[12px]">
            <span className="text-muted">Action Window</span>
            <span className="font-semibold text-brand">3-Hour Takedown Ready</span>
          </div>
        </Panel>
      </div></StaggerItem>

      <StaggerItem><DetectorEvaluationPanel compact /></StaggerItem>
    </Stagger>
  );
}
