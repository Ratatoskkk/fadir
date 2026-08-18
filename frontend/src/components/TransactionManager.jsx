// Layout item 5 (SPEC §9): transaction manager with inline add/edit/delete and
// currency-aware inputs. Covers US-6.1 (add, FX auto-fetched with manual override),
// US-6.2 (delete, everything recomputes) and US-6.3 (record a SELL).

import { Fragment, useMemo, useState } from "react";
import { api } from "../api.js";
import { fullDate, money, num } from "../format.js";

const BLANK = {
  ticker: "",
  trade_date: new Date().toISOString().slice(0, 10),
  side: "BUY",
  quantity: "",
  price_native: "",
  fees_native: "0",
  fx_rate_override: "",
  note: "",
};

function currencyOf(instruments, ticker) {
  return instruments.find((i) => i.ticker === ticker)?.currency ?? "";
}

/**
 * Bucket transactions by ticker and total each group.
 *
 * Net quantity is signed by side, so a group containing sells reads correctly rather
 * than inflating the holding. Totals are summed in TRY as well as native currency,
 * since those are the two figures worth comparing across a group.
 */
function groupByTicker(transactions) {
  const groups = new Map();

  for (const txn of transactions) {
    let group = groups.get(txn.ticker);
    if (!group) {
      group = {
        ticker: txn.ticker,
        currency: txn.currency,
        rows: [],
        netQuantity: 0,
        totalNative: 0,
        totalTry: 0,
        buys: 0,
        sells: 0,
      };
      groups.set(txn.ticker, group);
    }

    const sign = txn.side === "SELL" ? -1 : 1;
    group.rows.push(txn);
    group.netQuantity += sign * Number(txn.quantity);
    group.totalNative += sign * Number(txn.total_native);
    group.totalTry += sign * Number(txn.total_try);
    if (txn.side === "SELL") group.sells += 1;
    else group.buys += 1;
  }

  for (const group of groups.values()) {
    // Newest first inside each group, matching the ungrouped ordering.
    group.rows.sort((a, b) => b.trade_date.localeCompare(a.trade_date) || b.id - a.id);
  }

  // Largest TRY commitment first; it is the most useful reading order.
  return [...groups.values()].sort((a, b) => b.totalTry - a.totalTry);
}

