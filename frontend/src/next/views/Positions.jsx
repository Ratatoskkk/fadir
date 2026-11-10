// Native and TRY PnL stay in separate columns — the two are never blended.

import { useMemo, useState } from "react";
import { LayoutGroup, motion } from "framer-motion";
import { useFlash } from "../../flash.js";
import { arrow, fullDate, money, num, ratioPct, signedMoney, toneOf } from "../../format.js";
import Icon from "../ui/Icons.jsx";
import { ease, spring } from "../ui/motion.js";
import { useT } from "../i18n/index.jsx";

const COLUMNS = [
  { key: "ticker", label: "pos.instrument", align: "left" },
  { key: "quantity", label: "pos.quantity" },
  { key: "price_native", label: "pos.price" },
  { key: "average_purchase_price_native", label: "pos.avgBuy" },
  { key: "cost_native", label: "pos.cost", group: true },
  { key: "market_value_native", label: "pos.value" },
  { key: "pnl_native", label: "pos.pnlLocal" },
  { key: "local_return", label: "pos.localReturn" },
  { key: "fx_rate_to_try", label: "pos.fx", group: true },
  { key: "fx_return", label: "pos.fxReturn" },
  { key: "cost_try", label: "pos.costTry", group: true },
  { key: "market_value_try", label: "pos.valueTry" },
  { key: "pnl_try", label: "pos.pnlTry" },
  { key: "daily_pnl_try", label: "pos.dailyTry", group: true },
  { key: "total_return", label: "pos.totalReturn" },
];

const VIEW_KEY = "fadir.positions.view";

function sortValue(p, key) {
  switch (key) {
    case "ticker": return p.ticker;
    case "local_return":
    case "fx_return":
    case "total_return":
      return p.attribution[key] === null ? -Infinity : Number(p.attribution[key]);
    case "daily_pnl_try": return p.daily?.available ? Number(p.daily.pnl_try) : -Infinity;
    case "average_purchase_price_native":
      return p.average_purchase_price_native === null ? -Infinity : Number(p.average_purchase_price_native);
    default: return Number(p[key]);
  }
}

function Badges({ p }) {
  const t = useT();
  return (
    <span className="badges">
      {Number(p.quantity) === 0
        ? <span className="badge">{t("pos.sold")}</span>
        : <span className={`badge ${p.session === "open" ? "open" : ""}`}>{t(p.session === "open" ? "pos.open" : "pos.closed")}</span>}
      {!p.ok && <span className="badge err">{t("common.noData")}</span>}
      {p.fx_triangulated && <span className="badge info" title={t("pos.crossTitle", { provider: p.fx_provider })}>{t("pos.cross")}</span>}
      {p.fx_provider === "manual" && <span className="badge warn">{t("pos.manualFx")}</span>}
    </span>
  );
}

function PriceCell({ p }) {
  const flash = useFlash(p.price_native);
  if (!p.ok) return <td className="num">—</td>;
  return <td className={`num ${flash}`}>{money(p.price_native, p.currency)}</td>;
}

function DailyCell({ daily, currency }) {
  const t = useT();
  if (!daily?.available) return <td className="num sep" title={t("hero.noPrevSession")}>—</td>;
  const title = [
    t("hero.prevSession", { date: fullDate(daily.reference_date) }),
    `${t("attr.price")}: ${signedMoney(daily.price_effect_try)}`,
    `${t("attr.fx")}: ${signedMoney(daily.fx_effect_try)}`,
    `${t("pos.local")}: ${signedMoney(daily.pnl_native, currency)}`,
  ].join("\n");
  return (
    <td className={`num sep ${toneOf(daily.pnl_try)}`} title={title}>
      {arrow(daily.pnl_try)} {signedMoney(daily.pnl_try)}
      {daily.return_ratio !== null && <small>{ratioPct(daily.return_ratio)}</small>}
    </td>
  );
}

function ReturnBar({ label, ratio }) {
  const v = ratio === null || ratio === undefined ? null : Number(ratio) - 1;
  const width = v === null ? 0 : Math.min(1, Math.abs(v) / 0.5);
  return (
    <div className="rbar">
      <span className="label">{label}</span>
      <span className="rbar-track">
        <motion.i
          className={toneOf(v)}
          initial={{ scaleX: 0 }}
          animate={{ scaleX: width }}
          transition={{ duration: 0.7, ease }}
        />
      </span>
      <span className={`num ${toneOf(v)}`}>{ratioPct(ratio)}</span>
    </div>
  );
}

