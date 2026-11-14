// One instrument's price, historical or live, with the trend filters from
// chart/indicators.js as toggleable panes. Any Yahoo symbol can be charted, held or not.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import { api } from "../../api.js";
import { arrow, dateTimeStamp, figure, fullDate, hourMinute, money, monthYear, quote, ratioPct, shortDate, signedMoney, toneOf } from "../../format.js";
import PriceChart from "../chart/PriceChart.jsx";
import { FILTERS, filterState } from "../chart/indicators.js";
import TickerSearch from "../components/TickerSearch.jsx";
import { useT } from "../i18n/index.jsx";
import Icon from "../ui/Icons.jsx";
import Popover from "../ui/Popover.jsx";
import { spring } from "../ui/motion.js";

const RANGES = ["1D", "5D", "1M", "6M", "1Y", "5Y"];
const INTRADAY = new Set(["1D", "5D", "1M"]);
const CLOSED_POLL_SECONDS = 300;
const STORE = "fadir.ticker";
/** What a filter's line is: [term, explanation], keyed by filter. */
const FILTER_NOTES = {
  maSlope: ["ticker.maSlope", "ticker.note.maSlope"],
  vhf: ["ticker.vhf", "ticker.note.vhf"],
  adx: ["ticker.adx", "ticker.note.adx"],
};

const X_FORMAT = {
  "1D": (ms) => hourMinute(new Date(ms)),
  "5Y": (ms) => monthYear(new Date(ms)),
};

function loadSaved() {
  try {
    return JSON.parse(localStorage.getItem(STORE)) ?? {};
  } catch {
    return {};
  }
}

function initialFilters(saved) {
  return Object.fromEntries(FILTERS.map((f) => [f.key, { on: false, ...f.defaults, ...saved?.[f.key] }]));
}

/** Integer N1 of at least 1; N2 any finite number. An unparseable field keeps the last good value. */
function parseParam(text, integer) {
  const n = Number(String(text).replace(",", "."));
  if (!Number.isFinite(n)) return null;
  return integer ? (n >= 1 ? Math.round(n) : null) : n;
}

function ParamInput({ label, ariaLabel, value, integer, onChange }) {
  const [text, setText] = useState(String(value));
  useEffect(() => { setText(String(value)); }, [value]);
  return (
    <label className="param">
      <span>{label}</span>
      <input
        className="small num"
        inputMode="decimal"
        aria-label={ariaLabel}
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          const n = parseParam(e.target.value, integer);
          if (n !== null) onChange(n);
        }}
        onBlur={() => setText(String(value))}
      />
    </label>
  );
}

/** Bars for (symbol, range), polled while the market is open. A stale answer is dropped. */
function useChart(symbol, range, pollSeconds) {
  const key = `${symbol}|${range}`;
  const keyRef = useRef(key);
  keyRef.current = key;
  const [state, setState] = useState({ key: null, data: null, error: null });

  const load = useCallback(async () => {
    if (!symbol) return;
    const asked = `${symbol}|${range}`;
    try {
      const data = await api.marketChart(symbol, range);
      if (keyRef.current === asked) setState({ key: asked, data, error: null });
    } catch (error) {
      // A failed poll keeps the chart on screen; only a first load shows the error.
      if (keyRef.current === asked) setState((s) => (s.key === asked && s.data ? s : { key: asked, data: null, error }));
    }
  }, [symbol, range]);

  useEffect(() => { load(); }, [load]);

  const fresh = state.key === key;
  const open = fresh && state.data?.market_open;
  useEffect(() => {
    const seconds = open ? pollSeconds : CLOSED_POLL_SECONDS;
    if (!symbol || !seconds) return undefined;
    const id = window.setInterval(() => { if (!document.hidden) load(); }, seconds * 1000);
    return () => window.clearInterval(id);
  }, [load, symbol, open, pollSeconds]);

  return {
    data: fresh ? state.data : null,
    error: fresh ? state.error : null,
    loading: !fresh,
    reload: () => { setState({ key: null, data: null, error: null }); load(); },
  };
}

