// One instrument's price, historical or live, with the trend filters from
// chart/indicators.js as toggleable panes. Any Yahoo symbol can be charted, held or not.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import { api } from "../../api.js";
import { arrow, dateTimeStamp, figure, fullDate, hourMinute, monthYear, quote, ratioPct, shortDate, toneOf } from "../../format.js";
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
/** What each line on the chart is: [term, explanation]. */
const NOTES = [
  ["ticker.priceLine", "ticker.note.price"],
  ["ticker.levelLine", "ticker.note.level"],
  ["ticker.maSlope", "ticker.note.maSlope"],
  ["ticker.vhf", "ticker.note.vhf"],
  ["ticker.adx", "ticker.note.adx"],
];

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

function ParamInput({ label, value, integer, onChange }) {
  const [text, setText] = useState(String(value));
  useEffect(() => { setText(String(value)); }, [value]);
  return (
    <label className="param">
      <span>{label}</span>
      <input
        className="small num"
        inputMode="decimal"
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
  const [hover, setHover] = useState(null);

  // First visit: open on the largest holding, if there is one.
  useEffect(() => {
    if (symbol || !portfolio?.positions?.length || !instruments.length) return;
    const largest = [...portfolio.positions].sort((a, b) => Number(b.market_value_try) - Number(a.market_value_try))[0];
    const match = instruments.find((i) => i.ticker === largest.ticker);
    if (match) setSymbol(match.yf_symbol);
  }, [symbol, portfolio, instruments]);

  useEffect(() => {
    try { localStorage.setItem(STORE, JSON.stringify({ symbol, range, filters })); } catch { /* private mode */ }
  }, [symbol, range, filters]);

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
    return FILTERS.filter((f) => filters[f.key].on).map((f) => {
      const { n1, n2 } = filters[f.key];
      const values = f.compute(series.all, n1).slice(series.from);
      const level = n2 * 5;
      return { key: f.key, filter: f, name: `${t(f.label)} ${f.period(n1)}`, values, level, n1, n2 };
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

  const picker = (
    <Popover
      label={t("ticker.choose")}
      align="left"
      className="ticker-pop"
      trigger={({ open, toggle }) => (
        <button type="button" className="ticker-pick" onClick={toggle} aria-expanded={open} aria-haspopup="dialog">
          <h2>{symbol}</h2>
          <span className="ticker-pick-name">{data?.name ?? current?.name ?? ""}</span>
          <motion.span animate={{ rotate: open ? 180 : 0 }}><Icon name="down" size={14} /></motion.span>
        </button>
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
        <div key={p.key} className="tip-row">{p.name}<b className="num">{figure(p.values[hover])}</b></div>
      ))}
    </>
  ) : null;

  const heads = panes.map((p) => {
    const value = at !== null ? p.values[at] : null;
    const state = filterState(value, p.level);
    return (
      <>
        <span className="pane-name">{p.name}</span>
        <span className="pane-value num">{figure(value)}</span>
        <span className={`pane-state ${state === "long" ? "up" : state === "short" ? "down" : "muted"}`}>
          {state ? t(`ticker.${state}`) : "—"}
        </span>
        <span className="pane-params">
          {p.filter.usesN1 && <ParamInput label="N1" integer value={p.n1} onChange={(n1) => setFilter(p.key, { n1 })} />}
          <ParamInput label="N2" value={p.n2} onChange={(n2) => setFilter(p.key, { n2 })} />
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
              <i aria-hidden="true" />{t(data.market_open ? "live.open" : "live.closed")}
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

      <div className="legend" role="group" aria-label={t("ticker.filters")}>
        {FILTERS.map((f) => (
          <button
            key={f.key}
            type="button"
            className={`legend-chip ${filters[f.key].on ? "" : "off"}`}
            aria-pressed={filters[f.key].on}
            onClick={() => setFilter(f.key, { on: !filters[f.key].on })}
          >
            <i style={{ background: "var(--fx)" }} />
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
        <dl className="footnotes">
          {NOTES.map(([term, text]) => (
            <div key={text}>
              <dt>{t(term)}</dt>
              <dd>{t(text)}</dd>
            </div>
          ))}
        </dl>
      )}
    </section>
  );
}
