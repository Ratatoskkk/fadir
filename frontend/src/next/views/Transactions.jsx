// Add (FX auto-fetched unless overridden), edit inline, delete with confirmation.

import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { api } from "../../api.js";
import { fullDate, money, num } from "../../format.js";
import TickerSearch from "../components/TickerSearch.jsx";
import { useT } from "../i18n/index.jsx";
import Dialog from "../ui/Dialog.jsx";
import Icon from "../ui/Icons.jsx";
import { collapse, ease, spring } from "../ui/motion.js";
import { useConfirm, useToast } from "../ui/overlays.jsx";

const today = () => new Date().toISOString().slice(0, 10);
const blank = () => ({
  trade_date: today(), side: "BUY", quantity: "", price_native: "",
  fees_native: "0", fx_rate_override: "", note: "",
});

function groupByTicker(transactions) {
  const groups = new Map();
  for (const txn of transactions) {
    let g = groups.get(txn.ticker);
    if (!g) {
      g = { ticker: txn.ticker, currency: txn.currency, rows: [], netQuantity: 0, totalNative: 0, totalTry: 0, buys: 0, sells: 0 };
      groups.set(txn.ticker, g);
    }
    const sign = txn.side === "SELL" ? -1 : 1;
    g.rows.push(txn);
    g.netQuantity += sign * Number(txn.quantity);
    g.totalNative += sign * Number(txn.total_native);
    g.totalTry += sign * Number(txn.total_try);
    if (txn.side === "SELL") g.sells += 1; else g.buys += 1;
  }
  for (const g of groups.values()) g.rows.sort((a, b) => b.trade_date.localeCompare(a.trade_date) || b.id - a.id);
  return [...groups.values()].sort((a, b) => b.totalTry - a.totalTry);
}

