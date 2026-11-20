// One instrument's price, historical or live, with the trend filters from
// chart/indicators.js as toggleable panes. Any Yahoo symbol can be charted, held or not.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import { api } from "../../api.js";
import { arrow, compact, dateTimeStamp, duration, figure, fullDate, hourMinute, money, monthYear, pct, quote, ratioPct, shortDate, signedCompact, signedMoney, signedQuote, toneOf, withSign } from "../../format.js";
import PriceChart from "../chart/PriceChart.jsx";
import { FILTERS, filterState, sma, volumeSplit } from "../chart/indicators.js";
import CompanyInfo from "../components/CompanyInfo.jsx";
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

/** Whether a chart's market is trading now, pre-market and after hours included. */
const trading = (data) => Boolean(data?.market_open || data?.extended_session);

/**
 * Bars for (symbol, range[, weeks]), polled while the market trades. A stale answer is
 * dropped. `tick` changes with every dashboard price update: the chart reloads then and
 * restarts its own timer, so the line moves with the prices on the rest of the page. The
 * timer covers a ticker whose market trades while the portfolio's are shut.
 */
function useChart(symbol, range, weeks, pollSeconds, tick) {
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
  const ticked = useRef(tick);
  // Whether the chart's market is trading; a price update elsewhere cannot move a chart
  // whose market is shut, and a hidden tab draws nothing.
  const liveRef = useRef(false);
  useEffect(() => {
    if (ticked.current === tick) return;
    ticked.current = tick;
    if (liveRef.current && !document.hidden) load();
  }, [tick, load]);

  const fresh = state.key === key;
  const open = fresh && trading(state.data);
  liveRef.current = open;
  useEffect(() => {
    const seconds = open ? pollSeconds : CLOSED_POLL_SECONDS;
    if (!symbol || !seconds) return undefined;
    const id = window.setInterval(() => { if (!document.hidden) load(); }, seconds * 1000);
    return () => window.clearInterval(id);
  }, [load, symbol, open, pollSeconds, tick]);

  return {
    data: fresh ? state.data : null,
    error: fresh ? state.error : null,
    loading: !fresh,
    reload: () => { setState({ key: null, data: null, error: null }); load(); },
  };
}

/** The close of the newest regular bar before index `end`; after-hours bars move after the
 *  session's close, so they never stand in for it. */
const lastRegularClose = (bars, end) => {
  for (let i = end - 1; i >= 0; i--) if (!bars[i].extended) return bars[i].close;
  return null;
};

const stateTone = (state) => (state === "long" ? "up" : state === "short" ? "down" : "muted");

