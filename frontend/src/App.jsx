// Single page, dense but readable (SPEC §9):
// hero -> attribution bar -> history chart -> positions -> transaction manager.
// The chart sits directly under the attribution bar because it is the same price/FX
// split the bar states as two numbers, drawn over time.
//
// Auto-refresh is user-configurable (US-5.1) with a visible last-updated time; the manual
// button additionally forces a cache bypass via POST /api/refresh (US-5.2). The poll drops
// to a slow cadence when every exchange is shut rather than stopping, because FX still
// trades and this portfolio is measured in lira (SPEC §8, market-hours awareness).
//
// The poll only *reads*; the server keeps the caches warm on its own schedule, so the
// numbers move without anything being clicked. See `_auto_refresh` in app/main.py.

import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "./api.js";
import { useFlash } from "./flash.js";
import { arrow, clockTime, money, ratioPct, toneOf } from "./format.js";
import { isIntradayRange, isPannable, rangeDays } from "./ranges.js";
import AttributionBar from "./components/AttributionBar.jsx";
import Brand from "./components/Brand.jsx";
import HeroCard from "./components/HeroCard.jsx";
import PositionsTable from "./components/PositionsTable.jsx";
import TransactionManager from "./components/TransactionManager.jsx";

// Recharts is by far the largest dependency and the chart sits below the fold, so the
// hero card and positions table are not made to wait on it. The data fetch starts
// immediately either way — only the rendering library is deferred.
const HistoryChart = lazy(() => import("./components/HistoryChart.jsx"));

// 10s is the default and the fast end of what is safe: every symbol goes out in one
// batched request, and Yahoo's delayed feed only reheats every 10-15s anyway, so faster
// returns the same number while courting a 429. 5s is offered for when you are watching
// a position move and want the chart to keep up.
const INTERVALS = [
  { value: 5, label: "5 sn" },
  { value: 10, label: "10 sn" },
  { value: 15, label: "15 sn" },
  { value: 30, label: "30 sn" },
  { value: 60, label: "60 sn" },
  { value: 300, label: "5 dk" },
  { value: 0, label: "kapalı" },
];
const DEFAULT_INTERVAL = 10;

const INCEPTION = "2026-03-29";

//: Floor for the poll while every exchange is shut. Only FX can move then, so there is
//: nothing to gain from the fast cadence — but plenty to lose from not polling at all.
const CLOSED_POLL_SECONDS = 900;

// The page is four screens tall, so the rail is navigation rather than decoration.
// `meta` puts the one number worth knowing before you jump next to each entry.
// Özet is not in this list: it is the pinned summary that condenses into the topbar on
// scroll, so it always leads. Everything below it is a widget the reader can reorder.
const WIDGETS = [
  { id: "ayristirma", label: "Ayrıştırma" },
  { id: "grafik", label: "Grafik" },
  { id: "pozisyonlar", label: "Pozisyonlar", meta: (p) => p?.positions?.length ?? null },
  { id: "islemler", label: "İşlemler" },
];
const DEFAULT_ORDER = WIDGETS.map((w) => w.id);
const LAYOUT_KEY = "fadir.layout";

/** Stored order, repaired against the current widget set. */
function loadOrder() {
  try {
    const saved = JSON.parse(localStorage.getItem(LAYOUT_KEY) ?? "null");
    if (!Array.isArray(saved)) return DEFAULT_ORDER;
    // Drop ids that no longer exist and append any widget added since the layout was
    // saved, so a release that adds a panel does not leave it invisible forever.
    const known = saved.filter((id) => DEFAULT_ORDER.includes(id));
    return [...known, ...DEFAULT_ORDER.filter((id) => !known.includes(id))];
  } catch {
    return DEFAULT_ORDER;
  }
}

const dfHm = new Intl.DateTimeFormat("tr-TR", { hour: "2-digit", minute: "2-digit" });
const dfWeekday = new Intl.DateTimeFormat("tr-TR", { weekday: "short" });