export default function TransactionManager({ transactions, instruments, onChanged }) {
  const [form, setForm] = useState(BLANK);
  const [editing, setEditing] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [collapsed, setCollapsed] = useState({});

  // Functional update: typing quickly in two fields must not have the second overwrite
  // the first from a stale snapshot.
  const set = (key) => (event) => {
    const { value } = event.target;
    setForm((prev) => ({ ...prev, [key]: value }));
  };
  const selectedCurrency = currencyOf(instruments, form.ticker);

  const groups = useMemo(() => groupByTicker(transactions), [transactions]);

  const toggleGroup = (ticker) =>
    setCollapsed((prev) => ({ ...prev, [ticker]: !prev[ticker] }));

  async function submit(event) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const payload = {
        ticker: form.ticker,
        trade_date: form.trade_date,
        side: form.side,
        quantity: form.quantity,
        price_native: form.price_native,
        fees_native: form.fees_native || "0",
        note: form.note || null,
      };
      // Only send an override when one was actually typed — otherwise the server
      // auto-fetches the published rate for the trade date (US-6.1).
      if (form.fx_rate_override.trim()) payload.fx_rate_override = form.fx_rate_override;

      await api.createTransaction(payload);
      setForm({ ...BLANK, ticker: form.ticker, trade_date: form.trade_date });
      await onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function saveEdit(id) {
    setError(null);
    setBusy(true);
    try {
      const payload = {
        quantity: editing.quantity,
        price_native: editing.price_native,
        fees_native: editing.fees_native || "0",
        trade_date: editing.trade_date,
        side: editing.side,
      };
      if (editing.fx_rate_override?.trim()) {
        payload.fx_rate_override = editing.fx_rate_override;
      }
      await api.updateTransaction(id, payload);
      setEditing(null);
      await onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function remove(txn) {
    const label = `${txn.ticker} · ${fullDate(txn.trade_date)} · ${num(txn.quantity, 0)} adet`;
    if (!window.confirm(`Bu işlem silinsin mi?\n\n${label}\n\nFIFO lotları ve geçmiş seri yeniden hesaplanacak.`)) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.deleteTransaction(txn.id);
      await onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel" id="islemler">
      <div className="panel-head">
        <h2>İşlemler</h2>
        <span className="updated">{transactions.length} kayıt</span>
      </div>

      <form className="txn-form" onSubmit={submit}>
        <div className="field">
          <label htmlFor="f-ticker">Enstrüman</label>
          <select id="f-ticker" value={form.ticker} onChange={set("ticker")} required>
            <option value="">seçin…</option>
            {instruments.map((i) => (
              <option key={i.ticker} value={i.ticker}>
                {i.ticker} ({i.currency})
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label htmlFor="f-date">Tarih</label>
          <input id="f-date" type="date" value={form.trade_date} onChange={set("trade_date")} required />
        </div>

        <div className="field">
          <label htmlFor="f-side">Yön</label>
          <select id="f-side" value={form.side} onChange={set("side")}>
            <option value="BUY">ALIŞ</option>
            <option value="SELL">SATIŞ</option>
          </select>
        </div>

        <div className="field">
          <label htmlFor="f-qty">Adet</label>
          <input
            id="f-qty"
            type="number"
            step="any"
            min="0.00000001"
            value={form.quantity}
            onChange={set("quantity")}
            required
          />
        </div>

        <div className="field">
          <label htmlFor="f-price">Fiyat {selectedCurrency && `(${selectedCurrency})`}</label>
          <input
            id="f-price"
            type="number"
            step="any"
            min="0"
            value={form.price_native}
            onChange={set("price_native")}
            required
          />
        </div>

        <div className="field">
          <label htmlFor="f-fees">Masraf {selectedCurrency && `(${selectedCurrency})`}</label>
          <input id="f-fees" type="number" step="any" min="0" value={form.fees_native} onChange={set("fees_native")} />
        </div>

        <div className="field">
          <label htmlFor="f-fx">Kur (opsiyonel)</label>
          <input
            id="f-fx"
            type="number"
            step="any"
            min="0"
            placeholder="otomatik"
            value={form.fx_rate_override}
            onChange={set("fx_rate_override")}
          />
          <span className="hint">boşsa işlem gününün kuru çekilir</span>
        </div>

        <div className="field wide">
          <label htmlFor="f-note">Not</label>
          <input id="f-note" type="text" value={form.note} onChange={set("note")} />
        </div>

        <button className="btn primary" type="submit" disabled={busy || !form.ticker}>
          {busy ? <span className="spinner" /> : "Ekle"}
        </button>
      </form>

      {error && <div className="form-error">⚠ {error}</div>}

      <div className="table-wrap freeze-first">
        <table>
          <thead>
            <tr>
              <th scope="col">Enstrüman / not</th>
              <th scope="col">Tarih</th>
              <th scope="col">Yön</th>
              <th scope="col">Adet</th>
              <th scope="col">Fiyat</th>
              <th scope="col">Masraf</th>
              <th scope="col">Tutar (yerel)</th>
              <th scope="col" className="group-sep">Kur</th>
              <th scope="col">Kur tarihi</th>
              <th scope="col">Kaynak</th>
              <th scope="col" className="group-sep">Tutar ₺</th>
              <th scope="col" />
            </tr>
          </thead>

          <tbody>
            {transactions.length === 0 && (
              <tr>
                <td colSpan={12} className="empty">
                  Henüz işlem yok.
                </td>
              </tr>
            )}

            {groups.map((group) => (
              <Fragment key={group.ticker}>
                <tr
                  className="group-head"
                  onClick={() => toggleGroup(group.ticker)}
                  title="Grubu aç/kapat"
                >
                  <td>
                    <div className="group-title">
                      <span className="group-toggle" aria-hidden="true">
                        {collapsed[group.ticker] ? "▶" : "▼"}
                      </span>
                      <span className="sym">{group.ticker}</span>
                      <span className="group-meta">
                        {group.currency} · {group.rows.length} işlem
                        {group.sells > 0 && ` (${group.buys} alış, ${group.sells} satış)`}
                      </span>
                    </div>
                  </td>
                  <td colSpan={2} className="group-summary" />
                  <td className="num group-summary">{num(group.netQuantity, 0)}</td>
                  <td colSpan={2} className="group-summary" />
                  <td className="num group-summary">
                    {money(group.totalNative, group.currency)}
                  </td>
                  <td colSpan={3} className="group-summary group-sep" />
                  <td className="num group-summary group-sep">{money(group.totalTry)}</td>
                  <td />
                </tr>

                {!collapsed[group.ticker] &&
                  group.rows.map((t) => {
                    const isEditing = editing?.id === t.id;
                    return (
                <tr key={t.id} className="group-row">
                  {/* The ticker lives on the group header now, so this cell gives the
                      note a home instead of repeating it on every row. */}
                  <td>
                    <span className="name">{t.note || "—"}</span>
                  </td>

                  <td className="num">
                    {isEditing ? (
                      <input
                        className="small"
                        type="date"
                        value={editing.trade_date}
                        onChange={(e) => setEditing({ ...editing, trade_date: e.target.value })}
                      />
                    ) : (
                      fullDate(t.trade_date)
                    )}
                  </td>

                  <td>
                    {isEditing ? (
                      <select
                        className="small"
                        value={editing.side}
                        onChange={(e) => setEditing({ ...editing, side: e.target.value })}
                      >
                        <option value="BUY">ALIŞ</option>
                        <option value="SELL">SATIŞ</option>
                      </select>
                    ) : (
                      <span className={`badge ${t.side === "BUY" ? "open" : "warn"}`}>
                        {t.side === "BUY" ? "alış" : "satış"}
                      </span>
                    )}
                  </td>

                  <td className="num">
                    {isEditing ? (
                      <input
                        className="small"
                        type="number"
                        step="any"
                        style={{ width: 80 }}
                        value={editing.quantity}
                        onChange={(e) => setEditing({ ...editing, quantity: e.target.value })}
                      />
                    ) : (
                      num(t.quantity, 0)
                    )}
                  </td>

                  <td className="num">
                    {isEditing ? (
                      <input
                        className="small"
                        type="number"
                        step="any"
                        style={{ width: 90 }}
                        value={editing.price_native}
                        onChange={(e) => setEditing({ ...editing, price_native: e.target.value })}
                      />
                    ) : (
                      money(t.price_native, t.currency)
                    )}
                  </td>

                  <td className="num">{money(t.fees_native, t.currency)}</td>
                  <td className="num">{money(t.total_native, t.currency)}</td>

                  <td className="num group-sep">
                    {isEditing ? (
                      <input
                        className="small"
                        type="number"
                        step="any"
                        style={{ width: 90 }}
                        placeholder={num(t.fx_rate_to_try, 4)}
                        value={editing.fx_rate_override ?? ""}
                        onChange={(e) => setEditing({ ...editing, fx_rate_override: e.target.value })}
                      />
                    ) : (
                      num(t.fx_rate_to_try, 4)
                    )}
                  </td>

                  <td className="num">
                    {fullDate(t.fx_rate_date)}{" "}
                    {t.fx_carried_forward && (
                      <span className="badge warn" title="İşlem gününde kur yayınlanmamış; önceki yayın taşındı">
                        taşındı
                      </span>
                    )}
                  </td>

                  <td>
                    {t.fx_provider === "manual" ? (
                      <span className="badge warn">manuel</span>
                    ) : t.fx_provider.includes("*") ? (
                      <span className="badge info" title={t.fx_provider}>
                        çapraz
                      </span>
                    ) : (
                      <span className="name">{t.fx_provider}</span>
                    )}
                  </td>

                  <td className="num group-sep">{money(t.total_try)}</td>

                  <td>
                    <div className="row-actions">
                      {isEditing ? (
                        <>
                          <button className="btn small primary" onClick={() => saveEdit(t.id)} disabled={busy}>
                            kaydet
                          </button>
                          <button className="btn small ghost" onClick={() => setEditing(null)} disabled={busy}>
                            vazgeç
                          </button>
                        </>
                      ) : (
                        <>
                          <button
                            className="btn small ghost"
                            onClick={() =>
                              setEditing({
                                id: t.id,
                                trade_date: t.trade_date,
                                side: t.side,
                                quantity: t.quantity,
                                price_native: t.price_native,
                                fees_native: t.fees_native,
                                fx_rate_override: "",
                              })
                            }
                            disabled={busy}
                          >
                            düzenle
                          </button>
                          <button className="btn small danger" onClick={() => remove(t)} disabled={busy}>
                            sil
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
                    );
                  })}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>

      <p className="footnote">
        Kur alanı boş bırakılırsa işlem gününün yayınlanmış kuru otomatik çekilir; hafta
        sonu ve tatil günlerinde en yakın önceki yayın taşınır ve “taşındı” olarak
        işaretlenir. Elle kur girilirse kaynak <em>manuel</em> olarak kaydedilir.
      </p>
    </section>
  );
}
