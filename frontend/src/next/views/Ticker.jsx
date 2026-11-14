// One instrument's price, historical or live, with the trend filters from
// chart/indicators.js as toggleable panes. Any Yahoo symbol can be charted, held or not.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import { api } from "../../api.js";
import { arrow, dateTimeStamp, figure, fullDate, hourMinute, money, monthYear, pct, quote, ratioPct, shortDate, signedMoney, toneOf } from "../../format.js";
import PriceChart from "../chart/PriceChart.jsx";
import { FILTERS, filterState } from "../chart/indicators.js";
import TickerSearch from "../components/TickerSearch.jsx";
import { WeekPicker } from "../components/WeekPicker.jsx";
import { useT } from "../i18n/index.jsx";
import Icon from "../ui/Icons.jsx";
import Popover from "../ui/Popover.jsx";
import { spring } from "../ui/motion.js";

const RANGES = ["1D", "5D", "1M", "6M", "1Y", "5Y"];
const INTRADAY = new Set(["1D", "5D", "1M"]);
const CLOSED_POLL_SECONDS = 300;
const INTERVAL_MS = { "5m": 300000, "15m": 900000, "1h": 3600000, "1d": 86400000, "1wk": 604800000 };
/** An intraday gap longer than this is a closed market, not a quiet one. */
const CLOSED_GAP = 3 * 3600000;
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

