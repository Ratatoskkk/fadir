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
  const { _recoveryAttempted = false, ...fetchOptions } = options;
  const method = (fetchOptions.method ?? "GET").toUpperCase();
  const headers = { "Content-Type": "application/json", ...fetchOptions.headers };
  if (["POST", "PATCH", "PUT", "DELETE"].includes(method) && path !== "/api/guest/bootstrap") {
    const token = readableCsrfToken();
    if (token) headers["X-CSRF-Token"] = token;
  }
  const response = await fetch(path, {
    ...fetchOptions,
    credentials: "include",
    headers,
  });
  if (!response.ok) {
    if (
      response.status === 401 &&
      method === "GET" &&
      !_recoveryAttempted &&
      path !== "/api/auth/recover-user-cookie" &&
      path !== "/api/guest/bootstrap"
    ) {
      try {
        await request("/api/auth/recover-user-cookie", {
          method: "POST",
          _recoveryAttempted: true,
        });
        return request(path, { ...options, _recoveryAttempted: true });
      } catch {
        // Preserve the original rejected request when recovery is not applicable.
      }
    }
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

const withPortfolioId = (path, portfolioId) => {
  if (portfolioId === null || portfolioId === undefined || portfolioId === "") return path;
  const separator = path.includes("?") ? "&" : "?";
  return `${path}${separator}portfolio_id=${encodeURIComponent(portfolioId)}`;
};

export const api = {
  portfolios: () => request("/api/portfolios"),
  bootstrapGuest: () => request("/api/guest/bootstrap", { method: "POST" }),
  recoverUserCookie: () => request("/api/auth/recover-user-cookie", { method: "POST" }),
  googleStart: () => request("/api/auth/google/start", { method: "POST" }),
  googleVerify: (payload) =>
    request("/api/auth/google/verify", { method: "POST", body: JSON.stringify(payload) }),
  googleTransition: (payload) =>
    request("/api/auth/google/transition", { method: "POST", body: JSON.stringify(payload) }),
  mergeOptions: () => request("/api/portfolio/merge/options"),
  mergePreview: (payload) =>
    request("/api/portfolio/merge/preview", { method: "POST", body: JSON.stringify(payload) }),
  mergeConfirm: (payload) =>
    request("/api/portfolio/merge/confirm", { method: "POST", body: JSON.stringify(payload) }),
  portfolio: (portfolioId) => request(withPortfolioId("/api/portfolio", portfolioId)),
  history: ({ from, to, freq = "D", tickers, portfolioId } = {}) => {
    const params = new URLSearchParams();
    if (from) params.set("from", from);
    if (to) params.set("to", to);
    params.set("freq", freq);
    return request(withPortfolioId(`/api/portfolio/history?${withTickers(params, tickers)}`, portfolioId));
  },
  intraday: ({ interval = "5m", force = false, tickers, offset = 0, portfolioId } = {}) => {
    const params = new URLSearchParams({ interval });
    if (force) params.set("force", "true");
    if (offset) params.set("offset", String(offset));
    return request(withPortfolioId(`/api/portfolio/intraday?${withTickers(params, tickers)}`, portfolioId));
  },
  transactions: (portfolioId) => request(withPortfolioId("/api/transactions", portfolioId)),
  createTransaction: (payload, portfolioId) =>
    request(withPortfolioId("/api/transactions", portfolioId), { method: "POST", body: JSON.stringify(payload) }),
  updateTransaction: (id, payload, portfolioId) =>
    request(withPortfolioId(`/api/transactions/${id}`, portfolioId), { method: "PATCH", body: JSON.stringify(payload) }),
  deleteTransaction: (id, portfolioId) => request(withPortfolioId(`/api/transactions/${id}`, portfolioId), { method: "DELETE" }),
  instruments: () => request("/api/instruments"),
  refresh: () => request("/api/refresh", { method: "POST" }),
  health: () => request("/api/health"),
  taxProfile: (year) => request(`/api/tax/profile?year=${encodeURIComponent(year)}`),
  taxEstimate: (year) => request(`/api/tax/estimate?year=${encodeURIComponent(year)}`),
};
