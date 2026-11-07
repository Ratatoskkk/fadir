// Add (FX auto-fetched unless overridden), edit inline, delete with confirmation.

import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { api } from "../../api.js";
import { fullDate, money, num } from "../../format.js";
import Icon from "../ui/Icons.jsx";
import Sheet from "../ui/Sheet.jsx";
import { collapse, ease, spring } from "../ui/motion.js";
import { useConfirm, useToast } from "../ui/overlays.jsx";

const today = () => new Date().toISOString().slice(0, 10);
const blank = () => ({
  ticker: "", trade_date: today(), side: "BUY", quantity: "", price_native: "",
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

export function TransactionForm({ instruments, portfolioId, onChanged, onDone, initialTicker = "" }) {
  const [form, setForm] = useState(() => ({ ...blank(), ticker: initialTicker }));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const toast = useToast();
  const set = (key) => (e) => { const { value } = e.target; setForm((prev) => ({ ...prev, [key]: value })); };
  const currency = instruments.find((i) => i.ticker === form.ticker)?.currency ?? "";

  async function submit(e) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const payload = {
        ticker: form.ticker, trade_date: form.trade_date, side: form.side, quantity: form.quantity,
        price_native: form.price_native, fees_native: form.fees_native || "0", note: form.note || null,
      };
      if (form.fx_rate_override.trim()) payload.fx_rate_override = form.fx_rate_override;
      await api.createTransaction(payload, portfolioId);
      toast({ tone: "up", text: `${form.ticker} ${form.side === "BUY" ? "alışı" : "satışı"} eklendi` });
      setForm({ ...blank(), ticker: form.ticker, trade_date: form.trade_date });
      await onChanged();
      onDone?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="txn-form" onSubmit={submit}>
      <div className="side-toggle" role="radiogroup" aria-label="Yön">
        {[["BUY", "Alış"], ["SELL", "Satış"]].map(([value, label]) => (
          <button key={value} type="button" role="radio" aria-checked={form.side === value} className={value === "BUY" ? "buy" : "sell"} onClick={() => setForm((p) => ({ ...p, side: value }))}>
            {form.side === value && <motion.span layoutId="side-pill" className="side-pill" transition={spring} />}
            <span>{label}</span>
          </button>
        ))}
      </div>
      <div className="field">
        <label htmlFor="f-ticker">Enstrüman</label>
        <select id="f-ticker" value={form.ticker} onChange={set("ticker")} required>
          <option value="">seçin…</option>
          {instruments.map((i) => <option key={i.ticker} value={i.ticker}>{i.ticker} ({i.currency})</option>)}
        </select>
      </div>
      <div className="field">
        <label htmlFor="f-date">Tarih</label>
        <input id="f-date" type="date" value={form.trade_date} onChange={set("trade_date")} required />
      </div>
      <div className="field-row">
        <div className="field">
          <label htmlFor="f-qty">Adet</label>
          <input id="f-qty" type="number" step="any" min="0.00000001" inputMode="decimal" value={form.quantity} onChange={set("quantity")} required />
        </div>
        <div className="field">
          <label htmlFor="f-price">Fiyat {currency && `(${currency})`}</label>
          <input id="f-price" type="number" step="any" min="0" inputMode="decimal" value={form.price_native} onChange={set("price_native")} required />
        </div>
      </div>
      <div className="field-row">
        <div className="field">
          <label htmlFor="f-fees">Masraf {currency && `(${currency})`}</label>
          <input id="f-fees" type="number" step="any" min="0" inputMode="decimal" value={form.fees_native} onChange={set("fees_native")} />
        </div>
        <div className="field">
          <label htmlFor="f-fx">Kur</label>
          <input id="f-fx" type="number" step="any" min="0" inputMode="decimal" placeholder="otomatik" value={form.fx_rate_override} onChange={set("fx_rate_override")} />
        </div>
      </div>
      <div className="field">
        <label htmlFor="f-note">Not</label>
        <input id="f-note" type="text" value={form.note} onChange={set("note")} />
      </div>
      <AnimatePresence>
        {error && <motion.div className="form-error" role="alert" {...collapse}><div>{error}</div></motion.div>}
      </AnimatePresence>
      <button className="btn primary block" type="submit" disabled={busy || !form.ticker}>
        {busy ? <span className="spinner" /> : <><Icon name="plus" size={16} /> Ekle</>}
      </button>
      <p className="fineprint">Kur boşsa işlem gününün yayınlanmış kuru çekilir; tatil günlerinde önceki yayın taşınır.</p>
    </form>
  );
}

function TxnRow({ t, editing, setEditing, busy, onSave, onDelete, index }) {
  const isEditing = editing?.id === t.id;
  const edit = (key) => (e) => setEditing({ ...editing, [key]: e.target.value });
  return (
    <motion.tr
      layout="position"
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0, transition: { delay: index * 0.02, duration: 0.3, ease } }}
      exit={{ opacity: 0, x: 30, transition: { duration: 0.2 } }}
      className={isEditing ? "editing" : ""}
    >
      <td className="left sticky"><span className="ticker-name">{t.note || "—"}</span></td>
      <td className="num">{isEditing ? <input className="small" type="date" value={editing.trade_date} onChange={edit("trade_date")} /> : fullDate(t.trade_date)}</td>
      <td>
        {isEditing ? (
          <select className="small" value={editing.side} onChange={edit("side")}>
            <option value="BUY">ALIŞ</option>
            <option value="SELL">SATIŞ</option>
          </select>
        ) : (
          <span className={`badge ${t.side === "BUY" ? "open" : "warn"}`}>{t.side === "BUY" ? "alış" : "satış"}</span>
        )}
      </td>
      <td className="num">{isEditing ? <input className="small w80" type="number" step="any" value={editing.quantity} onChange={edit("quantity")} /> : num(t.quantity, 0)}</td>
      <td className="num">{isEditing ? <input className="small w90" type="number" step="any" value={editing.price_native} onChange={edit("price_native")} /> : money(t.price_native, t.currency)}</td>
      <td className="num">{isEditing ? <input className="small w80" type="number" step="any" value={editing.fees_native} onChange={edit("fees_native")} /> : money(t.fees_native, t.currency)}</td>
      <td className="num">{money(t.total_native, t.currency)}</td>
      <td className="num sep">
        {isEditing
          ? <input className="small w90" type="number" step="any" placeholder={num(t.fx_rate_to_try, 4)} value={editing.fx_rate_override ?? ""} onChange={edit("fx_rate_override")} />
          : num(t.fx_rate_to_try, 4)}
      </td>
      <td className="num">
        {fullDate(t.fx_rate_date)}{" "}
        {t.fx_carried_forward && <span className="badge warn" title="İşlem gününde kur yayınlanmamış; önceki yayın taşındı">taşındı</span>}
      </td>
      <td>
        {t.fx_provider === "manual"
          ? <span className="badge warn">manuel</span>
          : t.fx_provider.includes("*")
            ? <span className="badge info" title={t.fx_provider}>çapraz</span>
            : <span className="ticker-name">{t.fx_provider}</span>}
      </td>
      <td className="num sep">{money(t.total_try)}</td>
      <td>
        <div className="row-actions">
          {isEditing ? (
            <>
              <button type="button" className="icon-btn ok" onClick={() => onSave(t.id)} disabled={busy} aria-label="Kaydet"><Icon name="check" size={16} /></button>
              <button type="button" className="icon-btn" onClick={() => setEditing(null)} disabled={busy} aria-label="Vazgeç"><Icon name="undo" size={16} /></button>
            </>
          ) : (
            <>
              <button
                type="button"
                className="icon-btn"
                aria-label="Düzenle"
                disabled={busy}
                onClick={() => setEditing({ id: t.id, trade_date: t.trade_date, side: t.side, quantity: t.quantity, price_native: t.price_native, fees_native: t.fees_native, fx_rate_override: "" })}
              >
                <Icon name="edit" size={15} />
              </button>
              <button type="button" className="icon-btn danger" onClick={() => onDelete(t)} disabled={busy} aria-label="Sil"><Icon name="trash" size={15} /></button>
            </>
          )}
        </div>
      </td>
    </motion.tr>
  );
}