/** "yarın 09:30" / "16:30" — short label for when polling resumes. */
function nextOpenLabel(iso) {
  const when = new Date(iso);
  const time = dfHm.format(when);

  const today = new Date();
  const days = Math.round(
    (new Date(when.getFullYear(), when.getMonth(), when.getDate()) -
      new Date(today.getFullYear(), today.getMonth(), today.getDate())) /
      86400000,
  );

  if (days <= 0) return time;
  if (days === 1) return `yarın ${time}`;
  return `${dfWeekday.format(when)} ${time}`;
}

const isoOf = (d) => d.toISOString().slice(0, 10);

/**
 * The [from, to] window for a range, slid `pan` whole windows into the past.
 *
 * Paging by a whole window rather than a fixed number of days keeps each step the same
 * size as what is on screen, so "back" always means "the previous 1A", never a partial
 * overlap that makes two adjacent views hard to compare.
 */
function rangeWindow(range, pan = 0) {
  const days = rangeDays(range);
  if (days === null) return { from: INCEPTION, to: undefined };

  const to = new Date();
  to.setDate(to.getDate() - days * pan);
  const from = new Date(to);
  from.setDate(from.getDate() - days);

  const fromIso = isoOf(from);
  return {
    from: fromIso < INCEPTION ? INCEPTION : fromIso,
    to: pan > 0 ? isoOf(to) : undefined, // live window stays open-ended at today
  };
}

/** True once the window would sit entirely before the first trade. */
function panExhausted(range, pan) {
  const days = rangeDays(range);
  if (days === null) return true;
  const to = new Date();
  to.setDate(to.getDate() - days * pan);
  return isoOf(to) <= INCEPTION;
}

/**
 * One reorderable panel.
 *
 * Native drag-and-drop rather than a library: four items need a handle, a drop
 * indicator and an ordered array, and that is all HTML5 DnD is. The handle carries
 * arrow-key support too, so the layout is reachable without a mouse.
 */
function Widget({
  id,
  label,
  children,
  dragging,
  hint,
  onDragStart,
  onDragEnd,
  onHover,
  onDrop,
  onNudge,
}) {
  return (
    <div
      className={`widget ${dragging ? "dragging" : ""} ${hint ? `drop-${hint}` : ""}`}
      onDragOver={(e) => {
        e.preventDefault(); // without this the drop never fires
        const box = e.currentTarget.getBoundingClientRect();
        onHover(e.clientY < box.top + box.height / 2 ? "before" : "after");
      }}
      onDragLeave={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget)) onHover(null);
      }}
      onDrop={(e) => {
        e.preventDefault();
        const box = e.currentTarget.getBoundingClientRect();
        onDrop(e.clientY < box.top + box.height / 2 ? "before" : "after");
      }}
    >
      <button
        type="button"
        className="widget-handle"
        draggable
        onDragStart={onDragStart}
        onDragEnd={onDragEnd}
        onKeyDown={(e) => {
          if (e.key === "ArrowUp") { e.preventDefault(); onNudge(-1); }
          if (e.key === "ArrowDown") { e.preventDefault(); onNudge(1); }
        }}
        title={`${label} — sürükleyerek taşıyın, ok tuşlarıyla da olur`}
        aria-label={`${label} bölümünü taşı`}
      >
        ⠿
      </button>
      {children}
    </div>
  );
}

