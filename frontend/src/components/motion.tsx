import { animate, AnimatePresence, motion, MotionConfig, useReducedMotion } from "framer-motion";
import { ReactNode, useEffect, useRef, useState } from "react";

const EASE = [0.22, 1, 0.36, 1] as const;

/** Wrap the app once. `reducedMotion="user"` makes every framer-motion transform respect the OS setting. */
export function MotionRoot({ children }: { children: ReactNode }) {
  return <MotionConfig reducedMotion="user">{children}</MotionConfig>;
}

export function Reveal({ children, delay = 0, className = "" }: { children: ReactNode; delay?: number; className?: string }) {
  return (
    <motion.div initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay, ease: EASE }} className={className}>
      {children}
    </motion.div>
  );
}

const staggerVariants = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.07 } } };
const itemVariants = { hidden: { opacity: 0, y: 14 }, show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: EASE } } };

/** Children must be <StaggerItem> (or any motion element using the same "hidden"/"show" variants) to stagger. */
export function Stagger({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <motion.div initial="hidden" animate="show" variants={staggerVariants} className={className}>{children}</motion.div>;
}

export function StaggerItem({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <motion.div variants={itemVariants} className={className}>{children}</motion.div>;
}

const NUMERIC = /^(-?\d+(?:\.\d+)?)(%?)$/;

/**
 * Counts up to a REAL value. Strings that are not plain numbers ("3 of 7", "—") fade in unchanged.
 * Screen readers get the final value only (no stream of intermediate numbers).
 */
export function AnimatedNumber({ value, duration = 0.9 }: { value: number | string; duration?: number }) {
  const reduce = useReducedMotion();
  const parsed = typeof value === "number" ? { n: value, suffix: "", decimals: decimalsOf(String(value)) } : parse(value);
  const [shown, setShown] = useState<number>(parsed && !reduce ? 0 : parsed?.n ?? 0);
  const first = useRef(true);

  useEffect(() => {
    if (!parsed) return;
    if (reduce) { setShown(parsed.n); return; }
    const from = first.current ? 0 : shown;
    first.current = false;
    const controls = animate(from, parsed.n, { duration, ease: EASE, onUpdate: (v) => setShown(v) });
    return () => controls.stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [parsed?.n, reduce, duration]);

  if (!parsed) {
    return <motion.span initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }}>{value}</motion.span>;
  }
  const text = `${shown.toFixed(parsed.decimals)}${parsed.suffix}`;
  return (
    <span>
      <span aria-hidden="true">{text}</span>
      <span className="sr-only">{`${parsed.n.toFixed(parsed.decimals)}${parsed.suffix}`}</span>
    </span>
  );
}

function decimalsOf(s: string) { return s.includes(".") ? s.split(".")[1].length : 0; }
function parse(v: string) {
  const m = NUMERIC.exec(v.trim());
  return m ? { n: parseFloat(m[1]), suffix: m[2], decimals: decimalsOf(m[1]) } : null;
}

/** Cross-fade between screens. Pair with <AnimatePresence mode="wait"> and a changing `id`. */
export function PageTransition({ id, children, className = "" }: { id: string; children: ReactNode; className?: string }) {
  return (
    <motion.div data-screen={id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} transition={{ duration: 0.22, ease: "easeOut" }} className={className}>
      {children}
    </motion.div>
  );
}

export { AnimatePresence };