/** Bars for (symbol, range[, weeks]), polled while the market is open. A stale answer is dropped. */
function useChart(symbol, range, weeks, pollSeconds) {
  const weekList = range === "W" ? weeks.join(",") : "";
  const key = `${symbol}|${range}|${weekList}`;
  const keyRef = useRef(key);
  keyRef.current = key;
  const [state, setState] = useState({ key: null, data: null, error: null });

  const load = useCallback(async () => {
    if (!symbol) return;
    const asked = `${symbol}|${range}|${weekList}`;
    try {
      const data = await api.marketChart(symbol, range, weekList ? weekList.split(",") : []);
      if (keyRef.current === asked) setState({ key: asked, data, error: null });
    } catch (error) {
      // A failed poll keeps the chart on screen; only a first load shows the error.
      if (keyRef.current === asked) setState((s) => (s.key === asked && s.data ? s : { key: asked, data: null, error }));
    }
  }, [symbol, range, weekList]);

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
  const [weeks, setWeeks] = useState(() => (Array.isArray(saved.weeks) ? saved.weeks.filter((w) => /^\d{4}-W\d{2}$/.test(w)) : []));
  const [range, setRange] = useState(() => (RANGES.includes(saved.range) || (saved.range === "W" && weeks.length) ? saved.range : "1D"));
  const [filters, setFilters] = useState(() => initialFilters(saved.filters));
  const [avgOn, setAvgOn] = useState(() => saved.avgOn ?? true);
  const [compareSymbol, setCompareSymbol] = useState(() => saved.compare ?? null);
  const [hover, setHover] = useState(null);

  // First visit: open on the largest holding, if there is one.
  useEffect(() => {
    if (symbol || !portfolio?.positions?.length || !instruments.length) return;
    const largest = [...portfolio.positions].sort((a, b) => Number(b.market_value_try) - Number(a.market_value_try))[0];
    const match = instruments.find((i) => i.ticker === largest.ticker);
    if (match) setSymbol(match.yf_symbol);
  }, [symbol, portfolio, instruments]);

  useEffect(() => {
    try { localStorage.setItem(STORE, JSON.stringify({ symbol, range, weeks, filters, avgOn, compare: compareSymbol })); } catch { /* private mode */ }
  }, [symbol, range, weeks, filters, avgOn, compareSymbol]);

  const { data, error, loading, reload } = useChart(symbol, range, weeks, interval);
  const weekKey = weeks.join(",");
  useEffect(() => { setHover(null); }, [symbol, range, weekKey]);

  // Indicators run over every bar, lead-in included, so their values are true where each
  // shown segment starts; only the bars inside the segments are drawn.
  const series = useMemo(() => {
    if (!data?.bars?.length) return null;
    const bars = data.bars;
    const all = {
      close: bars.map((b) => b.close),
      high: bars.map((b) => b.high),
      low: bars.map((b) => b.low),
    };
    const segments = data.segments?.length ? data.segments : [[data.warmup, bars.length]];
    const idx = segments.flatMap(([s, e]) => Array.from({ length: e - s }, (_, k) => s + k));
    // Where a later segment starts on screen: a gap of unselected weeks lies behind it.
    const breaks = [];
    segments.slice(0, -1).reduce((at, [s, e]) => { breaks.push(at + e - s); return at + e - s; }, 0);
    // The change over what is shown: each segment from the close before it to its last
    // close, compounded, so the weeks in a gap never count.
    const ratio = segments.reduce((r, [s, e]) => {
      const before = s > 0 ? bars[s - 1].close : bars[s].open;
      return before ? r * (bars[e - 1].close / before) : r;
    }, 1);
    return {
      bars: idx.map((i) => bars[i]),
      times: idx.map((i) => Date.parse(bars[i].at)),
      close: idx.map((i) => all.close[i]),
      all, idx, breaks, ratio,
    };
  }, [data]);

  const { data: cmpData, error: cmpError } = useChart(compareSymbol, range, weeks, interval);

  // What the chart draws. Alone, the ticker's own bars. With a comparison, both lines
  // show the change since the window starts, so tickers at different prices or in
  // different currencies share one axis (no dual axes), and the x axis takes both
  // tickers' bar times. Each line is drawn through its own bars only and connects
  // straight across times it has none, so a thinly traded ticker reads as a line, not
  // as steps. A connection is dashed only when its market was closed: a gap longer than
  // CLOSED_GAP while the other ticker kept trading. Each segment restarts from the close
  // before it and compounds onto the ones before, so a line ends at its chip's change.
  // `*Read` arrays hold each line's last value at every point, for the tooltip and the
  // pane headers; `mainAt` and `cmpAt` are the bar each point reads.
  const view = useMemo(() => {
    if (!series) return null;
    if (!cmpData?.bars?.length) {
      const all = series.times.map(() => true);
      return { times: series.times, close: series.close, closeRead: series.close, mainOwn: all, mainAt: series.times.map((_, i) => i), breaks: series.breaks, compare: null };
    }
    const bars = data.bars;
    const mTimes = bars.map((b) => Date.parse(b.at));
    const cBars = cmpData.bars;
    const cTimes = cBars.map((b) => Date.parse(b.at));
    const cOwnTimes = new Set(cTimes);
    const step = INTERVAL_MS[data.interval] ?? INTERVAL_MS["1h"];
    const closedGap = step >= INTERVAL_MS["1d"] ? step * 1.5 : Math.max(CLOSED_GAP, 4 * step);
    const segments = data.segments?.length ? data.segments : [[data.warmup, bars.length]];
    const out = { times: [], close: [], closeRead: [], compare: [], compareRead: [], mainOwn: [], cmpOwn: [], mainAt: [], cmpAt: [], breaks: [] };
    let mainSoFar = 1, otherSoFar = 1, shown = 0;
    let cj = -1;
    segments.forEach(([s, e], k) => {
      const first = mTimes[s];
      // The last segment runs on to the compared ticker's latest bar; an earlier one
      // stops at its own last bar, so gap weeks stay out.
      const until = k === segments.length - 1 ? Infinity : mTimes[e - 1];
      const mOwnTimes = new Set(mTimes.slice(s, e));
      const merged = [...new Set([...mOwnTimes, ...cTimes.filter((c) => c >= first && c <= until)])].sort((a, b) => a - b);
      const base = s > 0 ? bars[s - 1].close : bars[s].open;
      const baseTime = mTimes[s > 0 ? s - 1 : s];
      while (cj + 1 < cTimes.length && cTimes[cj + 1] <= baseTime) cj++;
      const cBase = (cj >= 0 ? cBars[cj] : cBars.find((_, i) => cTimes[i] >= first))?.close;
      if (k > 0) out.breaks.push(out.times.length);
      let mi = s, mainLast = 1, otherLast = 1;
      for (const time of merged) {
        while (mi + 1 < e && mTimes[mi + 1] <= time) mi++;
        while (cj + 1 < cTimes.length && cTimes[cj + 1] <= time) cj++;
        mainLast = bars[mi].close / base;
        const mainPct = (mainSoFar * mainLast - 1) * 100;
        const mainOwn = mOwnTimes.has(time);
        out.times.push(time);
        out.mainOwn.push(mainOwn);
        out.close.push(mainOwn ? mainPct : null);
        out.closeRead.push(mainPct);
        out.mainAt.push(shown + mi - s);
        out.cmpAt.push(cj);
        const cmpOwn = cOwnTimes.has(time);
        out.cmpOwn.push(cmpOwn);
        if (cj < 0 || !cBase) { out.compare.push(null); out.compareRead.push(null); continue; }
        otherLast = cBars[cj].close / cBase;
        const otherPct = (otherSoFar * otherLast - 1) * 100;
        out.compare.push(cmpOwn ? otherPct : null);
        out.compareRead.push(otherPct);
      }
      mainSoFar *= mainLast;
      otherSoFar *= otherLast;
      shown += e - s;
    });
    // For each line: which connections into its own points are dashed (its market was
    // closed while the other traded), and at which points it is not trading.
    const lineMarks = (own) => {
      const dash = own.map(() => false);
      const idle = own.map(() => true);
      let prev = -1;
      own.forEach((isOwn, i) => {
        if (!isOwn) return;
        idle[i] = false;
        if (prev >= 0) {
          const closed = i - prev > 1 && out.times[i] - out.times[prev] > closedGap;
          dash[i] = closed;
          for (let j = prev + 1; j < i; j++) idle[j] = closed;
        }
        prev = i;
      });
      for (let j = prev + 1; j < own.length; j++) idle[j] = prev < 0 || out.times[j] - out.times[prev] > closedGap;
      return { dash, idle };
    };
    ({ dash: out.closeDash, idle: out.closeIdle } = lineMarks(out.mainOwn));
    ({ dash: out.compareDash, idle: out.compareIdle } = lineMarks(out.cmpOwn));
    const lastOther = [...out.compareRead].reverse().find((v) => v !== null);
    out.change = lastOther === undefined ? null : 1 + lastOther / 100;
    return out;
  }, [series, data, cmpData]);
  const comparing = Boolean(view?.compare);

  // The compared ticker's own bars, lead-in included, for its indicator lines.
  const cmpAll = useMemo(() => (cmpData?.bars?.length
    ? { close: cmpData.bars.map((b) => b.close), high: cmpData.bars.map((b) => b.high), low: cmpData.bars.map((b) => b.low) }
    : null), [cmpData]);

  const panes = useMemo(() => {
    if (!series) return [];
    // Each filter keeps its own shade wherever it appears: chip, pane line, pane name.
    return FILTERS.map((f, tone) => ({ f, tone })).filter(({ f }) => filters[f.key].on).map(({ f, tone }) => {
      const { n1, n2 } = filters[f.key];
      const full = f.compute(series.all, n1);
      const read = view.mainAt.map((at) => full[series.idx[at]]);
      const values = read.map((v, i) => (view.mainOwn[i] ? v : null));
      const level = n2 * 5;
      const pane = { key: f.key, filter: f, name: t(f.label), bars: f.period(n1), tone, values, read, dash: view.closeDash ?? null, level, n1, n2 };
      if (comparing && cmpAll) {
        // The same formula over the compared ticker's own bars, in its colour.
        const cFull = f.compute(cmpAll, n1);
        const cRead = view.cmpAt.map((at) => (at >= 0 ? cFull[at] : null));
        pane.cmp = { values: cRead.map((v, i) => (view.cmpOwn[i] ? v : null)), read: cRead, dash: view.compareDash };
      }
      return pane;
    });
  }, [series, view, comparing, cmpAll, filters, t]);

  const setFilter = (key, patch) => setFilters((prev) => ({ ...prev, [key]: { ...prev[key], ...patch } }));

  const byWeek = range === "W";
  // Selected weeks show their own last close; a live range shows the latest quote.
  const price = !series ? null : byWeek ? series.close[series.close.length - 1] : data.price;
  const change = !series
    ? null
    : byWeek
      ? series.ratio
      : (() => {
        const base = data.warmup > 0 ? data.bars[data.warmup - 1].close : series.bars[0].open;
        return base ? price / base : null;
      })();
  const at = hover ?? (view ? view.times.length - 1 : null);
  const hoverBar = hover !== null && view ? series.bars[view.mainAt[hover]] : null;
  const formatX = X_FORMAT[range] ?? ((ms) => shortDate(ms));
  const intraday = byWeek ? /[mh]$/.test(data?.interval ?? "") : INTRADAY.has(range);
  const stamp = intraday ? (ms) => dateTimeStamp(ms) : (ms) => fullDate(ms);
  const pickRange = (r) => setRange(r);
  const pickWeeks = (next) => { setWeeks(next); setRange("W"); };
  const current = instruments.find((i) => i.yf_symbol === symbol);
  // The open position in this ticker, when the Portfolio holds it.
  const holding = current ? portfolio?.positions?.find((p) => p.ticker === current.ticker && Number(p.quantity) > 0) ?? null : null;
  // The average buy is in the instrument's own currency, so it only belongs on a chart
  // quoted in that same currency.
  const avgBuy = holding?.average_purchase_price_native != null && data?.currency === holding.currency
    ? Number(holding.average_purchase_price_native)
    : null;
  // A price-level line has no place on a chart of % changes.
  const marks = avgBuy !== null && avgOn && !comparing ? [{ value: avgBuy, label: `${t("pos.avgBuy")} ${quote(avgBuy)}` }] : [];
  // Explain only what is on the chart now.
  const notes = [
    comparing ? ["ticker.compareLine", "ticker.note.compare"] : ["ticker.priceLine", "ticker.note.price"],
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

  // A held point is "not trading": the line there is that market's last value.
  const closedNote = (held) => (held ? <span className="muted">{t("ticker.notTrading")}</span> : null);
  const tooltip = hoverBar ? (
    <>
      <div className="tip-date">{stamp(view.times[hover])}</div>
      {comparing ? (
        <>
          <div className="tip-row"><i style={{ background: "var(--accent)" }} />{symbol} {closedNote(view.closeIdle[hover])}<b className="num">{pct(view.closeRead[hover])}</b></div>
          <div className="tip-row"><i style={{ background: "var(--compare)" }} />{compareSymbol} {closedNote(view.compareIdle[hover])}<b className="num">{pct(view.compareRead[hover])}</b></div>
        </>
      ) : (
        [["ticker.open", "open"], ["ticker.high", "high"], ["ticker.low", "low"], ["ticker.close", "close"]].map(([label, key]) => (
          <div key={key} className="tip-row">{t(label)}<b className="num">{quote(hoverBar[key])}</b></div>
        ))
      )}
      {panes.length > 0 && <div className="tip-sep" />}
      {panes.map((p) => (
        <div key={p.key} className="tip-row">
          <i style={{ background: `var(--pane-${p.tone + 1})` }} />{p.name}
          <b className="num">{figure(p.read[hover])}</b>
          {p.cmp && <span className="tip-cmp num"><i style={{ background: "var(--compare)" }} />{figure(p.cmp.read[hover])}</span>}
        </div>
      ))}
    </>
  ) : null;

  const spoken = hoverBar
    ? [
      stamp(view.times[hover]),
      `${t("ticker.close")} ${quote(hoverBar.close)}`,
      ...(comparing ? [`${symbol} ${pct(view.closeRead[hover])}`, `${compareSymbol} ${pct(view.compareRead[hover])}`] : []),
      ...panes.map((p) => {
        const s = filterState(p.read[hover], p.level);
        const own = `${p.name} ${figure(p.read[hover])}${s ? ` ${t(`ticker.${s}`)}` : ""}`;
        return p.cmp ? `${own}, ${compareSymbol} ${figure(p.cmp.read[hover])}` : own;
      }),
    ].join(", ")
    : "";

  const heads = panes.map((p) => {
    const value = at !== null ? p.read[at] : null;
    const state = filterState(value, p.level);
    const cValue = p.cmp && at !== null ? p.cmp.read[at] : null;
    const cState = filterState(cValue, p.level);
    return (
      <>
        <span className="pane-name"><i aria-hidden="true" style={{ background: `var(--pane-${p.tone + 1})` }} />{p.name}</span>
        <span className="pane-bars num">{t("ticker.bars", { n: p.bars })}</span>
        <span className="pane-value num">{figure(value)}</span>
        <span className={`pane-state ${state === "long" ? "up" : state === "short" ? "down" : "muted"}`}>
          {state ? t(`ticker.${state}`) : "—"}
        </span>
        {p.cmp && (
          <span className="pane-cmp">
            <i aria-hidden="true" />{compareSymbol}
            <span className="num">{figure(cValue)}</span>
            <span className={cState === "long" ? "up" : cState === "short" ? "down" : "muted"}>{cState ? t(`ticker.${cState}`) : "—"}</span>
          </span>
        )}
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
          {change !== null && (
            <span className={`chip num ${toneOf(change - 1)}`}>{arrow(change - 1)} {ratioPct(change)}</span>
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
              <button key={r} type="button" aria-pressed={range === r} onClick={() => pickRange(r)}>
                {range === r && <motion.span layoutId="ticker-range-pill" className="segmented-pill" transition={spring} />}
                <span>{t(`ticker.range.${r}`)}</span>
              </button>
            ))}
            <WeekPicker weeks={weeks} active={byWeek} onChange={pickWeeks} />
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
        {avgBuy !== null && !comparing && (
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
        {compareSymbol ? (
          <span className="legend-chip compare-chip">
            <i style={{ background: "var(--compare)" }} />
            {t("ticker.vs", { symbol: compareSymbol })}
            {view?.change != null ? (
              <span className={`num ${toneOf(view.change - 1)}`}>{ratioPct(view.change)}</span>
            ) : cmpError ? (
              <span className="muted">{t("ticker.compareNoData")}</span>
            ) : null}
            <button type="button" className="chip-x" onClick={() => setCompareSymbol(null)} aria-label={t("ticker.compareRemove", { symbol: compareSymbol })}>
              <Icon name="x" size={12} />
            </button>
          </span>
        ) : (
          <Popover
            label={t("ticker.compare")}
            align="left"
            className="ticker-pop"
            trigger={({ open, toggle }) => (
              <button type="button" className="legend-chip" onClick={toggle} aria-expanded={open} aria-haspopup="dialog">
                <Icon name="plus" size={13} />{t("ticker.compare")}
              </button>
            )}
          >
            {({ close }) => (
              <TickerSearch
                instruments={instruments}
                search={api.searchMarket}
                onPick={(item) => { close(); if (item.yf_symbol !== symbol) setCompareSymbol(item.yf_symbol); }}
              />
            )}
          </Popover>
        )}
      </div>

      <div className="chart-stage">
        {series ? (
          <PriceChart
            times={view.times}
            close={view.close}
            compare={view.compare}
            closeDash={view.closeDash}
            compareDash={view.compareDash}
            formatY={comparing ? (v) => pct(v, 1) : quote}
            panes={panes}
            marks={marks}
            breaks={view.breaks}
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
