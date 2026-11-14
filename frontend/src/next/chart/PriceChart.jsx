// Canvas chart for one instrument: the price line on top, one pane per enabled
// indicator below it, all on a shared x axis so the crosshair reads every pane at once.
// Same reasoning as ValueChart for canvas: a poll repaints one canvas, not a DOM tree.
// Panes are separate rather than overlaid because price and indicators never share a
// unit (DESLOP 51: no dual y axes).

import { useEffect, useLayoutEffect, useRef } from "react";
import { quote, figure } from "../../format.js";

const PAD = { left: 64, right: 14, top: 14, bottom: 28 };
const PANE_PLOT = 78;
const NARROW = 560;

const mainHeight = (width) => (width < NARROW ? 240 : 320);
/** A narrow pane header wraps its N1/N2 inputs (44px touch targets) onto a second row. */
const paneHead = (width) => (width < NARROW ? 80 : 40);
const paneHeight = (width) => paneHead(width) + PANE_PLOT;

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
    panes: [v("--pane-1"), v("--pane-2"), v("--pane-3")],
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
export default function PriceChart({ times, close, compare = null, formatY = quote, panes, marks = [], breaks = [], heads, formatX, live, onHover, tooltip, ariaLabel }) {
  const wrapRef = useRef(null);
  const canvasRef = useRef(null);
  const tipRef = useRef(null);
  const st = useRef({ w: 0, h: 0, dpr: 1, colors: null, hover: null, frame: 0 }).current;
  st.props = { times, close, compare, formatY, panes, marks, breaks, formatX, live };
  st.onHover = onHover;

  const draw = () => {
    st.frame = 0;
    const canvas = canvasRef.current;
    if (!canvas || !st.colors) return;
    const { times: xsT, close: ys, compare: cs, formatY: fy, panes: ps, marks: ms, breaks: bs, formatX: fx, live: isLive } = st.props;
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

    const stroke = (values, yOf, color, width) => {
      ctx.strokeStyle = color;
      ctx.lineWidth = width;
      ctx.lineJoin = "round";
      ctx.lineCap = "round";
      ctx.beginPath();
      let open = false;
      for (let i = 0; i < n; i++) {
        const v = values[i];
        if (v === null || v === undefined) { open = false; continue; }
        if (open) ctx.lineTo(xOf(i), yOf(v));
        else { ctx.moveTo(xOf(i), yOf(v)); open = true; }
      }
      ctx.stroke();
    };

    // Price.
    const [pLo, pHi] = cs ? extent([...ys, ...cs]) : extent(ys);
    const yPrice = area(PAD.top, mainH, pLo, pHi, fy, Math.max(3, Math.round(mainH / 64)));
    if (n > 1) {
      const grad = ctx.createLinearGradient(0, PAD.top, 0, PAD.top + mainH);
      grad.addColorStop(0, c.price);
      grad.addColorStop(1, "transparent");
      ctx.globalAlpha = 0.14;
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.moveTo(xOf(0), yPrice(ys[0]));
      for (let i = 1; i < n; i++) ctx.lineTo(xOf(i), yPrice(ys[i]));
      ctx.lineTo(xOf(n - 1), PAD.top + mainH);
      ctx.lineTo(xOf(0), PAD.top + mainH);
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
    if (cs) stroke(cs, yPrice, c.compare, 1.8);
    stroke(ys, yPrice, c.price, 2);
    const dots = [[yPrice(ys[st.hover ?? 0]), c.price]];
    if (cs && st.hover !== null && cs[st.hover] != null) dots.push([yPrice(cs[st.hover]), c.compare]);

    // Indicator panes: the formula's left side against its level.
    const paneY = [];
    ps.forEach((pane, k) => {
      const top = PAD.top + mainH + k * paneHeight(w) + paneHead(w);
      const [lo, hi] = extent(pane.values, [pane.level]);
      const yOf = area(top, PANE_PLOT, lo, hi, figure, 2);
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
      stroke(pane.values, yOf, c.panes[pane.tone] ?? c.price, 1.6);
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
    for (let i = every; i < n; i += every) {
      if (starts.every((b) => Math.abs(b - i) >= every * 0.6)) labelled.push(i);
    }
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
      dots[0][0] = yPrice(ys[i]);
      ps.forEach((pane, k) => { if (pane.values[i] !== null) dots.push([paneY[k](pane.values[i]), c.panes[pane.tone] ?? c.price]); });
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
      const x = xOf(n - 1), y = yPrice(ys[n - 1]);
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
  const height = (w) => PAD.top + mainHeight(w) + st.props.panes.length * paneHeight(w) + PAD.bottom;

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
      wrap.style.setProperty("--pane-head", `${paneHead(st.w)}px`);
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

  const setHover = (i) => {
    if (i === st.hover) return;
    st.hover = i;
    st.onHover?.(i);
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
    setHover(Math.max(0, Math.min(n - 1, next)));
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
        role="img"
        aria-label={ariaLabel}
      />
      {/* Pane headers are DOM, laid over the canvas, so their inputs are real inputs. */}
      <div className="pchart-heads" style={{ top: `calc(${PAD.top}px + var(--main-h, 320px))` }}>
        {heads.map((head, k) => (
          <div key={panes[k]?.key ?? k} className="pchart-head" style={{ marginBottom: PANE_PLOT }}>{head}</div>
        ))}
      </div>
      <div ref={tipRef} className={`vchart-tip ${tooltip ? "on" : ""}`} aria-hidden="true">{tooltip}</div>
    </div>
  );
}