export default function Ticker({ dash }) {
  const t = useT();
  const { instruments, portfolio, interval, lastUpdated } = dash;
  const [saved] = useState(loadSaved);
  const [symbol, setSymbol] = useState(() => saved.symbol ?? null);
  const [weeks, setWeeks] = useState(() => (Array.isArray(saved.weeks) ? saved.weeks.filter((w) => /^\d{4}-W\d{2}$/.test(w)) : []));
  const [range, setRange] = useState(() => (RANGES.includes(saved.range) || (saved.range === "W" && weeks.length) ? saved.range : "1D"));
  const [filters, setFilters] = useState(() => initialFilters(saved.filters));
  const [avgOn, setAvgOn] = useState(() => saved.avgOn ?? true);
  const [prevOn, setPrevOn] = useState(() => saved.prevOn ?? true);
  const [volOn, setVolOn] = useState(() => saved.volOn ?? false);
  const [fullDay, setFullDay] = useState(() => saved.fullDay ?? false);
  const [compareSymbol, setCompareSymbol] = useState(() => saved.compare ?? null);
  const [hover, setHover] = useState(null);
  // Whether the keyboard moved the reading: only then is it spoken.
  const [keyed, setKeyed] = useState(false);
  // Panes whose N1/N2 inputs are open on a narrow chart.
  const [editing, setEditing] = useState(() => new Set());

  // First visit: open on the largest holding, if there is one.
  useEffect(() => {
    if (symbol || !portfolio?.positions?.length || !instruments.length) return;
    const largest = [...portfolio.positions].sort((a, b) => Number(b.market_value_try) - Number(a.market_value_try))[0];
    const match = instruments.find((i) => i.ticker === largest.ticker);
    if (match) setSymbol(match.yf_symbol);
  }, [symbol, portfolio, instruments]);

  useEffect(() => {
    try { localStorage.setItem(STORE, JSON.stringify({ symbol, range, weeks, filters, avgOn, prevOn, volOn, fullDay, compare: compareSymbol })); } catch { /* private mode */ }
  }, [symbol, range, weeks, filters, avgOn, prevOn, volOn, fullDay, compareSymbol]);

  const { data, error, loading, reload } = useChart(symbol, range, weeks, interval, lastUpdated);
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
      volume: bars.map((b) => b.volume ?? 0),
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
    // Indices, currencies and some funds report no volume at all.
    const hasVolume = idx.some((i) => all.volume[i] > 0);
    const split = hasVolume ? volumeSplit(all) : null;
    return {
      hasVolume, split,
      bars: idx.map((i) => bars[i]),
      times: idx.map((i) => Date.parse(bars[i].at)),
      close: idx.map((i) => all.close[i]),
      all, idx, breaks, ratio,
    };
  }, [data]);

  const { data: cmpData, error: cmpError } = useChart(compareSymbol, range, weeks, interval, lastUpdated);

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
      const closeExt = series.bars.map((b) => Boolean(b.extended));
      return { times: series.times, close: series.close, closeRead: series.close, closeExt, mainOwn: all, mainAt: series.times.map((_, i) => i), breaks: series.breaks, compare: null };
    }
    const bars = data.bars;
    const mTimes = bars.map((b) => Date.parse(b.at));
    const cBars = cmpData.bars;
    const cTimes = cBars.map((b) => Date.parse(b.at));
    const cOwnTimes = new Set(cTimes);
    const step = INTERVAL_MS[data.interval] ?? INTERVAL_MS["1h"];
    const closedGap = step >= INTERVAL_MS["1d"] ? step * 1.5 : Math.max(CLOSED_GAP, 4 * step);
    const segments = data.segments?.length ? data.segments : [[data.warmup, bars.length]];
    const out = { times: [], close: [], closeRead: [], closeExt: [], compare: [], compareRead: [], compareExt: [], mainOwn: [], cmpOwn: [], mainAt: [], cmpAt: [], breaks: [] };
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
        out.closeExt.push(mainOwn && Boolean(bars[mi].extended));
        out.mainAt.push(shown + mi - s);
        out.cmpAt.push(cj);
        const cmpOwn = cOwnTimes.has(time);
        out.cmpOwn.push(cmpOwn);
        out.compareExt.push(cmpOwn && cj >= 0 && Boolean(cBars[cj].extended));
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

  // Volume is the ticker's own: two tickers' share counts never share a scale.
  const showVolume = Boolean(series?.hasVolume) && !comparing;
  const volumeBars = useMemo(() => (showVolume
    ? view.mainAt.map((at, i) => {
      if (!view.mainOwn[i]) return null;
      const b = series.bars[at];
      return { v: b.volume ?? 0, up: b.close >= b.open };
    })
    : null), [showVolume, view, series]);

  const panes = useMemo(() => {
    if (!series) return [];
    // Net buying per bar: the estimated buying volume less the selling volume.
    const volumePane = volOn && showVolume ? (() => {
      const at = (arr) => view.mainAt.map((k) => arr[series.idx[k]]);
      const buy = at(series.split.buy), sell = at(series.split.sell);
      const read = buy.map((b, i) => b - sell[i]);
      const volume = view.mainAt.map((k) => series.bars[k].volume ?? 0);
      // The shown range's totals, read while no bar is pointed at; each bar counts once.
      const total = { buy: 0, sell: 0, volume: 0 };
      view.mainOwn.forEach((own, i) => {
        if (!own) return;
        total.buy += buy[i];
        total.sell += sell[i];
        total.volume += volume[i];
      });
      total.net = total.buy - total.sell;
      return {
        key: "volume", histogram: true, name: t("ticker.volume"), level: 0, format: compact,
        values: read.map((v, i) => (view.mainOwn[i] ? v : null)), read, buy, sell, volume, total,
      };
    })() : null;
    // Every pane is named, so a pane's line is the ticker's own colour, as the compared
    // ticker's is its colour.
    const filterPanes = FILTERS.filter((f) => filters[f.key].on).map((f) => {
      const { n1, n2 } = filters[f.key];
      // MA slope is in price units, so two tickers at different prices cannot share its
      // axis. While comparing, each line is its slope less the level, as a % of its own
      // average: the level sits at 0 and the sign, so Long or Short, is unchanged.
      const asPct = comparing && f.key === "maSlope";
      const toPct = (raw, bars) => {
        const avg = sma(bars.close, f.period(n1));
        return raw.map((v, i) => (v === null || !avg[i] ? null : ((v - n2 * 5) / avg[i]) * 100));
      };
      const full = asPct ? toPct(f.compute(series.all, n1), series.all) : f.compute(series.all, n1);
      const read = view.mainAt.map((at) => full[series.idx[at]]);
      const values = read.map((v, i) => (view.mainOwn[i] ? v : null));
      const level = asPct ? 0 : n2 * 5;
      const format = asPct ? (v) => pct(v, 4) : figure;
      const pane = { key: f.key, filter: f, name: t(f.label), bars: f.period(n1), editing: editing.has(f.key), values, read, dash: view.closeDash ?? null, level, format, asPct, n1, n2 };
      if (comparing && cmpAll) {
        // The same formula over the compared ticker's own bars, in its colour.
        const cFull = asPct ? toPct(f.compute(cmpAll, n1), cmpAll) : f.compute(cmpAll, n1);
        const cRead = view.cmpAt.map((at) => (at >= 0 ? cFull[at] : null));
        pane.cmp = { values: cRead.map((v, i) => (view.cmpOwn[i] ? v : null)), read: cRead, dash: view.compareDash };
      }
      return pane;
    });
    return volumePane ? [volumePane, ...filterPanes] : filterPanes;
  }, [series, view, comparing, cmpAll, filters, editing, volOn, showVolume, t]);

  const setFilter = (key, patch) => setFilters((prev) => ({ ...prev, [key]: { ...prev[key], ...patch } }));
  const toggleEditing = (key) => setEditing((prev) => {
    const next = new Set(prev);
    if (!next.delete(key)) next.add(key);
    return next;
  });

  const byWeek = range === "W";
  // The close before the shown window, for the change on ranges other than 1D.
  const leadClose = useMemo(() => (data ? lastRegularClose(data.bars, data.warmup) : null), [data]);
  // 1D: the previous session's close, worked out by the server (official, closing auction
  // included, from the right session). The dotted line and the change chip measure from it.
  const prevClose = range === "1D" ? data?.previous_close ?? null : null;
  // Selected weeks show their own last close; a live range shows the latest quote.
  const price = !series ? null : byWeek ? series.close[series.close.length - 1] : data.price;
  const change = !series
    ? null
    : byWeek
      ? series.ratio
      : (() => {
        // With no close before the window, the first regular bar's open, never a pre-market one.
        const base = prevClose ?? leadClose ?? (series.bars.find((b) => !b.extended) ?? series.bars[0]).open;
        return base ? price / base : null;
      })();
  // While the listing trades before or after its session: the newest extended bar's price
  // and its change from the regular session's last price.
  const lastBar = data?.bars?.[data.bars.length - 1];
  const extQuote = data?.extended_session && lastBar?.extended && data.price
    ? { price: lastBar.close, change: lastBar.close / data.price }
    : null;
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
  // 1D: the previous session's last close, the base of the change chip.

  // A price-level line has no place on a chart of % changes.
  const marks = comparing ? [] : [
    ...(avgBuy !== null && avgOn ? [{ value: avgBuy, label: `${t("pos.avgBuy")} ${quote(avgBuy)}` }] : []),
    ...(prevClose !== null && prevOn ? [{ value: prevClose, label: `${t("ticker.prevClose")} ${quote(prevClose)}`, dotted: true, fit: true }] : []),
  ];
  // 1D over the whole session: the x axis runs on, one bar step at a time, to the close.
  // After the close the bars already span the session, so the option only shows while it
  // trades. A listing with extended hours runs from the pre-market open to the after-hours close.
  const session = range === "1D" && trading(data) ? data?.session ?? null : null;
  const axisTimes = useMemo(() => {
    if (!fullDay || !session || !view?.times.length) return null;
    const step = INTERVAL_MS[data.interval] ?? INTERVAL_MS["5m"];
    const end = Date.parse(session[1]);
    const out = [...view.times];
    for (let next = out[out.length - 1] + step; next <= end; next += step) out.push(next);
    return out;
  }, [fullDay, session, view, data]);
  // Explain only what is on the chart now.
  const notes = [
    comparing ? ["ticker.compareLine", "ticker.note.compare"] : ["ticker.priceLine", "ticker.note.price"],
    ...(view?.closeExt.some(Boolean) || view?.compareExt?.some(Boolean) ? [["ticker.extended", "ticker.note.extended"]] : []),
    ...(showVolume ? [["ticker.volume", "ticker.note.volume"]] : []),
    ...(panes.some((p) => !p.histogram) ? [["ticker.levelLine", "ticker.note.level"]] : []),
    ...panes.filter((p) => !p.histogram).map((p) => (p.asPct ? ["ticker.maSlope", "ticker.note.maSlopePct"] : FILTER_NOTES[p.key])).filter(Boolean),
    ...(marks.some((m) => !m.dotted) ? [["pos.avgBuy", "ticker.note.avgBuy"]] : []),
    ...(marks.some((m) => m.dotted) ? [["ticker.prevClose", "ticker.note.prevClose"]] : []),
    ["ticker.measure", "ticker.note.measure"],
    ...(holding ? [["attr.fx", "ticker.note.fx"]] : []),
  ];

  // Between two points (a before b): the change of everything on the chart, for the
  // measuring pop-up, and the same as one sentence for a screen reader. The move runs from
  // a's close to b's, so what traded in between (high, low, volume) counts from bar a + 1.
  // Rebuilt only when the data or the panes change, not on every hover.
  const measure = useCallback((a, b) => {
    const at = intraday ? (ms) => dateTimeStamp(ms) : (ms) => fullDate(ms);
    const took = duration(view.times[b] - view.times[a]);
    const when = `${at(view.times[a])} – ${at(view.times[b])}`;
    const said = [when, took];
    // One pass over the bars traded after the start: the main ticker's own bars only.
    const histograms = panes.filter((p) => p.histogram);
    const nets = histograms.map(() => 0);
    let high = -Infinity, low = Infinity, volume = 0;
    for (let i = a + 1; i <= b; i++) {
      if (!view.mainOwn[i]) continue;
      const bar = series.bars[view.mainAt[i]];
      if (bar.high > high) high = bar.high;
      if (bar.low < low) low = bar.low;
      volume += bar.volume ?? 0;
      histograms.forEach((p, k) => { nets[k] += p.read[i] ?? 0; });
    }
    const rows = [];
    let head;
    if (comparing) {
      // Each line is a % change since the window starts; between two points it compounds.
      const lines = [[symbol, "var(--accent)", view.closeRead], [compareSymbol, "var(--compare)", view.compareRead]].map(([name, color, read]) => {
        const r = read[a] == null || read[b] == null ? null : (1 + read[b] / 100) / (1 + read[a] / 100);
        said.push(`${name} ${r === null ? "—" : ratioPct(r)}`);
        return { name, color, r };
      });
      head = lines.map(({ name, color, r }) => (
        <div key={name} className="tip-row measure-line">
          <i style={{ background: color }} />{name}
          <b className={`num ${r === null ? "" : toneOf(r - 1)}`}>{r === null ? "—" : <>{arrow(r - 1)} {ratioPct(r)}</>}</b>
        </div>
      ));
    } else {
      const from = view.closeRead[a], to = view.closeRead[b];
      const diff = to - from;
      said.push(`${signedQuote(diff)} ${from ? ratioPct(to / from) : ""}`);
      head = (
        <div className={`measure-change num ${toneOf(diff)}`}>
          {arrow(diff)} {signedQuote(diff)}{from ? <small>{ratioPct(to / from)}</small> : null}
        </div>
      );
      rows.push(["ticker.measure.from", quote(from)], ["ticker.measure.to", quote(to)]);
      // The start price counts towards the range, so a quiet stretch never reads beyond it.
      if (Number.isFinite(high)) rows.push(["ticker.high", quote(Math.max(high, from))], ["ticker.low", quote(Math.min(low, from))]);
    }
    if (showVolume) rows.push(["ticker.volume", compact(volume)]);
    const paneRows = panes.map((p) => {
      if (p.histogram) {
        const net = nets[histograms.indexOf(p)];
        said.push(`${t("ticker.netVolume")} ${signedCompact(net)}`);
        return <div key={p.key} className="tip-row">{t("ticker.netVolume")}<b className={`num ${toneOf(net)}`}>{signedCompact(net)}</b></div>;
      }
      const change = (read) => (read[a] == null || read[b] == null ? null : read[b] - read[a]);
      const value = (v) => (v == null ? "—" : p.format(v));
      const d = change(p.read);
      said.push(`${p.name} ${withSign(d, p.format)}`);
      return (
        <div key={p.key} className="tip-row">
          {p.cmp && <i style={{ background: "var(--accent)" }} />}{p.name}
          <span className="measure-span num">{value(p.read[a])} → {value(p.read[b])}</span>
          <b className="num">{withSign(d, p.format)}</b>
          {p.cmp && <span className="tip-cmp num"><i style={{ background: "var(--compare)" }} />{withSign(change(p.cmp.read), p.format)}</span>}
        </div>
      );
    });
    return {
      spoken: said.join(", "),
      content: (
        <>
          <div className="tip-date measure-when">
            <span>{at(view.times[a])} → {at(view.times[b])}</span>
            <span className="measure-took">{took}</span>
          </div>
          {head}
          {rows.length > 0 && <div className="tip-sep" />}
          {rows.map(([label, value]) => <div key={label} className="tip-row">{t(label)}<b className="num">{value}</b></div>)}
          {paneRows.length > 0 && <div className="tip-sep" />}
          {paneRows}
        </>
      ),
    };
  }, [view, series, panes, comparing, showVolume, symbol, compareSymbol, intraday, t]);

  const picker = (
    <Popover
      label={t("ticker.choose")}
      align="left"
      className="ticker-pop"
      trigger={({ open, toggle }) => (
        <h2 className="ticker-heading">
          <button type="button" className="ticker-pick" onClick={toggle} aria-expanded={open} aria-haspopup="dialog">
            {comparing && <i className="ticker-swatch" aria-hidden="true" />}
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
  // A pre-market or after-hours point names its session.
  const closedNote = (held) => (held ? <span className="muted">{t("live.closed")}</span> : null);
  const sessionOf = (bar) => (bar?.extended ? t(`live.${bar.extended}`) : null);
  const cmpBarAt = (i) => (comparing && view.cmpOwn[i] && view.cmpAt[i] >= 0 ? cmpData.bars[view.cmpAt[i]] : null);
  const lineNote = (idle, bar) => closedNote(idle) ?? (sessionOf(bar) && <span className="muted">{sessionOf(bar)}</span>);
  const tooltip = hoverBar ? (
    <>
      <div className="tip-date">
        {stamp(view.times[hover])}
        {!comparing && sessionOf(hoverBar) && <span className="tip-session">{sessionOf(hoverBar)}</span>}
      </div>
      {comparing ? (
        <>
          <div className="tip-row"><i style={{ background: "var(--accent)" }} />{symbol} {lineNote(view.closeIdle[hover], view.mainOwn[hover] ? hoverBar : null)}<b className="num">{pct(view.closeRead[hover])}</b></div>
          <div className="tip-row"><i style={{ background: "var(--compare)" }} />{compareSymbol} {lineNote(view.compareIdle[hover], cmpBarAt(hover))}<b className="num">{pct(view.compareRead[hover])}</b></div>
        </>
      ) : (
        [["ticker.open", "open"], ["ticker.high", "high"], ["ticker.low", "low"], ["ticker.close", "close"]].map(([label, key]) => (
          <div key={key} className="tip-row">{t(label)}<b className="num">{quote(hoverBar[key])}</b></div>
        ))
      )}
      {showVolume && <div className="tip-row">{t("ticker.volume")}<b className="num">{compact(hoverBar.volume)}</b></div>}
      {prevClose !== null && !comparing && (
        <div className="tip-row">{t("ticker.vsPrevClose")}<b className={`num ${toneOf(hoverBar.close - prevClose)}`}>{ratioPct(hoverBar.close / prevClose)}</b></div>
      )}
      {panes.length > 0 && <div className="tip-sep" />}
      {panes.map((p) => (p.histogram ? (
        <div key={p.key} className="tip-row">
          {t("ticker.netVolume")}
          <b className={`num ${toneOf(p.read[hover])}`}>{signedCompact(p.read[hover])}</b>
        </div>
      ) : (
        <div key={p.key} className="tip-row">
          {p.cmp && <i style={{ background: "var(--accent)" }} />}{p.name}
          <b className="num">{p.format(p.read[hover])}</b>
          {p.cmp && <span className="tip-cmp num"><i style={{ background: "var(--compare)" }} />{p.format(p.cmp.read[hover])}</span>}
        </div>
      )))}
    </>
  ) : null;

  const spoken = hoverBar && keyed
    ? [
      stamp(view.times[hover]),
      ...(sessionOf(hoverBar) && (!comparing || view.mainOwn[hover]) ? [sessionOf(hoverBar)] : []),
      `${t("ticker.close")} ${quote(hoverBar.close)}`,
      ...(prevClose !== null && !comparing ? [`${t("ticker.vsPrevClose")} ${ratioPct(hoverBar.close / prevClose)}`] : []),
      ...(comparing ? [`${symbol} ${pct(view.closeRead[hover])}`, `${compareSymbol} ${pct(view.compareRead[hover])}`] : []),
      ...panes.map((p) => {
        if (p.histogram) {
          const net = p.read[hover];
          return `${t("ticker.netVolume")} ${signedCompact(net)}${net ? `, ${t(net > 0 ? "ticker.netBuyers" : "ticker.netSellers")}` : ""}`;
        }
        const s = filterState(p.read[hover], p.level);
        const own = `${p.name} ${p.format(p.read[hover])}${s ? ` ${t(`ticker.${s}`)}` : ""}`;
        return p.cmp ? `${own}, ${compareSymbol} ${p.format(p.cmp.read[hover])}` : own;
      }),
    ].join(", ")
    : "";

  // On a narrow chart a pane's N1/N2 inputs open from its name; a wide one always shows them.
  const heads = (narrow) => panes.map((p) => {
    if (p.histogram) {
      // The range's totals, or the bar under the pointer.
      const r = hover === null ? p.total : { buy: p.buy[hover], sell: p.sell[hover], volume: p.volume[hover], net: p.read[hover] };
      const net = r.net;
      return (
        <>
          <span className="pane-name"><i aria-hidden="true" />{p.name}</span>
          {/* What the figures cover: the shown range, or the bar under the pointer. */}
          <span className="pane-bars">
            {hover !== null ? stamp(view.times[hover]) : byWeek ? t("ticker.weeksCount", { n: weeks.length }) : t(`ticker.range.${range}`)}
          </span>
          <span className={`pane-value num ${toneOf(net)}`}>{signedCompact(net)}</span>
          <span className={`pane-state ${toneOf(net)}`}>{net ? t(net > 0 ? "ticker.netBuyers" : "ticker.netSellers") : "—"}</span>
          <span className="pane-params pane-volume num">
            <span>{t("ticker.buyVol")} <b className="up">{compact(r.buy)}</b></span>
            <span>{t("ticker.sellVol")} <b className="down">{compact(r.sell)}</b></span>
            <span>{t("ticker.volume")} <b>{compact(r.volume)}</b></span>
          </span>
        </>
      );
    }
    const value = at !== null ? p.read[at] : null;
    const state = filterState(value, p.level);
    const cValue = p.cmp && at !== null ? p.cmp.read[at] : null;
    const cState = filterState(cValue, p.level);
    const name = <><i aria-hidden="true" />{p.name}</>;
    return (
      <>
        {narrow ? (
          <button type="button" className="pane-name" aria-expanded={p.editing} aria-label={t("ticker.editParams", { name: p.name })} onClick={() => toggleEditing(p.key)}>
            {name}<Icon name="down" size={12} />
          </button>
        ) : (
          <span className="pane-name">{name}</span>
        )}
        <span className="pane-value num">{p.format(value)}</span>
        <span className={`pane-state ${stateTone(state)}`}>{state ? t(`ticker.${state}`) : "—"}</span>
        {p.cmp && (
          <span className="pane-cmp">
            <i aria-hidden="true" />{compareSymbol}
            <span className="num">{p.format(cValue)}</span>
            <span className={stateTone(cState)}>{cState ? t(`ticker.${cState}`) : "—"}</span>
          </span>
        )}
        {(!narrow || p.editing) && (
          <span className="pane-params">
            {p.filter.usesN1 && <ParamInput label="N1" ariaLabel={`${p.name} N1`} integer value={p.n1} onChange={(n1) => setFilter(p.key, { n1 })} />}
            <span className="pane-bars num">{t("ticker.bars", { n: p.bars })}</span>
            <ParamInput label="N2" ariaLabel={`${p.name} N2`} value={p.n2} onChange={(n2) => setFilter(p.key, { n2 })} />
            <span className="pane-level num" title={t("ticker.level")}><i aria-hidden="true" />{p.asPct ? pct(0, 0) : figure(p.level)}</span>
          </span>
        )}
      </>
    );
  });

  return (
    <div className="ticker-layout">
      <section className="card chart-card ticker-card">
        <header className="card-head chart-head">
          <div className="chart-title">
            {picker}
            {price !== null && <span className="ticker-price num">{quote(price)} <small>{data.currency}</small></span>}
            {change !== null && (
              <span className={`chip num ${toneOf(change - 1)}`}>{arrow(change - 1)} {ratioPct(change)}</span>
            )}
            {data && (
              <span className={`ticker-session ${data.market_open ? "open" : data.extended_session ? "extended" : ""}`}>
                <i aria-hidden="true" />{t(data.market_open ? "live.open" : data.extended_session ? `live.${data.extended_session}` : "live.closed")}
                {extQuote && (
                  <>
                    <span className="num">{quote(extQuote.price)}</span>
                    <span className={`num ${toneOf(extQuote.change - 1)}`}>{ratioPct(extQuote.change)}</span>
                  </>
                )}
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
          {(view?.closeExt.some(Boolean) || view?.compareExt?.some(Boolean)) && (
            <span className="legend-chip legend-key">
              <i style={{ background: comparing && !view.closeExt.some(Boolean) ? "var(--compare-extended)" : "var(--extended)" }} />
              {t("ticker.extendedKey")}
            </span>
          )}
          {prevClose !== null && !comparing && (
            <button
            type="button"
            className={`legend-chip ${prevOn ? "" : "off"}`}
            aria-pressed={prevOn}
            title={data.previous_close_date ? t("hero.prevSession", { date: fullDate(data.previous_close_date) }) : undefined}
            onClick={() => setPrevOn((v) => !v)}
          >
              <i className="dotted" />
              {t("ticker.prevClose")} <span className="num">{quote(prevClose)}</span>
            </button>
          )}
          {session && (
            <button type="button" className={`legend-chip ${fullDay ? "" : "off"}`} aria-pressed={fullDay} onClick={() => setFullDay((v) => !v)}>
              {t("ticker.fullDay")}
            </button>
          )}
          {showVolume && (
            <button type="button" className={`legend-chip ${volOn ? "" : "off"}`} aria-pressed={volOn} onClick={() => setVolOn((v) => !v)}>
              {t("ticker.volume")}
            </button>
          )}
          {FILTERS.map((f) => (
            <button
              key={f.key}
              type="button"
              className={`legend-chip ${filters[f.key].on ? "" : "off"}`}
              aria-pressed={filters[f.key].on}
              onClick={() => setFilter(f.key, { on: !filters[f.key].on })}
            >
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
              axisTimes={axisTimes}
              volume={volumeBars}
              close={view.close}
              compare={view.compare}
              closeDash={view.closeDash}
              compareDash={view.compareDash}
              closeExtended={view.closeExt}
              compareExtended={view.compareExt ?? null}
              formatY={comparing ? (v) => pct(v, 1) : quote}
              panes={panes}
              marks={marks}
              breaks={view.breaks}
              heads={heads}
              formatX={formatX}
              live={trading(data)}
              onHover={(i, byKey) => { setHover(i); setKeyed(byKey); }}
              tooltip={tooltip}
              measure={measure}
              measureName={t("ticker.measure")}
              measureLabel={t("ticker.measure.clear")}
              resetKey={`${symbol}|${range}|${weekKey}|${comparing ? compareSymbol : ""}`}
              ariaLabel={t("ticker.aria", { symbol })}
              roleLabel={t("ticker.chartRole")}
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
      <CompanyInfo symbol={symbol} />
    </div>
  );
}
