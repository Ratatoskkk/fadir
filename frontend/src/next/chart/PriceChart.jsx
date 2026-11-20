// Canvas chart for one instrument: the price line on top, one pane per enabled
// indicator below it, all on a shared x axis so the crosshair reads every pane at once.
// Same reasoning as ValueChart for canvas: a poll repaints one canvas, not a DOM tree.
// Panes are separate rather than overlaid because price and indicators never share a
// unit (DESLOP 51: no dual y axes).

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { quote, figure } from "../../format.js";
import Icon from "../ui/Icons.jsx";

const PAD = { left: 64, right: 14, top: 14, bottom: 28 };
const PANE_PLOT = 78;
const NARROW = 560;

const mainHeight = (width) => (width < NARROW ? 280 : 320);
/**
 * One row on a wide chart. On a narrow one the reading takes a row, a compared ticker's
 * reading one more, and the N1/N2 inputs (44px touch targets) a third, shown only while
 * that pane is being edited.
 */
const headHeight = (narrow, pane, compared) => (narrow ? 36 + ((compared && pane.cmp) || pane.histogram ? 32 : 0) + (pane.editing ? 52 : 0) : 40);
/** The smallest round number (1, 2, 2.5 or 5 times a power of ten) at or above `v`. */
const roundUp = (v) => {
  if (!(v > 0)) return 1;
  const mag = 10 ** Math.floor(Math.log10(v));
  return [1, 2, 2.5, 5, 10].map((f) => f * mag).find((x) => x >= v);
};
/** Viewers who ask for less motion get the measuring band without its easing. */
const REDUCED_MOTION = typeof window !== "undefined" && window.matchMedia
  ? window.matchMedia("(prefers-reduced-motion: reduce)")
  : { matches: false };
/** Pixels a press must travel before it measures instead of reading one bar. */
const DRAG_START = 4;
/** How far the measured band's edges close on their bars each 60 Hz frame (0..1). */
const EASE = 0.35;
/** The share of the price area the volume bars may fill, along its bottom. */
const VOLUME_BAND = 0.18;
/** Where each pane's plot starts, below the price and the panes and headers above it. */
const paneTops = (w, panes, compared) => {
  const narrow = w < NARROW;
  let at = PAD.top + mainHeight(w);
  return panes.map((pane) => {
    at += headHeight(narrow, pane, compared);
    const top = at;
    at += PANE_PLOT;
    return top;
  });
};

function niceTicks(min, max, count) {
  const span = max - min || Math.abs(max) || 1;
  const raw = span / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const norm = raw / mag;
  const step = (norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10) * mag;
  const ticks = [];
  // Built from integer multiples so a tick at zero is 0, not −1e-17 printed as "-0".
  for (let k = Math.ceil(min / step); k * step <= max + step * 1e-6; k++) ticks.push(k * step || 0);
  return ticks;
}

function readColors() {
  const s = getComputedStyle(document.documentElement);
  const v = (name) => s.getPropertyValue(name).trim();
  return {
    price: v("--accent"),
    level: v("--text-3"),
    mark: v("--cost"),
    compare: v("--compare"),
    extended: v("--extended"),
    compareExtended: v("--compare-extended"),
    grid: v("--chart-grid"),
    axis: v("--text-3"),
    cross: v("--text-2"),
    bg: v("--surface"),
    up: v("--up"),
    down: v("--down"),
    font: getComputedStyle(document.body).fontFamily,
  };
}

function extent(values, extra = []) {
  let lo = Infinity, hi = -Infinity;
  for (const v of values) {
    if (v === null || v === undefined) continue;
    if (v < lo) lo = v;
    if (v > hi) hi = v;
  }
  for (const v of extra) { if (v < lo) lo = v; if (v > hi) hi = v; }
  if (!Number.isFinite(lo)) return [0, 1];
  const pad = (hi - lo || Math.abs(hi) || 1) * 0.08;
  return [lo - pad, hi + pad];
}

/**
 * `times` and `close` are the shown window; each pane is { key, values, level } over the
 * same window. `formatX` labels the x axis; `onHover` receives a bar index or null.
 */
/**
 * `marks` are flat reference prices ({ value, label }, the average buy). The price axis
 * fits the price alone, so a far-off mark never flattens the line; a mark outside the
 * range is pinned to the edge it lies beyond, with an arrow.
 */
/** `breaks` are bar indices where a skipped stretch of time ends (unselected weeks). */
/**
 * `volume`, per point, is { v, up }: the bar's volume and whether it closed up, drawn as
 * bars along the bottom of the price area. A pane with `histogram` draws its values as a
 * histogram around zero (net buying), coloured by sign, instead of a line.
 */
