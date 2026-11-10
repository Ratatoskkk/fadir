// Number formatting (SPEC §9): tr-TR by default (1.234,56, TRY as ₺). The rebuilt
// interface switches the locale with `setFormatLocale` when the viewer's language changes.
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
  GBP: "£",
};

let locale = "tr-TR";
/** Turkish writes the percent sign first (%9,00); the other languages after (9.00%). */
let percentFirst = true;

const nf = (min, max) =>
  new Intl.NumberFormat(locale, {
    minimumFractionDigits: min,
    maximumFractionDigits: max,
  });

let nf2 = nf(2, 2);
let nf0 = nf(0, 0);
let nf1 = nf(1, 1);
let nf4 = nf(2, 4);
let nfRate = nf(4, 4);
const compactNf = () => new Intl.NumberFormat(locale, { notation: "compact", maximumFractionDigits: 2 });
let nfCompact = compactNf();

// Date formatters are built once for the same reason the number formatters are:
// constructing an Intl formatter is far more expensive than using one, and these run per
// table cell, per chart tick and per tooltip render.
const df = (options) => new Intl.DateTimeFormat(locale, options);

let dfShort = df({ day: "2-digit", month: "2-digit" });
let dfFull = df({ day: "2-digit", month: "2-digit", year: "numeric" });
let dfClock = df({ hour: "2-digit", minute: "2-digit", second: "2-digit" });

export function setFormatLocale(next) {
  if (!next || next === locale) return;
  locale = next;
  percentFirst = next.toLowerCase().startsWith("tr");
  nf2 = nf(2, 2);
  nf0 = nf(0, 0);
  nf1 = nf(1, 1);
  nf4 = nf(2, 4);
  nfRate = nf(4, 4);
  nfCompact = compactNf();
  dfShort = df({ day: "2-digit", month: "2-digit" });
  dfFull = df({ day: "2-digit", month: "2-digit", year: "numeric" });
  dfClock = df({ hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export const formatLocale = () => locale;

const percent = (sign, body) => (percentFirst ? `${sign}%${body}` : `${sign}${body}%`);

export function num(value, digits = 2) {
  const n = Number(value);
  if (value === null || value === undefined || Number.isNaN(n)) return "—";
  return digits === 0 ? nf0.format(n) : digits === 1 ? nf1.format(n) : digits === 4 ? nf4.format(n) : nf2.format(n);
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
  return percent(sign, num(Math.abs(pct), digits));
}

/** An exchange rate, always with four decimals so a column lines up. */
export function fxRate(value) {
  const n = Number(value);
  if (value === null || value === undefined || Number.isNaN(n)) return "—";
  return nfRate.format(n);
}

/** Lira in the viewer's short form (₺1.5M, ₺1,5 Mn), for chart axes. */
export function compactMoney(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "";
  return `₺${nfCompact.format(n)}`;
}

/** An unsigned share of a whole, already in percent (81.5%, %81,5). */
export function share(value, digits = 1) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  return percent("", num(n, digits));
}

/** A raw percentage value (not a ratio). */
export function pct(value, digits = 2) {
  if (value === null || value === undefined) return "—";
  const n = Number(value);
  const sign = n > 0 ? "+" : n < 0 ? "−" : "";
  return percent(sign, num(Math.abs(n), digits));
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
