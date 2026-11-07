import { useCallback, useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { arrow, fullDate, money, ratioPct, shortDate, signedMoney, toneOf } from "../../format.js";
import { RANGES, isIntradayRange, isPannable } from "../../ranges.js";
import ValueChart, { BAND_KEY, SERIES } from "../chart/ValueChart.jsx";
import Icon from "../ui/Icons.jsx";
import { collapse, spring } from "../ui/motion.js";
import { useT } from "../i18n/index.jsx";

const TZ = "Europe/Istanbul";
const dfStamp = new Intl.DateTimeFormat("tr-TR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit", timeZone: TZ });
(window.requestIdleCallback ?? ((fn) => window.setTimeout(fn, 1500)))(() => dfStamp.format(Date.now()));

/**
 * Δ between two points, decomposed exactly: value = cost + price effect + fx effect at
 * every point, so differencing gives Δvalue = Δcost + Δprice + Δfx with nothing left over.
 */
function comparison(data, a, b) {
  if (a == null || b == null || a === b) return null;
  if (a > b) [a, b] = [b, a];
  const start = data[a];
  const end = data[b];
  if (!start || !end) return null;
  const deltaValue = end.value_try - start.value_try;
  const deltaCost = end.cost_basis_try - start.cost_basis_try;
  const deltaConst = end.value_constant_fx_try - start.value_constant_fx_try;
  return {
    start, end, points: b - a + 1, deltaValue, deltaCost,
    deltaPrice: deltaConst - deltaCost,
    deltaFx: deltaValue - deltaConst,
    deltaAfterTax: end.value_after_tax_try - start.value_after_tax_try,
    ratio: start.value_try ? end.value_try / start.value_try : null,
  };
}

const SWATCH = { value_try: "var(--up)", value_constant_fx_try: "var(--price)", value_after_tax_try: "var(--tax)", cost_basis_try: "var(--cost)", [BAND_KEY]: "var(--fx)" };

function Tip({ point, intraday, anyTax }) {
  const t = useT();
  const carried = point.price_carried_forward || point.fx_carried_forward || point.carried_forward;
  return (
    <>
      <div className="tip-date">{intraday ? dfStamp.format(new Date(point.x)) : fullDate(point.x)}</div>
      <div className="tip-row"><i style={{ background: SWATCH.value_try }} />{t("chart.valueShort")}<b className="num">{money(point.value_try)}</b></div>
      <div className="tip-row"><i style={{ background: SWATCH.value_constant_fx_try }} />{t("chart.constantShort")}<b className="num">{money(point.value_constant_fx_try)}</b></div>
      {anyTax && <div className="tip-row"><i style={{ background: SWATCH.value_after_tax_try }} />{t("tax.afterTax")}<b className="num">{money(point.value_after_tax_try)}</b></div>}
      <div className="tip-row"><i style={{ background: SWATCH.cost_basis_try }} />{t("pos.cost")}<b className="num">{money(point.cost_basis_try)}</b></div>
      <div className="tip-sep" />
      <div className="tip-row">{t("attr.price")}<b className={`num ${toneOf(point.price_effect_try)}`}>{signedMoney(point.price_effect_try)}</b></div>
      <div className="tip-row">{t("attr.fx")}<b className={`num ${toneOf(point.fx_effect_try)}`}>{signedMoney(point.fx_effect_try)}</b></div>
      <div className="tip-row">{t("chart.totalPnl")}<b className={`num ${toneOf(point.pnl_try)}`}>{signedMoney(point.pnl_try)}</b></div>
      {anyTax && Math.abs(point.tax_try) > 0.005 && (
        <>
          <div className="tip-row">{t("tax.estimated")}<b className="num">−{money(point.tax_try)}</b></div>
          <div className="tip-row">{t("chart.pnlAfterTax")}<b className={`num ${toneOf(point.pnl_after_tax_try)}`}>{signedMoney(point.pnl_after_tax_try)}</b></div>
        </>
      )}
      {carried && (
        <div className="tip-note">
          {intraday
            ? t("chart.carriedClosed")
            : point.price_carried_forward && point.fx_carried_forward
              ? t("chart.carriedBoth")
              : t(point.price_carried_forward ? "chart.carriedPrice" : "chart.carriedFx")}
        </div>
      )}
    </>
  );
}