/**
 * `axisTimes`, when longer than `times`, is the whole x axis: the bars fill its start and
 * the rest is time still to trade (a full session). Its labels fall on the hour.
 * A mark with `fit` widens the price axis to include it; a `dotted` one is drawn faint.
 */
/**
 * `compare` is a second line over the same bars (a compared ticker), drawn in its own
 * colour; when given, `close` and `compare` share one axis labelled by `formatY`.
 */
/**
 * A line may hold null at points where it has no bar of its own (a compared ticker's
 * axis mixes two tickers' bar times); it is drawn straight across them. `closeDash` and
 * `compareDash` flag the points whose incoming connection crosses a closed market,
 * drawn faint and dashed. A pane may carry `cmp` ({ values, dash }), the compared
 * ticker's line for the same formula.
 */
/**
 * `closeExtended` and `compareExtended` flag the points that are pre-market or after-hours
 * bars; the connection into such a point is drawn in the line's extended-hours colour.
 */
/**
 * Dragging across the chart (or Enter, then the arrow keys) measures between two bars:
 * a band across every pane, a line between the two prices, and `measure(a, b)`'s
 * { content, spoken } in a pop-up beside the band, never over it (under the chart when there
 * is no room beside it, and always on a narrow chart); `a`
 * and `b` are point indices in time order. A click, Escape or a new drag clears it, and so
 * does a new `resetKey` (another ticker, range or comparison: the indices mean other bars).
 */
