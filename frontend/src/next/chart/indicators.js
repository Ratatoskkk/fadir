// The trend filters behind the Ticker view's indicator panes, written to match the
// EasyLanguage cases they come from:
//
//   Case 50  Average(Close, N1*5) - Average(Close, N1*5)[1]  vs  N2*5
//   Case 51  VHF(N1*5, High, Low, Close)                    vs  N2*5
//   Case 52  ADX(25)                                         vs  N2*5
//
// Long when the left side is above N2*5, short when below. Every series is the length
// of its input, with null wherever the lookback is not yet filled.

export function sma(values, length) {
  const out = new Array(values.length).fill(null);
  let sum = 0;
  for (let i = 0; i < values.length; i++) {
    sum += values[i];
    if (i >= length) sum -= values[i - length];
    if (i >= length - 1) out[i] = sum / length;
  }
  return out;
}

/** Case 50: one-bar change of the simple moving average. */
export function maSlope(close, length) {
  const avg = sma(close, length);
  return avg.map((v, i) => (v === null || i === 0 || avg[i - 1] === null ? null : v - avg[i - 1]));
}

/**
 * Case 51: Vertical Horizontal Filter. Range of the window (highest high less lowest
 * low, since the call passes High and Low) over the sum of absolute close-to-close moves.
 */
export function vhf(high, low, close, length) {
  const out = new Array(close.length).fill(null);
  for (let i = length; i < close.length; i++) {
    let hi = -Infinity, lo = Infinity, path = 0;
    for (let j = i - length + 1; j <= i; j++) {
      if (high[j] > hi) hi = high[j];
      if (low[j] < lo) lo = low[j];
      path += Math.abs(close[j] - close[j - 1]);
    }
    out[i] = path > 0 ? (hi - lo) / path : null;
  }
  return out;
}

/** Case 52: Wilder's ADX. The first value lands at bar 2·length − 1. */
export function adx(high, low, close, length) {
  const n = close.length;
  const out = new Array(n).fill(null);
  if (n <= 2 * length) return out;
  let tr = 0, plus = 0, minus = 0, dxSum = 0, value = null;
  for (let i = 1; i < n; i++) {
    const up = high[i] - high[i - 1];
    const down = low[i - 1] - low[i];
    const range = Math.max(high[i] - low[i], Math.abs(high[i] - close[i - 1]), Math.abs(low[i] - close[i - 1]));
    const pdm = up > down && up > 0 ? up : 0;
    const mdm = down > up && down > 0 ? down : 0;
    if (i <= length) {
      tr += range; plus += pdm; minus += mdm;
      if (i < length) continue;
    } else {
      tr += range - tr / length;
      plus += pdm - plus / length;
      minus += mdm - minus / length;
    }
    const pdi = tr > 0 ? (100 * plus) / tr : 0;
    const mdi = tr > 0 ? (100 * minus) / tr : 0;
    const dx = pdi + mdi > 0 ? (100 * Math.abs(pdi - mdi)) / (pdi + mdi) : 0;
    if (value === null) {
      dxSum += dx;
      if (i === 2 * length - 1) { value = dxSum / length; out[i] = value; }
    } else {
      value = (value * (length - 1) + dx) / length;
      out[i] = value;
    }
  }
  return out;
}

export const ADX_LENGTH = 25;

export const FILTERS = [
  {
    key: "maSlope",
    label: "ticker.maSlope",
    usesN1: true,
    defaults: { n1: 4, n2: 0 },
    compute: (bars, n1) => maSlope(bars.close, n1 * 5),
    period: (n1) => n1 * 5,
  },
  {
    key: "vhf",
    label: "ticker.vhf",
    usesN1: true,
    defaults: { n1: 6, n2: 0.07 },
    compute: (bars, n1) => vhf(bars.high, bars.low, bars.close, n1 * 5),
    period: (n1) => n1 * 5,
  },
  {
    key: "adx",
    label: "ticker.adx",
    usesN1: false,
    defaults: { n1: 5, n2: 5 },
    compute: (bars) => adx(bars.high, bars.low, bars.close, ADX_LENGTH),
    period: () => ADX_LENGTH,
  },
];

/** "long", "short", or null where the value equals the level or is not yet defined. */
export function filterState(value, level) {
  if (value === null || value === undefined) return null;
  if (value > level) return "long";
  if (value < level) return "short";
  return null;
}