export default function ChartCard({ dash }) {
  const t = useT();
  const { history, intraday, loading, range, changeRange, focusTickers, toggleFocus, pan, panDir, panBy, canPanBack } = dash;
  const isIntraday = isIntradayRange(range);
  const source = isIntraday ? intraday : history;
  const [hidden, setHidden] = useState({});
  const [hover, setHover] = useState(null);
  const [sel, setSel] = useState(null);

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
    }));
  }, [source, isIntraday]);

  const anyTax = useMemo(() => data.some((d) => Math.abs(d.tax_try) > 0.005), [data]);
  const focusKey = focusTickers.join(",");
  useEffect(() => { setSel(null); setHover(null); }, [range, focusKey, pan]);

  const compare = useMemo(() => (sel ? comparison(data, sel.a, sel.b) : null), [data, sel]);
  const onSelect = useCallback((value) => setSel(value), []);
  const toggle = (key) => setHidden((prev) => ({ ...prev, [key]: !prev[key] }));
  const labelFor = isIntraday ? (iso) => dfStamp.format(new Date(iso)) : fullDate;

  const windowLabel = !data.length
    ? "—"
    : isIntraday
      ? fullDate(source?.session_date ?? data[0].x)
      : `${shortDate(data[0].x)} – ${shortDate(data[data.length - 1].x)}`;

  const first = data[0];
  const last = data[data.length - 1];
  const periodDelta = first && last ? last.value_try - first.value_try : null;

  const legend = [
    ...SERIES.filter((s) => !s.taxOnly || anyTax).map((s) => ({ key: s.key, label: t(s.label) })),
    { key: BAND_KEY, label: t("chart.fxContribution") },
  ];

  return (
    <section className="card chart-card" id="grafik">
      <header className="card-head chart-head">
        <div className="chart-title">
          <h2>
            <AnimatePresence mode="popLayout" initial={false}>
              <motion.span
                key={focusKey || "all"}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={spring}
                style={{ display: "inline-block" }}
              >
                {focusTickers.length ? focusTickers.join(", ") : t("chart.title")}
              </motion.span>
            </AnimatePresence>
          </h2>
          {periodDelta !== null && (
            <span className={`chip num ${toneOf(periodDelta)}`}>
              {arrow(periodDelta)} {first.value_try ? ratioPct(last.value_try / first.value_try) : "—"}
            </span>
          )}
          <AnimatePresence>
            {focusTickers.length > 0 && (
              <motion.button
                type="button"
                className="chip chip-btn"
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.8 }}
                onClick={() => toggleFocus(null)}
              >
                <Icon name="x" size={12} /> {t("chart.wholePortfolio")}
              </motion.button>
            )}
          </AnimatePresence>
        </div>

        <div className="chart-controls">
          {/* Always rendered (inert on "Tümü") so the header never shifts when it appears. */}
          <div className={`pan ${isPannable(range) ? "" : "inert"}`} role="group" aria-label={t("chart.pan")} aria-disabled={!isPannable(range)}>
            <button type="button" className="icon-btn" onClick={() => panBy(1)} disabled={!isPannable(range) || !canPanBack} aria-label={t("chart.prev")}>
              <Icon name="left" size={16} />
            </button>
            <span className="pan-label num" aria-live="polite">{!isPannable(range) ? t("range.ALL") : pan === 0 ? t("pos.live") : windowLabel}</span>
            <button type="button" className="icon-btn" onClick={() => panBy(-1)} disabled={!isPannable(range) || pan === 0} aria-label={t("chart.next")}>
              <Icon name="right" size={16} />
            </button>
          </div>
          <div className="segmented" role="group" aria-label={t("chart.range")}>
            {RANGES.map((r) => (
              <button key={r.key} type="button" aria-pressed={range === r.key} onClick={() => changeRange(r.key)}>
                {range === r.key && <motion.span layoutId="range-pill" className="segmented-pill" transition={spring} />}
                <span>{t(`range.${r.key}`)}</span>
              </button>
            ))}
          </div>
        </div>
      </header>

      <div className="legend" role="group" aria-label={t("chart.series")}>
        {legend.map((item) => (
          <button
            key={item.key}
            type="button"
            className={`legend-chip ${hidden[item.key] ? "off" : ""}`}
            aria-pressed={!hidden[item.key]}
            onClick={() => toggle(item.key)}
          >
            <i style={{ background: SWATCH[item.key] }} className={item.key === BAND_KEY ? "band" : ""} />
            {item.label}
          </button>
        ))}
        {isIntraday && source?.session_date && <span className="legend-meta">{t("chart.session", { date: fullDate(source.session_date) })}</span>}
      </div>

      <div className="chart-stage">
        {data.length ? (
          <ValueChart
            data={data}
            intraday={isIntraday}
            hidden={hidden}
            anyTax={anyTax}
            panDir={panDir}
            live={pan === 0}
            selection={sel}
            onHover={setHover}
            onSelect={onSelect}
            tooltip={hover !== null && data[hover] ? <Tip point={data[hover]} intraday={isIntraday} anyTax={anyTax} /> : null}
          />
        ) : (
          <div className="chart-empty">
            {loading ? (
              <div className="skeleton-chart" />
            ) : isIntraday ? (
              t("chart.noIntraday")
            ) : (
              t("chart.noData")
            )}
          </div>
        )}
      </div>

      <AnimatePresence initial={false}>
        {compare ? (
          <motion.div key="cmp" className="compare" {...collapse}>
            <div className="compare-inner">
              <div className="compare-head">
                <span className="num">{labelFor(compare.start.x)} → {labelFor(compare.end.x)}</span>
                <span className="muted">{compare.points} nokta</span>
                <button type="button" className="chip chip-btn" onClick={() => setSel(null)}>
                  <Icon name="x" size={12} /> temizle
                </button>
              </div>
              <div className="compare-grid">
                <div className="compare-cell lead">
                  <span className="label">{t("chart.valueChange")}</span>
                  <span className={`big num ${toneOf(compare.deltaValue)}`}>
                    {arrow(compare.deltaValue)} {compare.ratio !== null ? ratioPct(compare.ratio) : "—"}
                  </span>
                  <span className={`num ${toneOf(compare.deltaValue)}`}>{signedMoney(compare.deltaValue)}</span>
                </div>
                <div className="compare-cell">
                  <span className="label">{t("chart.priceContribution")}</span>
                  <span className={`mid num ${toneOf(compare.deltaPrice)}`}>{signedMoney(compare.deltaPrice)}</span>
                </div>
                <div className="compare-cell">
                  <span className="label">{t("chart.fxContribution")}</span>
                  <span className={`mid num ${toneOf(compare.deltaFx)}`}>{signedMoney(compare.deltaFx)}</span>
                </div>
                <div className="compare-cell">
                  <span className="label">{t("chart.costBasis")}</span>
                  <span className="mid num">{Math.abs(compare.deltaCost) < 0.005 ? t("chart.unchanged") : signedMoney(compare.deltaCost)}</span>
                </div>
                {anyTax && (
                  <div className="compare-cell">
                    <span className="label">{t("tax.afterTax")}</span>
                    <span className={`mid num ${toneOf(compare.deltaAfterTax)}`}>{signedMoney(compare.deltaAfterTax)}</span>
                  </div>
                )}
              </div>
              <p className="fineprint">{t("chart.compareNote")}</p>
            </div>
          </motion.div>
        ) : (
          data.length > 1 && (
            <motion.p key="hint" className="chart-hint" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              {t("chart.dragHint")}
            </motion.p>
          )
        )}
      </AnimatePresence>
    </section>
  );
}
