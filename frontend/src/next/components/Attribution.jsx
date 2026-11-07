import { memo } from "react";
// Price effect vs FX effect. Segments are sized by magnitude so a negative contribution
// is still visible; negative segments are hatched so the sign never relies on colour.

import { motion } from "framer-motion";
import { arrow, signedMoney, toneOf } from "../../format.js";
import AnimatedNumber from "../ui/AnimatedNumber.jsx";
import { ease } from "../ui/motion.js";
import { useT } from "../i18n/index.jsx";

function Attribution({ totals }) {
  const t = useT();
  const price = Number(totals.price_effect_try);
  const fx = Number(totals.fx_effect_try);
  const pnl = Number(totals.pnl_try);
  const magnitude = Math.abs(price) + Math.abs(fx);
  const pricePct = magnitude === 0 ? 50 : (Math.abs(price) / magnitude) * 100;
  const share = (v) => (magnitude === 0 ? "—" : `${((Math.abs(v) / magnitude) * 100).toFixed(0)}%`);
  const realized = Number(totals.realized_pnl_try);

  return (
    <section className="card" id="ayristirma" aria-label={t("attr.aria")}>
      <header className="card-head">
        <h2>{t("attr.title")}</h2>
        <span className={`head-figure num ${toneOf(pnl)}`}>
          {arrow(pnl)} <AnimatedNumber value={pnl} format={signedMoney} />
        </span>
      </header>

      <div
        className="attr-track"
        role="img"
        aria-label={t("attr.barAria", { price: signedMoney(price), priceShare: share(price), fx: signedMoney(fx), fxShare: share(fx) })}
      >
        <motion.div
          className={`attr-seg price ${price < 0 ? "neg" : ""}`}
          initial={{ scaleX: 0 }}
          animate={{ scaleX: 1 }}
          transition={{ duration: 0.9, ease }}
          style={{ width: `${pricePct}%`, left: 0 }}
        >
          {pricePct > 14 && <span>Fiyat {share(price)}</span>}
        </motion.div>
        <motion.div
          className={`attr-seg fx ${fx < 0 ? "neg" : ""}`}
          initial={{ scaleX: 0 }}
          animate={{ scaleX: 1 }}
          transition={{ duration: 0.9, delay: 0.25, ease }}
          style={{ width: `${100 - pricePct}%`, left: `${pricePct}%` }}
        >
          {100 - pricePct > 14 && <span>Kur {share(fx)}</span>}
        </motion.div>
      </div>

      <div className="attr-legend">
        <div className="attr-item">
          <i className="dot price" />
          <span className="label">{t("attr.price")}</span>
          <span className={`num ${toneOf(price)}`}>{arrow(price)} <AnimatedNumber value={price} format={signedMoney} /></span>
        </div>
        <div className="attr-item">
          <i className="dot fx" />
          <span className="label">{t("attr.fx")}</span>
          <span className={`num ${toneOf(fx)}`}>{arrow(fx)} <AnimatedNumber value={fx} format={signedMoney} /></span>
        </div>
        {realized !== 0 && (
          <div className="attr-item">
            <i className="dot cost" />
            <span className="label">{t("attr.realized")}</span>
            <span className={`num ${toneOf(realized)}`}>{signedMoney(realized)}</span>
          </div>
        )}
      </div>
    </section>
  );
}

// Memoized: chart polls and range changes re-render the dashboard, not this card.
export default memo(Attribution);
