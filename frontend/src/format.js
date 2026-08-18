// Turkish number formatting (SPEC §9): 1.234,56 with tr-TR locale and TRY as ₺.
//
// Money arrives from the API as strings to preserve Decimal exactness. Formatting is the
// only place a Number is created, and only for display — nothing is ever computed from
// these values.

const CURRENCY_SYMBOL = {
  TRY: "₺",
  USD: "$",
  EUR: "€",
  SEK: "kr",
  TWD: "NT$",
};

const nf = (min, max) =>
  new Intl.NumberFormat("tr-TR", {
    minimumFractionDigits: min,
    maximumFractionDigits: max,
  });

const nf2 = nf(2, 2);
const nf0 = nf(0, 0);
const nf4 = nf(2, 4);

// Date formatters are built once for the same reason the number formatters are:
// constructing an Intl formatter is far more expensive than using one, and these run per
// table cell, per chart tick and per tooltip render.
const df = (options) => new Intl.DateTimeFormat("tr-TR", options);

const dfShort = df({ day: "2-digit", month: "2-digit" });
const dfFull = df({ day: "2-digit", month: "2-digit", year: "numeric" });
const dfClock = df({ hour: "2-digit", minute: "2-digit", second: "2-digit" });

export function num(value, digits = 2) {
  const n = Number(value);
  if (value === null || value === undefined || Number.isNaN(n)) return "—";
  return digits === 0 ? nf0.format(n) : digits === 4 ? nf4.format(n) : nf2.format(n);
}

export function money(value, currency = "TRY", digits = 2) {
  if (value === null || value === undefined) return "—";
  const symbol = CURRENCY_SYMBOL[currency] ?? currency;
  const formatted = num(value, digits);
  // Turkish convention puts the lira sign before the amount; other symbols follow suit
  // for column alignment.
  return `${symbol}${formatted}`;
}

/** Signed money, always with an explicit + or − so colour is never the only signal. */
export function signedMoney(value, currency = "TRY", digits = 2) {
  if (value === null || value === undefined) return "—";
  const n = Number(value);
  const sign = n > 0 ? "+" : n < 0 ? "−" : "";
  const symbol = CURRENCY_SYMBOL[currency] ?? currency;
  return `${sign}${symbol}${num(Math.abs(n), digits)}`;
}

/** A return *ratio* (1.09) rendered as a signed percentage (+9,00%). */
export function ratioPct(value, digits = 2) {
  if (value === null || value === undefined) return "—";
  const pct = (Number(value) - 1) * 100;
  const sign = pct > 0 ? "+" : pct < 0 ? "−" : "";
  return `${sign}%${num(Math.abs(pct), digits)}`;
}

/** A raw percentage value (not a ratio). */
export function pct(value, digits = 2) {
  if (value === null || value === undefined) return "—";
  const n = Number(value);
  const sign = n > 0 ? "+" : n < 0 ? "−" : "";
  return `${sign}%${num(Math.abs(n), digits)}`;
}

/** Accessibility (SPEC §9): colour must not be the sole PnL indicator. */
export function arrow(value) {
  const n = Number(value);
  if (!Number.isFinite(n) || n === 0) return "→";
  return n > 0 ? "▲" : "▼";
}

export function toneOf(value) {
  const n = Number(value);
  if (!Number.isFinite(n) || n === 0) return "flat";
  return n > 0 ? "up" : "down";
}

export function shortDate(iso) {
  if (!iso) return "—";
  return dfShort.format(new Date(iso));
}

export function fullDate(iso) {
  if (!iso) return "—";
  return dfFull.format(new Date(iso));
}

export function clockTime(date) {
  return dfClock.format(date);
}
