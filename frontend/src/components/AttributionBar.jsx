// Layout item 2 (SPEC §9): price effect vs FX effect as a stacked horizontal bar.
//
// The two effects can have opposite signs — that is the whole point of the decomposition,
// and it is what a single blended return number destroys. Segments are sized by absolute
// magnitude so a negative contribution is still visible, and negative segments are hatched
// so the sign survives without relying on colour (§9 accessibility).

import { arrow, money, signedMoney, toneOf } from "../format.js";

export default function AttributionBar({ totals }) {
  const price = Number(totals.price_effect_try);
  const fx = Number(totals.fx_effect_try);
  const pnl = Number(totals.pnl_try);

  const magnitude = Math.abs(price) + Math.abs(fx);
  const pricePct = magnitude === 0 ? 50 : (Math.abs(price) / magnitude) * 100;
  const fxPct = magnitude === 0 ? 50 : (Math.abs(fx) / magnitude) * 100;

  const share = (value) =>
    magnitude === 0 ? "—" : `${((Math.abs(value) / magnitude) * 100).toFixed(0)}%`;

  return (
    <section className="panel" id="ayristirma" aria-label="Getiri ayrıştırması">
      <div className="panel-head">
        <h2>Getiri ayrıştırması — fiyat etkisi / kur etkisi</h2>
        <div className={`num ${toneOf(pnl)}`} style={{ marginLeft: "auto", fontSize: 16 }}>
          <span aria-hidden="true">{arrow(pnl)}</span> {signedMoney(pnl)}
        </div>
      </div>

      <div className="panel-body">
        <div
          className="attr-bar"
          role="img"
          aria-label={
            `Fiyat etkisi ${signedMoney(price)}, toplamın ${share(price)}'i. ` +
            `Kur etkisi ${signedMoney(fx)}, toplamın ${share(fx)}'i.`
          }
        >
          <div
            className={`attr-seg ${price < 0 ? "price-neg" : "price"}`}
            style={{ flexGrow: pricePct }}
            title={`Fiyat etkisi ${signedMoney(price)}`}
          >
            {pricePct > 12 ? `Fiyat ${share(price)}` : ""}
          </div>
          <div
            className={`attr-seg ${fx < 0 ? "fx-neg" : "fx"}`}
            style={{ flexGrow: fxPct }}
            title={`Kur etkisi ${signedMoney(fx)}`}
          >
            {fxPct > 12 ? `Kur ${share(fx)}` : ""}
          </div>
        </div>

        <div className="attr-legend">
          <div className="attr-item">
            <span className="swatch price" />
            <div>
              <div className="k">Fiyat etkisi {price < 0 ? "(negatif)" : ""}</div>
              <div className={`v num ${toneOf(price)}`}>
                <span aria-hidden="true">{arrow(price)}</span> {signedMoney(price)}
              </div>
            </div>
          </div>

          <div className="attr-item">
            <span className="swatch fx" />
            <div>
              <div className="k">Kur etkisi {fx < 0 ? "(negatif)" : ""}</div>
              <div className={`v num ${toneOf(fx)}`}>
                <span aria-hidden="true">{arrow(fx)}</span> {signedMoney(fx)}
              </div>
            </div>
          </div>

          <div className="attr-item">
            <span className="swatch cost" />
            <div>
              <div className="k">Toplam TRY kâr / zarar</div>
              <div className={`v num ${toneOf(pnl)}`}>{signedMoney(pnl)}</div>
            </div>
          </div>

          {Number(totals.realized_pnl_try) !== 0 && (
            <div className="attr-item">
              <span className="swatch cost" />
              <div>
                <div className="k">Gerçekleşen (satışlardan)</div>
                <div className={`v num ${toneOf(totals.realized_pnl_try)}`}>
                  {signedMoney(totals.realized_pnl_try)}
                </div>
              </div>
            </div>
          )}
        </div>

        <p className="attr-explain">
          Yerel fiyat hareketi {signedMoney(price)}, kur hareketi {signedMoney(fx)} katkı
          yaptı; toplamı {money(totals.pnl_try)} eder. Bir pozisyon kendi para biriminde
          değer kaybederken TRY bazında kazandırabilir — bu iki bileşen bilerek ayrı
          tutulur.
        </p>
      </div>
    </section>
  );
}