export default function App() {
  const [portfolio, setPortfolio] = useState(null);
  const [history, setHistory] = useState(null);
  const [intraday, setIntraday] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [instruments, setInstruments] = useState([]);

  const [range, setRange] = useState("ALL");
  //: Empty means the whole portfolio. Clicking a ticker in the positions table filters
  //: the chart to it; clicking the same one again clears the filter.
  const [focusTickers, setFocusTickers] = useState([]);
  const [interval, setIntervalSeconds] = useState(DEFAULT_INTERVAL);
  const [theme, setTheme] = useState(
    () => document.documentElement.dataset.theme || "dark",
  );
  const [activeSection, setActiveSection] = useState("ozet");
  const [order, setOrder] = useState(loadOrder);
  const [dragId, setDragId] = useState(null);
  const [dropHint, setDropHint] = useState(null);
  //: True once the hero has scrolled out from under the topbar.
  const [condensed, setCondensed] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  //: Any fetch in flight, including a silent background poll — drives the sweep bar so
  //: "is this actually still updating?" is answerable at a glance.
  const [fetching, setFetching] = useState(false);
  const [error, setError] = useState(null);

  // Avoids a stale-closure re-subscribe loop in the polling effect.
  const loadRef = useRef(null);

  // The selected range is read by the loaders but must not be one of their dependencies:
  // if it were, changing the range would rebuild every callback, which would retrigger
  // the mount effect and fire a second full reload on top of the one changeRange already
  // performs. Holding it in a ref keeps the callbacks stable.
  const rangeRef = useRef(range);
  rangeRef.current = range;

  // Same reasoning as `rangeRef`: the chart filter is read by the loaders, not depended on.
  const focusRef = useRef(focusTickers);
  focusRef.current = focusTickers;

  //: How many whole windows back the chart is showing. 0 is live.
  const [pan, setPan] = useState(0);
  const panRef = useRef(pan);
  panRef.current = pan;
  //: Which way the last pan went, so the chart can slide in from the right side.
  const [panDir, setPanDir] = useState(0);

  const anyMarketOpen = useMemo(
    () => (portfolio?.positions ?? []).some((p) => p.session === "open"),
    [portfolio],
  );

  // Supplied by the server only when everything is shut.
  const nextMarketOpen = portfolio?.next_market_open ?? null;

  // Declared here, above the loading early-return, because hooks cannot be conditional.
  const flashMiniNet = useFlash(portfolio?.liquidation?.net_proceeds_try);
  const flashMiniReturn = useFlash(portfolio?.totals?.pnl_try);

  const loadHistory = useCallback(
    async (nextRange, { force = false, tickers, pan } = {}) => {
      const target = nextRange ?? rangeRef.current;
      const focus = tickers ?? focusRef.current;
      const at = pan ?? panRef.current;
      if (isIntradayRange(target)) {
        setIntraday(
          await api.intraday({ interval: "5m", force, tickers: focus, offset: at }),
        );
        return;
      }
      const { from, to } = rangeWindow(target, at);
      setHistory(await api.history({ from, to, freq: "D", tickers: focus }));
    },
    [],
  );

  // What the poll fetches. The chart is part of every refresh, not just range changes:
  // on the 1G view the whole point is that it moves, and on the longer ranges today's
  // point shifts with the price.
  const loadMarket = useCallback(
    async ({ force = false } = {}) => {
      const [p] = await Promise.all([api.portfolio(), loadHistory(undefined, { force })]);
      setPortfolio(p);
    },
    [loadHistory],
  );

  // Transactions and instruments only change when the user changes them, so they are
  // fetched on mount and after a mutation rather than on every tick of the poll.
  const loadLedger = useCallback(async () => {
    const [t, i] = await Promise.all([api.transactions(), api.instruments()]);
    setTransactions(t);
    setInstruments(i);
  }, []);

  const run = useCallback(async (work) => {
    setFetching(true);
    try {
      await work();
      setLastUpdated(new Date());
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
      setFetching(false);
    }
  }, []);

  const loadAll = useCallback(
    ({ force = false } = {}) => run(() => Promise.all([loadMarket({ force }), loadLedger()])),
    [run, loadMarket, loadLedger],
  );

  // The poll wants prices, not the ledger.
  loadRef.current = () => run(() => loadMarket());

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  // Poll fast while something is trading, slowly when nothing is.
  //
  // Not "not at all" when everything is shut, which is what this used to do: FX trades
  // around the clock on weekdays and this portfolio is valued in lira, so the TRY
  // figure genuinely moves overnight even though no share price does. Sleeping through
  // that meant the headline number was stale every morning. The slow cadence is the
  // `closed_market_interval_seconds` the server already publishes for exactly this.
  // Setting yenileme to "kapalı" still stops it dead.
  const closedInterval = CLOSED_POLL_SECONDS;
  useEffect(() => {
    if (interval === 0) return undefined;

    const every = (anyMarketOpen ? interval : Math.max(interval, closedInterval)) * 1000;
    const id = window.setInterval(() => {
      loadRef.current?.();
    }, every);
    return () => window.clearInterval(id);
  }, [interval, anyMarketOpen, closedInterval]);

  function toggleTheme() {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem("fadir.theme", next);
    } catch {
      /* private mode — the choice just does not persist */
    }
  }

  const goTo = (id) =>
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });

  // -- widget layout --------------------------------------------------------------

  const persistOrder = useCallback((next) => {
    setOrder(next);
    try {
      localStorage.setItem(LAYOUT_KEY, JSON.stringify(next));
    } catch {
      /* private mode — the layout just does not survive a reload */
    }
  }, []);

  /** Move `id` to sit before or after `targetId`. */
  const moveWidget = useCallback(
    (id, targetId, after) => {
      if (id === targetId) return;
      const next = order.filter((w) => w !== id);
      const at = next.indexOf(targetId);
      if (at < 0) return;
      next.splice(after ? at + 1 : at, 0, id);
      persistOrder(next);
    },
    [order, persistOrder],
  );

  /** Keyboard equivalent of the drag, so the layout is not mouse-only. */
  const nudgeWidget = useCallback(
    (id, delta) => {
      const from = order.indexOf(id);
      const to = from + delta;
      if (from < 0 || to < 0 || to >= order.length) return;
      const next = [...order];
      next.splice(to, 0, next.splice(from, 1)[0]);
      persistOrder(next);
    },
    [order, persistOrder],
  );

  const resetLayout = () => persistOrder(DEFAULT_ORDER);

  // -- condensed summary ----------------------------------------------------------

  // Watches a zero-height sentinel under the hero rather than the hero itself, so the
  // observer fires once at a single boundary instead of continuously as a tall element
  // crosses the viewport.
  const sentinelRef = useRef(null);
  useEffect(() => {
    const node = sentinelRef.current;
    if (!node) return undefined;
    const observer = new IntersectionObserver(
      ([entry]) => setCondensed(!entry.isIntersecting),
      { rootMargin: "-72px 0px 0px 0px", threshold: 0 },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [portfolio]);

  // Marks the rail entry for whatever is under the topbar. An observer costs nothing
  // per scroll frame, unlike measuring five elements on every scroll event.
  const navOrder = useMemo(() => ["ozet", ...order], [order]);

  useEffect(() => {
    if (!portfolio) return undefined;
    const nodes = navOrder.map((id) => document.getElementById(id)).filter(Boolean);
    if (!nodes.length) return undefined;

    const seen = new Map();
    const observer = new IntersectionObserver(
      (entries) => {
        for (const e of entries) seen.set(e.target.id, e.isIntersecting);
        // Topmost section overlapping the band wins, so scrolling down does not
        // light up a section still below the fold.
        const best = navOrder.find((id) => seen.get(id));
        if (best) setActiveSection(best);
      },
      // A reading band just under the topbar. `isIntersecting` at threshold 0 is the
      // test, deliberately not a ratio: intersectionRatio is a fraction of the
      // *target*, so a panel taller than the band — the positions table, the chart —
      // can never reach a meaningful ratio inside it and would never activate.
      { rootMargin: "-88px 0px -70% 0px", threshold: 0 },
    );
    nodes.forEach((n) => observer.observe(n));
    return () => observer.disconnect();
  }, [portfolio, navOrder]);

  async function manualRefresh() {
    setRefreshing(true);
    setError(null);
    try {
      await api.refresh(); // forces cache bypass and refetch
      await loadAll({ force: true }); // force also bypasses the intraday TTL
    } catch (err) {
      setError(err.message);
    } finally {
      setRefreshing(false);
    }
  }

  async function changeRange(next) {
    setRange(next);
    // A window offset measured in "1A"s means nothing once the range is "1H", so
    // changing range always returns to live.
    setPan(0);
    panRef.current = 0;
    setPanDir(0);
    try {
      await loadHistory(next, { pan: 0 });
    } catch (err) {
      setError(err.message);
    }
  }

  /** Slide the chart window `delta` steps: −1 further back in time, +1 towards now. */
  async function panBy(delta) {
    const next = Math.max(0, pan + delta);
    if (next === pan) return;
    setPan(next);
    panRef.current = next;
    setPanDir(delta);
    try {
      await loadHistory(undefined, { pan: next });
    } catch (err) {
      setError(err.message);
    }
  }

  /** Clicking a ticker focuses the chart on it; clicking it again returns to the whole
   *  portfolio. Only the chart is filtered — the positions table and the totals always
   *  describe everything held, so the filter can never be mistaken for a smaller portfolio. */
  async function toggleFocus(ticker) {
    const next = focusTickers.includes(ticker)
      ? focusTickers.filter((t) => t !== ticker)
      : [ticker];
    setFocusTickers(next);
    focusRef.current = next;
    try {
      await loadHistory(undefined, { tickers: next });
    } catch (err) {
      setError(err.message);
    }
  }

  if (loading && !portfolio) {
    return (
      <div className="app">
        <div className="empty">
          <span className="spinner" /> Portföy yükleniyor…
        </div>
      </div>
    );
  }

  const failed = (portfolio?.positions ?? []).filter((p) => !p.ok);
  const carriedForward = (portfolio?.positions ?? []).filter((p) => p.fx_carried_forward);
  const openCount = (portfolio?.positions ?? []).filter((p) => p.session === "open").length;

  return (
    <div className="app">
      <nav className="rail" aria-label="Bölümler">
        <div className="rail-brand">
          <Brand />
          <span>
            <span className="wordmark">faðir</span>
            <span className="wordmark-tag">TRY bazlı getiri ayrıştırması</span>
          </span>
        </div>

        <div className="rail-nav">
          {navOrder.map((id) => {
            const s = id === "ozet" ? { id, label: "Özet" } : WIDGETS.find((w) => w.id === id);
            if (!s) return null;
            return (
              <button
                key={s.id}
                type="button"
                className="navlink"
                aria-current={activeSection === s.id}
                onClick={() => goTo(s.id)}
              >
                <span className="navlink-dot" />
                {s.label}
                {s.meta?.(portfolio) && (
                  <span className="navlink-meta">{s.meta(portfolio)}</span>
                )}
              </button>
            );
          })}
        </div>

        <div className="rail-foot">
          {order.join() === DEFAULT_ORDER.join() ? (
            <span className="rail-version">v1.0</span>
          ) : (
            <button type="button" className="btn small ghost" onClick={resetLayout}>
              düzeni sıfırla
            </button>
          )}
          <button
            type="button"
            className="iconbtn"
            onClick={toggleTheme}
            title={theme === "dark" ? "Açık temaya geç" : "Koyu temaya geç"}
            aria-label={theme === "dark" ? "Açık temaya geç" : "Koyu temaya geç"}
          >
            {theme === "dark" ? "☾" : "☀"}
          </button>
        </div>
      </nav>

      <div className="main">
        <header className="topbar">
          {/* Both states occupy the same fixed slot and crossfade, so the topbar never
              changes height and nothing below it reflows as you scroll. */}
          <div className="title-slot">
            <h1 className={condensed ? "is-out" : "is-in"}>Portföy</h1>
            <div className={condensed ? "is-in" : "is-out"} aria-hidden={!condensed}>
              <span className="mini-stat">
                <span className="mini-label">Net</span>
                <span className={`mini-value num ${flashMiniNet}`}>
                  {money(portfolio.liquidation.net_proceeds_try)}
                </span>
              </span>
              <span className="mini-sep" />
              <span className="mini-stat">
                <span className="mini-label">Toplam getiri</span>
                <span
                  className={`mini-value num ${toneOf(portfolio.totals.pnl_try)} ${flashMiniReturn}`}
                >
                  <span aria-hidden="true">{arrow(portfolio.totals.pnl_try)}</span>{" "}
                  {ratioPct(portfolio.totals.total_return)}
                </span>
              </span>
            </div>
          </div>

          <div className="topbar-status">
            {anyMarketOpen ? (
              <span className="badge open" title={`${openCount} borsa açık`}>
                <span className="badge-dot" />
                piyasa açık
              </span>
            ) : (
              <span
                className="badge closed"
                title={
                  nextMarketOpen
                    ? `Otomatik yenileme duraklatıldı. Sıradaki açılış: ${new Date(
                        nextMarketOpen,
                      ).toLocaleString("tr-TR")}`
                    : "Tüm piyasalar kapalı"
                }
              >
                <span className="badge-dot" />
                tüm piyasalar kapalı
              </span>
            )}

            {!anyMarketOpen && interval !== 0 && nextMarketOpen && (
              <span className="updated" title="Borsalar kapalı; kur hâlâ hareket ettiği için yavaş tempoda yenileniyor">
                sıradaki açılış{" "}
                <strong className="num">{nextOpenLabel(nextMarketOpen)}</strong>
              </span>
            )}

            <span className="updated">
              son güncelleme{" "}
              <strong className="num">{lastUpdated ? clockTime(lastUpdated) : "—"}</strong>
            </span>

            <label className="updated" htmlFor="interval">
              yenileme{" "}
              <select
                id="interval"
                className="small"
                value={interval}
                onChange={(e) => setIntervalSeconds(Number(e.target.value))}
              >
                {INTERVALS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </label>

            <button className="btn primary" onClick={manualRefresh} disabled={refreshing}>
              {refreshing ? (
                <>
                  <span className="spinner" /> yenileniyor
                </>
              ) : (
                "Yenile"
              )}
            </button>
          </div>
        </header>

        <div className={`refresh-bar ${fetching ? "on" : ""}`} aria-hidden="true" />

        <div className="content">
      {error && (
        <div className="banner err">
          <span aria-hidden="true">⚠</span>
          <div>
            <strong>Bağlantı hatası:</strong> {error}
          </div>
        </div>
      )}

      {failed.length > 0 && (
        <div className="banner warn">
          <span aria-hidden="true">⚠</span>
          <div>
            <strong>{failed.length} pozisyon fiyatlanamadı</strong> — bu satırlar toplamlara
            dahil edilmedi, panonun geri kalanı geçerlidir.
            <ul>
              {failed.map((p) => (
                <li key={p.ticker}>
                  {p.ticker}: {p.error ?? "veri yok"}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {carriedForward.length > 0 && (
        <div className="banner warn">
          <span aria-hidden="true">ℹ</span>
          <div>
            {carriedForward.length} pozisyonda kur, işlem/fiyat gününden önceki bir yayından
            taşındı ({carriedForward.map((p) => p.ticker).join(", ")}).
          </div>
        </div>
      )}

          <HeroCard portfolio={portfolio} />
          <div ref={sentinelRef} aria-hidden="true" />

          {order.map((id) => (
            <Widget
              key={id}
              id={id}
              label={WIDGETS.find((w) => w.id === id)?.label ?? id}
              dragging={dragId === id}
              hint={dropHint?.id === id ? dropHint.side : null}
              onDragStart={() => setDragId(id)}
              onDragEnd={() => {
                setDragId(null);
                setDropHint(null);
              }}
              onHover={(side) => setDropHint({ id, side })}
              onDrop={(side) => {
                if (dragId) moveWidget(dragId, id, side === "after");
                setDragId(null);
                setDropHint(null);
              }}
              onNudge={(delta) => nudgeWidget(id, delta)}
            >
              {id === "ayristirma" && <AttributionBar totals={portfolio.totals} />}
              {id === "grafik" && (
                <Suspense
                  fallback={
                    <section className="panel" id="grafik">
                      <div className="panel-body">
                        <div className="empty">
                          <span className="spinner" /> Grafik yükleniyor…
                        </div>
                      </div>
                    </section>
                  }
                >
                  <HistoryChart
                    history={history}
                    intraday={intraday}
                    loading={loading}
                    range={range}
                    onRangeChange={changeRange}
                    focusTickers={focusTickers}
                    onClearFocus={() => toggleFocus(focusTickers[0])}
                    pan={pan}
                    panDir={panDir}
                    onPan={panBy}
                    canPanBack={
                      isPannable(range) &&
                      (isIntradayRange(range)
                        ? pan + 1 < (intraday?.sessions_available ?? 0)
                        : !panExhausted(range, pan + 1))
                    }
                  />
                </Suspense>
              )}
              {id === "pozisyonlar" && (
                <PositionsTable
                  positions={portfolio.positions}
                  focusTickers={focusTickers}
                  onFocusTicker={toggleFocus}
                />
              )}
              {id === "islemler" && (
                <TransactionManager
                  transactions={transactions}
                  instruments={instruments}
                  onChanged={() => loadAll()}
                />
              )}
            </Widget>
          ))}
        </div>
      </div>
    </div>
  );
}
