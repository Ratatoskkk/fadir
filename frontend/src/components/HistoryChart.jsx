// Layout item 4 (SPEC §9): the three series from §6 plus an after-tax line, with a
// range selector that now reaches down to a single intraday session.
//
// The gap between "TRY value" and "constant-FX value" *is* the FX contribution, and the
// gap between "constant-FX value" and "cost basis" is the local price contribution. The
// shaded band between the first two makes the attribution visually obvious, which is the
// stated reason for emitting three series rather than one. The fourth line is the same
// value net of estimated tax, so the distance between it and the green line is what the
// taxman would take on a full exit today.
//
// 1G runs off intraday bars from a separate endpoint (they are not persisted — see
// app/providers/intraday.py); every other range runs off daily closes.

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { arrow, fullDate, money, ratioPct, shortDate, signedMoney, toneOf } from "../format.js";
import { RANGES, isIntradayRange, isPannable } from "../ranges.js";

function compactTry(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "";
  if (Math.abs(n) >= 1_000_000) return `₺${(n / 1_000_000).toFixed(1).replace(".", ",")}M`;
  if (Math.abs(n) >= 1_000) return `₺${Math.round(n / 1000)}B`;
  return `₺${Math.round(n)}`;
}

// Built once — `clockLabel` is the intraday tick formatter, so it runs for every bar on
// the axis on every render.
const TZ = "Europe/Istanbul";
const dfTime = new Intl.DateTimeFormat("tr-TR", {
  hour: "2-digit",
  minute: "2-digit",
  timeZone: TZ,
});
const dfDay = new Intl.DateTimeFormat("tr-TR", {
  day: "2-digit",
  month: "2-digit",
  timeZone: TZ,
});

/**
 * Chart colours come from the same CSS custom properties as the rest of the UI, so the
 * palette has one definition and the chart follows a theme switch automatically.
 *
 * They have to be *resolved* rather than passed through: Recharts writes `stroke` and
 * `fill` as SVG presentation attributes, where `var()` is not reliably honoured. Reading
 * the computed values keeps a single source of truth without depending on that.
 */
function useChartColors() {
  const read = useCallback(() => {
    const s = getComputedStyle(document.documentElement);
    const v = (name, fallback) => s.getPropertyValue(name).trim() || fallback;
    return {
      value: v("--up", "#72ce7b"),
      price: v("--price", "#839cb2"),
      fx: v("--fx", "#a892c4"),
      tax: v("--taupe", "#c0ab93"),
      cost: v("--cost", "#7d7d7d"),
      grid: v("--border", "#ffffff1a"),
      axis: v("--text-faint", "#6b6b6b"),
    };
  }, []);

  const [colors, setColors] = useState(read);

  useEffect(() => {
    const observer = new MutationObserver(() => setColors(read()));
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });
    return () => observer.disconnect();
  }, [read]);

  return colors;
}

const clockLabel = (iso) => dfTime.format(new Date(iso));

const stampLabel = (iso) => {
  const at = new Date(iso);
  return `${dfDay.format(at)} ${dfTime.format(at)}`;
};

