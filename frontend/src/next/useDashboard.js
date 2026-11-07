// Everything the dashboard knows and can do, independent of how it is drawn.
//
// Ported from the classic App so both interfaces share one behaviour: the same loaders,
// the same poll cadence (fast while something trades, 15 min floor while only FX moves),
// the same per-portfolio race guards. Views read state and call actions; none of them
// talks to the API for portfolio data directly.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api.js";
import { isIntradayRange, isPannable, rangeDays } from "../ranges.js";

export const INTERVALS = [
  { value: 5, label: "interval.5s" },
  { value: 10, label: "interval.10s" },
  { value: 15, label: "interval.15s" },
  { value: 30, label: "interval.30s" },
  { value: 60, label: "interval.60s" },
  { value: 300, label: "interval.5m" },
  { value: 0, label: "interval.off" },
];
const DEFAULT_INTERVAL = 10;
const INTERVAL_KEY = "fadir.interval";
const INCEPTION = "2026-03-29";
const CLOSED_POLL_SECONDS = 900;

const isoOf = (d) => d.toISOString().slice(0, 10);

function rangeWindow(range, pan = 0) {
  const days = rangeDays(range);
  if (days === null) return { from: INCEPTION, to: undefined };
  const to = new Date();
  to.setDate(to.getDate() - days * pan);
  const from = new Date(to);
  from.setDate(from.getDate() - days);
  const fromIso = isoOf(from);
  return { from: fromIso < INCEPTION ? INCEPTION : fromIso, to: pan > 0 ? isoOf(to) : undefined };
}

function panExhausted(range, pan) {
  const days = rangeDays(range);
  if (days === null) return true;
  const to = new Date();
  to.setDate(to.getDate() - days * pan);
  return isoOf(to) <= INCEPTION;
}

function loadInterval() {
  try {
    const raw = localStorage.getItem(INTERVAL_KEY);
    if (raw === null) return DEFAULT_INTERVAL;
    const saved = Number(raw);
    return INTERVALS.some((i) => i.value === saved) ? saved : DEFAULT_INTERVAL;
  } catch {
    return DEFAULT_INTERVAL;
  }
}

