// The rebuilt interface. Four views behind hash routes (#/genel, #/pozisyonlar,
// #/islemler, #/hesap) so links and the back button work; one data hook shared by all.

import { startTransition, useCallback, useEffect, useMemo, useState } from "react";
import { flushSync } from "react-dom";
import { MotionConfig, motion } from "framer-motion";
import "@fontsource-variable/geologica";
import { api } from "../api.js";
import { switchUi } from "../ui.js";
import { RANGES } from "../ranges.js";
import { INTERVALS, useDashboard } from "./useDashboard.js";
import CodeGate from "./components/CodeGate.jsx";
import CommandPalette from "./components/CommandPalette.jsx";
import NewPortfolio from "./components/NewPortfolio.jsx";
import Notices from "./components/Notices.jsx";
import TopBar, { NavTabs, VIEWS } from "./components/TopBar.jsx";
import Icon from "./ui/Icons.jsx";
import { OverlayProvider, useToast } from "./ui/overlays.jsx";
import { prefersReducedMotion, viewTransition } from "./ui/motion.js";
import Account from "./views/Account.jsx";
import TaxView from "./views/TaxView.jsx";
import { I18nProvider, useI18n, useT } from "./i18n/index.jsx";
import Overview from "./views/Overview.jsx";
import Positions from "./views/Positions.jsx";
import Transactions from "./views/Transactions.jsx";

