// Hero stays pinned on top; the sections under it can be dragged (or nudged with the
// arrow keys on the handle) into any order, which persists per browser.

import { useCallback, useState } from "react";
import { Reorder, useDragControls } from "framer-motion";
import Allocation from "../components/Allocation.jsx";
import Attribution from "../components/Attribution.jsx";
import ChartCard from "../components/ChartCard.jsx";
import Hero from "../components/Hero.jsx";
import Icon from "../ui/Icons.jsx";
import { spring } from "../ui/motion.js";

const SECTIONS = [
  { id: "grafik", label: "Grafik" },
  { id: "ayristirma", label: "Fiyat ve kur" },
  { id: "dagilim", label: "Dağılım" },
];
const DEFAULT_ORDER = SECTIONS.map((s) => s.id);
const LAYOUT_KEY = "fadir.next.layout";

function loadOrder() {
  try {
    const saved = JSON.parse(localStorage.getItem(LAYOUT_KEY) ?? "null");
    if (!Array.isArray(saved)) return DEFAULT_ORDER;
    const known = saved.filter((id) => DEFAULT_ORDER.includes(id));
    return [...known, ...DEFAULT_ORDER.filter((id) => !known.includes(id))];
  } catch {
    return DEFAULT_ORDER;
  }
}

function Section({ id, label, onNudge, children }) {
  const controls = useDragControls();
  return (
    <Reorder.Item
      value={id}
      dragListener={false}
      dragControls={controls}
      className="reorder-item"
      transition={spring}
      whileDrag={{ scale: 1.012, boxShadow: "0 30px 80px -20px rgba(0,0,0,0.55)", zIndex: 5 }}
    >
      <button
        type="button"
        className="drag-handle"
        onPointerDown={(e) => { e.preventDefault(); controls.start(e); }}
        onKeyDown={(e) => {
          if (e.key === "ArrowUp") { e.preventDefault(); onNudge(-1); }
          if (e.key === "ArrowDown") { e.preventDefault(); onNudge(1); }
        }}
        aria-label={`${label} bölümünü taşı (ok tuşları)`}
        title="Sürükleyerek taşıyın"
      >
        <Icon name="drag" size={16} />
      </button>
      {children}
    </Reorder.Item>
  );
}

export default function Overview({ dash }) {
  const [order, setOrder] = useState(loadOrder);
  const { portfolio } = dash;

  const persist = useCallback((next) => {
    setOrder(next);
    try { localStorage.setItem(LAYOUT_KEY, JSON.stringify(next)); } catch { /* private mode */ }
  }, []);

  const nudge = (id, delta) => {
    const from = order.indexOf(id);
    const to = from + delta;
    if (from < 0 || to < 0 || to >= order.length) return;
    const next = [...order];
    next.splice(to, 0, next.splice(from, 1)[0]);
    persist(next);
  };

  return (
    <div className="stack">
      <Hero portfolio={portfolio} />
      <Reorder.Group axis="y" values={order} onReorder={persist} className="reorder">
        {order.map((id) => {
          const meta = SECTIONS.find((s) => s.id === id);
          return (
            <Section key={id} id={id} label={meta.label} onNudge={(d) => nudge(id, d)}>
              {id === "grafik" && <ChartCard dash={dash} />}
              {id === "ayristirma" && <Attribution totals={portfolio.totals} />}
              {id === "dagilim" && <Allocation positions={portfolio.positions} focusTickers={dash.focusTickers} onFocus={dash.toggleFocus} />}
            </Section>
          );
        })}
      </Reorder.Group>
      {order.join() !== DEFAULT_ORDER.join() && (
        <button type="button" className="btn ghost small center" onClick={() => persist(DEFAULT_ORDER)}>
          Düzeni sıfırla
        </button>
      )}
    </div>
  );
}
