// Layout item 3 (SPEC §9): sortable positions table with per-row native PnL and TRY PnL
// as *separate columns* — the two are never blended into one figure.

import { useMemo, useState } from "react";
import { useFlash } from "../flash.js";
import { arrow, fullDate, money, num, ratioPct, signedMoney, toneOf } from "../format.js";

const COLUMNS = [
  { key: "ticker", label: "Enstrüman", align: "left" },
  { key: "quantity", label: "Adet" },
  { key: "price_native", label: "Fiyat" },
  { key: "average_purchase_price_native", label: "Ort. alış" },
  { key: "cost_native", label: "Maliyet", group: true },
  { key: "market_value_native", label: "Değer" },
  { key: "pnl_native", label: "K/Z (yerel)" },
  { key: "local_return", label: "Yerel get." },
  { key: "fx_rate_to_try", label: "Kur", group: true },
  { key: "fx_return", label: "Kur get." },
  { key: "cost_try", label: "Maliyet ₺", group: true },
  { key: "market_value_try", label: "Değer ₺" },
  { key: "pnl_try", label: "K/Z ₺" },
  { key: "daily_pnl_try", label: "Günlük ₺", group: true },
  { key: "total_return", label: "Toplam get." },
];

function sortValue(position, key) {
  switch (key) {
    case "ticker":
      return position.ticker;
    case "local_return":
    case "fx_return":
    case "total_return":
      return position.attribution[key] === null ? -Infinity : Number(position.attribution[key]);
    case "daily_pnl_try":
      // Rows with no previous session sort last rather than as a zero move.
      return position.daily?.available ? Number(position.daily.pnl_try) : -Infinity;
    case "average_purchase_price_native":
      return position.average_purchase_price_native === null
        ? -Infinity
        : Number(position.average_purchase_price_native);
    default:
      return Number(position[key]);
  }
}

/** The live quote. Its own component so the flash hook is per row, not per table. */
function PriceCell({ position }) {
  const flash = useFlash(position.price_native);
  if (!position.ok) return <td className="num">—</td>;
  return (
    <td className={`num ${flash}`}>{money(position.price_native, position.currency)}</td>
  );
}

/** Day's move in TRY, with the price/FX split and the session compared against. */
function DailyCell({ daily, currency }) {
  if (!daily?.available) {
    return (
      <td className="num group-sep" title="Karşılaştırılacak önceki seans yok">
        —
      </td>
    );
  }

  const title = [
    `Önceki seans: ${fullDate(daily.reference_date)}`,
    `Fiyat etkisi: ${signedMoney(daily.price_effect_try)}`,
    `Kur etkisi: ${signedMoney(daily.fx_effect_try)}`,
    `Yerel: ${signedMoney(daily.pnl_native, currency)}`,
  ].join("\n");

  return (
    <td className={`num group-sep ${toneOf(daily.pnl_try)}`} title={title}>
      <span aria-hidden="true">{arrow(daily.pnl_try)}</span>{" "}
      {signedMoney(daily.pnl_try)}
      {daily.return_ratio !== null && (
        <span className="daily-pct">{ratioPct(daily.return_ratio)}</span>
      )}
    </td>
  );
}

