// Development-only mock of the faðir API, served by the Vite dev server in `mock` mode:
//
//   npm run dev:mock      → http://localhost:5173 with synthetic data, no backend needed
//
// Why it exists: the real server only accepts requests whose Origin is the hosted
// domain, so a local browser cannot get past guest bootstrap. This lets either interface
// be developed and checked end to end. All data is synthetic (AGENTS.md) and lives in
// memory; it is never part of a production build.
//
// Prices random-walk on every read so polling, flashes and chart easing can be seen.
// Transactions drive the positions, so adding or deleting one changes the dashboard.

const INCEPTION = "2026-03-29";

const INSTRUMENTS = [
  { id: 1, ticker: "AAPL", exchange: "NASDAQ", yf_symbol: "AAPL", currency: "USD", name: "Apple Inc.", active: true, price: 231.4, fx: 41.2, vol: 0.012, fxVol: 0.003 },
  { id: 2, ticker: "ASML", exchange: "AEX", yf_symbol: "ASML.AS", currency: "EUR", name: "ASML Holding", active: true, price: 712.8, fx: 47.9, vol: 0.016, fxVol: 0.004 },
  { id: 3, ticker: "THYAO", exchange: "BIST", yf_symbol: "THYAO.IS", currency: "TRY", name: "Türk Hava Yolları", active: true, price: 318.25, fx: 1, vol: 0.018, fxVol: 0 },
  { id: 4, ticker: "VOLV-B", exchange: "STO", yf_symbol: "VOLV-B.ST", currency: "SEK", name: "Volvo B", active: true, price: 268.6, fx: 4.31, vol: 0.014, fxVol: 0.004, triangulated: true },
  { id: 5, ticker: "2330", exchange: "TWSE", yf_symbol: "2330.TW", currency: "TWD", name: "TSMC", active: true, price: 1045, fx: 1.29, vol: 0.017, fxVol: 0.003, triangulated: true },
];

// Synthetic stand-ins for Yahoo search hits that are not yet known instruments.
const YAHOO = [
  ["MSFT", "Microsoft Corporation", "NASDAQ"], ["NVDA", "NVIDIA Corporation", "NASDAQ"],
  ["AMZN", "Amazon.com, Inc.", "NASDAQ"], ["AAPL.MX", "Apple Inc.", "MEX"], ["SAP.DE", "SAP SE", "XETRA"],
  ["AIR.PA", "Airbus SE", "PAR"], ["ASELS.IS", "Aselsan Elektronik", "BIST"], ["BP.L", "BP p.l.c.", "LSE"],
  ["AMD", "Advanced Micro Devices, Inc.", "NASDAQ"], ["ADBE", "Adobe Inc.", "NASDAQ"],
];

let nextTxnId = 100;
const seedTxns = [
  ["AAPL", "2026-04-02", "BUY", 40, 198.5, 1, 38.4],
  ["AAPL", "2026-06-11", "BUY", 15, 214.2, 1, 39.6],
  ["ASML", "2026-04-08", "BUY", 8, 640.0, 2, 43.9],
  ["THYAO", "2026-04-15", "BUY", 600, 286.0, 12, 1],
  ["THYAO", "2026-08-20", "SELL", 150, 305.5, 8, 1],
  ["VOLV-B", "2026-05-06", "BUY", 120, 241.0, 9, 3.98],
  ["2330", "2026-07-01", "BUY", 200, 960.0, 40, 1.21],
];

