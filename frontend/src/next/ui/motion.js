// Shared motion vocabulary. Everything animates transform and opacity only, so it all
// runs on the compositor and holds 60fps; layout-affecting properties are never tweened
// except height on rare disclosures.

export const spring = { type: "spring", stiffness: 520, damping: 46, mass: 0.9 };
export const softSpring = { type: "spring", stiffness: 260, damping: 30 };
export const bouncy = { type: "spring", stiffness: 420, damping: 38 };
export const ease = [0.16, 1, 0.3, 1];

export const fadeUp = {
  hidden: { opacity: 0, y: 8 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease } },
};

export const stagger = (gap = 0.06, delay = 0) => ({
  hidden: {},
  show: { transition: { staggerChildren: gap, delayChildren: delay } },
});

export const viewTransition = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.32, ease } },
  exit: { opacity: 0, y: -8, transition: { duration: 0.18, ease } },
};

export const collapse = {
  initial: { height: 0, opacity: 0 },
  animate: { height: "auto", opacity: 1, transition: { height: { duration: 0.32, ease }, opacity: { duration: 0.25, delay: 0.05 } } },
  exit: { height: 0, opacity: 0, transition: { height: { duration: 0.24, ease }, opacity: { duration: 0.12 } } },
};

export const prefersReducedMotion = () =>
  typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
