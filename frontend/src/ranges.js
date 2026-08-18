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