function makeStore() {
  return {
    authed: false,
    guestNoticeDue: true,
    // "none" until the browser enters a code, starts a Portfolio, or signs in.
    access: "none",
    passPortfolio: null,
    codeFailures: 0,
    portfolios: [
      { id: 1, name: "Ana Portföy", base_currency: "TRY", code: "4821" },
      { id: 2, name: "Uzun vade", base_currency: "TRY", code: "0730" },
    ],
    txns: {
      1: seedTxns.map(([ticker, trade_date, side, quantity, price_native, fees_native, fx], i) => txn(i + 1, ticker, trade_date, side, quantity, price_native, fees_native, fx)),
      2: [txn(50, "AAPL", "2026-05-02", "BUY", 10, 205, 1, 39.1), txn(51, "ASML", "2026-09-01", "BUY", 3, 690, 2, 46.8)],
    },
    live: Object.fromEntries(INSTRUMENTS.map((i) => [i.ticker, { price: i.price, fx: i.fx, prevPrice: i.price * 0.994, prevFx: i.fx * 0.999 }])),
  };
}

function txn(id, ticker, trade_date, side, quantity, price_native, fees_native, fx, note = null, manual = false) {
  const inst = INSTRUMENTS.find((i) => i.ticker === ticker);
  const total_native = side === "BUY" ? quantity * price_native + fees_native : quantity * price_native - fees_native;
  return {
    id, instrument_id: inst.id, ticker, currency: inst.currency, trade_date, side,
    quantity: String(quantity), price_native: String(price_native), fees_native: String(fees_native),
    total_native: total_native.toFixed(2), fx_rate_to_try: fx.toFixed(4), fx_rate_date: trade_date,
    fx_provider: manual ? "manual" : inst.currency === "TRY" ? "identity" : inst.triangulated ? `yfinance:${inst.currency}USD*USDTRY` : "tcmb",
    fx_carried_forward: new Date(trade_date).getDay() % 6 === 0,
    total_try: (total_native * fx).toFixed(2), note,
  };
}

let store = makeStore();

const isOpen = (exchange) => {
  const h = new Date().getUTCHours();
  if ([0, 6].includes(new Date().getUTCDay())) return false;
  if (exchange === "BIST") return h >= 7 && h < 15;
  if (exchange === "NASDAQ") return h >= 13 && h < 20;
  if (exchange === "TWSE") return h >= 1 && h < 5;
  return h >= 7 && h < 16;
};

function tick() {
  for (const inst of INSTRUMENTS) {
    const s = store.live[inst.ticker];
    const open = isOpen(inst.exchange);
    if (open) s.price *= 1 + (Math.random() - 0.48) * inst.vol * 0.08;
    if (inst.fxVol) s.fx *= 1 + (Math.random() - 0.47) * inst.fxVol * 0.05;
  }
}

const f = (n, d = 2) => Number(n).toFixed(d);

