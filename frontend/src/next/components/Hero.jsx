import { memo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { arrow, fullDate, money, num, pct, ratioPct, signedMoney, toneOf } from "../../format.js";
import AnimatedNumber from "../ui/AnimatedNumber.jsx";
import Icon from "../ui/Icons.jsx";
import { collapse, fadeUp, stagger } from "../ui/motion.js";
import { useTilt } from "../ui/useTilt.js";

function Metric({ label, children, sub, tone }) {
  const tilt = useTilt();
  return (
    <motion.div variants={fadeUp} className="tilt-host" {...tilt}>
      <div className={`metric tilt ${tone ?? ""}`}>
        <span className="label">{label}</span>
        <div className="metric-value">{children}</div>
        {sub && <div className="metric-sub">{sub}</div>}
      </div>
    </motion.div>
  );
}

function Hero({ portfolio }) {
  const { liquidation, totals, tax } = portfolio;
  const daily = totals.daily;
  const [showTax, setShowTax] = useState(false);
  const hasHaircut = Number(liquidation.haircut_pct) > 0;
  const taxShown = tax?.applicable && Number(tax.tax_try) > 0;
  const tone = toneOf(liquidation.net_pnl_try);

  return (
    <motion.section className="hero" id="ozet" aria-label="Portföy özeti" variants={stagger(0.07)} initial="hidden" animate="show">
      <motion.div variants={fadeUp} className={`hero-main glow-${tone}`}>
        <span className="label">Nakde çevirme değeri · net</span>
        <AnimatedNumber value={liquidation.net_proceeds_try} format={money} className="hero-figure" />
        <div className={`hero-pnl ${tone}`}>
          <span className="pill num">
            {arrow(liquidation.net_pnl_try)} <AnimatedNumber value={liquidation.net_pnl_try} format={signedMoney} />
          </span>
          <span className="pill num">{ratioPct(liquidation.net_return)}</span>
        </div>
        <p className="hero-caveat">
          Tahminî · <strong>vergi hariç</strong> ·{" "}
          {hasHaircut
            ? `%${(Number(liquidation.haircut_pct) * 100).toFixed(2)} kur/komisyon kesintisi (${money(liquidation.haircut_try)})`
            : "kesinti yok"}
        </p>

        {tax?.applicable && (
          <div className="after-tax">
            <button type="button" className="after-tax-row" onClick={() => setShowTax((v) => !v)} aria-expanded={showTax}>
              <span className="label">Vergi sonrası</span>
              <AnimatedNumber value={tax.net_after_tax_try} format={money} className="after-tax-value" />
              <motion.span animate={{ rotate: showTax ? 180 : 0 }} className="after-tax-caret">
                <Icon name="down" size={16} />
              </motion.span>
            </button>
            <div className="after-tax-sub num">
              {taxShown ? (
                <>
                  vergi <strong>−{money(tax.tax_try)}</strong> · matrah {money(tax.taxable_gain_try)} · efektif{" "}
                  {pct(Number(tax.effective_rate) * 100)} · dilim %{num(Number(tax.marginal_rate) * 100, 0)}
                </>
              ) : (
                "vergiye tabi kazanç yok"
              )}
            </div>
            <AnimatePresence initial={false}>
              {showTax && (
                <motion.div className="tax-detail" {...collapse}>
                  <div className="tax-detail-inner">
                    {taxShown && Number(tax.fx_portion_try) !== 0 && (
                      <div className="tax-split">
                        <span>Yerel fiyat kazancı</span>
                        <span className="num">{signedMoney(tax.price_portion_try)}</span>
                        <span className="num">≈ {money(tax.tax_on_price_try)}</span>
                        <span className="fx-text">Kur farkı kazancı</span>
                        <span className="num">{signedMoney(tax.fx_portion_try)}</span>
                        <span className="num">≈ {money(tax.tax_on_fx_try)}</span>
                        <strong>Matrah</strong>
                        <strong className="num">{money(tax.taxable_gain_try)}</strong>
                        <strong className="num">{money(tax.tax_try)}</strong>
                      </div>
                    )}
                    <ul>
                      {tax.assumptions.map((a, i) => <li key={i}>{a}</li>)}
                    </ul>
                    <p className="fineprint">{tax.disclaimer}</p>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}
      </motion.div>

      <div className="hero-metrics">
        <Metric label="Yatırılan">
          <AnimatedNumber value={liquidation.total_invested_try} format={money} />
        </Metric>
        <Metric label="Piyasa değeri">
          <AnimatedNumber value={totals.market_value_try} format={money} />
        </Metric>
        <Metric label="Toplam getiri" tone={toneOf(totals.pnl_try)} sub={<AnimatedNumber value={totals.pnl_try} format={signedMoney} className={toneOf(totals.pnl_try)} />}>
          <span className={toneOf(totals.pnl_try)}>
            {arrow(totals.pnl_try)} <AnimatedNumber value={totals.total_return} format={ratioPct} />
          </span>
        </Metric>
        <Metric
          label="Günlük"
          tone={daily?.available ? toneOf(daily.pnl_try) : undefined}
          sub={
            daily?.available ? (
              <span className="num" title={`Önceki seans: ${fullDate(daily.reference_date)}`}>
                fiyat {signedMoney(daily.price_effect_try)} · kur {signedMoney(daily.fx_effect_try)}
              </span>
            ) : null
          }
        >
          {daily?.available ? (
            <span className={toneOf(daily.pnl_try)}>
              {arrow(daily.pnl_try)} <AnimatedNumber value={daily.pnl_try} format={signedMoney} />
              {daily.return_ratio !== null && <small className="num"> {ratioPct(daily.return_ratio)}</small>}
            </span>
          ) : (
            <span className="muted small-text">önceki seans yok</span>
          )}
        </Metric>
      </div>
    </motion.section>
  );
}

// Memoized: chart polls and range changes re-render the dashboard, not this card.
export default memo(Hero);
