// Canvas chart for the portfolio series, replacing Recharts in the new interface.
//
// Why canvas: the chart animates constantly (polls, range swaps, series toggles, the
// crosshair) and an SVG chart re-renders hundreds of DOM nodes through React for each of
// those. Here React renders the container once; one draw function paints everything, and
// it only runs while something is moving, so an idle chart costs nothing.
//
// Motion model: every visual quantity (y domain, each value, each series' opacity, the
// crosshair) eases exponentially toward its target each frame. A poll that nudges today's
// point therefore glides; a range change crossfades the old window out and slides the
// new one in from the direction of travel.

import { useEffect, useLayoutEffect, useRef } from "react";
import { prefersReducedMotion } from "../ui/motion.js";
import { useT } from "../i18n/index.jsx";

export const SERIES = [
  { key: "value_try", label: "chart.value", color: "value", width: 2.4, dash: [] },
  { key: "value_constant_fx_try", label: "chart.constantFx", color: "price", width: 1.7, dash: [6, 4] },
  { key: "value_after_tax_try", label: "tax.afterTax", color: "tax", width: 1.6, dash: [2, 4], taxOnly: true },
  { key: "cost_basis_try", label: "chart.costBasis", color: "cost", width: 1.6, dash: [] },
];
export const BAND_KEY = "fx_band";

const PAD = { left: 64, right: 14, top: 14, bottom: 28 };
const SMOOTH_MS = 110; // time constant of the exponential easing
const SWAP_MS = 620;

const TZ = "Europe/Istanbul";
const dfTime = new Intl.DateTimeFormat("tr-TR", { hour: "2-digit", minute: "2-digit", timeZone: TZ });
const dfShort = new Intl.DateTimeFormat("tr-TR", { day: "2-digit", month: "2-digit" });

// The first format() with an explicit timeZone loads ICU zone data synchronously, a
// ~30ms stall that would land on the first intraday (1G) frame. Pay it while idle.
(window.requestIdleCallback ?? ((fn) => window.setTimeout(fn, 1500)))(() => {
  dfTime.format(Date.now());
  dfShort.format(Date.now());
});

export function compactTry(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "";
  if (Math.abs(n) >= 1_000_000) return `₺${(n / 1_000_000).toFixed(2).replace(".", ",")}M`;
  if (Math.abs(n) >= 10_000) return `₺${Math.round(n / 1000)}B`;
  if (Math.abs(n) >= 1_000) return `₺${(n / 1000).toFixed(1).replace(".", ",")}B`;
  return `₺${Math.round(n)}`;
}

function niceTicks(min, max, count = 5) {
  const span = max - min || Math.abs(max) || 1;
  const raw = span / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const norm = raw / mag;
  const step = (norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10) * mag;
  const ticks = [];
  for (let v = Math.ceil(min / step) * step; v <= max + step * 1e-6; v += step) ticks.push(v);
  return ticks;
}

function readColors() {
  const s = getComputedStyle(document.documentElement);
  const v = (name, fallback) => s.getPropertyValue(name).trim() || fallback;
  return {
    value: v("--accent", "#7ea6f0"),
    price: v("--price", "#7aa2ff"),
    fx: v("--fx", "#b78cff"),
    tax: v("--tax", "#e8b06a"),
    cost: v("--cost", "#8a8f9c"),
    grid: v("--chart-grid", "rgba(255,255,255,0.06)"),
    axis: v("--text-3", "#6b6f7a"),
    cross: v("--text-2", "#a7abb5"),
    selection: v("--accent", "#7ea6f0"),
    bg: v("--surface-solid", "#0d0f15"),
  };
}