function positionsFor(portfolioId, tickers) {
  const txns = store.txns[portfolioId] ?? [];
  const rows = [];
  for (const inst of INSTRUMENTS) {
    if (tickers?.length && !tickers.includes(inst.ticker)) continue;
    const mine = txns.filter((t) => t.ticker === inst.ticker).sort((a, b) => a.trade_date.localeCompare(b.trade_date));
    if (!mine.length) continue;
    let qty = 0, costNative = 0, costTry = 0, buyQty = 0, buyCost = 0, realizedTry = 0;
    for (const t of mine) {
      const q = Number(t.quantity), p = Number(t.price_native), fee = Number(t.fees_native), fx = Number(t.fx_rate_to_try);
      if (t.side === "BUY") {
        qty += q; costNative += q * p + fee; costTry += (q * p + fee) * fx; buyQty += q; buyCost += q * p + fee;
      } else if (qty > 0) {
        const share = Math.min(1, q / qty);
        realizedTry += (q * p - fee) * fx - costTry * share;
        costNative *= 1 - share; costTry *= 1 - share; qty -= q;
      }
    }
    if (qty <= 0) continue;
    rows.push({ inst, qty, costNative, costTry, avg: buyQty ? buyCost / buyQty : null, realizedTry });
  }
  return rows.map(({ inst, qty, costNative, costTry, avg, realizedTry }) => {
    const s = store.live[inst.ticker];
    const failed = inst.ticker === "2330" && portfolioId === 1 && Math.random() < 0;
    const mvNative = qty * s.price;
    const mvTry = mvNative * s.fx;
    const avgFx = costTry / costNative;
    const localReturn = mvNative / costNative;
    const totalReturn = mvTry / costTry;
    const fxReturn = totalReturn / localReturn;
    const priceEffect = (mvNative - costNative) * avgFx;
    const fxEffect = mvTry - costTry - priceEffect;
    const dailyTry = qty * (s.price * s.fx - s.prevPrice * s.prevFx);
    const dailyPrice = qty * (s.price - s.prevPrice) * s.prevFx;
    const open = isOpen(inst.exchange);
    return {
      ticker: inst.ticker, name: inst.name, exchange: inst.exchange, currency: inst.currency,
      quantity: f(qty, 4), average_purchase_price_native: avg === null ? null : f(avg, 4),
      cost_native: f(costNative), cost_try: f(costTry), market_value_native: f(mvNative), market_value_try: f(mvTry),
      pnl_native: f(mvNative - costNative), pnl_try: f(mvTry - costTry),
      attribution: { local_return: f(localReturn, 6), fx_return: f(fxReturn, 6), total_return: f(totalReturn, 6) },
      realized: { quantity: "0", pnl_native: "0", pnl_try: f(realizedTry), price_effect_try: "0", fx_effect_try: "0" },
      daily: {
        available: true, reference_date: new Date(Date.now() - 86400000).toISOString().slice(0, 10),
        pnl_try: f(dailyTry), price_effect_try: f(dailyPrice), fx_effect_try: f(dailyTry - dailyPrice),
        pnl_native: f(qty * (s.price - s.prevPrice)), return_ratio: f((s.price * s.fx) / (s.prevPrice * s.prevFx), 6),
      },
      price_native: f(s.price, 4), price_date: new Date().toISOString().slice(0, 10),
      fx_rate_to_try: f(s.fx, 6), fx_rate_date: new Date().toISOString().slice(0, 10),
      fx_provider: inst.currency === "TRY" ? "identity" : inst.triangulated ? `yfinance:${inst.currency}USD*USDTRY` : "yfinance",
      fx_triangulated: !!inst.triangulated, fx_carried_forward: inst.ticker === "VOLV-B",
      lot_count: 1, ok: !failed, session: open ? "open" : "closed", stale: !open, error: failed ? "Yahoo yanıt vermedi" : null,
    };
  });
}