function ChartTooltip({ active, payload, label, intraday }) {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload;
  const hasTax = Math.abs(point.tax_try) > 0.005;

  return (
    <div className="chart-tip">
      <div className="tip-date">{intraday ? stampLabel(label) : fullDate(label)}</div>

      <div className="tip-row">
        <span className="k">Değer (TRY)</span>
        <span className="num">{money(point.value_try)}</span>
      </div>
      <div className="tip-row">
        <span className="k">Sabit kurla değer</span>
        <span className="num">{money(point.value_constant_fx_try)}</span>
      </div>
      {hasTax && (
        <div className="tip-row">
          <span className="k">Vergi sonrası</span>
          <span className="num">{money(point.value_after_tax_try)}</span>
        </div>
      )}
      <div className="tip-row">
        <span className="k">Maliyet bazı</span>
        <span className="num">{money(point.cost_basis_try)}</span>
      </div>

      <div className="tip-row tip-sep">
        <span className="k">Fiyat etkisi</span>
        <span className="num">{signedMoney(point.price_effect_try)}</span>
      </div>
      <div className="tip-row">
        <span className="k">Kur etkisi</span>
        <span className="num">{signedMoney(point.fx_effect_try)}</span>
      </div>
      <div className="tip-row">
        <span className="k">Toplam K/Z</span>
        <span className="num">{signedMoney(point.pnl_try)}</span>
      </div>
      {hasTax && (
        <>
          <div className="tip-row">
            <span className="k">Tahminî vergi</span>
            <span className="num">−{money(point.tax_try)}</span>
          </div>
          <div className="tip-row">
            <span className="k">Vergi sonrası K/Z</span>
            <span className="num">{signedMoney(point.pnl_after_tax_try)}</span>
          </div>
        </>
      )}

      {(point.price_carried_forward || point.fx_carried_forward || point.carried_forward) && (
        <div className="tip-row tip-sep">
          <span className="k" style={{ fontSize: 11 }}>
            {intraday
              ? "Kapalı borsalar için son fiyat taşındı"
              : point.price_carried_forward && point.fx_carried_forward
                ? "Fiyat ve kur önceki günden taşındı"
                : point.price_carried_forward
                  ? "Fiyat önceki kapanıştan taşındı"
                  : "Kur önceki yayından taşındı"}
          </span>
        </div>
      )}
    </div>
  );
}

/**
 * The delta between the two ends of a dragged selection.
 *
 * The decomposition is exact rather than approximate, and falls straight out of the two
 * identities the series already satisfy at every point:
 *
 *     price_effect = value_constant_fx - cost_basis
 *     fx_effect    = value_try         - value_constant_fx
 *   → value_try    = cost_basis + price_effect + fx_effect
 *
 * Differencing that across the window gives Δvalue = Δcost + Δprice + Δfx, so the three
 * parts always add back to the headline number. Δcost is not noise: it is money paid in
 * or taken out during the window, and without it a purchase would read as a gain.
 */
function comparison(data, from, to) {
  if (from == null || to == null || from === to) return null;

  let a = data.findIndex((d) => d.x === from);
  let b = data.findIndex((d) => d.x === to);
  if (a < 0 || b < 0) return null;
  if (a > b) [a, b] = [b, a];

  const start = data[a];
  const end = data[b];
  const deltaValue = end.value_try - start.value_try;
  const deltaCost = end.cost_basis_try - start.cost_basis_try;
  const deltaConst = end.value_constant_fx_try - start.value_constant_fx_try;

  return {
    start,
    end,
    points: b - a + 1,
    deltaValue,
    deltaCost,
    // Δ of each effect, not a re-derivation — see the identity above.
    deltaPrice: deltaConst - deltaCost,
    deltaFx: deltaValue - deltaConst,
    deltaAfterTax: end.value_after_tax_try - start.value_after_tax_try,
    // Growth of the money already in, so a deposit mid-window cannot read as a return.
    ratio: start.value_try ? end.value_try / start.value_try : null,
  };
}

