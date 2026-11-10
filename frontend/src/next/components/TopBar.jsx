import { AnimatePresence, motion } from "framer-motion";
import { arrow, clockTime, daysFromToday, hourMinute, money, ratioPct, toneOf, weekdayShort } from "../../format.js";
import { INTERVALS } from "../useDashboard.js";
import AnimatedNumber from "../ui/AnimatedNumber.jsx";
import Icon from "../ui/Icons.jsx";
import Popover from "../ui/Popover.jsx";
import { copyCode } from "../ui/copy.js";
import { useToast } from "../ui/overlays.jsx";
import { spring } from "../ui/motion.js";
import Brand from "./Brand.jsx";
import { useT } from "../i18n/index.jsx";

export const VIEWS = [
  { id: "genel", label: "nav.overview", icon: "home" },
  { id: "pozisyonlar", label: "nav.positions", icon: "layers" },
  { id: "islemler", label: "nav.transactions", icon: "receipt" },
  { id: "vergi", label: "nav.tax", icon: "percent" },
  { id: "hesap", label: "nav.account", icon: "user" },
];

function nextOpenLabel(iso, t) {
  const when = new Date(iso);
  const time = hourMinute(when);
  const days = daysFromToday(when);
  if (days <= 0) return time;
  if (days === 1) return t("live.tomorrow", { time });
  return `${weekdayShort(when)} ${time}`;
}

export function NavTabs({ view, onChange, className = "", layoutId = "nav-pill" }) {
  const t = useT();
  return (
    <nav className={`nav-tabs ${className}`} aria-label={t("nav.sections")}>
      {VIEWS.map((v) => (
        <button key={v.id} type="button" aria-current={view === v.id ? "page" : undefined} onClick={() => onChange(v.id)}>
          {view === v.id && <motion.span layoutId={layoutId} className="nav-pill" transition={spring} />}
          <Icon name={v.icon} size={17} />
          <span className="nav-label">{t(v.label)}</span>
        </button>
      ))}
    </nav>
  );
}

function PortfolioSwitcher({ dash, onNewPortfolio }) {
  const { portfolios, selectedPortfolioId, selectPortfolio, loading, fetching } = dash;
  const current = portfolios.find((p) => Number(p.id) === Number(selectedPortfolioId));
  const toast = useToast();
  const t = useT();
  if (!portfolios.length) return null;
  return (
    <Popover
      label={t("portfolio.choose")}
      align="left"
      trigger={({ open, toggle }) => (
        <button type="button" className="switcher" onClick={toggle} aria-expanded={open} aria-haspopup="menu" disabled={loading && !current}>
          <span className="switcher-name">{current?.name ?? t("portfolio.label")}</span>
          <span className="switcher-ccy">{current?.base_currency}</span>
          <motion.span animate={{ rotate: open ? 180 : 0 }}><Icon name="down" size={14} /></motion.span>
        </button>
      )}
    >
      {({ close }) => (
        <>
          <div className="menu-label">{t("portfolio.label")}</div>
          {portfolios.map((p) => {
            const on = Number(p.id) === Number(selectedPortfolioId);
            return (
              <button
                key={p.id}
                type="button"
                role="menuitemradio"
                aria-checked={on}
                className={`menu-item ${on ? "on" : ""}`}
                disabled={fetching}
                onClick={() => { close(); selectPortfolio(Number(p.id)); }}
              >
                <span>{p.name}</span>
                <span className="muted">{p.base_currency}</span>
                {on && <Icon name="check" size={14} />}
              </button>
            );
          })}
          {current?.code && (
            <>
              <div className="menu-label">{t("code.short")}</div>
              <button type="button" role="menuitem" className="menu-item" onClick={() => { close(); copyCode(current.code, toast, t); }}>
                <span className="code-chip">{current.code}</span>
                <Icon name="copy" size={14} />
              </button>
            </>
          )}
          {onNewPortfolio && (
            <button type="button" role="menuitem" className="menu-item" onClick={() => { close(); onNewPortfolio(); }}>
              <span>{t("portfolio.new")}</span>
              <Icon name="plus" size={14} />
            </button>
          )}
        </>
      )}
    </Popover>
  );
}