function portfolioOut(portfolioId) {
  tick();
  const positions = positionsFor(portfolioId);
  const ok = positions.filter((p) => p.ok);
  const sum = (key) => ok.reduce((s, p) => s + Number(p[key]), 0);
  const cost = sum("cost_try"), mv = sum("market_value_try"), pnl = mv - cost;
  const price = ok.reduce((s, p) => s + (Number(p.pnl_native) * (Number(p.cost_try) / Number(p.cost_native))), 0);
  const realized = ok.reduce((s, p) => s + Number(p.realized.pnl_try), 0);
  const daily = ok.reduce((s, p) => s + Number(p.daily.pnl_try), 0);
  const dailyPrice = ok.reduce((s, p) => s + Number(p.daily.price_effect_try), 0);
  const haircut = 0.0035;
  const net = mv * (1 - haircut);
  const taxable = Math.max(0, pnl * 0.4);
  const tax = taxable * 0.15;
  const anyOpen = positions.some((p) => p.session === "open");
  const next = new Date();
  next.setUTCHours(7, 0, 0, 0);
  if (next < new Date()) next.setUTCDate(next.getUTCDate() + 1);
  return {
    as_of: new Date().toISOString(), base_currency: "TRY", positions,
    totals: {
      cost_try: f(cost), market_value_try: f(mv), pnl_try: f(pnl), price_effect_try: f(price), fx_effect_try: f(pnl - price),
      total_return: cost ? f(mv / cost, 6) : null, realized_pnl_try: f(realized), realized_price_effect_try: "0", realized_fx_effect_try: "0",
      daily: { available: positions.length > 0, reference_date: new Date(Date.now() - 86400000).toISOString().slice(0, 10), pnl_try: f(daily), price_effect_try: f(dailyPrice), fx_effect_try: f(daily - dailyPrice), pnl_native: "0", return_ratio: mv ? f(mv / (mv - daily), 6) : null },
    },
    liquidation: {
      gross_proceeds_try: f(mv), haircut_pct: f(haircut, 4), haircut_try: f(mv * haircut), net_proceeds_try: f(net),
      total_invested_try: f(cost), net_pnl_try: f(net - cost), net_return: cost ? f(net / cost, 6) : null, excludes_tax: true,
    },
    tax: {
      applicable: positions.length > 0, gross_gain_try: f(pnl), taxable_gain_try: f(taxable), tax_try: f(tax), net_after_tax_try: f(net - tax),
      effective_rate: f(pnl > 0 ? tax / pnl : 0, 4), marginal_rate: "0.15", indexing_applied: true, indexing_rate: "0.21",
      price_portion_try: f(taxable * 0.62), fx_portion_try: f(taxable * 0.38), tax_on_price_try: f(tax * 0.62), tax_on_fx_try: f(tax * 0.38),
      assumptions: ["Yİ-ÜFE endekslemesi alış ayından bir önceki aya göre uygulanır.", "Yabancı hisse kazançları beyana tabidir; BIST hisseleri stopaja tabidir (%0)."],
      disclaimer: "Sentetik geliştirme verisi — vergi danışmanlığı değildir.",
    },
    warnings: [], next_market_open: anyOpen ? null : next.toISOString(),
  };
}

function seriesValue(portfolioId, tickers, t, seed) {
  // Smooth synthetic path that ends on today's real mock value.
  const positions = positionsFor(portfolioId, tickers);
  const mv = positions.reduce((s, p) => s + Number(p.market_value_try), 0);
  const cost = positions.reduce((s, p) => s + Number(p.cost_try), 0);
  const wave = Math.sin(t * 9 + seed) * 0.035 + Math.sin(t * 23 + seed * 2) * 0.015 + Math.sin(t * 57) * 0.006;
  const growth = 1 + (mv / (cost || 1) - 1) * t;
  const fxPart = 0.5 + 0.5 * t;
  const costT = cost * (0.55 + 0.45 * Math.min(1, t * 1.6));
  const value = costT * (growth + wave * (1 - t * 0.6));
  const constFx = costT + (value - costT) * (1 - fxPart * 0.45);
  const tax = Math.max(0, (value - costT) * 0.06);
  return { value, constFx, cost: costT, tax };
}

function point(v, extra) {
  return {
    ...extra,
    value_try: f(v.value), value_constant_fx_try: f(v.constFx), cost_basis_try: f(v.cost),
    value_after_tax_try: f(v.value - v.tax), pnl_try: f(v.value - v.cost), pnl_after_tax_try: f(v.value - v.cost - v.tax),
    tax_try: f(v.tax), price_effect_try: f(v.constFx - v.cost), fx_effect_try: f(v.value - v.constFx), missing: [],
  };
}

function history(portfolioId, from, to, tickers) {
  const start = new Date(INCEPTION);
  const end = to ? new Date(to) : new Date();
  const total = (new Date() - start) / 86400000;
  const points = [];
  for (let d = new Date(from ?? INCEPTION); d <= end; d.setDate(d.getDate() + 1)) {
    if (d < start) continue;
    const t = Math.min(1, (d - start) / 86400000 / total);
    points.push(point(seriesValue(portfolioId, tickers, t, tickers?.length ?? 0), { date: d.toISOString().slice(0, 10), price_carried_forward: [0, 6].includes(d.getDay()), fx_carried_forward: false }));
  }
  return { start: from ?? INCEPTION, end: end.toISOString().slice(0, 10), freq: "D", points, tickers: tickers ?? [] };
}