/** `access` is the browser's authority: "user", "guest" or "code" (one Portfolio). */
export function useDashboard(access = "guest", { onAccessLost } = {}) {
  const [portfolios, setPortfolios] = useState([]);
  const [selectedPortfolioId, setSelectedPortfolioId] = useState(null);
  const [portfolio, setPortfolio] = useState(null);
  const [history, setHistory] = useState(null);
  const [intraday, setIntraday] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [instruments, setInstruments] = useState([]);
  const [range, setRange] = useState("ALL");
  const [focusTickers, setFocusTickers] = useState([]);
  const [interval, setIntervalState] = useState(loadInterval);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [fetching, setFetching] = useState(false);
  const [error, setError] = useState(null);
  const [guestAccess, setGuestAccess] = useState(null);
  const [identityReady, setIdentityReady] = useState(false);
  const [pan, setPan] = useState(0);
  const [panDir, setPanDir] = useState(0);

  const loadRef = useRef(null);
  const portfolioIdRef = useRef(null);
  const rangeRef = useRef(range);
  rangeRef.current = range;
  const focusRef = useRef(focusTickers);
  focusRef.current = focusTickers;
  const panRef = useRef(pan);
  panRef.current = pan;

  const anyMarketOpen = useMemo(
    () => (portfolio?.positions ?? []).some((p) => p.session === "open"),
    [portfolio],
  );
  const nextMarketOpen = portfolio?.next_market_open ?? null;

  const loadHistory = useCallback(async (nextRange, { force = false, tickers, pan, portfolioId } = {}) => {
    const selectedId = portfolioId ?? portfolioIdRef.current;
    const target = nextRange ?? rangeRef.current;
    const focus = tickers ?? focusRef.current;
    const at = pan ?? panRef.current;
    if (isIntradayRange(target)) {
      const value = await api.intraday({ interval: "5m", force, tickers: focus, offset: at, portfolioId: selectedId });
      if (portfolioIdRef.current === selectedId) setIntraday(value);
      return;
    }
    const { from, to } = rangeWindow(target, at);
    const value = await api.history({ from, to, freq: "D", tickers: focus, portfolioId: selectedId });
    if (portfolioIdRef.current === selectedId) setHistory(value);
  }, []);

  const loadMarket = useCallback(async ({ force = false, portfolioId } = {}) => {
    const selectedId = portfolioId ?? portfolioIdRef.current;
    const [p] = await Promise.all([
      api.portfolio(selectedId),
      loadHistory(undefined, { force, portfolioId: selectedId }),
    ]);
    if (portfolioIdRef.current === selectedId) setPortfolio(p);
  }, [loadHistory]);

  const loadLedger = useCallback(async (portfolioId) => {
    const selectedId = portfolioId ?? portfolioIdRef.current;
    const [t, i] = await Promise.all([api.transactions(selectedId), api.instruments()]);
    if (portfolioIdRef.current === selectedId) setTransactions(t);
    setInstruments(i);
  }, []);

  const loadPortfolios = useCallback(async () => {
    const value = await api.portfolios();
    const list = (Array.isArray(value) ? value : []).filter(
      (item) => item && Number.isFinite(Number(item.id)) && item.name && item.base_currency,
    );
    const current = portfolioIdRef.current;
    const selected = list.some((item) => Number(item.id) === current)
      ? current
      : list.length > 0 ? Number(list[0].id) : null;
    portfolioIdRef.current = selected;
    setPortfolios(list);
    setSelectedPortfolioId(selected);
    return selected;
  }, []);

  const run = useCallback(async (work) => {
    setFetching(true);
    try {
      await work();
      setLastUpdated(new Date());
      setError(null);
    } catch (err) {
      // A code whose Portfolio got a new code stops working; go back to the code screen.
      if (access === "code" && err?.status === 401) onAccessLost?.();
      setError(err.message);
    } finally {
      setLoading(false);
      setFetching(false);
    }
  }, [access, onAccessLost]);

  const loadAll = useCallback(
    ({ force = false } = {}) => run(async () => {
      const selectedId = await loadPortfolios();
      await Promise.all([loadMarket({ force, portfolioId: selectedId }), loadLedger(selectedId)]);
    }),
    [run, loadPortfolios, loadMarket, loadLedger],
  );

  const readGuestAccess = useCallback(async () => {
    const bootstrap = await api.bootstrapGuest();
    setGuestAccess({
      noticeDue: bootstrap?.guest?.notice_due === true,
      expiresAt: bootstrap?.guest?.expires_at ?? null,
    });
  }, []);

  const readUserAccess = useCallback(async () => {
    try {
      await api.userSessions();
      setIdentityReady(true);
    } catch (err) {
      if (err?.status !== 401) setIdentityReady(false);
    }
  }, []);

  const reloadAfterTransaction = useCallback(async () => {
    await loadAll();
    if (access === "code") return;
    try {
      await readGuestAccess();
    } catch {
      // A successful transaction must not fail because a best-effort notice refresh did.
    }
  }, [loadAll, readGuestAccess, access]);

  const refreshAfterIdentity = useCallback(async () => {
    setIdentityReady(true);
    await loadAll();
    try {
      await readGuestAccess();
    } catch {
      // Identity transitions succeed independently of the dashboard refresh.
    }
  }, [loadAll, readGuestAccess]);

  loadRef.current = () => run(() => loadMarket());

  useEffect(() => {
    run(async () => {
      // A code-opened Portfolio has no Guest Workspace or User of its own on this browser.
      if (access !== "code") {
        await readGuestAccess();
        await readUserAccess();
      }
      const selectedId = await loadPortfolios();
      await Promise.all([loadMarket({ portfolioId: selectedId }), loadLedger(selectedId)]);
    });
  }, [run, readGuestAccess, readUserAccess, loadPortfolios, loadMarket, loadLedger, access]);

  useEffect(() => {
    if (interval === 0) return undefined;
    const every = (anyMarketOpen ? interval : Math.max(interval, CLOSED_POLL_SECONDS)) * 1000;
    const id = window.setInterval(() => {
      // A hidden tab gains nothing from a poll; the next visible tick catches up.
      if (document.visibilityState === "visible") loadRef.current?.();
    }, every);
    return () => window.clearInterval(id);
  }, [interval, anyMarketOpen]);

  // Coming back to a tab that skipped polls refreshes at once rather than on the next tick.
  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === "visible" && interval !== 0) loadRef.current?.();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [interval]);

  const setIntervalSeconds = useCallback((value) => {
    setIntervalState(value);
    try {
      localStorage.setItem(INTERVAL_KEY, String(value));
    } catch {
      /* private mode */
    }
  }, []);

  const manualRefresh = useCallback(async () => {
    setRefreshing(true);
    setError(null);
    try {
      await api.refresh();
      await loadAll({ force: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setRefreshing(false);
    }
  }, [loadAll]);

  const selectPortfolio = useCallback(async (id) => {
    if (id === portfolioIdRef.current) return;
    portfolioIdRef.current = id;
    setSelectedPortfolioId(id);
    setPortfolio(null);
    setHistory(null);
    setIntraday(null);
    setTransactions([]);
    setLoading(true);
    await run(() => Promise.all([loadMarket({ portfolioId: id }), loadLedger(id)]));
  }, [run, loadMarket, loadLedger]);

  const changeRange = useCallback(async (next) => {
    setRange(next);
    rangeRef.current = next;
    setPan(0);
    panRef.current = 0;
    setPanDir(0);
    try {
      await loadHistory(next, { pan: 0 });
    } catch (err) {
      setError(err.message);
    }
  }, [loadHistory]);

  const panBy = useCallback(async (delta) => {
    const next = Math.max(0, panRef.current + delta);
    if (next === panRef.current) return;
    setPan(next);
    panRef.current = next;
    setPanDir(delta);
    try {
      await loadHistory(undefined, { pan: next });
    } catch (err) {
      setError(err.message);
    }
  }, [loadHistory]);

  /** Focus the chart on one ticker; the same ticker again returns to the whole portfolio. */
  const toggleFocus = useCallback(async (ticker) => {
    const current = focusRef.current;
    const next = ticker == null || current.includes(ticker) ? [] : [ticker];
    setFocusTickers(next);
    focusRef.current = next;
    try {
      await loadHistory(undefined, { tickers: next });
    } catch (err) {
      setError(err.message);
    }
  }, [loadHistory]);

  const clearAfterAccountDeletion = useCallback(() => {
    setIdentityReady(false);
    setGuestAccess(null);
    setPortfolio(null);
    setPortfolios([]);
    setSelectedPortfolioId(null);
    portfolioIdRef.current = null;
  }, []);

  const canPanBack =
    isPannable(range) &&
    (isIntradayRange(range)
      ? pan + 1 < (intraday?.sessions_available ?? 0)
      : !panExhausted(range, pan + 1));

  const renewCode = useCallback(async (id) => {
    const { code } = await api.renewCode(id);
    setPortfolios((list) => list.map((p) => (Number(p.id) === Number(id) ? { ...p, code } : p)));
    return code;
  }, []);

  return {
    access, renewCode,
    portfolios, selectedPortfolioId, portfolio, history, intraday, transactions, instruments,
    range, focusTickers, interval, lastUpdated, loading, refreshing, fetching, error,
    guestAccess, identityReady, pan, panDir, anyMarketOpen, nextMarketOpen, canPanBack,
    selectPortfolio, changeRange, panBy, toggleFocus, setIntervalSeconds, manualRefresh,
    reloadAfterTransaction, refreshAfterIdentity, loadAll, clearAfterAccountDeletion,
    setError,
  };
}
