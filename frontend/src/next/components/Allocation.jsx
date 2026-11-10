import { memo } from "react";
// Holdings by weight. A row click focuses the chart on that instrument.

import { motion } from "framer-motion";
import { arrow, money, ratioPct, share, toneOf } from "../../format.js";
import { ease, spring } from "../ui/motion.js";
import { useT } from "../i18n/index.jsx";

function Allocation({ positions, focusTickers, onFocus }) {
  const t = useT();
  const rows = positions
    // A sold-out position holds nothing, so it has no place in a split of what is held.
    .filter((p) => p.ok && Number(p.quantity) !== 0)
    .map((p) => ({ ...p, value: Number(p.market_value_try) }))
    .sort((a, b) => b.value - a.value);
  const total = rows.reduce((s, p) => s + p.value, 0) || 1;
  const max = rows[0]?.value || 1;

  return (
    <section className="card" id="dagilim" aria-label={t("alloc.title")}>
      <header className="card-head">
        <h2>{t("alloc.title")}</h2>
        <span className="muted num">{rows.length}</span>
      </header>
      <ul className="alloc">
        {rows.map((p, i) => {
          const on = focusTickers.includes(p.ticker);
          return (
            <motion.li
              key={p.ticker}
              layout
              transition={spring}
              initial={{ opacity: 0, x: -12 }}
              animate={{ opacity: 1, x: 0, transition: { delay: 0.04 * i, duration: 0.4, ease } }}
            >
              <button type="button" className={`alloc-row ${on ? "on" : ""}`} aria-pressed={on} onClick={() => onFocus(p.ticker)}>
                <span className="alloc-sym">
                  <span className={`session-dot ${p.session === "open" ? "open" : ""}`} />
                  {p.ticker}
                </span>
                <span className="alloc-bar">
                  <motion.i
                    initial={{ scaleX: 0 }}
                    animate={{ scaleX: p.value / max }}
                    transition={{ duration: 0.8, delay: 0.05 * i, ease }}
                  />
                </span>
                <span className="alloc-weight num">{share((p.value / total) * 100)}</span>
                <span className="alloc-value num">{money(p.value)}</span>
                <span className={`alloc-ret num ${toneOf(Number(p.attribution.total_return) - 1)}`}>
                  {arrow(Number(p.attribution.total_return) - 1)} {ratioPct(p.attribution.total_return)}
                </span>
              </button>
            </motion.li>
          );
        })}
      </ul>
    </section>
  );
}

// Memoized: chart polls and range changes re-render the dashboard, not this card.
export default memo(Allocation);
