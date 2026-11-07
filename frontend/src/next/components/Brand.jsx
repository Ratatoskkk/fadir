// The mark: one origin, two strokes travelling apart — local price and currency. They
// draw themselves in on load, in the same colours the chart uses for those two series.

import { motion } from "framer-motion";

export default function Brand({ size = 26 }) {
  const draw = (delay) => ({
    initial: { pathLength: 0, opacity: 0 },
    animate: { pathLength: 1, opacity: 1, transition: { pathLength: { duration: 1.1, delay, ease: [0.65, 0, 0.35, 1] }, opacity: { duration: 0.2, delay } } },
  });
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} fill="none" aria-hidden="true" className="brand-mark">
      <motion.path d="M3 17.5C7.5 17.5 10 13 13 9.5C15.5 6.5 18 5 21 5" style={{ stroke: "var(--price)" }} strokeWidth="2" strokeLinecap="round" {...draw(0.15)} />
      <motion.path d="M3 17.5C7.5 17.5 11 16 14.5 15C17.5 14.2 19.5 14 21 14" style={{ stroke: "var(--fx)" }} strokeWidth="2" strokeLinecap="round" {...draw(0.35)} />
      <motion.circle cx="3" cy="17.5" r="2.3" style={{ fill: "var(--text)" }} initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: "spring", stiffness: 500, damping: 15 }} />
    </svg>
  );
}