export default function PriceChart({ times, axisTimes = null, volume = null, close, compare = null, closeDash = null, compareDash = null, closeExtended = null, compareExtended = null, formatY = quote, panes, marks = [], breaks = [], heads, formatX, live, onHover, tooltip, measure = null, measureName, measureLabel, resetKey, ariaLabel, roleLabel }) {
  const wrapRef = useRef(null);
  const canvasRef = useRef(null);
  const tipRef = useRef(null);
  const measureRef = useRef(null);
  const st = useRef({
    w: 0, h: 0, dpr: 1, colors: null, hover: null, frame: 0,
    // The measured bars ({ from, to }, as pressed: `to` may be before `from`), the press
    // that may become a drag, and the band as drawn, eased towards its bars.
    sel: null, down: null, dragging: false,
    band: { x0: 0, x1: 0, alpha: 0, at: 0 }, popW: 0,
  }).current;
  const [narrow, setNarrow] = useState(false);
  const [sel, setSelState] = useState(null);
  // Whether a drag is under way: the pop-up ignores the pointer and stays unannounced.
  const [dragging, setDragging] = useState(false);
  // Whether the band leaves no room beside it, so the pop-up sits under the chart. Set
  // from the drawing loop only when that changes.
  const [popBelow, setPopBelow] = useState(false);
  st.setPopBelow = setPopBelow;
  // What the pop-up last showed, kept while it fades out.
  const shown = useRef(null);
  // A press or drag in progress belongs to one pointer; the rest are ignored.
  const endPress = () => {
    st.down = null;
    if (st.dragging) { st.dragging = false; setDragging(false); }
  };
  st.props = { times, axisTimes, volume, close, compare, closeDash, compareDash, closeExtended, compareExtended, formatY, panes, marks, breaks, formatX, live };
  st.onHover = onHover;

  const draw = () => {
    st.frame = 0;
    const canvas = canvasRef.current;
    if (!canvas || !st.colors) return;
    const { times: barTimes, axisTimes: span, volume: vol, close: ys, compare: cs, closeDash: yDash, compareDash: cDash, closeExtended: yExt, compareExtended: cExt, formatY: fy, panes: ps, marks: ms, breaks: bs, formatX: fx, live: isLive } = st.props;
    const { w, h, dpr, colors: c } = st;
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    const n = ys.length;
    if (!n) return;
    const xsT = span && span.length > n ? span : barTimes;
    const slots = xsT.length;

    const plotW = Math.max(10, w - PAD.left - PAD.right);
    const mainH = mainHeight(w);
    const xOf = (i) => PAD.left + (slots > 1 ? (i * plotW) / (slots - 1) : plotW / 2);

    // The measured stretch: its edges ease towards their bars, by elapsed time so the
    // motion is the same at any refresh rate, and the band fades in and out.
    const m = st.sel && st.sel.from !== st.sel.to && Math.max(st.sel.from, st.sel.to) < n ? st.sel : null;
    const band = st.band;
    const now = performance.now();
    const frames = band.at ? Math.min(4, (now - band.at) / (1000 / 60)) : 1;
    const k = REDUCED_MOTION.matches ? 1 : 1 - (1 - EASE) ** frames;
    band.at = now;
    let moving = false;
    if (m) {
      const t0 = xOf(Math.min(m.from, m.to)), t1 = xOf(Math.max(m.from, m.to));
      if (band.alpha <= 0.01) { band.x0 = t0; band.x1 = t1; }
      band.x0 += (t0 - band.x0) * k;
      band.x1 += (t1 - band.x1) * k;
      band.alpha += (1 - band.alpha) * k;
      moving = Math.abs(t0 - band.x0) > 0.3 || Math.abs(t1 - band.x1) > 0.3 || band.alpha < 0.99;
      if (!moving) { band.x0 = t0; band.x1 = t1; band.alpha = 1; }
    } else if (band.alpha > 0.01) {
      band.alpha -= band.alpha * k;
      moving = band.alpha > 0.01;
      if (!moving) band.alpha = 0;
    }
    if (band.alpha > 0) {
      ctx.globalAlpha = 0.1 * band.alpha;
      ctx.fillStyle = c.price;
      ctx.fillRect(band.x0, PAD.top, band.x1 - band.x0, h - PAD.bottom - PAD.top);
      ctx.globalAlpha = 0.55 * band.alpha;
      ctx.strokeStyle = c.price;
      ctx.lineWidth = 1;
      for (const x of [band.x0, band.x1]) {
        ctx.beginPath();
        ctx.moveTo(Math.round(x) + 0.5, PAD.top);
        ctx.lineTo(Math.round(x) + 0.5, h - PAD.bottom);
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
    }
    ctx.font = `11.5px ${c.font}`;
    ctx.lineWidth = 1;

    // `ticks` overrides the evenly spaced ones; nothing is labelled below `floor` (a y).
    const area = (top, height, lo, hi, format, tickCount, { ticks = null, floor = Infinity } = {}) => {
      const yOf = (v) => top + (1 - (v - lo) / (hi - lo || 1)) * height;
      ctx.textAlign = "right";
      ctx.textBaseline = "middle";
      for (const tick of ticks ?? niceTicks(lo, hi, tickCount)) {
        const y = Math.round(yOf(tick)) + 0.5;
        if (y < top - 1 || y > top + height + 1 || y > floor) continue;
        ctx.strokeStyle = c.grid;
        ctx.beginPath();
        ctx.moveTo(PAD.left, y);
        ctx.lineTo(w - PAD.right, y);
        ctx.stroke();
        ctx.fillStyle = c.axis;
        ctx.fillText(format(tick), PAD.left - 10, y);
      }
      return yOf;
    };

    // Each line runs through its non-null points, straight across the nulls between them.
    // Solid connections, then faint dashes across closed markets; each in the line's own
    // colour, or its extended-hours colour into a pre-market or after-hours point.
    const stroke = (values, yOf, color, width, dash = null, ext = null, extColor = color) => {
      ctx.lineJoin = "round";
      ctx.lineCap = "round";
      for (const dashed of dash ? [false, true] : [false]) {
        ctx.globalAlpha = dashed ? 0.45 : 1;
        ctx.setLineDash(dashed ? [2, 4] : []);
        for (const extended of ext ? [false, true] : [false]) {
          // Extended hours are also thinner, so they read apart from the session by more than hue.
          ctx.lineWidth = Math.max(1, (dashed ? width - 0.6 : width) - (extended ? 0.6 : 0));
          ctx.strokeStyle = extended ? extColor : color;
          ctx.beginPath();
          let prev = -1;
          for (let i = 0; i < n; i++) {
            if (values[i] == null) continue;
            if (prev >= 0 && Boolean(dash?.[i]) === dashed && Boolean(ext?.[i]) === extended) {
              ctx.moveTo(xOf(prev), yOf(values[prev]));
              ctx.lineTo(xOf(i), yOf(values[i]));
            }
            prev = i;
          }
          ctx.stroke();
        }
      }
      ctx.setLineDash([]);
      ctx.globalAlpha = 1;
    };
    // Where a line crosses point i: its own value, or between its neighbours.
    const valueAt = (values, i) => {
      if (values[i] != null) return values[i];
      let a = i - 1, b = i + 1;
      while (a >= 0 && values[a] == null) a--;
      while (b < n && values[b] == null) b++;
      if (a < 0 || b >= n) return a >= 0 ? values[a] : b < n ? values[b] : null;
      return values[a] + ((values[b] - values[a]) * (i - a)) / (b - a);
    };

    // A line's value at a fractional x, so a measurement's ends glide with the band.
    const valueAtX = (values, x) => {
      const f = Math.max(0, Math.min(n - 1, ((x - PAD.left) / plotW) * (slots - 1)));
      const lo = valueAt(values, Math.floor(f)), hi = valueAt(values, Math.ceil(f));
      return lo == null || hi == null ? lo ?? hi : lo + (hi - lo) * (f - Math.floor(f));
    };
    // A point on a line: a dot in the line's colour, ringed in the surface colour.
    const drawDot = (x, y, color) => {
      ctx.fillStyle = c.bg;
      ctx.beginPath();
      ctx.arc(x, y, 5, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(x, y, 3.2, 0, Math.PI * 2);
      ctx.fill();
    };

    // Price.
    let [pLo, pHi] = cs ? extent([...ys, ...cs]) : extent(ys, ms.filter((m) => m.fit).map((m) => m.value));
    // Volume bars take the bottom band; the price range drops to make room, so the line
    // runs above them rather than through them.
    if (vol) pLo -= ((pHi - pLo) * VOLUME_BAND) / (1 - VOLUME_BAND);
    const yPrice = area(PAD.top, mainH, pLo, pHi, fy, Math.max(3, Math.round(mainH / 64)), {
      // No price label among the volume bars: the range only drops there to make room.
      floor: vol ? PAD.top + mainH * (1 - VOLUME_BAND) : Infinity,
    });
    const barW = (count) => Math.max(1, Math.min(8, (plotW / Math.max(1, count - 1)) * 0.6));
    if (vol) {
      let top = 0;
      for (const b of vol) if (b && b.v > top) top = b.v;
      const band = mainH * VOLUME_BAND;
      const bw = barW(slots);
      ctx.globalAlpha = 0.45;
      for (let i = 0; i < n; i++) {
        const b = vol[i];
        if (!b || !b.v || !top) continue;
        const bh = Math.max(1, (b.v / top) * band);
        ctx.fillStyle = b.up ? c.up : c.down;
        ctx.fillRect(xOf(i) - bw / 2, PAD.top + mainH - bh, bw, bh);
      }
      ctx.globalAlpha = 1;
    }
    if (n > 1 && ys.some((v) => v != null)) {
      const grad = ctx.createLinearGradient(0, PAD.top, 0, PAD.top + mainH);
      grad.addColorStop(0, c.price);
      grad.addColorStop(1, "transparent");
      ctx.globalAlpha = 0.14;
      ctx.fillStyle = grad;
      ctx.beginPath();
      const own = [];
      for (let i = 0; i < n; i++) if (ys[i] != null) own.push(i);
      own.forEach((i, k) => (k ? ctx.lineTo(xOf(i), yPrice(ys[i])) : ctx.moveTo(xOf(i), yPrice(ys[i]))));
      ctx.lineTo(xOf(own[own.length - 1]), PAD.top + mainH);
      ctx.lineTo(xOf(own[0]), PAD.top + mainH);
      ctx.closePath();
      ctx.fill();
      ctx.globalAlpha = 1;
    }
    for (const mark of ms) {
      const above = mark.value > pHi, below = mark.value < pLo;
      const right = w - PAD.right;
      // The label is text, so it takes the readable secondary ink; the line keeps the mark colour.
      ctx.fillStyle = c.cross;
      ctx.textAlign = "right";
      if (above || below) {
        ctx.textBaseline = above ? "top" : "bottom";
        ctx.fillText(`${mark.label} ${above ? "↑" : "↓"}`, right - 4, above ? PAD.top + 4 : PAD.top + mainH - 4);
        continue;
      }
      const y = Math.round(yPrice(mark.value)) + 0.5;
      ctx.strokeStyle = mark.dotted ? c.axis : c.mark;
      ctx.lineWidth = mark.dotted ? 1.2 : 1.4;
      ctx.setLineDash(mark.dotted ? [1, 4] : [6, 4]);
      ctx.beginPath();
      ctx.moveTo(PAD.left, y);
      ctx.lineTo(right, y);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.textBaseline = "bottom";
      // A backing in the surface colour, so a price line crossing the label never runs through it.
      const tw = ctx.measureText(mark.label).width;
      ctx.fillStyle = c.bg;
      ctx.globalAlpha = 0.85;
      ctx.fillRect(right - 8 - tw, y - 19, tw + 8, 15);
      ctx.globalAlpha = 1;
      ctx.fillStyle = c.cross;
      ctx.fillText(mark.label, right - 4, y - 4);
    }
    if (cs) stroke(cs, yPrice, c.compare, 1.8, cDash, cExt, c.compareExtended);
    stroke(ys, yPrice, c.price, 2, yDash, yExt, c.extended);
    const dots = [];

    // Indicator panes: the formula's left side against its level.
    const paneY = [];
    const tops = paneTops(w, ps, Boolean(cs));
    ps.forEach((pane, k) => {
      const top = tops[k];
      // A histogram is symmetric around zero, labelled at a round bound above and below.
      let bound = 0;
      if (pane.histogram) for (const v of pane.values) if (v != null && Math.abs(v) > bound) bound = Math.abs(v);
      bound = roundUp(bound);
      const [lo, hi] = pane.histogram
        // Headroom so the ± labels, centred on their ticks, stay inside the pane.
        ? [-bound * 1.25, bound * 1.25]
        : extent(pane.cmp ? [...pane.values, ...pane.cmp.values] : pane.values, [pane.level]);
      const yOf = area(top, PANE_PLOT, lo, hi, pane.format ?? figure, 2, pane.histogram ? { ticks: [-bound, 0, bound] } : {});
      paneY.push(yOf);
      if (pane.histogram) {
        const zero = yOf(0);
        const bw = barW(slots);
        ctx.globalAlpha = 0.8;
        for (let i = 0; i < n; i++) {
          const v = pane.values[i];
          if (v == null || v === 0) continue;
          const y = yOf(v);
          ctx.fillStyle = v > 0 ? c.up : c.down;
          ctx.fillRect(xOf(i) - bw / 2, Math.min(y, zero), bw, Math.max(1, Math.abs(zero - y)));
        }
        ctx.globalAlpha = 1;
        const zy = Math.round(zero) + 0.5;
        ctx.strokeStyle = c.grid;
        ctx.beginPath();
        ctx.moveTo(PAD.left, zy);
        ctx.lineTo(w - PAD.right, zy);
        ctx.stroke();
        return;
      }
      const ly = Math.round(yOf(pane.level)) + 0.5;
      ctx.strokeStyle = c.level;
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(PAD.left, ly);
      ctx.lineTo(w - PAD.right, ly);
      ctx.stroke();
      ctx.setLineDash([]);
      if (pane.cmp) stroke(pane.cmp.values, yOf, c.compare, 1.4, pane.cmp.dash, cExt, c.compareExtended);
      stroke(pane.values, yOf, c.price, 1.6, pane.dash, yExt, c.extended);
    });

    // A skipped stretch: a solid rule between the last bar before it and the first after,
    // through every pane, so a jump in the line reads as a gap in time.
    ctx.strokeStyle = c.level;
    ctx.lineWidth = 1;
    for (const b of bs) {
      if (b <= 0 || b >= n) continue;
      const x = Math.round((xOf(b - 1) + xOf(b)) / 2) + 0.5;
      ctx.beginPath();
      ctx.moveTo(x, PAD.top);
      ctx.lineTo(x, h - PAD.bottom);
      ctx.stroke();
    }

    // X labels under the last pane: each break's first bar is labelled, so every
    // segment names where it starts; other labels keep clear of those.
    ctx.fillStyle = c.axis;
    ctx.textAlign = "center";
    ctx.textBaseline = "alphabetic";
    const fit = Math.max(2, Math.floor(plotW / 90));
    const every = Math.max(1, Math.ceil(slots / fit));
    const starts = bs.filter((b) => b > 0 && b < n);
    // The first slot of each local hour: a gap in trading or a viewer in a half-hour zone
    // still gets one label per hour.
    const hours = xsT !== barTimes
      ? xsT.map((t, i) => (i > 0 && new Date(t).getHours() !== new Date(xsT[i - 1]).getHours() ? i : -1)).filter((i) => i >= 0)
      : [];
    let labelled;
    if (hours.length >= 2) {
      // A full session: every k-th whole hour, as many as fit.
      // A full session: every k-th whole hour, as many as fit, and the close, so the axis
      // says where the day ends; an hour too close to the close gives way.
      const k = Math.ceil(hours.length / fit);
      const close = slots - 1;
      const gap = (k * slots) / hours.length;
      labelled = [...hours.filter((i, j) => j % k === 0 && close - i >= gap * 0.6), close];
      // Faint hour rules, so the stretch still to trade reads as time, not missing data.
      ctx.strokeStyle = c.grid;
      for (const i of labelled) {
        const x = Math.round(xOf(i)) + 0.5;
        ctx.beginPath();
        ctx.moveTo(x, PAD.top);
        ctx.lineTo(x, PAD.top + mainH);
        ctx.stroke();
      }
      ctx.fillStyle = c.axis;
    } else {
      labelled = [0, ...starts];
      // The last bar is always labelled, so the axis says where the window ends; a regular
      // label too close to it gives way.
      const last = slots - 1;
      for (let i = every; i < slots; i += every) {
        if ([...starts, last].every((b) => Math.abs(b - i) >= every * 0.6)) labelled.push(i);
      }
      if (last > 0 && !labelled.includes(last)) labelled.push(last);
    }
    for (const i of labelled) {
      ctx.fillText(fx(xsT[i]), Math.min(w - PAD.right - 18, Math.max(PAD.left + 18, xOf(i))), h - 8);
    }

    // The measured change: a dashed line between the two prices, in the colour of its
    // direction, with each end on its line; the pop-up rides centred over the band.
    if (band.alpha > 0) {
      const [a, b] = m ? [Math.min(m.from, m.to), Math.max(m.from, m.to)] : st.bandEnds ?? [0, 0];
      if (m) st.bandEnds = [a, b];
      // Each line joins its two prices only where it has a value of its own at or before
      // the start and at or after the end, as the pop-up does; it never reaches into a gap.
      const has = (values, from, to, dir) => {
        for (let i = from; dir < 0 ? i >= to : i <= to; i += dir) if (values[i] != null) return true;
        return false;
      };
      const link = (values, color) => {
        if (!has(values, a, 0, -1) || !has(values, b, n - 1, 1)) return;
        const v0 = valueAtX(values, band.x0), v1 = valueAtX(values, band.x1);
        if (v0 == null || v1 == null) return;
        const y0 = yPrice(v0), y1 = yPrice(v1);
        const ink = color(v1 - v0);
        ctx.globalAlpha = band.alpha;
        ctx.strokeStyle = ink;
        ctx.lineWidth = 1.5;
        ctx.setLineDash([5, 4]);
        ctx.beginPath();
        ctx.moveTo(band.x0, y0);
        ctx.lineTo(band.x1, y1);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.lineWidth = 1;
        drawDot(band.x0, y0, ink);
        drawDot(band.x1, y1, ink);
        ctx.globalAlpha = 1;
      };
      if (cs) link(cs, () => c.compare);
      link(ys, (d) => (d > 0 ? c.up : d < 0 ? c.down : c.cross));
      // Never over the measured stretch: right of the band when it fits, else left of it,
      // else under the chart (as on a narrow chart, where it always sits there). Going back
      // beside the band needs a little more room than leaving, so an edge doesn't flicker.
      const pop = measureRef.current;
      if (pop && w >= NARROW) {
        // The width beside the band, as last measured (see the layout effect below).
        if (!st.popW && !st.popBelow) st.popW = pop.offsetWidth;
        const gap = 12, pw = st.popW, spare = st.popBelow ? 24 : 0;
        const right = band.x1 + gap + pw + spare <= w;
        const left = band.x0 - gap - pw - spare >= 0;
        const below = !right && !left;
        if (below !== st.popBelow) { st.popBelow = below; st.setPopBelow(below); }
        if (!below) {
          const x = right ? band.x1 + gap : band.x0 - gap - pw;
          pop.style.transform = `translate3d(${Math.round(x)}px, ${PAD.top + 4}px, 0)`;
        }
      }
    }
    if (moving) schedule();
    else band.at = 0; // idle: the next start counts as one fresh frame

    // Crosshair across every pane; a measurement takes its place.
    const tip = tipRef.current;
    if (st.hover !== null && st.hover < n && !m) {
      const i = st.hover;
      const x = Math.round(xOf(i)) + 0.5;
      ctx.strokeStyle = c.cross;
      ctx.globalAlpha = 0.35;
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(x, PAD.top);
      ctx.lineTo(x, h - PAD.bottom);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.globalAlpha = 1;
      const dot = (values, yOf, color) => {
        const v = values && valueAt(values, i);
        if (v != null) dots.push([yOf(v), color]);
      };
      dot(ys, yPrice, yExt?.[i] ? c.extended : c.price);
      dot(cs, yPrice, cExt?.[i] ? c.compareExtended : c.compare);
      ps.forEach((pane, k) => {
        if (pane.histogram) return;
        dot(pane.values, paneY[k], c.price);
        dot(pane.cmp?.values, paneY[k], c.compare);
      });
      for (const [y, color] of dots) drawDot(x, y, color);
      if (tip) {
        const tw = tip.offsetWidth || 200;
        // Right of the crosshair when it fits, else left of it, never past either edge.
        const left = Math.max(0, Math.min(w - tw, x + 16 + tw > w ? x - 16 - tw : x + 16));
        tip.style.transform = `translate3d(${Math.round(left)}px, ${PAD.top + 4}px, 0)`;
      }
    } else if (isLive && !m) {
      // The newest bar is still forming: mark where the line ends.
      let last = n - 1;
      while (last > 0 && ys[last] == null) last--;
      const x = xOf(last), y = yPrice(ys[last]);
      ctx.fillStyle = c.bg;
      ctx.beginPath();
      ctx.arc(x, y, 5.5, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = yExt?.[last] ? c.extended : c.price;
      ctx.beginPath();
      ctx.arc(x, y, 3.5, 0, Math.PI * 2);
      ctx.fill();
    }
  };

  const schedule = () => { if (!st.frame) st.frame = requestAnimationFrame(draw); };
  st.schedule = schedule;

  // Reads the latest props through `st`: the ResizeObserver callback outlives the render
  // that created it, and must not size the canvas for a stale pane count.
  const height = (w) => {
    const { panes: ps, compare: cs } = st.props;
    const tops = paneTops(w, ps, Boolean(cs));
    return (ps.length ? tops[tops.length - 1] + PANE_PLOT : PAD.top + mainHeight(w)) + PAD.bottom;
  };

  useEffect(() => {
    // Fewer bars than the reading points at (a new session): drop the reading and say so,
    // or the owner keeps an index past the end of its arrays.
    if (st.hover !== null && st.hover >= close.length) {
      st.hover = null;
      st.onHover?.(null, false);
    }
    // Fewer bars than the measurement spans (a new session): drop it.
    if (st.sel && Math.max(st.sel.from, st.sel.to) >= close.length) { endPress(); setSel(null); }
    const canvas = canvasRef.current;
    if (canvas && st.w) {
      st.h = height(st.w);
      canvas.height = Math.round(st.h * st.dpr);
      canvas.style.height = `${st.h}px`;
    }
    schedule();
  });

  useLayoutEffect(() => {
    const wrap = wrapRef.current;
    const canvas = canvasRef.current;
    st.colors = readColors();
    const resize = () => {
      st.w = wrap.getBoundingClientRect().width;
      st.h = height(st.w);
      wrap.style.setProperty("--main-h", `${mainHeight(st.w)}px`);
      setNarrow(st.w < NARROW);
      st.dpr = Math.min(2, window.devicePixelRatio || 1);
      canvas.width = Math.round(st.w * st.dpr);
      canvas.height = Math.round(st.h * st.dpr);
      canvas.style.width = `${st.w}px`;
      canvas.style.height = `${st.h}px`;
      draw();
    };
    const ro = new ResizeObserver(resize);
    ro.observe(wrap);
    resize();
    const mo = new MutationObserver(() => { st.colors = readColors(); st.schedule(); });
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    document.fonts?.ready.then(() => st.schedule());
    return () => {
      ro.disconnect();
      mo.disconnect();
      cancelAnimationFrame(st.frame);
      st.frame = 0;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // `keyed` is true when the keyboard moved the reading, the only time it is announced.
  const setHover = (i, keyed = false) => {
    if (i === st.hover) return;
    st.hover = i;
    st.onHover?.(i, keyed);
    st.schedule();
  };

  // Another ticker, range or comparison: the measured indices would mean other bars.
  useEffect(() => {
    endPress();
    setSel(null);
  }, [resetKey]); // eslint-disable-line react-hooks/exhaustive-deps

  // Only a change of bars reaches React (the pop-up's content); the band itself moves
  // in the canvas loop.
  const setSel = (next) => {
    const same = next === st.sel || (next && st.sel && next.from === st.sel.from && next.to === st.sel.to);
    st.sel = next;
    if (!same) setSelState(next);
    st.schedule?.();
  };

  // Arrow keys step through the bars (Shift for ten), Home and End jump, Escape leaves.
  // Enter starts a measurement at the reading; the keys then move its far end, and Enter
  // or Escape ends it.
  const onKeyDown = (e) => {
    const n = st.props.close.length;
    if (!n) return;
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      if (st.sel) { clearMeasure(); return; }
      const from = st.hover ?? n - 1;
      setSel({ from, to: from });
      setHover(from, true);
      return;
    }
    if (e.key === "Escape") {
      if (st.sel) { clearMeasure(); return; }
      setHover(null);
      return;
    }
    const now = st.sel ? st.sel.to : st.hover ?? n - 1;
    const step = e.shiftKey ? 10 : 1;
    const next = { ArrowLeft: now - step, ArrowRight: now + step, Home: 0, End: n - 1 }[e.key];
    if (next === undefined) return;
    e.preventDefault();
    const to = Math.max(0, Math.min(n - 1, next));
    if (st.sel) setSel({ from: st.sel.from, to });
    else setHover(to, true);
  };

  /** Ends a measurement, leaving the reading on its far end so the keys go on from there. */
  const clearMeasure = () => {
    const to = st.sel?.to ?? null;
    setSel(null);
    if (to !== null && to < st.props.close.length) setHover(to, true);
  };

  /** The bar under the pointer. Over a full session's untraded stretch, the newest bar. */
  const indexAt = (e) => {
    const n = st.props.close.length;
    const rect = canvasRef.current.getBoundingClientRect();
    const rel = (e.clientX - rect.left - PAD.left) / Math.max(10, st.w - PAD.left - PAD.right);
    const slots = Math.max(n, st.props.axisTimes?.length ?? 0);
    return Math.max(0, Math.min(n - 1, Math.round(rel * (slots - 1))));
  };

  const onPointerDown = (e) => {
    if (!st.props.close.length || e.button !== 0) return;
    // A second finger or pen while one press is held changes nothing.
    if (st.down && st.down.id !== e.pointerId) return;
    const i = indexAt(e);
    // A press on a measurement clears it, unless it turns into a new drag.
    st.down = { i, x: e.clientX, id: e.pointerId, clears: Boolean(st.sel) };
    if (!st.sel) setHover(i);
  };

  const onPointerMove = (e) => {
    if (!st.props.close.length) return;
    // A press released outside the canvas never sent its pointerup here: with no button
    // down any more, it is over.
    if (st.down && st.down.id === e.pointerId && !(e.buttons & 1)) endPress();
    const i = indexAt(e);
    const down = st.down;
    if (st.dragging && down?.id !== e.pointerId) return;
    if (down && down.id === e.pointerId && !st.dragging && Math.abs(e.clientX - down.x) > DRAG_START) {
      st.dragging = true;
      setDragging(true);
      setHover(null);
      // Keeps the drag when the pointer leaves the canvas; a pointer that is already
      // gone cannot be captured, and the drag simply ends at the canvas edge.
      try { canvasRef.current.setPointerCapture(e.pointerId); } catch { /* no active pointer */ }
    }
    if (st.dragging) setSel({ from: down.i, to: i });
    else if (!st.sel) setHover(i);
  };

  const onPointerUp = (e) => {
    const down = st.down;
    if (!down || down.id !== e.pointerId) return;
    const dragged = st.dragging;
    endPress();
    if (dragged) {
      // Released where it started: nothing measured.
      if (st.sel && st.sel.from === st.sel.to) setSel(null);
      return;
    }
    if (down.clears) {
      setSel(null);
      setHover(indexAt(e));
    }
  };

  // A touch the browser took over for scrolling measures nothing.
  const onPointerCancel = (e) => {
    if (st.down?.id !== e.pointerId) return;
    const dragged = st.dragging;
    endPress();
    if (dragged) setSel(null);
  };

  // Capture lost without a pointerup (the window lost focus mid-drag): keep what was measured.
  const onLostPointerCapture = (e) => {
    if (st.dragging && st.down?.id === e.pointerId) {
      endPress();
      if (st.sel && st.sel.from === st.sel.to) setSel(null);
    }
  };

  // Built once per measured stretch (and per new `measure`, when the data changes), never
  // on a pointer move within the same bars.
  const measured = useMemo(
    () => (sel && sel.from !== sel.to && measure ? measure(Math.min(sel.from, sel.to), Math.max(sel.from, sel.to)) : null),
    [sel, measure],
  );
  useEffect(() => { if (measured) shown.current = measured; }, [measured]);
  const content = measured ?? shown.current;
  // The pop-up's width beside the band, measured once each time its content changes (one
  // layout read, never per frame). Under the chart it spans the chart, which says nothing
  // about its width beside the band, so the last width beside it stands.
  useLayoutEffect(() => {
    const pop = measureRef.current;
    if (!pop || !measured || narrow || popBelow) return;
    st.popW = pop.offsetWidth;
    st.schedule();
  }, [measured, narrow, popBelow]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="pchart" ref={wrapRef}>
      <canvas
        ref={canvasRef}
        onPointerMove={onPointerMove}
        onPointerDown={onPointerDown}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerCancel}
        onLostPointerCapture={onLostPointerCapture}
        onPointerLeave={() => { if (!st.dragging) setHover(null); }}
        onKeyDown={onKeyDown}
        onFocus={() => { if (st.hover === null && !st.sel) setHover(st.props.close.length - 1); }}
        onBlur={() => setHover(null)}
        tabIndex={0}
        role="group"
        aria-roledescription={roleLabel}
        aria-label={ariaLabel}
        aria-keyshortcuts="ArrowLeft ArrowRight Home End Enter Escape"
      />
      {/* Pane headers are DOM, laid over the canvas, so their inputs are real inputs. */}
      <div className={`pchart-heads ${narrow ? "narrow" : ""}`} style={{ top: `calc(${PAD.top}px + var(--main-h, 320px))` }}>
        {heads(narrow).map((head, k) => (
          <div key={panes[k].key} className="pchart-head" style={{ height: headHeight(narrow, panes[k], Boolean(compare)), marginBottom: PANE_PLOT }}>{head}</div>
        ))}
      </div>
      <div ref={tipRef} className={`vchart-tip ${tooltip && !measured ? "on" : ""}`} aria-hidden="true">{tooltip}</div>
      <div ref={measureRef} className={`pchart-measure ${measured ? "on" : ""} ${dragging ? "dragging" : ""} ${narrow || popBelow ? "under" : ""}`} aria-hidden={!measured}>
        <div className="measure-body">
          {content?.content}
          {measured && (
            <button type="button" className="measure-x" aria-label={measureLabel} onClick={() => { clearMeasure(); canvasRef.current?.focus(); }}>
              <Icon name="x" size={12} />
            </button>
          )}
        </div>
      </div>
      {/* The finished measurement, or, when the keys start one, that measuring has begun. */}
      <p className="sr-only" aria-live="polite">{dragging ? "" : measured ? measured.spoken : sel ? measureName : ""}</p>
    </div>
  );
}