function intraday(portfolioId, offset, tickers) {
  const day = new Date();
  day.setDate(day.getDate() - offset);
  day.setUTCHours(6, 0, 0, 0);
  const bars = offset === 0 ? Math.min(132, Math.max(12, Math.floor((Date.now() - day) / 300000))) : 132;
  const base = seriesValue(portfolioId, tickers, 1 - offset * 0.004, 0);
  const points = [];
  for (let i = 0; i < bars; i++) {
    const k = i / 132;
    const drift = 1 + Math.sin(k * 7 + offset) * 0.006 + Math.sin(k * 31) * 0.002 + (k - 0.5) * 0.004;
    const v = { value: base.value * drift, constFx: base.constFx * (1 + (drift - 1) * 0.7), cost: base.cost, tax: base.tax };
    points.push(point(v, { at: new Date(day.getTime() + i * 300000).toISOString(), carried_forward: i % 17 === 0 }));
  }
  return { interval: "5m", session_date: day.toISOString().slice(0, 10), points, warnings: [], tickers: tickers ?? [], offset, sessions_available: 5 };
}

function send(res, status, body, headers = {}) {
  res.statusCode = status;
  for (const [k, v] of Object.entries(headers)) res.setHeader(k, v);
  if (body === null) return res.end();
  if (typeof body === "string") return res.end(body);
  res.setHeader("Content-Type", "application/json");
  res.end(JSON.stringify(body));
}

const readBody = (req) => new Promise((resolve) => {
  let data = "";
  req.on("data", (c) => { data += c; });
  req.on("end", () => { try { resolve(data ? JSON.parse(data) : {}); } catch { resolve({}); } });
});

