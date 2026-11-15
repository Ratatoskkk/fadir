// Canvas chart for one instrument: the price line on top, one pane per enabled
// indicator below it, all on a shared x axis so the crosshair reads every pane at once.
// Same reasoning as ValueChart for canvas: a poll repaints one canvas, not a DOM tree.
// Panes are separate rather than overlaid because price and indicators never share a
// unit (DESLOP 51: no dual y axes).

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { quote, figure } from "../../format.js";

const PAD = { left: 64, right: 14, top: 14, bottom: 28 };
const PANE_PLOT = 78;
const NARROW = 560;

const mainHeight = (width) => (width < NARROW ? 280 : 320);
/**
 * One row on a wide chart. On a narrow one the reading takes a row, a compared ticker's
 * reading one more, and the N1/N2 inputs (44px touch targets) a third, shown only while
 * that pane is being edited.
 */
const headHeight = (narrow, pane, compared) => (narrow ? 36 + (compared ? 32 : 0) + (pane.editing ? 52 : 0) : 40);
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
export default function PriceChart({ times, close, compare = null, closeDash = null, compareDash = null, formatY = quote, panes, marks = [], breaks = [], heads, formatX, live, onHover, tooltip, ariaLabel, roleLabel }) {
  const wrapRef = useRef(null);
  const canvasRef = useRef(null);
  const tipRef = useRef(null);
  const st = useRef({ w: 0, h: 0, dpr: 1, colors: null, hover: null, frame: 0 }).current;
  const [narrow, setNarrow] = useState(false);
  st.props = { times, close, compare, closeDash, compareDash, formatY, panes, marks, breaks, formatX, live };
  st.onHover = onHover;

  const draw = () => {
    st.frame = 0;
    const canvas = canvasRef.current;
    if (!canvas || !st.colors) return;
    const { times: xsT, close: ys, compare: cs, closeDash: yDash, compareDash: cDash, formatY: fy, panes: ps, marks: ms, breaks: bs, formatX: fx, live: isLive } = st.props;
    const { w, h, dpr, colors: c } = st;
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    const n = ys.length;
    if (!n) return;

    const plotW = Math.max(10, w - PAD.left - PAD.right);
    const mainH = mainHeight(w);
    const xOf = (i) => PAD.left + (n > 1 ? (i * plotW) / (n - 1) : plotW / 2);
    ctx.font = `11.5px ${c.font}`;
    ctx.lineWidth = 1;

    const area = (top, height, lo, hi, format, tickCount) => {
      const yOf = (v) => top + (1 - (v - lo) / (hi - lo || 1)) * height;
      ctx.textAlign = "right";
      ctx.textBaseline = "middle";
      for (const tick of niceTicks(lo, hi, tickCount)) {
        const y = Math.round(yOf(tick)) + 0.5;
        if (y < top - 1 || y > top + height + 1) continue;
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
    // Two passes: solid connections, then faint dashes across closed markets.
    const stroke = (values, yOf, color, width, dash = null) => {
      ctx.strokeStyle = color;
      ctx.lineJoin = "round";
      ctx.lineCap = "round";
      for (const dashed of dash ? [false, true] : [false]) {
        ctx.lineWidth = dashed ? Math.max(1, width - 0.6) : width;
        ctx.globalAlpha = dashed ? 0.45 : 1;
        ctx.setLineDash(dashed ? [2, 4] : []);
        ctx.beginPath();
        let prev = -1;
        for (let i = 0; i < n; i++) {
          if (values[i] == null) continue;
          if (prev >= 0 && Boolean(dash?.[i]) === dashed) {
            ctx.moveTo(xOf(prev), yOf(values[prev]));
            ctx.lineTo(xOf(i), yOf(values[i]));
          }
          prev = i;
        }
        ctx.stroke();
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

    // Price.
    const [pLo, pHi] = cs ? extent([...ys, ...cs]) : extent(ys);
    const yPrice = area(PAD.top, mainH, pLo, pHi, fy, Math.max(3, Math.round(mainH / 64)));
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
      ctx.strokeStyle = c.mark;
      ctx.lineWidth = 1.4;
      ctx.setLineDash([6, 4]);
      ctx.beginPath();
      ctx.moveTo(PAD.left, y);
      ctx.lineTo(right, y);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.textBaseline = "bottom";
      ctx.fillText(mark.label, right - 4, y - 4);
    }
    if (cs) stroke(cs, yPrice, c.compare, 1.8, cDash);
    stroke(ys, yPrice, c.price, 2, yDash);
    const dots = [];

    // Indicator panes: the formula's left side against its level.
    const paneY = [];
    const tops = paneTops(w, ps, Boolean(cs));
    ps.forEach((pane, k) => {
      const top = tops[k];
      const [lo, hi] = extent(pane.cmp ? [...pane.values, ...pane.cmp.values] : pane.values, [pane.level]);
      const yOf = area(top, PANE_PLOT, lo, hi, pane.format ?? figure, 2);
      paneY.push(yOf);
      const ly = Math.round(yOf(pane.level)) + 0.5;
      ctx.strokeStyle = c.level;
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(PAD.left, ly);
      ctx.lineTo(w - PAD.right, ly);
      ctx.stroke();
      ctx.setLineDash([]);
      if (pane.cmp) stroke(pane.cmp.values, yOf, c.compare, 1.4, pane.cmp.dash);
      stroke(pane.values, yOf, c.price, 1.6, pane.dash);
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
    const every = Math.max(1, Math.ceil(n / Math.max(2, Math.floor(plotW / 90))));
    const starts = bs.filter((b) => b > 0 && b < n);
    const labelled = [0, ...starts];
    // The last bar is always labelled, so the axis says where the window ends; a regular
    // label too close to it gives way.
    const last = n - 1;
    for (let i = every; i < n; i += every) {
      if ([...starts, last].every((b) => Math.abs(b - i) >= every * 0.6)) labelled.push(i);
    }
    if (last > 0 && !labelled.includes(last)) labelled.push(last);
    for (const i of labelled) {
      ctx.fillText(fx(xsT[i]), Math.min(w - PAD.right - 18, Math.max(PAD.left + 18, xOf(i))), h - 8);
    }

    // Crosshair across every pane.
    const tip = tipRef.current;
    if (st.hover !== null && st.hover < n) {
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
      dot(ys, yPrice, c.price);
      dot(cs, yPrice, c.compare);
      ps.forEach((pane, k) => {
        dot(pane.values, paneY[k], c.price);
        dot(pane.cmp?.values, paneY[k], c.compare);
      });
      for (const [y, color] of dots) {
        ctx.fillStyle = c.bg;
        ctx.beginPath();
        ctx.arc(x, y, 5, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(x, y, 3.2, 0, Math.PI * 2);
        ctx.fill();
      }
      if (tip) {
        const tw = tip.offsetWidth || 200;
        const left = x + 16 + tw > w ? x - 16 - tw : x + 16;
        tip.style.transform = `translate3d(${Math.round(left)}px, ${PAD.top + 4}px, 0)`;
      }
    } else if (isLive) {
      // The newest bar is still forming: mark where the line ends.
      let last = n - 1;
      while (last > 0 && ys[last] == null) last--;
      const x = xOf(last), y = yPrice(ys[last]);
      ctx.fillStyle = c.bg;
      ctx.beginPath();
      ctx.arc(x, y, 5.5, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = c.price;
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
    if (st.hover !== null && st.hover >= close.length) st.hover = null;
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

  // Arrow keys step through the bars (Shift for ten), Home and End jump, Escape leaves.
  const onKeyDown = (e) => {
    const n = st.props.close.length;
    if (!n) return;
    const now = st.hover ?? n - 1;
    const step = e.shiftKey ? 10 : 1;
    const next = { ArrowLeft: now - step, ArrowRight: now + step, Home: 0, End: n - 1 }[e.key];
    if (e.key === "Escape") { setHover(null); return; }
    if (next === undefined) return;
    e.preventDefault();
    setHover(Math.max(0, Math.min(n - 1, next)), true);
  };

  const onPointerMove = (e) => {
    const n = st.props.close.length;
    if (!n) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const rel = (e.clientX - rect.left - PAD.left) / Math.max(10, st.w - PAD.left - PAD.right);
    setHover(Math.max(0, Math.min(n - 1, Math.round(rel * (n - 1)))));
  };

  return (
    <div className="pchart" ref={wrapRef}>
      <canvas
        ref={canvasRef}
        onPointerMove={onPointerMove}
        onPointerDown={onPointerMove}
        onPointerLeave={() => setHover(null)}
        onKeyDown={onKeyDown}
        onFocus={() => { if (st.hover === null) setHover(st.props.close.length - 1); }}
        onBlur={() => setHover(null)}
        tabIndex={0}
        role="group"
        aria-roledescription={roleLabel}
        aria-label={ariaLabel}
        aria-keyshortcuts="ArrowLeft ArrowRight Home End"
      />
      {/* Pane headers are DOM, laid over the canvas, so their inputs are real inputs. */}
      <div className={`pchart-heads ${narrow ? "narrow" : ""}`} style={{ top: `calc(${PAD.top}px + var(--main-h, 320px))` }}>
        {heads(narrow).map((head, k) => (
          <div key={panes[k].key} className="pchart-head" style={{ height: headHeight(narrow, panes[k], Boolean(compare)), marginBottom: PANE_PLOT }}>{head}</div>
        ))}
      </div>
      <div ref={tipRef} className={`vchart-tip ${tooltip ? "on" : ""}`} aria-hidden="true">{tooltip}</div>
    </div>
  );
}
