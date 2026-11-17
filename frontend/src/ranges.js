// The chart's range selector, kept in its own module so App.jsx can read it without
// importing HistoryChart.jsx — that import would pull Recharts into the initial bundle
// and defeat the lazy load.

export const RANGES = [
  { key: "1G", label: "1G", days: 1, intraday: true },
  { key: "1H", label: "1H", days: 7 },
  { key: "1M", label: "1A", days: 30 },
  { key: "3M", label: "3A", days: 90 },
  { key: "6M", label: "6A", days: 180 },
  { key: "ALL", label: "Tümü", days: null },
];

export const isIntradayRange = (range) =>
  RANGES.find((r) => r.key === range)?.intraday === true;

/** Every range but "Tümü" covers a fixed window, so it can be slid back through time. */
export const isPannable = (range) => RANGES.find((r) => r.key === range)?.days != null;

export const rangeDays = (range) => RANGES.find((r) => r.key === range)?.days ?? null;

/** The Portfolio's first trade date (ISO), or null before its transactions load. */
export const firstTradeDate = (transactions) =>
  (transactions ?? []).reduce((first, t) => (t?.trade_date && (!first || t.trade_date < first) ? t.trade_date : first), null);

const isoOf = (d) => d.toISOString().slice(0, 10);

/**
 * The [from, to] window for a range, slid `pan` whole windows into the past.
 *
 * Paging by a whole window rather than a fixed number of days keeps each step the same
 * size as what is on screen, so "back" always means "the previous 1A", never a partial
 * overlap that makes two adjacent views hard to compare. "Tümü" leaves `from` to the
 * server, which starts at the Portfolio's own first trade.
 */
export function rangeWindow(range, pan = 0, inception = null) {
  const days = rangeDays(range);
  if (days === null) return { from: undefined, to: undefined };

  const to = new Date();
  to.setDate(to.getDate() - days * pan);
  const from = new Date(to);
  from.setDate(from.getDate() - days);

  const fromIso = isoOf(from);
  return {
    from: inception && fromIso < inception ? inception : fromIso,
    to: pan > 0 ? isoOf(to) : undefined, // live window stays open-ended at today
  };
}

/** True once the window would sit entirely before the first trade. */
export function panExhausted(range, pan, inception = null) {
  const days = rangeDays(range);
  if (days === null || !inception) return true;
  const to = new Date();
  to.setDate(to.getDate() - days * pan);
  return isoOf(to) <= inception;
}