async function handle(req, res) {
  const url = new URL(req.url, "http://mock");
  const path = url.pathname;
  const method = req.method;
  const visible = store.access === "code" ? store.portfolios.filter((p) => p.id === store.passPortfolio) : store.portfolios;
  const pid = Number(url.searchParams.get("portfolio_id") || visible[0]?.id || 1);
  const tickers = url.searchParams.getAll("ticker");
  await new Promise((r) => setTimeout(r, 120 + Math.random() * 220)); // network feel

  if (path === "/api/health") return send(res, 200, { ok: true });
  if (path === "/api/access") return send(res, 200, { mode: store.authed ? "user" : store.access, code_lengths: [4] });
  if (path === "/api/access/code" && method === "POST") {
    const { code } = await readBody(req);
    if (store.codeFailures >= 8) return send(res, 429, { detail: "too many attempts" });
    const hit = store.portfolios.find((p) => p.code === code);
    if (!hit) { store.codeFailures += 1; return send(res, 404, { detail: "code not found" }); }
    store.access = "code";
    store.passPortfolio = hit.id;
    return send(res, 200, { mode: "code", code_lengths: [4] });
  }
  if (path === "/api/access/code" && method === "DELETE") { store.access = "none"; store.passPortfolio = null; return send(res, 204, null); }
  if (path === "/api/portfolios/start") {
    if (!store.portfolios.length) store.portfolios.push({ id: 1, name: "Ana Portföy", base_currency: "TRY", code: "5190" });
    return send(res, 200, store.portfolios[0]);
  }
  if (path === "/api/portfolios" && method === "POST") {
    const body = await readBody(req);
    const name = String(body?.name ?? "").trim();
    if (store.portfolios.some((x) => x.name === name)) return send(res, 409, { detail: "name taken" });
    const created = { id: store.portfolios.length + 1, name, base_currency: body?.base_currency ?? "TRY", code: String(1000 + Math.floor(Math.random() * 9000)) };
    store.portfolios.push(created);
    return send(res, 201, created);
  }
  if (path === "/api/auth/sign-out") { store.access = "none"; store.passPortfolio = null; return send(res, 204, null); }
  const codeMatch = path.match(/^\/api\/portfolios\/(\d+)\/code$/);
  if (codeMatch) {
    const p = store.portfolios.find((x) => x.id === Number(codeMatch[1]));
    p.code = String(Math.floor(Math.random() * 10000)).padStart(4, "0");
    return send(res, 200, { code: p.code });
  }
  if (path === "/api/guest/bootstrap") {
    if (store.access === "none") store.access = "guest";
  }
  if (path === "/api/guest/bootstrap") return send(res, 200, { guest: { notice_due: store.guestNoticeDue, expires_at: new Date(Date.now() + 80 * 86400000).toISOString() } });
  if (path === "/api/auth/recover-user-cookie") return send(res, 403, { detail: "request rejected" });
  if (path === "/api/user/sessions") return store.authed ? send(res, 200, { sessions: [] }) : send(res, 401, { detail: "request rejected" });
  if (path === "/api/auth/google/start") return send(res, 200, { nonce: "mock-nonce", client_id: "mock-client" });
  if (path === "/api/auth/google/verify") {
    return send(res, 200, { expires_at: new Date(Date.now() + 600000).toISOString(), choice_needed: true, account_exists: false, guest_portfolios: store.portfolios.length, name_conflicts: [] });
  }
  if (path === "/api/auth/google/transition") {
    const body = await readBody(req);
    if (body.action !== "merge") { store.authed = true; store.guestNoticeDue = false; }
    return send(res, 200, { action: body.action });
  }
  if (path === "/api/portfolio/merge/options") return send(res, 200, { source: [store.portfolios[1]].filter(Boolean), target: [store.portfolios[0]].filter(Boolean) });
  if (path === "/api/portfolio/merge/preview") {
    const body = await readBody(req);
    const src = store.txns[body.source_portfolio_id] ?? [];
    const tgt = store.txns[body.target_portfolio_id] ?? [];
    return send(res, 200, {
      source_portfolio_id: body.source_portfolio_id, target_portfolio_id: body.target_portfolio_id, revision_token: "mock-rev",
      movable_source_rows: src.slice(1), candidates: src[0] && tgt[0] ? [{ source: src[0], target: tgt[0], differences: [{ field: "price_native" }] }] : [],
    });
  }
  if (path === "/api/portfolio/merge/confirm") {
    store.authed = true;
    return send(res, 200, { moved_count: 1, skipped_count: 1 });
  }
  if (path === "/api/portfolios" && method === "GET") return send(res, 200, visible);
  if (path === "/api/portfolio") return send(res, 200, portfolioOut(pid));
  if (path === "/api/portfolio/history") return send(res, 200, history(pid, url.searchParams.get("from"), url.searchParams.get("to"), tickers));
  if (path === "/api/portfolio/intraday") return send(res, 200, intraday(pid, Number(url.searchParams.get("offset") || 0), tickers));
  if (path === "/api/instruments") return send(res, 200, INSTRUMENTS.map(({ id, ticker, exchange, yf_symbol, currency, name, active }) => ({ id, ticker, exchange, yf_symbol, currency, name, active })));
  if (path === "/api/refresh") { tick(); return send(res, 200, { refreshed: true }); }
  if (path === "/api/transactions" && method === "GET") return send(res, 200, store.txns[pid] ?? []);
  if (path === "/api/transactions" && method === "POST") {
    const b = await readBody(req);
    if (b.yf_symbol && !INSTRUMENTS.some((i) => i.yf_symbol === b.yf_symbol)) {
      const hit = YAHOO.find(([sym]) => sym === b.yf_symbol);
      const price = Number(b.price_native) || 100;
      INSTRUMENTS.push({ id: INSTRUMENTS.length + 1, ticker: b.yf_symbol, exchange: hit?.[2] ?? "NASDAQ", yf_symbol: b.yf_symbol, currency: "USD", name: hit?.[1] ?? b.yf_symbol, active: true, price, fx: 41.2, vol: 0.012, fxVol: 0.003 });
      store.live[b.yf_symbol] = { price, fx: 41.2, prevPrice: price, prevFx: 41.2 };
    }
    if (b.yf_symbol) b.ticker = INSTRUMENTS.find((i) => i.yf_symbol === b.yf_symbol).ticker;
    const inst = INSTRUMENTS.find((i) => i.ticker === b.ticker);
    if (!inst || !(Number(b.quantity) > 0)) return send(res, 422, { detail: "Geçersiz işlem" });
    if (!store.portfolios.length) store.portfolios.push({ id: 1, name: "Ana Portföy", base_currency: "TRY", code: "5190" });
    const fx = b.fx_rate_override ? Number(b.fx_rate_override) : store.live[inst.ticker].fx;
    const row = txn(nextTxnId++, b.ticker, b.trade_date, b.side, Number(b.quantity), Number(b.price_native), Number(b.fees_native || 0), fx, b.note, !!b.fx_rate_override);
    (store.txns[pid] ??= []).push(row);
    return send(res, 201, row);
  }
  const txnMatch = path.match(/^\/api\/transactions\/(\d+)$/);
  if (txnMatch) {
    const list = store.txns[pid] ?? [];
    const idx = list.findIndex((t) => t.id === Number(txnMatch[1]));
    if (idx < 0) return send(res, 404, { detail: "request rejected" });
    if (method === "DELETE") { list.splice(idx, 1); return send(res, 204, null); }
    const b = await readBody(req);
    const old = list[idx];
    const fx = b.fx_rate_override ? Number(b.fx_rate_override) : Number(old.fx_rate_to_try);
    list[idx] = txn(old.id, old.ticker, b.trade_date ?? old.trade_date, b.side ?? old.side, Number(b.quantity ?? old.quantity), Number(b.price_native ?? old.price_native), Number(b.fees_native ?? old.fees_native), fx, old.note, !!b.fx_rate_override);
    return send(res, 200, list[idx]);
  }
  const exportMatch = path.match(/^\/api\/portfolios\/(\d+)\/export$/);
  if (exportMatch) {
    const format = url.searchParams.get("format");
    const rows = store.txns[Number(exportMatch[1])] ?? [];
    const body = format === "csv"
      ? ["ticker,trade_date,side,quantity,price_native", ...rows.map((r) => [r.ticker, r.trade_date, r.side, r.quantity, r.price_native].join(","))].join("\n")
      : JSON.stringify({ transactions: rows }, null, 2);
    return send(res, 200, body, { "Content-Type": format === "csv" ? "text/csv" : "application/json", "Content-Disposition": `attachment; filename="portfolio-${exportMatch[1]}.${format}"` });
  }
  const pfMatch = path.match(/^\/api\/portfolios\/(\d+)$/);
  if (pfMatch && method === "DELETE") {
    store.portfolios = store.portfolios.filter((p) => p.id !== Number(pfMatch[1]));
    delete store.txns[Number(pfMatch[1])];
    return send(res, 204, null);
  }
  if (path === "/api/account" && method === "DELETE") { store = makeStore(); store.portfolios = []; store.txns = {}; return send(res, 204, null); }
  if (path === "/api/instruments/search") {
    const q = (url.searchParams.get("q") || "").toUpperCase();
    const known = INSTRUMENTS.filter((i) => i.ticker.includes(q) || i.name.toUpperCase().includes(q))
      .map(({ yf_symbol, ticker, name, exchange, currency }) => ({ yf_symbol, ticker, name, exchange, currency, known: true }));
    const yahoo = YAHOO.filter(([sym, name]) => sym.includes(q) || name.toUpperCase().includes(q))
      .map(([sym, name, exchange]) => ({ yf_symbol: sym, ticker: sym, name, exchange, currency: null, known: false }));
    return send(res, 200, [...known, ...yahoo].slice(0, 8));
  }
  if (path === "/api/tax/jurisdictions") {
    return send(res, 200, [
      { code: "TR", currency: "TRY", years: [2025, 2026] },
      { code: "GB", currency: "GBP", years: [2025, 2026] },
      { code: "DE", currency: "EUR", years: [2025, 2026] },
      { code: "US", currency: "USD", years: [2025, 2026] },
      { code: "FR", currency: "EUR", years: [2026] },
    ]);
  }
  if (path === "/api/tax/estimates") {
    if (!store.authed) return send(res, 403, { detail: "Tax Profile requires a signed-in User" });
    const code = url.searchParams.get("jurisdiction");
    const year = Number(url.searchParams.get("year"));
    const ccy = { TR: "TRY", GB: "GBP", DE: "EUR", US: "USD", FR: "EUR" }[code];
    const gross = { TR: 86377.21, GB: 2012.4, DE: 1841.9, US: 2210.5, FR: 1841.9 }[code];
    const rate = { TR: 0.15, GB: 0, DE: 0.26375, US: 0, FR: 0.314 }[code];
    const taxable = code === "GB" ? 0 : code === "DE" ? gross - 1000 : code === "US" ? 0 : gross;
    const start = code === "GB" ? `${year}-04-06` : `${year}-01-01`;
    const end = code === "GB" ? `${year + 1}-04-05` : `${year}-12-31`;
    const keys = { TR: ["tr.tariff", "tr.fifo", "tr.no_exemption"], GB: ["gb.rates", "gb.exempt", "gb.no_income", "gb.no_pooling"], DE: ["de.flat", "de.allowance", "de.no_church"], US: ["us.single", "us.no_income", "us.holding", "us.niit", "us.federal_only"], FR: ["fr.pfu", "fr.no_bareme", "fr.no_carryforward"] }[code];
    const tax = taxable * rate;
    return send(res, 200, {
      jurisdiction: code, tax_year: year, currency: ccy, period_start: start, period_end: end,
      gross_gain: gross.toFixed(2), taxable_gain: taxable.toFixed(2), tax: tax.toFixed(2), net_after_tax: (gross * 4 - tax).toFixed(2),
      effective_rate: taxable ? String(rate) : "0", marginal_rate: String(rate), assumptions: keys,
      source_url: "https://example.invalid/tax", source_version: `Synthetic ${code} ${year}`,
    });
  }
  if (path === "/api/tax/profile") {
    if (!store.authed) return send(res, 403, { detail: "403" });
    if (url.searchParams.get("year") === "2001") return send(res, 404, { detail: "missing" });
    return send(res, 200, { id: 1, jurisdiction: "TR", tax_year: Number(url.searchParams.get("year")), currency: "TRY", source_url: "https://example.invalid/tarife", source_version: "mock-1", assumptions: ["Sentetik tarife."], disclaimer: "Geliştirme verisidir." });
  }
  if (path === "/api/tax/estimate") {
    const p = portfolioOut(pid);
    return send(res, 200, { tax_year: Number(url.searchParams.get("year")), jurisdiction: "TR", tax_try: p.tax.tax_try, taxable_gain_try: p.tax.taxable_gain_try, gross_gain_try: p.totals.realized_pnl_try, net_after_tax_try: p.tax.net_after_tax_try, effective_rate: p.tax.effective_rate, marginal_rate: p.tax.marginal_rate });
  }
  return send(res, 404, { detail: "mock: unknown endpoint" });
}

function mount(server) {
  server.middlewares.use((req, res, next) => {
    if (!req.url.startsWith("/api/")) return next();
    handle(req, res).catch((err) => send(res, 500, { detail: String(err) }));
  });
  server.config.logger.info("  faðir mock API active — synthetic data, no backend");
}

/** Dev server (`dev:mock`) and production-bundle preview (`preview:mock`); never a build. */
export default function mockApi() {
  return {
    name: "fadir-mock-api",
    apply: "serve",
    configureServer: mount,
    configurePreviewServer: mount,
  };
}
