// Pointer-follow tilt for cards. Writes CSS variables directly on the element, so the
// effect is a compositor-only transform with no React renders while the pointer moves.

import { useCallback } from "react";
import { prefersReducedMotion } from "./motion.js";

export function useTilt(strength = 6) {
  const onPointerMove = useCallback((e) => {
    if (e.pointerType !== "mouse" || prefersReducedMotion()) return;
    const el = e.currentTarget;
    const r = el.getBoundingClientRect();
    const px = (e.clientX - r.left) / r.width - 0.5;
    const py = (e.clientY - r.top) / r.height - 0.5;
    el.style.setProperty("--rx", `${(-py * strength).toFixed(2)}deg`);
    el.style.setProperty("--ry", `${(px * strength).toFixed(2)}deg`);
    el.style.setProperty("--mx", `${((px + 0.5) * 100).toFixed(1)}%`);
    el.style.setProperty("--my", `${((py + 0.5) * 100).toFixed(1)}%`);
  }, [strength]);

  const onPointerLeave = useCallback((e) => {
    const el = e.currentTarget;
    el.style.setProperty("--rx", "0deg");
    el.style.setProperty("--ry", "0deg");
  }, []);

  return { onPointerMove, onPointerLeave, "data-tilt": "" };
}