export default function PositionsTable({ positions, focusTickers = [], onFocusTicker }) {
  const [sort, setSort] = useState({ key: "market_value_try", dir: "desc" });

  const sorted = useMemo(() => {
    const rows = [...positions];
    rows.sort((a, b) => {
      const av = sortValue(a, sort.key);
      const bv = sortValue(b, sort.key);
      let cmp;
      if (typeof av === "string" || typeof bv === "string") {
        cmp = String(av).localeCompare(String(bv), "tr");
      } else {
        cmp = av === bv ? 0 : av < bv ? -1 : 1;
      }
      return sort.dir === "asc" ? cmp : -cmp;
    });
    return rows;
  }, [positions, sort]);

  const toggle = (key) =>
    setSort((prev) =>
      prev.key === key
        ? { key, dir: prev.dir === "asc" ? "desc" : "asc" }
        : { key, dir: key === "ticker" ? "asc" : "desc" },
    );

  // Only positions with a usable price contribute, matching the server's totals: a
  // failed symbol must not read as a position worth zero.
  const totals = useMemo(
    () =>
      positions.reduce(
        (acc, p) => {
          if (!p.ok) return acc;
          acc.cost += Number(p.cost_try);
          acc.value += Number(p.market_value_try);
          acc.pnl += Number(p.pnl_try);
          if (p.daily?.available) acc.daily += Number(p.daily.pnl_try);
          return acc;
        },
        { cost: 0, value: 0, pnl: 0, daily: 0 },
      ),
    [positions],
  );

  return (
    <section className="panel" id="pozisyonlar">
      <div className="panel-head">
        <h2>Pozisyonlar</h2>
        <span className="updated">
          Yerel ve TRY kâr/zarar ayrı sütunlarda — kur etkisi fiyat etkisine karışmaz
        </span>
      </div>

      {/* freeze-first keeps the instrument column pinned while the numbers scroll. */}
      <div className="table-wrap freeze-first">
        <table>
          <caption className="sr-only">
            Pozisyon listesi; yerel para birimi ve TRY bazında kâr/zarar ayrı sütunlarda.
            Enstrüman sütunu yatay kaydırmada sabit kalır.
          </caption>
          <thead>
            <tr>
              {COLUMNS.map((col) => (
                <th
                  key={col.key}
                  className={`sortable ${col.group ? "group-sep" : ""}`}
                  onClick={() => toggle(col.key)}
                  aria-sort={
                    sort.key === col.key
                      ? sort.dir === "asc"
                        ? "ascending"
                        : "descending"
                      : "none"
                  }
                  scope="col"
                >
                  {col.label}
                  {sort.key === col.key && (
                    <span className="sort-mark" aria-hidden="true">
                      {sort.dir === "asc" ? "↑" : "↓"}
                    </span>
                  )}
                </th>
              ))}
            </tr>
          </thead>

          <tbody>
            {sorted.map((p) => {
              const a = p.attribution;
              return (
                <tr key={p.ticker}>
                  <td>
                    <div className="ticker">
                      <span className="sym">
                        <button
                          type="button"
                          className={`ticker-btn ${focusTickers.includes(p.ticker) ? "on" : ""}`}
                          onClick={() => onFocusTicker?.(p.ticker)}
                          aria-pressed={focusTickers.includes(p.ticker)}
                          title={
                            focusTickers.includes(p.ticker)
                              ? "Grafiği tüm portföye döndür"
                              : `Grafiği yalnızca ${p.ticker} için göster`
                          }
                        >
                          {p.ticker}
                        </button>{" "}
                        <span className="badges">
                          <span className={`badge ${p.session === "open" ? "open" : "closed"}`}>
                            {p.session === "open" ? "açık" : "kapalı"}
                          </span>
                          {!p.ok && <span className="badge err">veri yok</span>}
                          {p.fx_triangulated && (
                            <span
                              className="badge info"
                              title={`Kur doğrudan yayınlanmıyor; USD üzerinden çapraz hesaplandı (${p.fx_provider})`}
                            >
                              çapraz kur
                            </span>
                          )}
                          {p.fx_provider === "manual" && (
                            <span className="badge warn">manuel kur</span>
                          )}
                        </span>
                      </span>
                      <span className="name">
                        {p.name} · {p.currency} ·{" "}
                        {p.ok
                          ? p.session === "open"
                            ? "canlı"
                            : `son işlem ${fullDate(p.price_date)}`
                          : p.error}
                      </span>
                    </div>
                  </td>

                  <td className="num">{num(p.quantity, 0)}</td>
                  <PriceCell position={p} />
                  <td className="num">
                    {p.average_purchase_price_native === null
                      ? "—"
                      : money(p.average_purchase_price_native, p.currency)}
                  </td>

                  <td className="num group-sep">{money(p.cost_native, p.currency)}</td>
                  <td className="num">{p.ok ? money(p.market_value_native, p.currency) : "—"}</td>
                  <td className={`num ${toneOf(p.pnl_native)}`}>
                    {p.ok ? (
                      <>
                        <span aria-hidden="true">{arrow(p.pnl_native)}</span>{" "}
                        {signedMoney(p.pnl_native, p.currency)}
                      </>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className={`num ${toneOf(Number(a.local_return) - 1)}`}>
                    {ratioPct(a.local_return)}
                  </td>

                  <td className="num group-sep" title={`Kaynak: ${p.fx_provider}`}>
                    {num(p.fx_rate_to_try, 4)}
                  </td>
                  <td className={`num ${toneOf(Number(a.fx_return) - 1)}`}>
                    {ratioPct(a.fx_return)}
                  </td>

                  <td className="num group-sep">{money(p.cost_try)}</td>
                  <td className="num">{p.ok ? money(p.market_value_try) : "—"}</td>
                  <td className={`num ${toneOf(p.pnl_try)}`}>
                    {p.ok ? (
                      <>
                        <span aria-hidden="true">{arrow(p.pnl_try)}</span>{" "}
                        {signedMoney(p.pnl_try)}
                      </>
                    ) : (
                      "—"
                    )}
                  </td>
                  <DailyCell daily={p.daily} currency={p.currency} />

                  <td className={`num ${toneOf(Number(a.total_return) - 1)}`}>
                    {ratioPct(a.total_return)}
                  </td>
                </tr>
              );
            })}
          </tbody>

          <tfoot>
            <tr>
              <td>Toplam</td>
              <td colSpan={6} />
              <td className="num group-sep" colSpan={3} />
              <td className="num group-sep">{money(totals.cost)}</td>
              <td className="num">{money(totals.value)}</td>
              <td className={`num ${toneOf(totals.pnl)}`}>
                <span aria-hidden="true">{arrow(totals.pnl)}</span> {signedMoney(totals.pnl)}
              </td>
              <td className={`num group-sep ${toneOf(totals.daily)}`}>
                <span aria-hidden="true">{arrow(totals.daily)}</span> {signedMoney(totals.daily)}
              </td>
              <td className={`num ${toneOf(totals.pnl)}`}>
                {totals.cost ? ratioPct(totals.value / totals.cost) : "—"}
              </td>
            </tr>
          </tfoot>
        </table>
      </div>

      <p className="footnote">
        <strong>Ort. alış</strong>, Stock Group içindeki tüm alışların miktar ağırlıklı
        ömür boyu ortalamasıdır; alış masrafları sayılır, satışlar sayılmaz. Grup tamamen
        satılsa da değer kalır.{" "}
        Kapalı borsalardaki fiyatlar son seans kapanışıdır, canlı değildir. “Çapraz kur”
        rozeti, Yahoo’da doğrudan TRY paritesi bulunmayan para birimleri için kurun USD
        üzerinden hesaplandığını gösterir. <strong>Enstrüman adına tıklayın</strong>:
        grafik yalnızca o hisseyi gösterir, tekrar tıklayınca portföye döner.{" "}
        <strong>Günlük ₺</strong> sütunu bir önceki seansa göre değişimdir; borsalar farklı
        saatlerde kapandığı için karşılaştırılan seans satır bazında değişebilir — hücrenin
        üzerine gelin.
      </p>
    </section>
  );
}