export function TransactionForm({ instruments, portfolioId, onChanged, onDone }) {
  const t = useT();
  const [picked, setPicked] = useState(null);
  const [form, setForm] = useState(blank);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const toast = useToast();
  const set = (key) => (e) => { const { value } = e.target; setForm((prev) => ({ ...prev, [key]: value })); };
  const currency = picked?.currency ?? "";

  async function submit(e) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const payload = {
        trade_date: form.trade_date, side: form.side, quantity: form.quantity,
        price_native: form.price_native, fees_native: form.fees_native || "0", note: form.note || null,
      };
      if (picked.known) payload.ticker = picked.ticker; else payload.yf_symbol = picked.yf_symbol;
      if (form.fx_rate_override.trim()) payload.fx_rate_override = form.fx_rate_override;
      const created = await api.createTransaction(payload, portfolioId);
      toast({ tone: "up", text: t(form.side === "BUY" ? "txn.addedBuy" : "txn.addedSell", { ticker: created?.ticker ?? picked.ticker }) });
      setForm({ ...blank(), trade_date: form.trade_date });
      // A first-time instrument has no cached prices yet; fetch them now rather than
      // showing it unpriced until the next background refresh (an hour when closed).
      if (!picked.known) await api.refresh().catch(() => {});
      await onChanged();
      onDone?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AnimatePresence mode="wait" initial={false}>
      {!picked ? (
        <motion.div key="search" initial={{ opacity: 0, x: -16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -16, transition: { duration: 0.12 } }}>
          <TickerSearch instruments={instruments} onPick={setPicked} />
        </motion.div>
      ) : (
        <motion.form key="form" className="txn-form" onSubmit={submit} initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 16 }}>
          <button type="button" className="picked" onClick={() => setPicked(null)} aria-label={t("txn.changeInstrument")}>
            <motion.span className="picked-sym" layoutId="picked-sym">{picked.ticker}</motion.span>
            <span className="picked-name">{picked.name}</span>
            <span className="picked-meta">{picked.exchange}{picked.currency && ` · ${picked.currency}`}</span>
            <Icon name="edit" size={15} />
          </button>
          <div className="side-toggle" role="radiogroup" aria-label={t("txn.side")}>
            {[["BUY", t("txn.buy")], ["SELL", t("txn.sell")]].map(([value, label]) => (
              <button key={value} type="button" role="radio" aria-checked={form.side === value} className={value === "BUY" ? "buy" : "sell"} onClick={() => setForm((p) => ({ ...p, side: value }))}>
                {form.side === value && <motion.span layoutId="side-pill" className="side-pill" transition={spring} />}
                <span>{label}</span>
              </button>
            ))}
          </div>
          <div className="field">
            <label htmlFor="f-date">{t("txn.date")}</label>
            <input id="f-date" type="date" value={form.trade_date} onChange={set("trade_date")} required />
          </div>
          <div className="field-row">
            <div className="field">
              <label htmlFor="f-qty">{t("txn.quantity")}</label>
              <input id="f-qty" type="number" step="any" min="0.00000001" inputMode="decimal" value={form.quantity} onChange={set("quantity")} required autoFocus />
            </div>
            <div className="field">
              <label htmlFor="f-price">{t("txn.price")} {currency && `(${currency})`}</label>
              <input id="f-price" type="number" step="any" min="0" inputMode="decimal" value={form.price_native} onChange={set("price_native")} required />
            </div>
          </div>
          <div className="field-row">
            <div className="field">
              <label htmlFor="f-fees">{t("txn.fees")} {currency && `(${currency})`}</label>
              <input id="f-fees" type="number" step="any" min="0" inputMode="decimal" value={form.fees_native} onChange={set("fees_native")} />
            </div>
            <div className="field">
              <label htmlFor="f-fx">{t("txn.fx")}</label>
              <input id="f-fx" type="number" step="any" min="0" inputMode="decimal" placeholder={t("txn.auto")} value={form.fx_rate_override} onChange={set("fx_rate_override")} />
            </div>
          </div>
          <div className="field">
            <label htmlFor="f-note">{t("txn.note")}</label>
            <input id="f-note" type="text" value={form.note} onChange={set("note")} />
          </div>
          <AnimatePresence>
            {error && <motion.div className="form-error" role="alert" {...collapse}><div>{error}</div></motion.div>}
          </AnimatePresence>
          <button className="btn primary block" type="submit" disabled={busy}>
            {busy ? <span className="spinner" /> : <><Icon name="plus" size={16} /> {t("txn.add")}</>}
          </button>
        </motion.form>
      )}
    </AnimatePresence>
  );
}