export default function Transactions({ dash, sheetOpen, setSheetOpen }) {
  const { transactions, instruments, selectedPortfolioId: portfolioId, reloadAfterTransaction: onChanged } = dash;
  const [editing, setEditing] = useState(null);
  const [busy, setBusy] = useState(false);
  const [collapsed, setCollapsed] = useState({});
  const [query, setQuery] = useState("");
  const confirm = useConfirm();
  const toast = useToast();

  const groups = useMemo(() => {
    const q = query.trim().toLocaleUpperCase("tr");
    return groupByTicker(q ? transactions.filter((t) => t.ticker.toLocaleUpperCase("tr").includes(q) || (t.note ?? "").toLocaleUpperCase("tr").includes(q)) : transactions);
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
      toast({ tone: "up", text: "İşlem güncellendi" });
      await onChanged();
    } catch (err) {
      toast({ tone: "down", text: err.message, duration: 7000 });
    } finally {
      setBusy(false);
    }
  }

  async function remove(t) {
    const ok = await confirm({
      title: "Bu işlem silinsin mi?",
      body: <><strong>{t.ticker}</strong> · {fullDate(t.trade_date)} · {num(t.quantity, 0)} adet<br /><span className="muted">FIFO lotları ve geçmiş seri yeniden hesaplanacak.</span></>,
      confirmLabel: "Sil",
      danger: true,
    });
    if (!ok) return;
    setBusy(true);
    try {
      await api.deleteTransaction(t.id, portfolioId);
      toast({ tone: "info", text: `${t.ticker} işlemi silindi` });
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
        <h2>İşlemler</h2>
        <span className="muted num">{transactions.length}</span>
        <div className="head-actions">
          <label className="search">
            <Icon name="search" size={15} />
            <span className="sr-only">İşlem ara</span>
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Ara" />
          </label>
          <motion.button type="button" className="btn primary" onClick={() => setSheetOpen(true)} whileTap={{ scale: 0.96 }}>
            <Icon name="plus" size={16} /> Yeni işlem
          </motion.button>
        </div>
      </header>

      {transactions.length === 0 ? (
        <div className="empty-state">
          <div className="empty-orb" />
          <p>Henüz işlem yok.</p>
          <button type="button" className="btn primary" onClick={() => setSheetOpen(true)}><Icon name="plus" size={16} /> İlk işlemi ekle</button>
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
                    <span className="muted">{g.currency} · {g.rows.length} işlem{g.sells > 0 && ` (${g.buys} alış, ${g.sells} satış)`}</span>
                    <span className="grow" />
                    <span className="num muted">{num(g.netQuantity, 0)} adet</span>
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
                                <th className="left">Not</th><th>Tarih</th><th>Yön</th><th>Adet</th><th>Fiyat</th><th>Masraf</th>
                                <th>Tutar</th><th className="sep">Kur</th><th>Kur tarihi</th><th>Kaynak</th><th className="sep">Tutar ₺</th><th />
                              </tr>
                            </thead>
                            <tbody>
                              <AnimatePresence initial={false}>
                                {g.rows.map((t, i) => (
                                  <TxnRow key={t.id} t={t} index={i} editing={editing} setEditing={setEditing} busy={busy} onSave={saveEdit} onDelete={remove} />
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

      <Sheet open={sheetOpen} onClose={() => setSheetOpen(false)} title="Yeni işlem">
        <TransactionForm instruments={instruments} portfolioId={portfolioId} onChanged={onChanged} />
      </Sheet>
    </section>
  );
}