function LiveStatus({ dash }) {
  const { anyMarketOpen, nextMarketOpen, lastUpdated, interval, setIntervalSeconds, portfolio } = dash;
  const openCount = (portfolio?.positions ?? []).filter((p) => p.session === "open").length;
  const t = useT();
  return (
    <Popover
      label={t("live.title")}
      trigger={({ open, toggle }) => (
        <button type="button" className={`live ${anyMarketOpen ? "open" : ""} ${interval === 0 ? "paused" : ""}`} onClick={toggle} aria-expanded={open} aria-haspopup="menu">
          <span className="live-dot"><i /></span>
          <span className="live-text">{t(anyMarketOpen ? "live.open" : "live.closed")}</span>
          <span className="live-time num">{lastUpdated ? clockTime(lastUpdated) : "—"}</span>
        </button>
      )}
    >
      {({ close }) => (
        <div className="live-menu">
          <div className="live-row">
            <span className="muted">{t("live.status")}</span>
            <span>{anyMarketOpen ? t("live.openCount", { n: openCount }) : t("live.allClosed")}</span>
          </div>
          {!anyMarketOpen && nextMarketOpen && (
            <div className="live-row">
              <span className="muted">{t("live.nextOpen")}</span>
              <span className="num">{nextOpenLabel(nextMarketOpen, t)}</span>
            </div>
          )}
          <div className="live-row">
            <span className="muted">{t("live.updated")}</span>
            <span className="num">{lastUpdated ? clockTime(lastUpdated) : "—"}</span>
          </div>
          <div className="menu-label">{t("live.interval")}</div>
          <div className="chip-grid">
            {INTERVALS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                role="menuitemradio"
                aria-checked={interval === opt.value}
                className={`chip chip-btn ${interval === opt.value ? "on" : ""}`}
                onClick={() => { setIntervalSeconds(opt.value); close(); }}
              >
                {t(opt.label)}
              </button>
            ))}
          </div>
          {!anyMarketOpen && interval !== 0 && <p className="fineprint">{t("live.closedNote")}</p>}
        </div>
      )}
    </Popover>
  );
}

export default function TopBar({ dash, view, onView, condensed, theme, onTheme, onPalette, onNewPortfolio }) {
  const { portfolio, manualRefresh, refreshing, fetching } = dash;
  const t = useT();
  return (
    <header className="topbar">
      <div className="topbar-inner">
        <div className="brand">
          <Brand />
          <span className="wordmark">faðir</span>
        </div>

        <PortfolioSwitcher dash={dash} onNewPortfolio={onNewPortfolio} />

        <AnimatePresence>
          {condensed && portfolio && (
            <motion.div
              className="mini"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={spring}
              aria-hidden="true"
            >
              <AnimatedNumber value={portfolio.liquidation.net_proceeds_try} format={money} countUp={false} className="mini-net" />
              <span className={`mini-ret num ${toneOf(portfolio.totals.pnl_try)}`}>
                {arrow(portfolio.totals.pnl_try)} {ratioPct(portfolio.totals.total_return)}
              </span>
            </motion.div>
          )}
        </AnimatePresence>

        <NavTabs view={view} onChange={onView} className="desktop-only" />

        <div className="topbar-actions">
          <LiveStatus dash={dash} />
          <motion.button
            type="button"
            className="icon-btn"
            onClick={manualRefresh}
            disabled={refreshing}
            aria-label={t("common.refresh")}
            title={`${t("common.refresh")} (R)`}
            whileTap={{ scale: 0.9 }}
          >
            <motion.span
              style={{ display: "inline-flex" }}
              animate={refreshing ? { rotate: 360 } : { rotate: 0 }}
              transition={refreshing ? { repeat: Infinity, duration: 0.8, ease: "linear" } : { duration: 0 }}
            >
              <Icon name="refresh" />
            </motion.span>
          </motion.button>
          <motion.button type="button" className="icon-btn" onClick={onTheme} aria-label={t(theme === "dark" ? "theme.toLight" : "theme.toDark")} whileTap={{ scale: 0.9 }}>
            <AnimatePresence mode="popLayout" initial={false}>
              <motion.span
                key={theme}
                style={{ display: "inline-flex" }}
                initial={{ rotate: -90, scale: 0.4, opacity: 0 }}
                animate={{ rotate: 0, scale: 1, opacity: 1 }}
                exit={{ rotate: 90, scale: 0.4, opacity: 0 }}
                transition={spring}
              >
                <Icon name={theme === "dark" ? "moon" : "sun"} />
              </motion.span>
            </AnimatePresence>
          </motion.button>
          <button type="button" className="kbd-btn desktop-only" onClick={onPalette} aria-label={t("palette.title")}>
            <Icon name="search" size={15} />
            <kbd>Ctrl K</kbd>
          </button>
        </div>
      </div>
      <div className={`sweep ${fetching ? "on" : ""}`} aria-hidden="true" />
    </header>
  );
}
