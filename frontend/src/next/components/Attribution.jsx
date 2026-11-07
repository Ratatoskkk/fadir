// Price effect vs FX effect. Segments are sized by magnitude so a negative contribution
// is still visible; negative segments are hatched so the sign never relies on colour.

import { motion } from "framer-motion";
import { arrow, signedMoney, toneOf } from "../../format.js";
import AnimatedNumber from "../ui/AnimatedNumber.jsx";
import { ease } from "../ui/motion.js";

export default function Attribution({ totals }) {
  const price = Number(totals.price_effect_try);
  const fx = Number(totals.fx_effect_try);
  const pnl = Number(totals.pnl_try);
  const magnitude = Math.abs(price) + Math.abs(fx);
  const pricePct = magnitude === 0 ? 50 : (Math.abs(price) / magnitude) * 100;
  const share = (v) => (magnitude === 0 ? "—" : `${((Math.abs(v) / magnitude) * 100).toFixed(0)}%`);
  const realized = Number(totals.realized_pnl_try);

  return (
    <section className="card" id="ayristirma" aria-label="Getiri ayrıştırması">
      <header className="card-head">
        <h2>Fiyat ve kur</h2>
        <span className={`head-figure num ${toneOf(pnl)}`}>
          {arrow(pnl)} <AnimatedNumber value={pnl} format={signedMoney} />
        </span>
      </header>

      <div
        className="attr-track"
        role="img"
        aria-label={`Fiyat etkisi ${signedMoney(price)}, toplamın ${share(price)}'i. Kur etkisi ${signedMoney(fx)}, toplamın ${share(fx)}'i.`}
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
          <span className="label">Fiyat etkisi</span>
          <span className={`num ${toneOf(price)}`}>{arrow(price)} <AnimatedNumber value={price} format={signedMoney} /></span>
        </div>
        <div className="attr-item">
          <i className="dot fx" />
          <span className="label">Kur etkisi</span>
          <span className={`num ${toneOf(fx)}`}>{arrow(fx)} <AnimatedNumber value={fx} format={signedMoney} /></span>
        </div>
        {realized !== 0 && (
          <div className="attr-item">
            <i className="dot cost" />
            <span className="label">Gerçekleşen</span>
            <span className={`num ${toneOf(realized)}`}>{signedMoney(realized)}</span>
          </div>
        )}
      </div>
    </section>
  );
}