/** Monotone cubic path (Fritsch–Carlson): smooth, but never overshoots a data point. */
function tracePath(ctx, xs, ys) {
  const n = xs.length;
  if (n === 0) return;
  ctx.moveTo(xs[0], ys[0]);
  if (n < 3 || n > 160) {
    for (let i = 1; i < n; i++) ctx.lineTo(xs[i], ys[i]);
    return;
  }
  const dx = [], m = [], t = new Array(n);
  for (let i = 0; i < n - 1; i++) {
    dx[i] = xs[i + 1] - xs[i];
    m[i] = (ys[i + 1] - ys[i]) / (dx[i] || 1);
  }
  t[0] = m[0];
  t[n - 1] = m[n - 2];
  for (let i = 1; i < n - 1; i++) t[i] = m[i - 1] * m[i] <= 0 ? 0 : (m[i - 1] + m[i]) / 2;
  for (let i = 0; i < n - 1; i++) {
    if (m[i] === 0) { t[i] = 0; t[i + 1] = 0; continue; }
    const a = t[i] / m[i], b = t[i + 1] / m[i], h = a * a + b * b;
    if (h > 9) { const k = 3 / Math.sqrt(h); t[i] = k * a * m[i]; t[i + 1] = k * b * m[i]; }
  }
  for (let i = 0; i < n - 1; i++) {
    const d = dx[i] / 3;
    ctx.bezierCurveTo(xs[i] + d, ys[i] + t[i] * d, xs[i + 1] - d, ys[i + 1] - t[i + 1] * d, xs[i + 1], ys[i + 1]);
  }
}

const easeOut = (t) => 1 - (1 - t) ** 3;

function datasetFrom(data) {
  const out = { n: data.length, x: data.map((d) => d.x) };
  for (const s of SERIES) out[s.key] = Float64Array.from(data, (d) => d[s.key]);
  return out;
}

function sameShape(a, b) {
  return a && b && a.n === b.n && a.n > 0 && a.x[0] === b.x[0] && a.x[a.n - 2] === b.x[b.n - 2];
}