function TxnRow({ t: txn, editing, setEditing, busy, onSave, onDelete, index }) {
  const t = useT();
  const isEditing = editing?.id === txn.id;
  const edit = (key) => (e) => setEditing({ ...editing, [key]: e.target.value });
  return (
    <motion.tr
      layout="position"
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0, transition: { delay: index * 0.02, duration: 0.3, ease } }}
      exit={{ opacity: 0, x: 30, transition: { duration: 0.2 } }}
      className={isEditing ? "editing" : ""}
    >
      <td className="left sticky"><span className="ticker-name">{txn.note || "—"}</span></td>
      <td className="num">{isEditing ? <input className="small" type="date" value={editing.trade_date} onChange={edit("trade_date")} /> : fullDate(txn.trade_date)}</td>
      <td>
        {isEditing ? (
          <select className="small" value={editing.side} onChange={edit("side")}>
            <option value="BUY">{t("txn.buy")}</option>
            <option value="SELL">{t("txn.sell")}</option>
          </select>
        ) : (
          <span className={`badge ${txn.side === "BUY" ? "open" : "warn"}`}>{t(txn.side === "BUY" ? "txn.buy" : "txn.sell")}</span>
        )}
      </td>
      <td className="num">{isEditing ? <input className="small w80" type="number" step="any" value={editing.quantity} onChange={edit("quantity")} /> : num(txn.quantity, 0)}</td>
      <td className="num">{isEditing ? <input className="small w90" type="number" step="any" value={editing.price_native} onChange={edit("price_native")} /> : money(txn.price_native, txn.currency)}</td>
      <td className="num">{isEditing ? <input className="small w80" type="number" step="any" value={editing.fees_native} onChange={edit("fees_native")} /> : money(txn.fees_native, txn.currency)}</td>
      <td className="num">{money(txn.total_native, txn.currency)}</td>
      <td className="num sep">
        {isEditing
          ? <input className="small w90" type="number" step="any" placeholder={num(txn.fx_rate_to_try, 4)} value={editing.fx_rate_override ?? ""} onChange={edit("fx_rate_override")} />
          : num(txn.fx_rate_to_try, 4)}
      </td>
      <td className="num">
        {fullDate(txn.fx_rate_date)}{" "}
        {txn.fx_carried_forward && <span className="badge warn" title={t("txn.carriedTitle")}>{t("txn.carried")}</span>}
      </td>
      <td>
        {txn.fx_provider === "manual"
          ? <span className="badge warn">{t("txn.manual")}</span>
          : txn.fx_provider.includes("*")
            ? <span className="badge info" title={txn.fx_provider}>{t("txn.cross")}</span>
            : <span className="ticker-name">{txn.fx_provider}</span>}
      </td>
      <td className="num sep">{money(txn.total_try)}</td>
      <td>
        <div className="row-actions">
          {isEditing ? (
            <>
              <button type="button" className="icon-btn ok" onClick={() => onSave(txn.id)} disabled={busy} aria-label={t("common.save")}><Icon name="check" size={16} /></button>
              <button type="button" className="icon-btn" onClick={() => setEditing(null)} disabled={busy} aria-label={t("common.cancel")}><Icon name="undo" size={16} /></button>
            </>
          ) : (
            <>
              <button
                type="button"
                className="icon-btn"
                aria-label={t("common.edit")}
                disabled={busy}
                onClick={() => setEditing({ id: txn.id, trade_date: txn.trade_date, side: txn.side, quantity: txn.quantity, price_native: txn.price_native, fees_native: txn.fees_native, fx_rate_override: "" })}
              >
                <Icon name="edit" size={15} />
              </button>
              <button type="button" className="icon-btn danger" onClick={() => onDelete(txn)} disabled={busy} aria-label={t("common.delete")}><Icon name="trash" size={15} /></button>
            </>
          )}
        </div>
      </td>
    </motion.tr>
  );
}