function PositionCard({ p, on, onFocus, index }) {
  const t = useT();
  return (
    <motion.article
      layout
      initial={{ opacity: 0, y: 20, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1, transition: { delay: index * 0.03, duration: 0.45, ease } }}
      transition={spring}
    >
      <div className={`pos-card ${on ? "on" : ""}`}>
      <header>
        <button type="button" className="sym-btn" aria-pressed={on} onClick={() => onFocus(p.ticker)} title={t("palette.focus")}>
          {p.ticker}
          <Icon name="focus" size={14} />
        </button>
        <Badges p={p} />
      </header>
      <p className="pos-name">{p.name}, {p.currency}</p>
      <div className="pos-value num">{p.ok ? money(p.market_value_try) : "—"}</div>
      <div className={`pos-pnl num ${toneOf(p.pnl_try)}`}>
        {p.ok ? <>{arrow(p.pnl_try)} {signedMoney(p.pnl_try)}</> : p.error}
      </div>
      <ReturnBar label={t("pos.local")} ratio={p.attribution.local_return} />
      <ReturnBar label={t("pos.fx")} ratio={p.attribution.fx_return} />
      <ReturnBar label={t("pos.total")} ratio={p.attribution.total_return} />
      <footer className="num">
        <span>{t("txn.units", { n: num(p.quantity, 0) })}</span>
        <span>{p.ok ? money(p.price_native, p.currency) : "—"}</span>
        <span className={p.daily?.available ? toneOf(p.daily.pnl_try) : "muted"}>
          {p.daily?.available ? `${arrow(p.daily.pnl_try)} ${signedMoney(p.daily.pnl_try)}` : "—"}
        </span>
      </footer>
      </div>
    </motion.article>
  );
}

function loadView() {
  try {
    const saved = localStorage.getItem(VIEW_KEY);
    if (saved === "cards" || saved === "table") return saved;
  } catch {
    /* private mode */
  }
  return window.matchMedia("(max-width: 760px)").matches ? "cards" : "table";
}

