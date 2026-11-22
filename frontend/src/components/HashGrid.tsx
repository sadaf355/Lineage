import { motion, useReducedMotion } from "framer-motion";
import { gridColumns, hexToBits, popcount } from "../lib/hashBits";

/**
 * Draws a REAL perceptual hash: one cell per bit (set = filled). Cells appear in reading order.
 * Returns nothing when the value is absent or not hex, so no placeholder pattern is ever shown as if it were data.
 */
export default function HashGrid({ label, hex }: { label: string; hex: string | null | undefined }) {
  const reduce = useReducedMotion();
  const bits = hexToBits(hex);
  if (!bits || bits.length === 0) return null;
  const cols = gridColumns(bits.length);
  const set = popcount(bits);
  return (
    <figure className="min-w-0">
      <div role="img" aria-label={`${label}: ${bits.length}-bit hash ${hex}, ${set} bits set`}
        className="grid gap-[3px] w-full max-w-[120px] mx-auto" style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}>
        {bits.map((b, i) => (
          <motion.span key={i} aria-hidden="true" className={`aspect-square rounded-[2px] ${b ? "bg-brand" : "bg-soft border border-border/60"}`}
            initial={reduce ? false : { opacity: 0, scale: 0.4 }} animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.25, delay: reduce ? 0 : i * 0.012 }} />
        ))}
      </div>
      <figcaption className="mt-2 text-center">
        <span className="block text-[10.5px] font-semibold text-ink">{label}</span>
        <span className="block font-mono text-[9.5px] text-muted break-all">{hex}</span>
        <span className="block text-[10px] text-muted">{set} of {bits.length} bits set</span>
      </figcaption>
    </figure>
  );
}
