// Ambient background: soft radial blobs drifting on CSS keyframes. Radial gradients need
// no blur filter, and only transform animates, so the whole thing lives on the
// compositor at no main-thread cost. Frozen under prefers-reduced-motion.

export default function Aurora() {
  return (
    <div className="aurora" aria-hidden="true">
      <i className="blob b1" />
      <i className="blob b2" />
      <i className="blob b3" />
      <div className="grain" />
    </div>
  );
}
