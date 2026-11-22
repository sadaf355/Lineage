import { animate, useReducedMotion } from "framer-motion";
import { useEffect, useState } from "react";

/** Ring that sweeps to a REAL percentage (0-100). Remounts per result via `key` so each new detection re-reveals. */
export default function RingGauge({ value, color = "#B96255", label }: { value: number; color?: string; label: string }) {
  const target = Math.max(0, Math.min(100, Number.isFinite(value) ? value : 0));
  const reduce = useReducedMotion();
  const [shown, setShown] = useState(reduce ? target : 0);
  useEffect(() => {
    if (reduce) { setShown(target); return; }
    const c = animate(0, target, { duration: 1.1, ease: [0.22, 1, 0.36, 1], onUpdate: setShown });
    return () => c.stop();
  }, [target, reduce]);
  return (
    <div role="img" aria-label={`${label}: ${Math.round(target)} percent`}
      className="h-36 w-36 rounded-full flex items-center justify-center shrink-0 shadow-xs"
      style={{ background: `conic-gradient(${color} ${shown}%, #E9EDE8 0)` }}>
      <div className="h-28 w-28 bg-card rounded-full flex flex-col items-center justify-center shadow-xs" aria-hidden="true">
        <b className="text-[34px] font-semibold text-ink leading-none">{Math.round(shown)}%</b>
        <span className="text-[10px] text-muted font-medium mt-1">likelihood</span>
      </div>
    </div>
  );
}
