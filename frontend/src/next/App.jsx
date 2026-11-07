// The rebuilt interface. Four views behind hash routes (#/genel, #/pozisyonlar,
// #/islemler, #/hesap) so links and the back button work; one data hook shared by all.

import { useCallback, useEffect, useMemo, useState } from "react";
import { MotionConfig, motion } from "framer-motion";
import "@fontsource-variable/inter";
import "@fontsource-variable/space-grotesk";
import { switchUi } from "../ui.js";
import { RANGES } from "../ranges.js";
import { INTERVALS, useDashboard } from "./useDashboard.js";
import Aurora from "./components/Aurora.jsx";
import CommandPalette from "./components/CommandPalette.jsx";
import Notices from "./components/Notices.jsx";
import TopBar, { NavTabs, VIEWS } from "./components/TopBar.jsx";
import Icon from "./ui/Icons.jsx";
import { OverlayProvider, useToast } from "./ui/overlays.jsx";
import { viewTransition } from "./ui/motion.js";
import Account from "./views/Account.jsx";
import Overview from "./views/Overview.jsx";
import Positions from "./views/Positions.jsx";
import Transactions from "./views/Transactions.jsx";

const viewFromHash = () => {
  const id = window.location.hash.replace(/^#\/?/, "");
  return VIEWS.some((v) => v.id === id) ? id : "genel";
};

function useHashView() {
  const [view, setView] = useState(viewFromHash);
  useEffect(() => {
    const onHash = () => setView(viewFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  const go = useCallback((id) => {
    if (`#/${id}` !== window.location.hash) window.location.hash = `/${id}`;
    setView(id);
  }, []);
  return [view, go];
}

function useTheme() {
  const [theme, setTheme] = useState(() => document.documentElement.dataset.theme || "dark");
  const toggle = useCallback(() => {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    // A short global crossfade class so every colour changes together, then removed so
    // ordinary hover transitions are not slowed down.
    document.documentElement.classList.add("theme-swap");
    document.documentElement.dataset.theme = next;
    window.setTimeout(() => document.documentElement.classList.remove("theme-swap"), 450);
    setTheme(next);
    try { localStorage.setItem("fadir.theme", next); } catch { /* private mode */ }
  }, []);
  return [theme, toggle];
}

function Skeleton() {
  return (
    <div className="stack" aria-busy="true" aria-label="Portföy yükleniyor">
      <div className="skeleton hero-skel" />
      <div className="skeleton-row">
        {Array.from({ length: 4 }, (_, i) => <div key={i} className="skeleton tile-skel" style={{ animationDelay: `${i * 0.08}s` }} />)}
      </div>
      <div className="skeleton chart-skel" />
    </div>
  );
}

function Shell() {
  const dash = useDashboard();
  const [view, go] = useHashView();
  const [theme, toggleTheme] = useTheme();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [heroOut, setHeroOut] = useState(false);
  const toast = useToast();
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

  const focusTicker = useCallback((ticker) => {
    const turningOn = !dash.focusTickers.includes(ticker);
    dash.toggleFocus(ticker);
    if (turningOn) {
      toast({ text: `Grafik: ${ticker}` });
      if (view !== "genel") go("genel");
      window.setTimeout(() => document.getElementById("grafik")?.scrollIntoView({ behavior: "smooth", block: "center" }), 380);
    }
  }, [dash, toast, view, go]);

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
      const index = ["1", "2", "3", "4"].indexOf(e.key);
      if (index >= 0) go(VIEWS[index].id);
      else if (e.key === "/") { e.preventDefault(); setPaletteOpen(true); }
      else if (e.key.toLowerCase() === "r" && !dash.refreshing) dash.manualRefresh();
      else if (e.key.toLowerCase() === "n") newTransaction();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [go, dash, paletteOpen, newTransaction]);

  const commands = useMemo(() => {
    const list = [
      ...VIEWS.map((v, i) => ({ id: `view-${v.id}`, group: "Git", label: v.label, icon: v.icon, hint: String(i + 1), run: () => go(v.id) })),
      { id: "new-txn", group: "İşlem", label: "Yeni işlem", icon: "plus", hint: "N", run: newTransaction },
      { id: "refresh", group: "İşlem", label: "Yenile", icon: "refresh", hint: "R", run: () => dash.manualRefresh() },
      { id: "theme", group: "İşlem", label: theme === "dark" ? "Açık tema" : "Koyu tema", icon: theme === "dark" ? "sun" : "moon", run: toggleTheme },
      ...RANGES.map((r) => ({ id: `range-${r.key}`, group: "Grafik aralığı", label: r.label, icon: "clock", keywords: "aralık range", run: () => { go("genel"); dash.changeRange(r.key); } })),
      ...(portfolio?.positions ?? []).map((p) => ({
        id: `focus-${p.ticker}`, group: "Grafikte göster", label: p.ticker, hint: p.name, icon: "focus", run: () => focusTicker(p.ticker),
      })),
      ...(dash.focusTickers.length ? [{ id: "focus-clear", group: "Grafikte göster", label: "Tüm portföy", icon: "x", run: () => dash.toggleFocus(null) }] : []),
      ...dash.portfolios.map((p) => ({
        id: `pf-${p.id}`, group: "Portföy", label: p.name, hint: p.base_currency, icon: "layers", run: () => dash.selectPortfolio(Number(p.id)),
      })),
      ...INTERVALS.map((o) => ({ id: `int-${o.value}`, group: "Yenileme", label: o.label, icon: "clock", keywords: "yenileme interval", run: () => dash.setIntervalSeconds(o.value) })),
      { id: "classic", group: "Arayüz", label: "Klasik arayüze geç", icon: "swap", run: () => switchUi("classic") },
    ];
    return list;
  }, [go, newTransaction, dash, theme, toggleTheme, portfolio, focusTicker]);

  const needsPortfolio = view === "genel" || view === "pozisyonlar";

  let body;
  if (needsPortfolio && !portfolio) {
    body = loading || !error ? (
      <Skeleton />
    ) : (
      <div className="empty-state">
        <div className="empty-orb" />
        <p>Portföy yüklenemedi.</p>
        <button type="button" className="btn primary" onClick={() => dash.loadAll()}><Icon name="refresh" size={16} /> Tekrar dene</button>
      </div>
    );
  } else if (view === "genel") body = <Overview dash={dash} />;
  else if (view === "pozisyonlar") body = <Positions dash={dash} onFocusTicker={focusTicker} />;
  else if (view === "islemler") body = <Transactions dash={dash} sheetOpen={sheetOpen} setSheetOpen={setSheetOpen} />;
  else body = <Account dash={dash} />;

  return (
    <div className="app">
      <Aurora />
      <TopBar
        dash={dash}
        view={view}
        onView={go}
        condensed={heroOut}
        theme={theme}
        onTheme={toggleTheme}
        onPalette={() => setPaletteOpen(true)}
      />
      <main className="content">
        {!loading && !error && dash.portfolios.length === 0 && (
          <div className="notice notice-info first-run">
            <Icon name="sparkle" size={16} />
            <div className="notice-body">İlk geçerli işlem kaydedildiğinde Ana Portföy oluşturulur.</div>
            <button type="button" className="btn primary small" onClick={newTransaction}>Yeni işlem</button>
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
    </div>
  );
}

export default function App() {
  return (
    <MotionConfig reducedMotion="user">
      <OverlayProvider>
        <Shell />
      </OverlayProvider>
    </MotionConfig>
  );
}
