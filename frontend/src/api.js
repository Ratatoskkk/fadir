// Thin API client. Everything is same-origin in production; the Vite dev server proxies
// /api to the FastAPI app on 127.0.0.1:8000.

function readableCsrfToken() {
  if (typeof document === "undefined") return null;
  const prefix = "__Host-fadir-csrf=";
  const cookie = document.cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(prefix));
  return cookie ? cookie.slice(prefix.length) : null;
}

async function request(path, options = {}) {
  const method = (options.method ?? "GET").toUpperCase();
  const headers = { "Content-Type": "application/json", ...options.headers };
  if (["POST", "PATCH", "PUT", "DELETE"].includes(method) && path !== "/api/guest/bootstrap") {
    const token = readableCsrfToken();
    if (token) headers["X-CSRF-Token"] = token;
  }
  const response = await fetch(path, {
    ...options,
    credentials: "include",
    headers,
  });
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* response had no JSON body */
    }
    throw new Error(detail);
  }
  return response.status === 204 ? null : response.json();
}

/** `tickers` narrows a series to a subset; omit or pass [] for the whole portfolio. */
const withTickers = (params, tickers) => {
  for (const t of tickers ?? []) params.append("ticker", t);
  return params;
};

export const api = {
  bootstrapGuest: () => request("/api/guest/bootstrap", { method: "POST" }),
  portfolio: () => request("/api/portfolio"),
  history: ({ from, to, freq = "D", tickers } = {}) => {
    const params = new URLSearchParams();
    if (from) params.set("from", from);
    if (to) params.set("to", to);
    params.set("freq", freq);
    return request(`/api/portfolio/history?${withTickers(params, tickers)}`);
  },
  intraday: ({ interval = "5m", force = false, tickers, offset = 0 } = {}) => {
    const params = new URLSearchParams({ interval });
    if (force) params.set("force", "true");
    if (offset) params.set("offset", String(offset));
    return request(`/api/portfolio/intraday?${withTickers(params, tickers)}`);
  },
  transactions: () => request("/api/transactions"),
  createTransaction: (payload) =>
    request("/api/transactions", { method: "POST", body: JSON.stringify(payload) }),
  updateTransaction: (id, payload) =>
    request(`/api/transactions/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteTransaction: (id) => request(`/api/transactions/${id}`, { method: "DELETE" }),
  instruments: () => request("/api/instruments"),
  refresh: () => request("/api/refresh", { method: "POST" }),
  health: () => request("/api/health"),
};