const viewFromHash = () => {
  const id = window.location.hash.replace(/^#\/?/, "");
  return VIEWS.some((v) => v.id === id) ? id : "genel";
};

function useHashView() {
  const [view, setView] = useState(viewFromHash);
  // Views mount inside a transition, so React time-slices the render of a whole view
  // instead of blocking one long frame; the outgoing view stays until the new one is ready.
  useEffect(() => {
    const onHash = () => startTransition(() => setView(viewFromHash()));
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  const go = useCallback((id) => {
    if (`#/${id}` !== window.location.hash) window.location.hash = `/${id}`;
    startTransition(() => setView(id));
  }, []);
  return [view, go];
}

function useTheme() {
  const [theme, setTheme] = useState(() => document.documentElement.dataset.theme || "dark");
  /**
   * The new theme is revealed as a circle growing from the toggle. Uses the View
   * Transitions API: the browser snapshots old and new pages and animates the snapshots
   * on the compositor, so nothing on the page restyles per frame. Browsers without it,
   * and reduced motion, switch instantly.
   */
  const toggle = useCallback((event) => {
    const root = document.documentElement;
    const next = root.dataset.theme === "dark" ? "light" : "dark";
    const apply = () => {
      root.dataset.theme = next;
      setTheme(next);
    };
    try { localStorage.setItem("fadir.theme", next); } catch { /* private mode */ }
    if (!document.startViewTransition || prefersReducedMotion()) { apply(); return; }
    const rect = event?.currentTarget?.getBoundingClientRect?.();
    const x = rect ? rect.left + rect.width / 2 : window.innerWidth - 60;
    const y = rect ? rect.top + rect.height / 2 : 32;
    root.style.setProperty("--vt-x", `${x}px`);
    root.style.setProperty("--vt-y", `${y}px`);
    root.style.setProperty("--vt-r", `${Math.hypot(Math.max(x, window.innerWidth - x), Math.max(y, window.innerHeight - y))}px`);
    document.startViewTransition(() => flushSync(apply));
  }, []);
  return [theme, toggle];
}

function Skeleton() {
  const t = useT();
  return (
    <div className="stack" aria-busy="true" aria-label={t("common.loading")}>
      <div className="skeleton hero-skel" />
      <div className="skeleton-row">
        {Array.from({ length: 4 }, (_, i) => <div key={i} className="skeleton tile-skel" style={{ animationDelay: `${i * 0.08}s` }} />)}
      </div>
      <div className="skeleton chart-skel" />
    </div>
  );
}

function Shell({ access, onLeave, onSignOut, onAccessLost }) {
  const dash = useDashboard(access, { onAccessLost });
  const [view, go] = useHashView();
  const [theme, toggleTheme] = useTheme();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [newPortfolioOpen, setNewPortfolioOpen] = useState(false);
  // A code opens exactly one Portfolio; only the Workspace owner adds more.
  const openNewPortfolio = access === "code" ? null : () => setNewPortfolioOpen(true);
  const [heroOut, setHeroOut] = useState(false);
  const toast = useToast();
  const t = useT();
  const { portfolio, loading, error } = dash;

  // Mini summary in the topbar once the hero has scrolled away, or on any other view.
  useEffect(() => {
    if (view !== "genel" || !portfolio) { setHeroOut(true); return undefined; }
    const node = document.getElementById("ozet");
    if (!node) return undefined;
    const io = new IntersectionObserver(([e]) => setHeroOut(!e.isIntersecting), { rootMargin: "-64px 0px 0px 0px" });
    io.observe(node);
    return () => io.disconnect();
  }, [view, portfolio]);

  useEffect(() => { window.scrollTo({ top: 0, behavior: "instant" }); }, [view]);

  // `dash` is a new object every render; depend on its stable members instead.
  const { focusTickers, toggleFocus, manualRefresh, refreshing, changeRange, portfolios, selectPortfolio, setIntervalSeconds } = dash;

  const focusTicker = useCallback((ticker) => {
    const turningOn = !focusTickers.includes(ticker);
    toggleFocus(ticker);
    if (turningOn) {
      toast({ text: t("chart.focusToast", { ticker }) });
      if (view !== "genel") go("genel");
      window.setTimeout(() => document.getElementById("grafik")?.scrollIntoView({ behavior: "smooth", block: "center" }), 380);
    }
  }, [focusTickers, toggleFocus, toast, view, go, t]);

  const newTransaction = useCallback(() => {
    go("islemler");
    window.setTimeout(() => setSheetOpen(true), 120);
  }, [go]);

  useEffect(() => {
    const onKey = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((v) => !v);
        return;
      }
      const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName) || e.target.isContentEditable;
      if (typing || e.ctrlKey || e.metaKey || e.altKey || paletteOpen) return;
      const index = ["1", "2", "3", "4", "5"].indexOf(e.key);
      if (index >= 0) go(VIEWS[index].id);
      else if (e.key === "/") { e.preventDefault(); setPaletteOpen(true); }
      else if (e.key.toLowerCase() === "r" && !refreshing) manualRefresh();
      else if (e.key.toLowerCase() === "n") newTransaction();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [go, refreshing, manualRefresh, paletteOpen, newTransaction]);

  const commands = useMemo(() => [
    ...VIEWS.map((v, i) => ({ id: `view-${v.id}`, group: t("palette.go"), label: t(v.label), icon: v.icon, hint: String(i + 1), run: () => go(v.id) })),
    { id: "new-txn", group: t("palette.actions"), label: t("txn.new"), icon: "plus", hint: "N", run: newTransaction },
    { id: "refresh", group: t("palette.actions"), label: t("common.refresh"), icon: "refresh", hint: "R", run: manualRefresh },
    { id: "theme", group: t("palette.actions"), label: t(theme === "dark" ? "theme.light" : "theme.dark"), icon: theme === "dark" ? "sun" : "moon", run: toggleTheme },
    ...RANGES.map((r) => ({ id: `range-${r.key}`, group: t("palette.range"), label: t(`range.${r.key}`), icon: "clock", keywords: "range", run: () => { go("genel"); changeRange(r.key); } })),
    ...(portfolio?.positions ?? []).map((p) => ({
      id: `focus-${p.ticker}`, group: t("palette.focus"), label: p.ticker, hint: p.name, icon: "focus", run: () => focusTicker(p.ticker),
    })),
    ...(focusTickers.length ? [{ id: "focus-clear", group: t("palette.focus"), label: t("chart.wholePortfolio"), icon: "x", run: () => toggleFocus(null) }] : []),
    ...portfolios.map((p) => ({
      id: `pf-${p.id}`, group: t("portfolio.label"), label: p.name, hint: p.base_currency, icon: "layers", run: () => selectPortfolio(Number(p.id)),
    })),
    ...INTERVALS.map((o) => ({ id: `int-${o.value}`, group: t("live.interval"), label: t(o.label), icon: "clock", keywords: "interval", run: () => setIntervalSeconds(o.value) })),
    { id: "classic", group: t("ui.title"), label: t("ui.classic"), icon: "swap", run: () => switchUi("classic") },
    ...(access === "code"
      ? [{ id: "leave", group: t("portfolio.label"), label: t("code.leave"), icon: "x", run: onLeave }]
      : [{ id: "new-portfolio", group: t("portfolio.label"), label: t("portfolio.new"), icon: "plus", run: () => setNewPortfolioOpen(true) }]),
  ], [go, newTransaction, manualRefresh, changeRange, focusTickers, toggleFocus, portfolios, selectPortfolio, setIntervalSeconds, theme, toggleTheme, portfolio, focusTicker, access, onLeave, t]);

  const needsPortfolio = view === "genel" || view === "pozisyonlar";

  let body;
  if (needsPortfolio && !portfolio) {
    body = loading || !error ? (
      <Skeleton />
    ) : (
      <div className="empty-state">
        <p>{t("portfolio.loadFailed")}</p>
        <button type="button" className="btn primary" onClick={() => dash.loadAll()}><Icon name="refresh" size={16} /> {t("common.retry")}</button>
      </div>
    );
  } else if (view === "genel") body = <Overview dash={dash} />;
  else if (view === "pozisyonlar") body = <Positions dash={dash} onFocusTicker={focusTicker} />;
  else if (view === "islemler") body = <Transactions dash={dash} sheetOpen={sheetOpen} setSheetOpen={setSheetOpen} />;
  else if (view === "vergi") body = <TaxView dash={dash} onSignIn={access === "code" ? null : () => go("hesap")} />;
  else body = <Account dash={dash} access={access} onLeave={onLeave} onSignOut={onSignOut} />;

  return (
    <div className="app">
      <TopBar
        dash={dash}
        view={view}
        onView={go}
        condensed={heroOut}
        theme={theme}
        onTheme={toggleTheme}
        onPalette={() => setPaletteOpen(true)}
        onNewPortfolio={openNewPortfolio}
      />
      <main className="content">
        {!loading && !error && dash.portfolios.length === 0 && (
          <div className="notice notice-info first-run">
            <Icon name="sparkle" size={16} />
            <div className="notice-body">{t("portfolio.firstRun")}</div>
            <button type="button" className="btn primary small" onClick={newTransaction}>{t("txn.new")}</button>
          </div>
        )}
        <Notices dash={dash} />
        {/* Entrance-only keyed swap: the outgoing view unmounts at once, so navigation
            never waits on (or gets stuck behind) an exit animation. */}
        <motion.div key={view} initial={viewTransition.initial} animate={viewTransition.animate}>
          {body}
        </motion.div>
      </main>
      <NavTabs view={view} onChange={go} className="bottom-nav mobile-only" layoutId="bottom-pill" />
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} commands={commands} />
      {openNewPortfolio && <NewPortfolio open={newPortfolioOpen} onClose={() => setNewPortfolioOpen(false)} dash={dash} />}
    </div>
  );
}

const GOOGLE_INTENT_KEY = "fadir.google-intent";

/** Ask what this browser can open; a browser with nothing gets the code screen first. */
function useAccess() {
  const [access, setAccess] = useState(null);
  const [codeLengths, setCodeLengths] = useState([4]);
  const read = useCallback(async () => {
    try {
      const value = await api.access();
      setCodeLengths(Array.isArray(value?.code_lengths) ? value.code_lengths : [4]);
      setAccess(value?.mode ?? "none");
    } catch {
      // The dashboard has its own error and retry surface.
      setAccess("guest");
    }
  }, []);
  useEffect(() => { read(); }, [read]);
  return { access, setAccess, codeLengths, read };
}

function Root() {
  const { access, setAccess, codeLengths, read } = useAccess();

  const openGoogle = useCallback(async () => {
    await api.bootstrapGuest();
    try { sessionStorage.setItem(GOOGLE_INTENT_KEY, "1"); } catch { /* private mode */ }
    window.location.hash = "/hesap";
    setAccess("guest");
  }, [setAccess]);

  const createPortfolio = useCallback(async () => {
    await api.bootstrapGuest();
    await api.startPortfolio();
    window.location.hash = "/genel";
    setAccess("guest");
  }, [setAccess]);

  const leave = useCallback(async () => {
    try { await api.leaveCode(); } finally {
      window.location.hash = "/genel";
      setAccess(null);
      read();
    }
  }, [read, setAccess]);

  const signOut = useCallback(async () => {
    await api.signOut();
    window.location.hash = "/genel";
    setAccess(null);
    read();
  }, [read, setAccess]);

  if (access === null) return <div className="app" />;
  if (access === "none") {
    return (
      <CodeGate
        codeLengths={codeLengths}
        onOpened={() => { window.location.hash = "/genel"; setAccess("code"); }}
        onGoogle={openGoogle}
        onCreate={createPortfolio}
      />
    );
  }
  // Guest → User happens inside the Shell (sign-in), so it keeps its state; a code is its own Shell.
  return <Shell key={access === "code" ? "code" : "owner"} access={access} onLeave={leave} onSignOut={signOut} onAccessLost={read} />;
}

/** A language change re-renders every number and date in the new locale. */
function LocalizedRoot() {
  const { lang } = useI18n();
  const t = useT();
  useEffect(() => { document.title = t("app.title"); }, [t]);
  return <Root key={lang} />;
}

export default function App() {
  return (
    <MotionConfig reducedMotion="user">
      <I18nProvider>
        <OverlayProvider>
          <LocalizedRoot />
        </OverlayProvider>
      </I18nProvider>
    </MotionConfig>
  );
}
