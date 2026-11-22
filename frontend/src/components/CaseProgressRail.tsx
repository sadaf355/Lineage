import { motion } from "framer-motion";
import { AlertTriangle, Check, Loader2, Minus } from "lucide-react";
import { useCase } from "../context/CaseContext";
import { deriveCaseProgress, progressSummary, ProgressStep } from "../lib/caseProgress";
import { AnimatedNumber } from "./motion";
import type { ScreenKey } from "./Sidebar";

/**
 * Case-wide progress rail, shown on every investigation screen.
 * Every state comes from lib/caseProgress.ts, which reads stored data and the live pipeline stage / report-job status.
 * There is no percentage and no timer: the API does not report either, so the rail does not invent them.
 */
export default function CaseProgressRail({ activeTab, onNavigate }: { activeTab: ScreenKey; onNavigate: (key: ScreenKey) => void }) {
  const c = useCase();
  const steps = deriveCaseProgress({
    analysisStage: c.analysisStage, reportJobStatus: c.reportJobStatus,
    media: c.media, detection: c.detection, fingerprint: c.fingerprint, sources: c.sources,
    evidence: c.evidence, attributionGap: c.attributionGap, report: c.report,
  });
  const { done, total, active } = progressSummary(steps);
  const announcement = active ? `${active.label}: ${active.detail}` : `${done} of ${total} steps complete`;

  return (
    <nav aria-label="Case progress" className="glass rounded-2xl px-4 py-4">
      <div className="flex items-center justify-between mb-3">
        <p className="text-[11px] tracking-[.14em] uppercase font-semibold text-muted">Case progress</p>
        <p className="text-[12px] text-muted"><b className="text-ink"><AnimatedNumber value={done} /></b> of {total} complete</p>
      </div>
      <p role="status" className="sr-only">{announcement}</p>
      <div className="overflow-x-auto">
        <ol className="flex items-start min-w-[720px]">
          {steps.map((s, i) => (
            <li key={s.key} className="flex items-start flex-1 last:flex-none">
              <StepButton step={s} index={i} current={s.screen === activeTab} onClick={() => onNavigate(s.screen as ScreenKey)} />
              {i < steps.length - 1 && <Connector filled={s.state === "done" || s.state === "skipped"} flowing={steps[i + 1].state === "active" && s.state === "done"} />}
            </li>
          ))}
        </ol>
      </div>
    </nav>
  );
}

function StepButton({ step, index, current, onClick }: { step: ProgressStep; index: number; current: boolean; onClick: () => void }) {
  const tone = {
    done: "bg-brand border-brand text-white",
    active: "bg-amber border-[#D4AE62] text-[#76591E]",
    failed: "bg-red border-[#B96255] text-[#8A4138]",
    pending: "bg-card border-border text-faint",
    skipped: "bg-card border-dashed border-border text-faint",
  }[step.state];
  return (
    <button
      type="button" onClick={onClick} aria-current={current ? "page" : undefined}
      aria-label={`${step.label}: ${step.detail}`}
      className={`group flex flex-col items-center gap-1.5 min-w-[84px] rounded-xl px-1 py-1 ${current ? "bg-soft/60" : "hover:bg-soft/40"}`}
    >
      <motion.span
        layout initial={false} animate={step.state === "done" ? { scale: [0.85, 1.08, 1] } : { scale: 1 }} transition={{ duration: 0.35 }}
        className={`relative h-8 w-8 rounded-full border flex items-center justify-center text-[11px] font-bold ${tone}`}
      >
        {step.state === "done" ? <Check size={15} /> : step.state === "active" ? <Loader2 size={15} className="animate-spin" /> :
          step.state === "failed" ? <AlertTriangle size={14} /> : step.state === "skipped" ? <Minus size={14} /> : String(index + 1).padStart(2, "0")}
        {step.state === "active" && <span className="absolute inset-0 rounded-full pulse-dot" aria-hidden="true" />}
      </motion.span>
      <span className={`text-[10px] tracking-[.1em] font-bold uppercase ${step.state === "pending" || step.state === "skipped" ? "text-muted" : "text-brand"}`}>{step.label}</span>
      <span className="text-[10.5px] leading-tight text-muted text-center max-w-[110px] line-clamp-2">{step.detail}</span>
    </button>
  );
}

function Connector({ filled, flowing }: { filled: boolean; flowing: boolean }) {
  return (
    <div className="relative h-px flex-1 mt-4 mx-1 bg-border overflow-hidden" aria-hidden="true">
      <motion.div className="absolute inset-y-0 left-0 right-0 bg-brand/70 origin-left" initial={false} animate={{ scaleX: filled ? 1 : 0 }} transition={{ duration: 0.5, ease: "easeOut" }} />
      {flowing && <div className="absolute inset-y-0 w-1/3 bg-gradient-to-r from-transparent via-brand to-transparent scan-line-x" />}
    </div>
  );
}
