// The mark is the thesis: one investment, entering at a single point, whose return
// in lira separates into two components that travel apart — the local price move and
// the currency move. Two strokes diverging from one origin, in the same slate and
// dusty purple the chart uses for those two series, so the logo and the data agree.

export default function Brand() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      {/* `var()` is set through `style` rather than as a presentation attribute — the
          latter is not reliably resolved for SVG paint. */}
      <path
        d="M3 17.5C7.5 17.5 10 13 13 9.5C15.5 6.5 18 5 21 5"
        style={{ stroke: "var(--price)" }}
        strokeWidth="1.6"
        strokeLinecap="round"
      />
      <path
        d="M3 17.5C7.5 17.5 11 16 14.5 15C17.5 14.2 19.5 14 21 14"
        style={{ stroke: "var(--fx)" }}
        strokeWidth="1.6"
        strokeLinecap="round"
      />
      <circle cx="3" cy="17.5" r="2.1" style={{ fill: "var(--text)" }} />
    </svg>
  );
}