export default function Positions({ dash, onFocusTicker }) {
  const t = useT();
  const positions = dash.portfolio.positions;
  const focusTickers = dash.focusTickers;
  const [sort, setSort] = useState({ key: "market_value_try", dir: "desc" });
  const [view, setView] = useState(loadView);

  const changeView = (next) => {
    setView(next);
    try { localStorage.setItem(VIEW_KEY, next); } catch { /* private mode */ }
  };

  const sorted = useMemo(() => {
    const rows = [...positions];
    rows.sort((a, b) => {
      const av = sortValue(a, sort.key);
      const bv = sortValue(b, sort.key);
      const cmp = typeof av === "string" || typeof bv === "string"
        ? String(av).localeCompare(String(bv), "tr")
        : av === bv ? 0 : av < bv ? -1 : 1;
      return sort.dir === "asc" ? cmp : -cmp;
    });
    return rows;
  }, [positions, sort]);

  const toggle = (key) =>
    setSort((prev) => (prev.key === key
      ? { key, dir: prev.dir === "asc" ? "desc" : "asc" }
      : { key, dir: key === "ticker" ? "asc" : "desc" }));

  // The server's exact sums over priced positions, so the footer agrees with the Hero.
  const { totals: sums } = dash.portfolio;
  const totals = {
    cost: Number(sums.cost_try),
    value: Number(sums.market_value_try),
    pnl: Number(sums.pnl_try),
    daily: sums.daily.available ? Number(sums.daily.pnl_try) : 0,
  };

  return (
    <section className="card" id="pozisyonlar">
      <header className="card-head">
        <h2>{t("nav.positions")}</h2>
        <span className="muted num">{positions.length}</span>
        <div className="head-actions">
          {view === "cards" && (
            <label className="sort-select">
              <span className="sr-only">{t("pos.sort")}</span>
              <select value={`${sort.key}:${sort.dir}`} onChange={(e) => { const [key, dir] = e.target.value.split(":"); setSort({ key, dir }); }}>
                <option value="market_value_try:desc">{t("pos.valueTry")} ↓</option>
                <option value="pnl_try:desc">{t("pos.pnlTry")} ↓</option>
                <option value="total_return:desc">{t("hero.totalReturn")} ↓</option>
                <option value="daily_pnl_try:desc">{t("hero.daily")} ↓</option>
                <option value="ticker:asc">A → Z</option>
              </select>
            </label>
          )}
          <div className="segmented small" role="group" aria-label={t("pos.view")}>
            {[["table", "list", t("pos.table")], ["cards", "grid", t("pos.cards")]].map(([key, icon, label]) => (
              <button key={key} type="button" aria-pressed={view === key} onClick={() => changeView(key)} aria-label={label} title={label}>
                {view === key && <motion.span layoutId="pos-view-pill" className="segmented-pill" transition={spring} />}
                <span><Icon name={icon} size={15} /></span>
              </button>
            ))}
          </div>
        </div>
      </header>

      {view === "cards" ? (
          <motion.div key="cards" className="pos-grid" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            <LayoutGroup>
              {sorted.map((p, i) => (
                <PositionCard key={p.ticker} p={p} index={i} on={focusTickers.includes(p.ticker)} onFocus={onFocusTicker} />
              ))}
            </LayoutGroup>
          </motion.div>
        ) : (
          <motion.div key="table" className="table-wrap" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            <table className="grid-table">
              <caption className="sr-only">{t("pos.caption")}</caption>
              <thead>
                <tr>
                  {COLUMNS.map((col) => (
                    <th
                      key={col.key}
                      scope="col"
                      className={`${col.group ? "sep" : ""} ${col.align === "left" ? "left" : ""}`}
                      aria-sort={sort.key === col.key ? (sort.dir === "asc" ? "ascending" : "descending") : "none"}
                    >
                      <button type="button" className="th-btn" onClick={() => toggle(col.key)}>
                        {t(col.label)}
                        <motion.span
                          className="sort-mark"
                          animate={{ opacity: sort.key === col.key ? 1 : 0, rotate: sort.dir === "asc" ? 180 : 0 }}
                          transition={spring}
                        >
                          <Icon name="down" size={12} />
                        </motion.span>
                      </button>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sorted.map((p, i) => {
                  const a = p.attribution;
                  const on = focusTickers.includes(p.ticker);
                  return (
                    <motion.tr
                      key={p.ticker}
                      layout="position"
                      transition={spring}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0, transition: { delay: i * 0.025, duration: 0.35, ease } }}
                      className={on ? "on" : ""}
                    >
                      <td className="left sticky">
                        <div className="ticker">
                          <button type="button" className="sym-btn" aria-pressed={on} onClick={() => onFocusTicker(p.ticker)} title={t("palette.focus")}>
                            {p.ticker}
                          </button>
                          <Badges p={p} />
                          <span className="ticker-name">
                            {p.name}, {p.currency}, {p.ok ? (p.session === "open" ? t("pos.live") : t("pos.last", { date: fullDate(p.price_date) })) : p.error}
                          </span>
                        </div>
                      </td>
                      <td className="num">{num(p.quantity, 0)}</td>
                      <PriceCell p={p} />
                      <td className="num">{p.average_purchase_price_native === null ? "—" : money(p.average_purchase_price_native, p.currency)}</td>
                      <td className="num sep">{money(p.cost_native, p.currency)}</td>
                      <td className="num">{p.ok ? money(p.market_value_native, p.currency) : "—"}</td>
                      <td className={`num ${toneOf(p.pnl_native)}`}>{p.ok ? <>{arrow(p.pnl_native)} {signedMoney(p.pnl_native, p.currency)}</> : "—"}</td>
                      <td className={`num ${toneOf(Number(a.local_return) - 1)}`}>{ratioPct(a.local_return)}</td>
                      <td className="num sep" title={`Kaynak: ${p.fx_provider}`}>{num(p.fx_rate_to_try, 4)}</td>
                      <td className={`num ${toneOf(Number(a.fx_return) - 1)}`}>{ratioPct(a.fx_return)}</td>
                      <td className="num sep">{money(p.cost_try)}</td>
                      <td className="num">{p.ok ? money(p.market_value_try) : "—"}</td>
                      <td className={`num ${toneOf(p.pnl_try)}`}>{p.ok ? <>{arrow(p.pnl_try)} {signedMoney(p.pnl_try)}</> : "—"}</td>
                      <DailyCell daily={p.daily} currency={p.currency} />
                      <td className={`num ${toneOf(Number(a.total_return) - 1)}`}>{ratioPct(a.total_return)}</td>
                    </motion.tr>
                  );
                })}
              </tbody>
              <tfoot>
                <tr>
                  <td className="left sticky">{t("pos.total")}</td>
                  <td colSpan={6} />
                  <td className="sep" colSpan={3} />
                  <td className="num sep">{money(totals.cost)}</td>
                  <td className="num">{money(totals.value)}</td>
                  <td className={`num ${toneOf(totals.pnl)}`}>{arrow(totals.pnl)} {signedMoney(totals.pnl)}</td>
                  <td className={`num sep ${toneOf(totals.daily)}`}>{arrow(totals.daily)} {signedMoney(totals.daily)}</td>
                  <td className={`num ${toneOf(totals.pnl)}`}>{totals.cost ? ratioPct(totals.value / totals.cost) : "—"}</td>
                </tr>
              </tfoot>
            </table>
          </motion.div>
        )}

      <p className="fineprint">
        {t("pos.footnote")}
      </p>
    </section>
  );
}
