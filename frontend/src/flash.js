// Movement feedback for figures that update underneath the reader.
//
// A dashboard that refreshes silently has a specific failure: you cannot tell whether a
// number is current or whether the poll died twenty minutes ago. A brief tint on the
// values that actually changed answers that without a banner, and says which way they
// went while it does it.
//
// Deliberately restrained — a short, low-opacity wash, no motion, nothing that moves
// layout. It also respects `prefers-reduced-motion` through the global block in
// styles.css, which collapses the animation rather than removing the information.

import { useEffect, useRef, useState } from "react";

const FLASH_MS = 900;

/**
 * Returns a class name for one render cycle after `value` changes: `flash-up` when it
 * rose, `flash-down` when it fell, empty otherwise.
 *
 * The first observed value never flashes — arriving is not changing, so a fresh page
 * load stays calm instead of lighting up every figure at once.
 */
export function useFlash(value) {
  const previous = useRef(undefined);
  const [state, setState] = useState("");

  useEffect(() => {
    const before = previous.current;
    previous.current = value;

    if (before === undefined || value === undefined || value === null) return undefined;
    if (Object.is(before, value)) return undefined;

    const rose = Number(value) > Number(before);
    if (!Number.isFinite(Number(value)) || !Number.isFinite(Number(before))) return undefined;

    setState(rose ? "flash-up" : "flash-down");
    const timer = window.setTimeout(() => setState(""), FLASH_MS);
    return () => window.clearTimeout(timer);
  }, [value]);

  return state;
}