export default function Ticker({ dash }) {
  const t = useT();
  const { instruments, portfolio, interval } = dash;
  const [saved] = useState(loadSaved);
  const [symbol, setSymbol] = useState(() => saved.symbol ?? null);
  const [range, setRange] = useState(() => (RANGES.includes(saved.range) ? saved.range : "1D"));
  const [filters, setFilters] = useState(() => initialFilters(saved.filters));
  const [avgOn, setAvgOn] = useState(() => saved.avgOn ?? true);
  const [hover, setHover] = useState(null);

  // First visit: open on the largest holding, if there is one.
  useEffect(() => {
    if (symbol || !portfolio?.positions?.length || !instruments.length) return;
    const largest = [...portfolio.positions].sort((a, b) => Number(b.market_value_try) - Number(a.market_value_try))[0];
    const match = instruments.find((i) => i.ticker === largest.ticker);
    if (match) setSymbol(match.yf_symbol);
  }, [symbol, portfolio, instruments]);

  useEffect(() => {
    try { localStorage.setItem(STORE, JSON.stringify({ symbol, range, filters, avgOn })); } catch { /* private mode */ }
  }, [symbol, range, filters, avgOn]);

  const { data, error, loading, reload } = useChart(symbol, range, interval);
  useEffect(() => { setHover(null); }, [symbol, range]);

  const series = useMemo(() => {
    if (!data?.bars?.length) return null;
    const bars = data.bars;
    const all = {
      close: bars.map((b) => b.close),
      high: bars.map((b) => b.high),
      low: bars.map((b) => b.low),
    };
    const from = data.warmup;
    return { bars: bars.slice(from), times: bars.slice(from).map((b) => Date.parse(b.at)), close: all.close.slice(from), all, from };
  }, [data]);

  const panes = useMemo(() => {
    if (!series) return [];
    // Each filter keeps its own shade wherever it appears: chip, pane line, pane name.
    return FILTERS.map((f, tone) => ({ f, tone })).filter(({ f }) => filters[f.key].on).map(({ f, tone }) => {
      const { n1, n2 } = filters[f.key];
      const values = f.compute(series.all, n1).slice(series.from);
      const level = n2 * 5;
      return { key: f.key, filter: f, name: t(f.label), bars: f.period(n1), tone, values, level, n1, n2 };
    });
  }, [series, filters, t]);

  const setFilter = (key, patch) => setFilters((prev) => ({ ...prev, [key]: { ...prev[key], ...patch } }));

  const price = data?.price ?? null;
  const base = data && series ? (data.warmup > 0 ? data.bars[data.warmup - 1].close : series.bars[0].open) : null;
  const delta = price !== null && base ? price - base : null;
  const at = hover ?? (series ? series.close.length - 1 : null);
  const formatX = X_FORMAT[range] ?? ((ms) => shortDate(ms));
  const stamp = INTRADAY.has(range) ? (ms) => dateTimeStamp(ms) : (ms) => fullDate(ms);
  const current = instruments.find((i) => i.yf_symbol === symbol);
  // The open position in this ticker, when the Portfolio holds it.
  const holding = current ? portfolio?.positions?.find((p) => p.ticker === current.ticker && Number(p.quantity) > 0) ?? null : null;
  // The average buy is in the instrument's own currency, so it only belongs on a chart
  // quoted in that same currency.
  const avgBuy = holding?.average_purchase_price_native != null && data?.currency === holding.currency
    ? Number(holding.average_purchase_price_native)
    : null;
  const marks = avgBuy !== null && avgOn ? [{ value: avgBuy, label: `${t("pos.avgBuy")} ${quote(avgBuy)}` }] : [];
  // Explain only what is on the chart now.
  const notes = [
    ["ticker.priceLine", "ticker.note.price"],
    ...(panes.length ? [["ticker.levelLine", "ticker.note.level"]] : []),
    ...panes.map((p) => FILTER_NOTES[p.key]).filter(Boolean),
    ...(marks.length ? [["pos.avgBuy", "ticker.note.avgBuy"]] : []),
    ...(holding ? [["attr.fx", "ticker.note.fx"]] : []),
  ];

  const picker = (
    <Popover
      label={t("ticker.choose")}
      align="left"
      className="ticker-pop"
      trigger={({ open, toggle }) => (
        <h2 className="ticker-heading">
          <button type="button" className="ticker-pick" onClick={toggle} aria-expanded={open} aria-haspopup="dialog">
            <span className="ticker-symbol">{symbol}</span>
            <span className="ticker-pick-name">{data?.name ?? current?.name ?? ""}</span>
            <motion.span animate={{ rotate: open ? 180 : 0 }}><Icon name="down" size={14} /></motion.span>
          </button>
        </h2>
      )}
    >
      {({ close }) => (
        <TickerSearch instruments={instruments} search={api.searchMarket} onPick={(item) => { close(); setSymbol(item.yf_symbol); }} />
      )}
    </Popover>
  );

  if (!symbol) {
    return (
      <section className="card ticker-empty-card">
        <h2>{t("ticker.choose")}</h2>
        <TickerSearch instruments={instruments} search={api.searchMarket} onPick={(item) => setSymbol(item.yf_symbol)} />
      </section>
    );
  }

  const tooltip = hover !== null && series?.bars[hover] ? (
    <>
      <div className="tip-date">{stamp(series.times[hover])}</div>
      {[["ticker.open", "open"], ["ticker.high", "high"], ["ticker.low", "low"], ["ticker.close", "close"]].map(([label, key]) => (
        <div key={key} className="tip-row">{t(label)}<b className="num">{quote(series.bars[hover][key])}</b></div>
      ))}
      {panes.length > 0 && <div className="tip-sep" />}
      {panes.map((p) => (
        <div key={p.key} className="tip-row"><i style={{ background: `var(--pane-${p.tone + 1})` }} />{p.name}<b className="num">{figure(p.values[hover])}</b></div>
      ))}
    </>
  ) : null;

  const spoken = hover !== null && series?.bars[hover]
    ? [
      stamp(series.times[hover]),
      `${t("ticker.close")} ${quote(series.bars[hover].close)}`,
      ...panes.map((p) => {
        const s = filterState(p.values[hover], p.level);
        return `${p.name} ${figure(p.values[hover])}${s ? ` ${t(`ticker.${s}`)}` : ""}`;
      }),
    ].join(", ")
    : "";

  const heads = panes.map((p) => {
    const value = at !== null ? p.values[at] : null;
    const state = filterState(value, p.level);
    return (
      <>
        <span className="pane-name"><i aria-hidden="true" style={{ background: `var(--pane-${p.tone + 1})` }} />{p.name}</span>
        <span className="pane-bars num">{t("ticker.bars", { n: p.bars })}</span>
        <span className="pane-value num">{figure(value)}</span>
        <span className={`pane-state ${state === "long" ? "up" : state === "short" ? "down" : "muted"}`}>
          {state ? t(`ticker.${state}`) : "—"}
        </span>
        <span className="pane-params">
          {p.filter.usesN1 && <ParamInput label="N1" ariaLabel={`${p.name} N1`} integer value={p.n1} onChange={(n1) => setFilter(p.key, { n1 })} />}
          <ParamInput label="N2" ariaLabel={`${p.name} N2`} value={p.n2} onChange={(n2) => setFilter(p.key, { n2 })} />
          <span className="pane-level num" title={t("ticker.level")}><i aria-hidden="true" />{figure(p.level)}</span>
        </span>
      </>
    );
  });

  return (
    <section className="card chart-card ticker-card">
      <header className="card-head chart-head">
        <div className="chart-title">
          {picker}
          {price !== null && <span className="ticker-price num">{quote(price)} <small>{data.currency}</small></span>}
          {delta !== null && (
            <span className={`chip num ${toneOf(delta)}`}>{arrow(delta)} {ratioPct(price / base)}</span>
          )}
          {data && (
            <span className={`ticker-session ${data.market_open ? "open" : ""}`}>
              <i aria-hidden="true" />{t(data.market_open ? "ticker.trading" : "ticker.notTrading")}
            </span>
          )}
        </div>
        <div className="chart-controls">
          <div className="segmented" role="group" aria-label={t("chart.range")}>
            {RANGES.map((r) => (
              <button key={r} type="button" aria-pressed={range === r} onClick={() => setRange(r)}>
                {range === r && <motion.span layoutId="ticker-range-pill" className="segmented-pill" transition={spring} />}
                <span>{t(`ticker.range.${r}`)}</span>
              </button>
            ))}
          </div>
        </div>
      </header>

      {holding && (
        <dl className="holding">
          <div><dt>{t("pos.value")}</dt><dd className="num">{holding.ok ? money(holding.market_value_try) : "—"}</dd></div>
          <div><dt>{t("pos.cost")}</dt><dd className="num">{money(holding.cost_try)}</dd></div>
          <div>
            <dt>{t("chart.totalPnl")}</dt>
            <dd className={`num ${holding.ok ? toneOf(holding.pnl_try) : "muted"}`}>
              {holding.ok ? <>{arrow(holding.pnl_try)} {signedMoney(holding.pnl_try)} <small>{ratioPct(holding.attribution.total_return)}</small></> : "—"}
            </dd>
          </div>
          <div><dt>{t("attr.price")}</dt><dd className={`num ${toneOf(holding.attribution.price_effect_try)}`}>{signedMoney(holding.attribution.price_effect_try)}</dd></div>
          <div><dt>{t("attr.fx")}</dt><dd className={`num ${toneOf(holding.attribution.fx_effect_try)}`}>{signedMoney(holding.attribution.fx_effect_try)}</dd></div>
        </dl>
      )}

      <div className="legend" role="group" aria-label={t("ticker.filters")}>
        {avgBuy !== null && (
          <button type="button" className={`legend-chip ${avgOn ? "" : "off"}`} aria-pressed={avgOn} onClick={() => setAvgOn((v) => !v)}>
            <i className="dashed" style={{ color: "var(--cost)" }} />
            {t("pos.avgBuy")} <span className="num">{quote(avgBuy)}</span>
          </button>
        )}
        {FILTERS.map((f, tone) => (
          <button
            key={f.key}
            type="button"
            className={`legend-chip ${filters[f.key].on ? "" : "off"}`}
            aria-pressed={filters[f.key].on}
            onClick={() => setFilter(f.key, { on: !filters[f.key].on })}
          >
            <i style={{ background: `var(--pane-${tone + 1})` }} />
            {t(f.label)}
          </button>
        ))}
      </div>

      <div className="chart-stage">
        {series ? (
          <PriceChart
            times={series.times}
            close={series.close}
            panes={panes}
            marks={marks}
            heads={heads}
            formatX={formatX}
            live={data.market_open}
            onHover={setHover}
            tooltip={tooltip}
            ariaLabel={t("ticker.aria", { symbol })}
          />
        ) : (
          <div className="chart-empty">
            {loading ? (
              <div className="skeleton-chart" />
            ) : error?.status === 404 ? (
              t("ticker.noData", { symbol })
            ) : error ? (
              <div className="chart-error">
                <p>{t("ticker.loadFailed")}</p>
                <button type="button" className="btn small" onClick={reload}><Icon name="refresh" size={14} /> {t("common.retry")}</button>
              </div>
            ) : null}
          </div>
        )}
      </div>

      {series && (
        <p className="sr-only" aria-live="polite">{spoken}</p>
      )}

      {series && (
        <details className="footnotes-wrap">
          <summary>{t("ticker.explain")}</summary>
          <dl className="footnotes">
            {notes.map(([term, text]) => (
              <div key={text}>
                <dt>{t(term)}</dt>
                <dd>{t(text)}</dd>
              </div>
            ))}
          </dl>
        </details>
      )}
    </section>
  );
}
