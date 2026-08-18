// Layout item 1 (SPEC §9): liquidation-to-TRY value, absolute PnL, % return.
//
// The figure is explicitly labelled an estimate that excludes tax — §6 and US-3.2 both
// require the caveat to be visible, not buried in a tooltip.

import { useState } from "react";
import { useFlash } from "../flash.js";
import { arrow, fullDate, money, num, pct, ratioPct, signedMoney, toneOf } from "../format.js";

export default function HeroCard({ portfolio }) {
  const { liquidation, totals, tax } = portfolio;
  const daily = totals.daily;

  // The three figures that move on a poll. Flashing the whole card would be noise;
  // these are the ones worth noticing.
  const flashNet = useFlash(liquidation.net_proceeds_try);
  const flashValue = useFlash(totals.market_value_try);
  const flashReturn = useFlash(totals.pnl_try);
  const tone = toneOf(liquidation.net_pnl_try);
  const hasHaircut = Number(liquidation.haircut_pct) > 0;
  const [showTaxDetail, setShowTaxDetail] = useState(false);

  const taxShown = tax?.applicable && Number(tax.tax_try) > 0;

  return (
    <section className="hero" id="ozet" aria-label="Portföy özeti">
      <div className={`hero-cell flash-cell ${flashNet}`}>
        <div className="hero-label">Nakde çevirme değeri (net)</div>
        <div className="hero-value num">{money(liquidation.net_proceeds_try)}</div>

        <div className={`pnl-line num ${tone}`}>
          <span aria-hidden="true">{arrow(liquidation.net_pnl_try)}</span>
          <span>{signedMoney(liquidation.net_pnl_try)}</span>
          <span>{ratioPct(liquidation.net_return)}</span>
        </div>

        {tax?.applicable && (
          <div className="after-tax">
            <div className="after-tax-row">
              <span className="after-tax-label">
                Vergi sonrası (yaklaşık)
                <button
                  type="button"
                  className="info-toggle"
                  onClick={() => setShowTaxDetail((v) => !v)}
                  aria-expanded={showTaxDetail}
                  title="Hesaplama varsayımlarını göster"
                >
                  {showTaxDetail ? "gizle" : "nasıl?"}
                </button>
              </span>
              <span className="after-tax-value num">
                {money(tax.net_after_tax_try)}
              </span>
            </div>

            <div className="after-tax-sub num">
              {taxShown ? (
                <>
                  tahminî vergi <strong>−{money(tax.tax_try)}</strong>{" "}
                  · matrah {money(tax.taxable_gain_try)} · efektif{" "}
                  {pct(Number(tax.effective_rate) * 100)} · marjinal dilim %
                  {num(Number(tax.marginal_rate) * 100, 0)}
                </>
              ) : (
                <>vergiye tabi kazanç oluşmuyor</>
              )}
            </div>

            {showTaxDetail && (
              <div className="tax-detail">
                {/* The currency gain is inside the taxable base by construction, not a
                    separate charge. Spelling out the split is the only way that is
                    visible — the single tax figure alone cannot show it. */}
                {taxShown && Number(tax.fx_portion_try) !== 0 && (
                  <table className="tax-split">
                    <tbody>
                      <tr>
                        <td>Yerel fiyat kazancı</td>
                        <td className="num">{signedMoney(tax.price_portion_try)}</td>
                        <td className="num">≈ {money(tax.tax_on_price_try)} vergi</td>
                      </tr>
                      <tr>
                        <td>
                          <span className="fx-mark">Kur farkı kazancı</span>
                        </td>
                        <td className="num">{signedMoney(tax.fx_portion_try)}</td>
                        <td className="num">≈ {money(tax.tax_on_fx_try)} vergi</td>
                      </tr>
                      <tr className="tax-split-total">
                        <td>Matrah</td>
                        <td className="num">{money(tax.taxable_gain_try)}</td>
                        <td className="num">{money(tax.tax_try)} vergi</td>
                      </tr>
                    </tbody>
                  </table>
                )}
                <ul>
                  {tax.assumptions.map((a, i) => (
                    <li key={i}>{a}</li>
                  ))}
                </ul>
                <p className="tax-disclaimer">⚠ {tax.disclaimer}</p>
              </div>
            )}
          </div>
        )}

        <div className="hero-note">
          Tahminî değer. Tüm pozisyonların güncel piyasa fiyatından satılıp bugün TRY’ye
          çevrildiği varsayılır. <strong>Vergi hariçtir.</strong>{" "}
          {hasHaircut
            ? `Kur farkı ve komisyon için %${(Number(liquidation.haircut_pct) * 100).toFixed(2)} kesinti uygulandı (${money(liquidation.haircut_try)}).`
            : "Kur makası ve komisyon için kesinti uygulanmadı (%0)."}
        </div>
      </div>

      <div className="hero-cell metric">
        <div className="hero-label">Yatırılan (TRY)</div>
        <div className="hero-value num">{money(liquidation.total_invested_try)}</div>
        <div className="hero-sub">Maliyet bazı, işlem günü kurlarıyla</div>
      </div>

      <div className={`hero-cell metric flash-cell ${flashValue}`}>
        <div className="hero-label">Piyasa değeri (TRY)</div>
        <div className="hero-value num">{money(totals.market_value_try)}</div>
        <div className="hero-sub">Güncel fiyat × güncel kur</div>
      </div>

      <div className={`hero-cell metric flash-cell ${flashReturn}`}>
        <div className="hero-label">Toplam getiri</div>
        <div className={`hero-value num ${toneOf(totals.pnl_try)}`}>
          <span aria-hidden="true">{arrow(totals.pnl_try)}</span> {ratioPct(totals.total_return)}
        </div>
        <div className="hero-sub num">{signedMoney(totals.pnl_try)}</div>

        {/* The day's move, kept visually subordinate to the lifetime figure above it
            and split the same way — a flat day in local currency can still move the
            lira value, and that is the whole point of this dashboard. */}
        {daily?.available ? (
          <div className="hero-daily">
            <span className="hero-daily-label">Günlük</span>
            <span className={`hero-daily-value num ${toneOf(daily.pnl_try)}`}>
              <span aria-hidden="true">{arrow(daily.pnl_try)}</span>{" "}
              {signedMoney(daily.pnl_try)}
              {daily.return_ratio !== null && <> · {ratioPct(daily.return_ratio)}</>}
            </span>
            <span
              className="hero-daily-split num"
              title={`Önceki seans: ${fullDate(daily.reference_date)}`}
            >
              fiyat {signedMoney(daily.price_effect_try)} · kur{" "}
              {signedMoney(daily.fx_effect_try)}
            </span>
          </div>
        ) : (
          <div className="hero-daily">
            <span className="hero-daily-label">Günlük</span>
            <span className="hero-daily-value num flat">karşılaştırılacak seans yok</span>
          </div>
        )}
      </div>
    </section>
  );
}