export default function HistoryChart({
  history,
  intraday,
  loading,
  range,
  onRangeChange,
  focusTickers = [],
  onClearFocus,
  pan = 0,
  panDir = 0,
  onPan,
  canPanBack = false,
}) {
  const c = useChartColors();
  const [hidden, setHidden] = useState({});
  const [sel, setSel] = useState({ from: null, to: null, dragging: false });
  const isIntraday = isIntradayRange(range);
  const source = isIntraday ? intraday : history;

  const data = useMemo(() => {
    if (!source?.points) return [];
    return source.points.map((p) => ({
      ...p,
      x: isIntraday ? p.at : p.date,
      value_try: Number(p.value_try),
      value_constant_fx_try: Number(p.value_constant_fx_try),
      value_after_tax_try: Number(p.value_after_tax_try),
      cost_basis_try: Number(p.cost_basis_try),
      price_effect_try: Number(p.price_effect_try),
      fx_effect_try: Number(p.fx_effect_try),
      pnl_try: Number(p.pnl_try),
      pnl_after_tax_try: Number(p.pnl_after_tax_try),
      tax_try: Number(p.tax_try),
      // Band between the TRY value and the constant-FX value: the FX contribution.
      fx_band: [Number(p.value_constant_fx_try), Number(p.value_try)],
    }));
  }, [source, isIntraday]);

  const toggleSeries = (key) => setHidden((prev) => ({ ...prev, [key]: !prev[key] }));
  const anyTax = data.some((d) => Math.abs(d.tax_try) > 0.005);

  const compare = useMemo(() => comparison(data, sel.from, sel.to), [data, sel.from, sel.to]);

  // A selection is a pair of x values from the current series, so it stops meaning
  // anything the moment the range or the ticker filter changes the x domain.
  const focusKey = focusTickers.join(",");
  useEffect(() => {
    setSel({ from: null, to: null, dragging: false });
  }, [range, focusKey]);

  const beginDrag = useCallback((e) => {
    if (!e?.activeLabel) return;
    setSel({ from: e.activeLabel, to: e.activeLabel, dragging: true });
  }, []);

  const extendDrag = useCallback((e) => {
    if (!e?.activeLabel) return;
    setSel((prev) => (prev.dragging ? { ...prev, to: e.activeLabel } : prev));
  }, []);

  // A click without movement leaves from === to, which is not a range — treat it as
  // clearing, so the only way out of a selection is the same gesture that made one.
  const endDrag = useCallback(() => {
    setSel((prev) =>
      prev.from === prev.to
        ? { from: null, to: null, dragging: false }
        : { ...prev, dragging: false },
    );
  }, []);

  const clearSelection = () => setSel({ from: null, to: null, dragging: false });
  const labelFor = isIntraday ? stampLabel : fullDate;

  // What window is on screen, taken from the data rather than recomputed from the
  // offset — so it always agrees with what is actually plotted.
  const windowLabel = useMemo(() => {
    if (!data.length) return "—";
    if (isIntraday) return fullDate(source?.session_date ?? data[0].x);
    return `${shortDate(data[0].x)} – ${shortDate(data[data.length - 1].x)}`;
  }, [data, isIntraday, source]);

  // Re-keying on the pan step restarts the slide, so each press animates even when the
  // direction is unchanged. transform+opacity only, so it stays on the compositor.
  // Going back in time brings the new window in from the left, so the motion matches
  // the direction of travel.
  const slideClass = panDir === 0 ? "" : panDir > 0 ? "slide-from-left" : "slide-from-right";

  return (
    <section className="panel" id="grafik">
      <div className="panel-head">
        <h2>
          {focusTickers.length ? `${focusTickers.join(", ")} değeri` : "Portföy değeri"} —
          TRY, sabit kur, vergi sonrası ve maliyet bazı
          {isIntraday && source?.session_date && (
            <span className="panel-sub"> · {fullDate(source.session_date)} seansı</span>
          )}
          {focusTickers.length > 0 && (
            <button type="button" className="btn small ghost focus-clear" onClick={onClearFocus}>
              ✕ tüm portföye dön
            </button>
          )}
        </h2>
        {isPannable(range) && (
          <div className="pan-group" role="group" aria-label="Zaman penceresini kaydır">
            {/* `pan` counts windows *back* from now, so going further back increments. */}
            <button
              type="button"
              className="iconbtn"
              onClick={() => onPan?.(1)}
              disabled={!canPanBack}
              title="Önceki pencere"
              aria-label="Önceki pencere"
            >
              ‹
            </button>
            <span className="pan-label num" aria-live="polite">
              {pan === 0 ? "canlı" : windowLabel}
            </span>
            <button
              type="button"
              className="iconbtn"
              onClick={() => onPan?.(-1)}
              disabled={pan === 0}
              title="Sonraki pencere"
              aria-label="Sonraki pencere"
            >
              ›
            </button>
          </div>
        )}

        <div className="range-picker" role="group" aria-label="Zaman aralığı">
          {RANGES.map((r) => (
            <button
              key={r.key}
              className={range === r.key ? "active" : ""}
              onClick={() => onRangeChange(r.key)}
              aria-pressed={range === r.key}
              title={r.intraday ? "Gün içi, 5 dakikalık barlar" : undefined}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      <div className="panel-body">
        {loading && !data.length ? (
          <div className="empty">
            <span className="spinner" /> Geçmiş yükleniyor…
          </div>
        ) : !data.length ? (
          <div className="empty">
            {isIntraday
              ? "Gün içi veri bulunamadı. Borsalar uzun süredir kapalıysa Yahoo bar döndürmeyebilir."
              : "Gösterilecek veri yok."}
          </div>
        ) : (
          <div className={`chart-box ${slideClass}`} key={`${range}:${pan}`}>
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart
                data={data}
                margin={{ top: 8, right: 12, bottom: 4, left: 8 }}
                onMouseDown={beginDrag}
                onMouseMove={extendDrag}
                onMouseUp={endDrag}
                onMouseLeave={endDrag}
                style={{ cursor: "crosshair", userSelect: "none" }}
              >
                <CartesianGrid stroke={c.grid} strokeDasharray="3 3" vertical={false} />
                <XAxis
                  dataKey="x"
                  tickFormatter={isIntraday ? clockLabel : shortDate}
                  minTickGap={40}
                  stroke={c.grid}
                  tick={{ fill: c.axis, fontSize: 12 }}
                  tickLine={false}
                />
                <YAxis
                  tickFormatter={compactTry}
                  width={72}
                  stroke={c.grid}
                  tick={{ fill: c.axis, fontSize: 12 }}
                  tickLine={false}
                  axisLine={false}
                  domain={["auto", "auto"]}
                />
                <Tooltip content={<ChartTooltip intraday={isIntraday} />} />
                <Legend
                  onClick={(entry) => toggleSeries(entry.dataKey)}
                  wrapperStyle={{ fontSize: 12, paddingTop: 8, cursor: "pointer" }}
                />

                {/* The FX contribution, drawn as the band between series 1 and 2. */}
                <Area
                  dataKey="fx_band"
                  name="Kur katkısı (aradaki fark)"
                  stroke="none"
                  fill={c.fx}
                  fillOpacity={0.18}
                  activeDot={false}
                  legendType="rect"
                  hide={hidden.fx_band}
                  isAnimationActive
                  animationDuration={320}
                  animationEasing="ease-out"
                />

                <Line
                  type="monotone"
                  dataKey="value_try"
                  name="Değer (TRY)"
                  stroke={c.value}
                  strokeWidth={2}
                  dot={false}
                  hide={hidden.value_try}
                  isAnimationActive
                  animationDuration={320}
                  animationEasing="ease-out"
                />
                <Line
                  type="monotone"
                  dataKey="value_constant_fx_try"
                  name="Sabit kurla değer"
                  stroke={c.price}
                  strokeWidth={1.8}
                  strokeDasharray="5 3"
                  dot={false}
                  hide={hidden.value_constant_fx_try}
                  isAnimationActive
                  animationDuration={320}
                  animationEasing="ease-out"
                />
                {anyTax && (
                  <Line
                    type="monotone"
                    dataKey="value_after_tax_try"
                    name="Vergi sonrası değer"
                    stroke={c.tax}
                    strokeWidth={1.6}
                    strokeDasharray="2 3"
                    dot={false}
                    hide={hidden.value_after_tax_try}
                    isAnimationActive
                  animationDuration={320}
                  animationEasing="ease-out"
                  />
                )}
                <Line
                  type="monotone"
                  dataKey="cost_basis_try"
                  name="Maliyet bazı (TRY)"
                  stroke={c.cost}
                  strokeWidth={1.6}
                  dot={false}
                  hide={hidden.cost_basis_try}
                  isAnimationActive
                  animationDuration={320}
                  animationEasing="ease-out"
                />

                {/* The dragged window. Rendered last so it sits above the series. */}
                {sel.from && sel.to && sel.from !== sel.to && (
                  <ReferenceArea
                    x1={sel.from}
                    x2={sel.to}
                    fill={c.price}
                    fillOpacity={0.12}
                    stroke={c.price}
                    strokeOpacity={0.5}
                    ifOverflow="extendDomain"
                  />
                )}
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        )}

        {compare ? (
          <div className="cmp">
            <div className="cmp-head">
              <div className="cmp-range">
                <span className="cmp-label">Seçili aralık</span>
                <strong className="num">
                  {labelFor(compare.start.x)} → {labelFor(compare.end.x)}
                </strong>
                <span className="cmp-span">{compare.points} nokta</span>
              </div>
              <button type="button" className="btn small ghost" onClick={clearSelection}>
                ✕ seçimi temizle
              </button>
            </div>

            <div className="cmp-grid">
              {/* The question a dragged range answers first is "how far did it move",
                  which is the percentage. The lira figure answers "by how much" — the
                  second question — so it sits underneath at reading size. */}
              <div className="cmp-cell lead">
                <span className="cmp-label">Değer değişimi</span>
                <span className={`cmp-value num ${toneOf(compare.deltaValue)}`}>
                  <span aria-hidden="true">{arrow(compare.deltaValue)}</span>{" "}
                  {compare.ratio !== null ? ratioPct(compare.ratio) : "—"}
                </span>
                <span className={`cmp-money num ${toneOf(compare.deltaValue)}`}>
                  {signedMoney(compare.deltaValue)}
                </span>
                <span className="cmp-sub num">
                  {money(compare.start.value_try)} → {money(compare.end.value_try)}
                </span>
              </div>

              <div className="cmp-cell">
                <span className="cmp-label">Fiyat katkısı</span>
                <span className={`cmp-value num ${toneOf(compare.deltaPrice)}`}>
                  {signedMoney(compare.deltaPrice)}
                </span>
                <span className="cmp-sub">yerel fiyat hareketi</span>
              </div>

              <div className="cmp-cell">
                <span className="cmp-label">Kur katkısı</span>
                <span className={`cmp-value num ${toneOf(compare.deltaFx)}`}>
                  {signedMoney(compare.deltaFx)}
                </span>
                <span className="cmp-sub">TRY’nin hareketi</span>
              </div>

              <div className="cmp-cell">
                <span className="cmp-label">Maliyet bazı</span>
                <span className={`cmp-value num ${Math.abs(compare.deltaCost) < 0.005 ? "flat" : ""}`}>
                  {Math.abs(compare.deltaCost) < 0.005 ? "değişmedi" : signedMoney(compare.deltaCost)}
                </span>
                <span className="cmp-sub">
                  {Math.abs(compare.deltaCost) < 0.005
                    ? "aralıkta işlem yok"
                    : "aralıkta yatırılan / çekilen"}
                </span>
              </div>

              {anyTax && (
                <div className="cmp-cell">
                  <span className="cmp-label">Vergi sonrası</span>
                  <span className={`cmp-value num ${toneOf(compare.deltaAfterTax)}`}>
                    {signedMoney(compare.deltaAfterTax)}
                  </span>
                  <span className="cmp-sub">tahminî vergi düşülmüş</span>
                </div>
              )}
            </div>

            <p className="cmp-note">
              Fiyat katkısı + kur katkısı + maliyet bazı değişimi ={" "}
              <strong>değer değişimi</strong> — üç bileşen tam olarak toplanır. Maliyet bazı
              aralıkta değiştiyse aradaki fark getiri değil, yatırılan paradır.
            </p>
          </div>
        ) : (
          data.length > 1 && (
            <p className="cmp-hint">
              İki tarih arasını karşılaştırmak için grafik üzerinde <strong>tıklayıp
              sürükleyin</strong>.
            </p>
          )
        )}

        <p className="attr-explain">
          Yeşil çizgi ile mavi kesikli çizgi arasındaki mor alan <strong>kur katkısıdır</strong>:
          kurlar alım günündeki seviyede sabit kalsaydı portföy mavi çizgiyi izlerdi. Mavi
          çizgi ile gri maliyet çizgisi arasındaki mesafe yerel fiyat hareketidir. Turuncu
          kesikli çizgi, bugün tamamen satılsaydı <strong>vergi sonrası</strong> kalacak
          tutardır — yeşil ile arasındaki fark tahminî vergidir.
          {isIntraday && (
            <>
              {" "}
              1G görünümü 5 dakikalık barlarla çizilir; o an kapalı olan borsaların son
              fiyatı taşınır, çünkü dört borsa aynı anda neredeyse hiç açık olmaz.
            </>
          )}
        </p>
      </div>
    </section>
  );
}