export default function Transactions({ dash, sheetOpen, setSheetOpen }) {
  const t = useT();
  const { transactions, instruments, selectedPortfolioId: portfolioId, reloadAfterTransaction: onChanged } = dash;
  const [editing, setEditing] = useState(null);
  const [busy, setBusy] = useState(false);
  const [collapsed, setCollapsed] = useState({});
  const [query, setQuery] = useState("");
  const confirm = useConfirm();
  const toast = useToast();

  const groups = useMemo(() => {
    const q = query.trim().toLocaleUpperCase();
    return groupByTicker(q ? transactions.filter((x) => x.ticker.toLocaleUpperCase().includes(q) || (x.note ?? "").toLocaleUpperCase().includes(q)) : transactions);
  }, [transactions, query]);

  async function saveEdit(id) {
    setBusy(true);
    try {
      const payload = {
        quantity: editing.quantity, price_native: editing.price_native, fees_native: editing.fees_native || "0",
        trade_date: editing.trade_date, side: editing.side,
      };
      if (editing.fx_rate_override?.trim()) payload.fx_rate_override = editing.fx_rate_override;
      await api.updateTransaction(id, payload, portfolioId);
      setEditing(null);
      toast({ tone: "up", text: t("txn.updated") });
      await onChanged();
    } catch (err) {
      toast({ tone: "down", text: err.message, duration: 7000 });
    } finally {
      setBusy(false);
    }
  }

  async function remove(txn) {
    const ok = await confirm({
      title: t("txn.deleteTitle"),
      body: <><strong>{txn.ticker}</strong> · {fullDate(txn.trade_date)} · {t("txn.units", { n: num(txn.quantity, 0) })}<br /><span className="muted">{t("txn.deleteBody")}</span></>,
      confirmLabel: t("common.delete"),
      danger: true,
    });
    if (!ok) return;
    setBusy(true);
    try {
      await api.deleteTransaction(txn.id, portfolioId);
      toast({ tone: "info", text: t("txn.deleted", { ticker: txn.ticker }) });
      await onChanged();
    } catch (err) {
      toast({ tone: "down", text: err.message, duration: 7000 });
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card" id="islemler">
      <header className="card-head">
        <h2>{t("nav.transactions")}</h2>
        <span className="muted num">{transactions.length}</span>
        <div className="head-actions">
          <label className="search">
            <Icon name="search" size={15} />
            <span className="sr-only">{t("txn.searchList")}</span>
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t("common.search")} />
          </label>
          <motion.button type="button" className="btn primary" onClick={() => setSheetOpen(true)} whileTap={{ scale: 0.96 }}>
            <Icon name="plus" size={16} /> {t("txn.new")}
          </motion.button>
        </div>
      </header>

      {transactions.length === 0 ? (
        <div className="empty-state">
          <div className="empty-orb" />
          <p>{t("txn.none")}</p>
          <button type="button" className="btn primary" onClick={() => setSheetOpen(true)}><Icon name="plus" size={16} /> {t("txn.first")}</button>
        </div>
      ) : (
        <div className="txn-groups">
          <AnimatePresence initial={false}>
            {groups.map((g, gi) => {
              const open = !collapsed[g.ticker];
              return (
                <motion.div
                  key={g.ticker}
                  layout="position"
                  className="txn-group"
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0, transition: { delay: gi * 0.04, duration: 0.4, ease } }}
                  exit={{ opacity: 0, scale: 0.98 }}
                  transition={spring}
                >
                  <button type="button" className="txn-group-head" aria-expanded={open} onClick={() => setCollapsed((p) => ({ ...p, [g.ticker]: !p[g.ticker] }))}>
                    <motion.span animate={{ rotate: open ? 0 : -90 }} transition={spring} className="caret"><Icon name="down" size={16} /></motion.span>
                    <span className="sym">{g.ticker}</span>
                    <span className="muted">
                      {g.currency} · {t("txn.count", { n: g.rows.length })}
                      {g.sells > 0 && ` (${t("txn.split", { buys: g.buys, sells: g.sells })})`}
                    </span>
                    <span className="grow" />
                    <span className="num muted">{t("txn.units", { n: num(g.netQuantity, 0) })}</span>
                    <span className="num muted hide-sm">{money(g.totalNative, g.currency)}</span>
                    <span className="num strong">{money(g.totalTry)}</span>
                  </button>
                  <AnimatePresence initial={false}>
                    {open && (
                      <motion.div {...collapse} className="txn-group-body">
                        <div className="table-wrap">
                          <table className="grid-table compact">
                            <thead>
                              <tr>
                                <th className="left">{t("txn.note")}</th><th>{t("txn.date")}</th><th>{t("txn.side")}</th><th>{t("txn.quantity")}</th><th>{t("txn.price")}</th><th>{t("txn.fees")}</th>
                                <th>{t("txn.amount")}</th><th className="sep">{t("txn.fx")}</th><th>{t("txn.fxDate")}</th><th>{t("txn.source")}</th><th className="sep">{t("txn.amountTry")}</th><th />
                              </tr>
                            </thead>
                            <tbody>
                              <AnimatePresence initial={false}>
                                {g.rows.map((row, i) => (
                                  <TxnRow key={row.id} t={row} index={i} editing={editing} setEditing={setEditing} busy={busy} onSave={saveEdit} onDelete={remove} />
                                ))}
                              </AnimatePresence>
                            </tbody>
                          </table>
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </motion.div>
              );
            })}
          </AnimatePresence>
        </div>
      )}

      <Dialog open={sheetOpen} onClose={() => setSheetOpen(false)} title={t("txn.new")} className="txn-dialog">
        <TransactionForm instruments={instruments} portfolioId={portfolioId} onChanged={onChanged} onDone={() => setSheetOpen(false)} />
      </Dialog>
    </section>
  );
}
