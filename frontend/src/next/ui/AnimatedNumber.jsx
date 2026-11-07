// A figure that counts to its new value instead of jumping.
//
// The tween writes textContent straight from requestAnimationFrame, so a counting number
// costs no React renders at all. The first value counts up from zero; later changes tween
// from what is on screen and tint briefly in the direction they moved.

import { useLayoutEffect, useRef, useState } from "react";
import { prefersReducedMotion } from "./motion.js";

const easeOutExpo = (t) => (t >= 1 ? 1 : 1 - 2 ** (-10 * t));

export default function AnimatedNumber({ value, format, className = "", duration = 750, countUp = true }) {
  const ref = useRef(null);
  const shown = useRef(null);
  // Held in a ref so an inline formatter does not restart the tween on every render.
  const formatRef = useRef(format);
  formatRef.current = format;
  const [tick, setTick] = useState("");

  useLayoutEffect(() => {
    const node = ref.current;
    if (!node) return undefined;
    const format = formatRef.current;
    const target = Number(value);
    if (value === null || value === undefined || !Number.isFinite(target)) {
      node.textContent = format(value);
      shown.current = null;
      return undefined;
    }

    const first = shown.current === null;
    const from = first ? (countUp ? 0 : target) : shown.current;
    if (prefersReducedMotion() || from === target) {
      node.textContent = format(target);
      shown.current = target;
      return undefined;
    }

    let timer;
    if (!first) {
      setTick(target > from ? "tick-up" : "tick-down");
      timer = window.setTimeout(() => setTick(""), 900);
    }

    const span = first ? duration * 1.5 : duration;
    const start = performance.now();
    let frame;
    const step = (now) => {
      const t = Math.min(1, (now - start) / span);
      const current = from + (target - from) * easeOutExpo(t);
      shown.current = t >= 1 ? target : current;
      node.textContent = format(shown.current);
      if (t < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => {
      cancelAnimationFrame(frame);
      window.clearTimeout(timer);
    };
  }, [value, duration, countUp]);

  return <span ref={ref} className={`anum num ${tick} ${className}`} />;
}