export default function ValueChart({
  data,
  intraday,
  hidden,
  anyTax,
  panDir = 0,
  live = false,
  selection,
  onHover,
  onSelect,
  tooltip = null,
  height = 340,
}) {
  const t = useT();
  const wrapRef = useRef(null);
  const canvasRef = useRef(null);
  const tipRef = useRef(null);
  const pulseRef = useRef(null);
  const S = useRef(null);

  if (S.current === null) {
    S.current = {
      w: 0, h: height, dpr: 1, colors: null,
      target: null, shown: null, old: null,
      swapStart: 0, swapDir: 0, mountReveal: true,
      domain: null, alpha: {}, frame: 0, last: 0,
      hover: null, tipX: null, sel: null, dragging: false,
      intraday, hidden, anyTax, live, cb: {},
    };
  }
  const st = S.current;
  st.cb.onHover = onHover;
  st.cb.onSelect = onSelect;

  // ---------------------------------------------------------------- drawing
  const drawRef = useRef(null);
  drawRef.current = function draw(now) {
    const canvas = canvasRef.current;
    if (!canvas || !st.target || !st.colors) return false;
    const ctx = canvas.getContext("2d");
    const { w, h, dpr, colors: c } = st;
    const dt = st.last ? Math.min(64, now - st.last) : 16;
    st.last = now;
    const k = prefersReducedMotion() ? 1 : 1 - Math.exp(-dt / SMOOTH_MS);
    let moving = false;

    const ease1 = (cur, target) => {
      const next = cur + (target - cur) * k;
      if (Math.abs(target - next) > Math.abs(target) * 1e-5 + 1e-3) moving = true;
      else return target;
      return next;
    };

    // Values glide toward their targets.
    const T = st.target;
    if (!st.shown || st.shown.n !== T.n) st.shown = { ...T, ...Object.fromEntries(SERIES.map((s) => [s.key, Float64Array.from(T[s.key])])) };
    const D = st.shown;
    D.x = T.x;
    for (const s of SERIES) {
      const a = D[s.key], b = T[s.key];
      for (let i = 0; i < T.n; i++) a[i] = ease1(a[i], b[i]);
    }

    // Series opacity.
    const visible = (s) => !st.hidden[s.key] && (!s.taxOnly || st.anyTax);
    for (const s of SERIES) {
      const target = visible(s) ? 1 : 0;
      st.alpha[s.key] = st.alpha[s.key] === undefined ? target : ease1(st.alpha[s.key], target);
    }
    st.alpha[BAND_KEY] = st.alpha[BAND_KEY] === undefined
      ? (st.hidden[BAND_KEY] ? 0 : 1)
      : ease1(st.alpha[BAND_KEY], st.hidden[BAND_KEY] ? 0 : 1);

    // Target domain over what is (becoming) visible.
    let lo = Infinity, hi = -Infinity;
    for (const s of SERIES) {
      if (!visible(s)) continue;
      const arr = T[s.key];
      for (let i = 0; i < T.n; i++) { if (arr[i] < lo) lo = arr[i]; if (arr[i] > hi) hi = arr[i]; }
    }
    if (!Number.isFinite(lo)) { lo = 0; hi = 1; }
    const padY = (hi - lo || Math.abs(hi) || 1) * 0.1;
    const tLo = lo - padY, tHi = hi + padY;
    if (!st.domain) st.domain = [tLo, tHi];
    st.domain = [ease1(st.domain[0], tLo), ease1(st.domain[1], tHi)];
    const [dLo, dHi] = st.domain;

    // Swap timeline (range change / pan): old fades out, new slides in.
    let swap = 1;
    if (st.swapStart) {
      swap = prefersReducedMotion() ? 1 : Math.min(1, (now - st.swapStart) / SWAP_MS);
      if (swap < 1) moving = true;
      else { st.swapStart = 0; st.old = null; st.mountReveal = false; }
    }
    const e = easeOut(swap);

    const plotW = Math.max(10, w - PAD.left - PAD.right);
    const plotH = Math.max(10, h - PAD.top - PAD.bottom);
    const yOf = (v) => PAD.top + (1 - (v - dLo) / (dHi - dLo || 1)) * plotH;

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);

    // Grid + y labels.
    ctx.font = '11.5px "Inter Variable", system-ui, sans-serif';
    ctx.textBaseline = "middle";
    ctx.textAlign = "right";
    ctx.lineWidth = 1;
    for (const tick of niceTicks(dLo, dHi, Math.max(3, Math.round(plotH / 70)))) {
      const y = Math.round(yOf(tick)) + 0.5;
      if (y < PAD.top - 2 || y > PAD.top + plotH + 2) continue;
      ctx.strokeStyle = c.grid;
      ctx.beginPath();
      ctx.moveTo(PAD.left, y);
      ctx.lineTo(w - PAD.right, y);
      ctx.stroke();
      ctx.fillStyle = c.axis;
      ctx.fillText(compactTry(tick), PAD.left - 10, y);
    }

    const paintSet = (set, alphaMul, offsetX, reveal) => {
      if (!set || set.n === 0) return;
      const step = set.n > 1 ? plotW / (set.n - 1) : 0;
      const xs = new Float64Array(set.n);
      for (let i = 0; i < set.n; i++) xs[i] = PAD.left + (set.n > 1 ? i * step : plotW / 2) + offsetX;
      ctx.save();
      ctx.beginPath();
      ctx.rect(PAD.left - 2, 0, (plotW + 4) * reveal, h);
      ctx.clip();

      // FX band: the space between TRY value and constant-FX value.
      const bandA = st.alpha[BAND_KEY] * alphaMul;
      if (bandA > 0.01 && set.n > 1) {
        ctx.globalAlpha = bandA * 0.32;
        ctx.fillStyle = c.fx;
        ctx.beginPath();
        const ya = Array.from(set.value_try, yOf);
        const yb = Array.from(set.value_constant_fx_try, yOf);
        tracePath(ctx, xs, ya);
        for (let i = set.n - 1; i >= 0; i--) ctx.lineTo(xs[i], yb[i]);
        ctx.closePath();
        ctx.fill();
      }

      // Soft gradient under the headline series.
      const va = st.alpha.value_try * alphaMul;
      if (va > 0.01 && set.n > 1) {
        const ys = Array.from(set.value_try, yOf);
        const grad = ctx.createLinearGradient(0, PAD.top, 0, PAD.top + plotH);
        grad.addColorStop(0, c.value);
        grad.addColorStop(1, "transparent");
        ctx.globalAlpha = va * 0.16;
        ctx.fillStyle = grad;
        ctx.beginPath();
        tracePath(ctx, xs, ys);
        ctx.lineTo(xs[set.n - 1], PAD.top + plotH);
        ctx.lineTo(xs[0], PAD.top + plotH);
        ctx.closePath();
        ctx.fill();
      }

      for (let si = SERIES.length - 1; si >= 0; si--) {
        const s = SERIES[si];
        const a = st.alpha[s.key] * alphaMul;
        if (a < 0.01) continue;
        ctx.globalAlpha = a;
        ctx.strokeStyle = c[s.color];
        ctx.lineWidth = s.width;
        ctx.lineJoin = "round";
        ctx.lineCap = "round";
        ctx.setLineDash(s.dash);
        ctx.beginPath();
        tracePath(ctx, xs, Array.from(set[s.key], yOf));
        ctx.stroke();
      }
      ctx.setLineDash([]);
      ctx.restore();
      ctx.globalAlpha = 1;
      return xs;
    };

    const dir = st.swapDir || 0;
    if (st.old && swap < 1) paintSet(st.old, 1 - e, -dir * 36 * e, 1);
    const reveal = st.mountReveal && st.swapStart ? e : 1;
    const xs = paintSet(D, st.old ? e : 1, st.old ? dir * 36 * (1 - e) : 0, reveal);

    // X labels.
    if (D.n > 0) {
      ctx.fillStyle = c.axis;
      ctx.textAlign = "center";
      ctx.textBaseline = "alphabetic";
      ctx.globalAlpha = st.old ? e : 1;
      const every = Math.max(1, Math.ceil(D.n / Math.max(2, Math.floor(plotW / 84))));
      for (let i = 0; i < D.n; i += every) {
        const label = st.intraday ? dfTime.format(new Date(D.x[i])) : dfShort.format(new Date(D.x[i]));
        ctx.fillText(label, Math.min(w - PAD.right - 16, Math.max(PAD.left + 16, xs[i])), h - 8);
      }
      ctx.globalAlpha = 1;
    }

    // Selection band.
    if (st.sel && st.sel.a !== st.sel.b && xs) {
      const x1 = xs[Math.min(st.sel.a, st.sel.b)], x2 = xs[Math.max(st.sel.a, st.sel.b)];
      ctx.fillStyle = c.selection;
      ctx.globalAlpha = 0.1;
      ctx.fillRect(x1, PAD.top, x2 - x1, plotH);
      ctx.globalAlpha = 0.6;
      ctx.fillRect(x1 - 0.5, PAD.top, 1, plotH);
      ctx.fillRect(x2 - 0.5, PAD.top, 1, plotH);
      ctx.globalAlpha = 1;
    }

    // Crosshair: eases toward the hovered point so it glides rather than snaps.
    const tip = tipRef.current;
    if (st.hover !== null && xs && st.hover < D.n) {
      const tx = xs[st.hover];
      st.tipX = st.tipX === null ? tx : ease1(st.tipX, tx);
      const x = st.tipX;
      ctx.strokeStyle = c.cross;
      ctx.globalAlpha = 0.35;
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(Math.round(x) + 0.5, PAD.top);
      ctx.lineTo(Math.round(x) + 0.5, PAD.top + plotH);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.globalAlpha = 1;
      for (const s of SERIES) {
        if (st.alpha[s.key] < 0.5) continue;
        const y = yOf(D[s.key][st.hover]);
        ctx.fillStyle = c.bg;
        ctx.beginPath();
        ctx.arc(tx, y, 5, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = c[s.color];
        ctx.beginPath();
        ctx.arc(tx, y, 3.2, 0, Math.PI * 2);
        ctx.fill();
      }
      if (tip) {
        const tw = tip.offsetWidth || 220;
        const left = x + 16 + tw > w ? x - 16 - tw : x + 16;
        tip.style.transform = `translate3d(${Math.round(left)}px, ${PAD.top + 4}px, 0)`;
      }
    } else {
      st.tipX = null;
    }

    // Live pulse sits on the last value as a DOM node, so its CSS animation runs on the
    // compositor and never forces the canvas to repaint.
    const pulse = pulseRef.current;
    if (pulse) {
      if (st.live && xs && D.n > 0 && st.alpha.value_try > 0.5 && !st.old) {
        const y = yOf(D.value_try[D.n - 1]);
        pulse.style.opacity = "1";
        pulse.style.transform = `translate3d(${xs[D.n - 1]}px, ${y}px, 0)`;
      } else {
        pulse.style.opacity = "0";
      }
    }

    return moving;
  };

  const kick = () => {
    if (st.frame) return;
    st.last = 0;
    const loop = (now) => {
      const more = drawRef.current(now);
      st.frame = more ? requestAnimationFrame(loop) : 0;
    };
    st.frame = requestAnimationFrame(loop);
  };

  // ---------------------------------------------------------------- inputs
  useEffect(() => {
    const next = datasetFrom(data);
    const prev = st.target;
    if (prev && sameShape(prev, next)) {
      st.target = next; // values glide
    } else {
      st.old = prev && prev.n ? st.shown : null;
      st.target = next;
      st.shown = null;
      st.hover = null;
      st.sel = null;
      st.swapStart = performance.now();
      st.swapDir = panDir > 0 ? -1 : panDir < 0 ? 1 : 0;
      if (!prev) st.mountReveal = true;
    }
    kick();
  }, [data]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    st.hidden = hidden;
    st.anyTax = anyTax;
    st.intraday = intraday;
    st.live = live;
    kick();
  }, [hidden, anyTax, intraday, live]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!selection) { st.sel = null; kick(); }
  }, [selection]); // eslint-disable-line react-hooks/exhaustive-deps

  useLayoutEffect(() => {
    const wrap = wrapRef.current;
    const canvas = canvasRef.current;
    st.colors = readColors();
    const resize = () => {
      const rect = wrap.getBoundingClientRect();
      st.w = rect.width;
      st.h = rect.height;
      st.dpr = Math.min(2, window.devicePixelRatio || 1);
      canvas.width = Math.round(st.w * st.dpr);
      canvas.height = Math.round(st.h * st.dpr);
      canvas.style.width = `${st.w}px`;
      canvas.style.height = `${st.h}px`;
      st.last = 0;
      drawRef.current(performance.now());
    };
    const ro = new ResizeObserver(resize);
    ro.observe(wrap);
    resize();
    const mo = new MutationObserver(() => { st.colors = readColors(); kick(); });
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    document.fonts?.ready.then(() => kick());
    return () => {
      ro.disconnect();
      mo.disconnect();
      cancelAnimationFrame(st.frame);
      st.frame = 0;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const indexAt = (clientX) => {
    const T = st.target;
    if (!T || T.n === 0) return null;
    const rect = canvasRef.current.getBoundingClientRect();
    const plotW = Math.max(10, st.w - PAD.left - PAD.right);
    const rel = (clientX - rect.left - PAD.left) / plotW;
    return Math.max(0, Math.min(T.n - 1, Math.round(rel * (T.n - 1))));
  };

  const setHover = (i) => {
    if (i === st.hover) return;
    st.hover = i;
    st.cb.onHover?.(i);
    kick();
  };

  const onPointerDown = (e) => {
    const i = indexAt(e.clientX);
    if (i === null) return;
    e.currentTarget.setPointerCapture?.(e.pointerId);
    st.dragging = true;
    st.sel = { a: i, b: i };
    setHover(i);
    kick();
  };
  const onPointerMove = (e) => {
    const i = indexAt(e.clientX);
    if (i === null) return;
    setHover(i);
    if (st.dragging && st.sel && st.sel.b !== i) {
      st.sel = { ...st.sel, b: i };
      st.cb.onSelect?.(st.sel.a === st.sel.b ? null : { a: st.sel.a, b: st.sel.b });
      kick();
    }
  };
  const endDrag = () => {
    if (!st.dragging) return;
    st.dragging = false;
    if (st.sel && st.sel.a === st.sel.b) {
      st.sel = null;
      st.cb.onSelect?.(null);
    }
    kick();
  };

  return (
    <div className="vchart" ref={wrapRef} style={{ height }}>
      <canvas
        ref={canvasRef}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        onPointerLeave={() => { if (!st.dragging) setHover(null); }}
        role="img"
        aria-label={t("chart.aria")}
      />
      <div ref={pulseRef} className="vchart-pulse" aria-hidden="true"><span /></div>
      <div ref={tipRef} className={`vchart-tip ${tooltip ? "on" : ""}`} aria-hidden="true">
        {tooltip}
      </div>
    </div>
  );
}
