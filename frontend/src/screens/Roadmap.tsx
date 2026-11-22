import { roadmapItems } from "../data/roadmapContent";
import { Panel, SectionTitle } from "../components/ui";
import { Stagger, StaggerItem } from "../components/motion";

export default function Roadmap() {
  return (
    <Stagger className="max-w-4xl mx-auto space-y-6">
      <StaggerItem><SectionTitle
        eyebrow="Beyond this build"
        title="What's real today, and what's next"
        description="This roadmap separates capabilities implemented in Phase 3–4 from integrations and evidence claims that still require external validation or deployment configuration."
      /></StaggerItem>

      <StaggerItem><div className="space-y-3">
        {roadmapItems.map((item, i) => (
          <Panel key={i} className="p-5 sm:p-6 flex flex-col sm:flex-row sm:items-start justify-between gap-3 sm:gap-6">
            <div>
              <p className="text-[13.5px] font-semibold text-ink mb-1">{item.title}</p>
              <p className="text-[12.5px] text-muted leading-relaxed max-w-xl">
                {item.detail}
              </p>
            </div>
            <span className="shrink-0 font-mono text-[11px] text-brand border border-brand/30 bg-soft px-2.5 py-1 rounded-lg self-start">
              {item.status}
            </span>
          </Panel>
        ))}
      </div></StaggerItem>
    </Stagger>
  );
}
