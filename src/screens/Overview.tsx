import { motion } from "framer-motion";
import { ArrowRight, FileText, Network, ShieldCheck, Plus, Activity } from "lucide-react";
import { evidenceItems } from "../data/caseData";
import { Panel, PanelHeader, StageTracker, StatusBadge } from "../components/ui";
import { pipelineStages } from "../data/caseData";
import { ScreenKey } from "../components/Sidebar";

const anim = { initial: { opacity: 0, y: 10 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.35 } };

export default function Overview({ onNavigate }: { onNavigate: (k: ScreenKey) => void }) {
  return (
    <motion.div {...anim} className="space-y-6">
      {/* Primary Row: Case Summary, Media Preview, & Manipulation Assessment */}
      <div className="grid xl:grid-cols-3 gap-5">
        {/* Case Summary Panel */}
        <Panel className="xl:col-span-1 p-5 sm:p-6 flex flex-col justify-between">
          <div>
            <PanelHeader
              title="Case Summary"
              right={<button className="text-[12px] border border-border rounded-lg px-3 py-1.5 hover:bg-soft transition">Edit</button>}
            />
            <p className="text-[13px] text-muted leading-relaxed">
              A suspicious video allegedly showing Riya making controversial statements has raised concerns about manipulation. This investigation aims to assess authenticity, trace the content's propagation, preserve evidence, and clarify what can and cannot be established.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-4 mt-6 pt-5 border-t border-border/60 text-[12px]">
            <div>
              <p className="text-muted font-medium">Media Type</p>
              <p className="font-semibold text-ink mt-1">Video (MP4)</p>
            </div>
            <div>
              <p className="text-muted font-medium">Platforms</p>
              <p className="font-semibold text-ink mt-1">5 observed</p>
            </div>
            <div>
              <p className="text-muted font-medium">Uploaded</p>
              <p className="font-semibold text-ink mt-1">Oct 14, 2024</p>
            </div>
            <div>
              <p className="text-muted font-medium">Evidence</p>
              <p className="font-semibold text-ink mt-1">{evidenceItems.length} items</p>
            </div>
          </div>
        </Panel>

        {/* Media Preview Panel */}
        <Panel className="xl:col-span-1 p-5 sm:p-6 flex flex-col justify-between">
          <div>
            <PanelHeader
              title="Media Preview"
              right={<button className="text-[12px] text-brand font-medium hover:underline">Open viewer ↗</button>}
            />
            <div className="h-[220px] rounded-xl bg-brandDark relative overflow-hidden flex items-center justify-center shadow-inner">
              <div className="absolute inset-0 opacity-25 bg-[radial-gradient(circle_at_50%_35%,#dce8d7,transparent_42%)]" />
              <div className="h-20 w-20 rounded-full border border-white/30 flex items-center justify-center text-white/80 bg-black/20 backdrop-blur-xs">
                <FileText size={32} />
              </div>
              <div className="absolute bottom-3 left-3 text-white text-[11.5px] bg-black/40 backdrop-blur-md px-3 py-1 rounded-lg">
                Riya_video.mp4 · 12.4 MB · 00:24
              </div>
            </div>
          </div>
          <div className="flex items-center justify-between mt-4 text-[12px] pt-3 border-t border-border/60">
            <span className="text-muted">Original media preserved</span>
            <span className="text-brand font-semibold flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-brand" /> Available
            </span>
          </div>
        </Panel>

        {/* Manipulation Assessment Panel */}
        <Panel className="xl:col-span-1 p-5 sm:p-6 flex flex-col justify-between">
          <div>
            <PanelHeader title="Manipulation Assessment" />
            <div className="flex items-center gap-5">
              <div
                className="h-32 w-32 rounded-full flex items-center justify-center shrink-0 shadow-sm"
                style={{ background: "conic-gradient(#B96255 0 87%, #E9EDE8 87% 100%)" }}
              >
                <div className="h-24 w-24 rounded-full bg-card flex flex-col items-center justify-center shadow-xs">
                  <b className="text-3xl text-ink font-semibold">87%</b>
                  <span className="text-[10px] text-muted font-medium">Likely manipulated</span>
                </div>
              </div>
              <div className="flex-1 space-y-2.5 text-[12px]">
                <div className="flex justify-between items-center">
                  <span className="text-muted">High likelihood</span>
                  <b className="text-ink">87%</b>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-muted">Uncertain</span>
                  <span className="text-muted font-medium">8%</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-muted">Likely authentic</span>
                  <span className="text-muted font-medium">5%</span>
                </div>
              </div>
            </div>
          </div>
          <div className="border-t border-border/60 mt-5 pt-4">
            <p className="font-semibold text-[12.5px] text-ink">Highest Similarity Match</p>
            <div className="flex items-end gap-2 mt-1">
              <b className="text-3xl font-semibold text-ink">96%</b>
              <span className="text-[12px] text-muted mb-1 font-medium">Instagram</span>
            </div>
          </div>
        </Panel>
      </div>

      {/* Case Analytics Row: Platform Distribution & Score Trend Charts */}
      <div className="grid lg:grid-cols-2 gap-5">
        <Panel className="p-5 sm:p-6">
          <PanelHeader title="Platform Distribution" subtitle="Discovered sources representing this case dataset" />
          <div className="flex flex-col sm:flex-row items-center gap-8 mt-4">
            <div
              className="h-36 w-36 rounded-full shrink-0 shadow-xs relative"
              style={{ background: "conic-gradient(#3E503C 0 35%,#72846F 35% 55%,#91A19A 55% 70%,#9B8BC2 70% 80%,#C79B42 80% 90%,#D4DAD5 90% 100%)" }}
            >
              <div className="h-24 w-24 bg-card rounded-full relative top-6 left-6 flex flex-col items-center justify-center shadow-xs">
                <b className="text-2xl font-semibold text-ink">5</b>
                <span className="text-[10px] text-muted font-medium">Case Sources</span>
              </div>
            </div>
            <div className="space-y-2 text-[12px] w-full">
              {["Instagram 35%", "X (Twitter) 25%", "Telegram 15%", "Reddit 15%", "YouTube 10%"].map((x) => (
                <div key={x} className="flex justify-between items-center py-1 border-b border-border/40 last:border-0">
                  <span className="text-muted font-medium">● {x.split(" ")[0]}</span>
                  <span className="font-semibold text-ink">{x.split(" ")[1]}</span>
                </div>
              ))}
            </div>
          </div>
        </Panel>

        <Panel className="p-5 sm:p-6">
          <PanelHeader title="Manipulation Score Trends" right={<span className="text-[11px] border border-border rounded-lg px-2.5 py-1 text-muted">Last 7 days</span>} />
          <svg viewBox="0 0 560 180" className="w-full h-44 mt-2">
            <path d="M25 145 L110 115 L195 125 L280 90 L365 105 L450 65 L535 30" fill="none" stroke="#3E503C" strokeWidth="3" />
            <path d="M25 145 L110 115 L195 125 L280 90 L365 105 L450 65 L535 30 L535 170 L25 170 Z" fill="#E8EEE6" opacity="0.6" />
            {[25, 110, 195, 280, 365, 450, 535].map((x, i) => (
              <circle key={x} cx={x} cy={[145, 115, 125, 90, 105, 65, 30][i]} r="5" fill="#3E503C" />
            ))}
          </svg>
        </Panel>
      </div>

      {/* Progress & Key Finding Row */}
      <div className="grid xl:grid-cols-3 gap-5">
        <Panel className="xl:col-span-2 p-5 sm:p-6">
          <PanelHeader title="Case Progress" subtitle="Follow the investigation from media upload to report" />
          <div className="mt-4 overflow-x-auto pb-2">
            <StageTracker stages={pipelineStages.map((s, i) => ({ ...s, current: i === 3 }))} />
          </div>
        </Panel>

        <Panel className="p-5 sm:p-6 flex flex-col justify-between">
          <PanelHeader title="Key Finding" />
          <div className="rounded-xl bg-soft/70 border border-brand/20 p-4">
            <div className="flex gap-3">
              <ShieldCheck className="text-brand shrink-0 mt-0.5" size={20} />
              <p className="text-[13px] text-ink leading-relaxed">
                The media is likely manipulated and similar content has been re-uploaded across multiple sources.
              </p>
            </div>
          </div>
          <p className="text-[11.5px] text-muted mt-3">Verified across 5 preserved evidence sources.</p>
        </Panel>
      </div>

      {/* Quick Actions & Recent Activity Row */}
      <div className="grid lg:grid-cols-3 gap-5">
        <Panel className="lg:col-span-1 p-5 sm:p-6">
          <PanelHeader title="Quick Actions" />
          <div className="space-y-2.5 mt-4">
            {[
              ["Continue Detection Analysis", "detection", ShieldCheck],
              ["Add Evidence Item", "evidence", Plus],
              ["View Lineage Graph", "lineage", Network],
              ["Generate Incident Report", "report", FileText],
            ].map(([t, k, I]: any) => (
              <button
                key={k}
                onClick={() => onNavigate(k)}
                className="w-full flex items-center justify-between rounded-xl border border-border px-4 py-3 text-[12.5px] font-medium text-ink hover:bg-soft hover:border-brand/40 transition group"
              >
                <span className="flex items-center gap-3">
                  <I size={16} className="text-brand shrink-0" />
                  {t}
                </span>
                <ArrowRight size={14} className="text-muted group-hover:translate-x-0.5 transition-transform" />
              </button>
            ))}
          </div>
        </Panel>

        <Panel className="lg:col-span-2 p-5 sm:p-6">
          <PanelHeader title="Recent Activity" right={<button className="text-[12px] text-brand font-medium hover:underline">View all →</button>} />
          <div className="grid sm:grid-cols-2 gap-4 mt-4">
            {["Detection completed", "Fingerprinting completed", "New evidence source added", "Report draft prepared"].map((x, i) => (
              <div key={x} className="flex gap-3.5 items-start p-3 rounded-xl hover:bg-soft/40 transition border border-transparent hover:border-border/50">
                <div className="h-8 w-8 rounded-full bg-soft flex items-center justify-center text-brand shrink-0">
                  <Activity size={15} />
                </div>
                <div>
                  <p className="text-[13px] font-semibold text-ink">{x}</p>
                  <p className="text-[11.5px] text-muted mt-0.5">{i * 7 + 3} minutes ago</p>
                </div>
              </div>
            ))}
          </div>
        </Panel>
      </div>
    </motion.div>
  );
}
