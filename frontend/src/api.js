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

let privateRequestTail = Promise.resolve();
const GET_TIMEOUT_MS = 30_000;

function serializePrivateRequest(work) {
  const next = privateRequestTail.then(work, work);
  privateRequestTail = next.catch(() => undefined);
  return next;
}

async function performRequest(path, options = {}) {
  const { _recoveryAttempted = false, _responseType = "json", ...fetchOptions } = options;
  const method = (fetchOptions.method ?? "GET").toUpperCase();
  const headers = { "Content-Type": "application/json", ...fetchOptions.headers };
  if (["POST", "PATCH", "PUT", "DELETE"].includes(method) && path !== "/api/guest/bootstrap") {
    const token = readableCsrfToken();
    if (token) headers["X-CSRF-Token"] = token;
  }
  const response = await fetch(path, {
    // Requests run one at a time, so a read that never settles would stall every later
    // one (and all polling) for good. Writes are left alone: they may still be landing.
    signal: fetchOptions.signal ?? (method === "GET" ? AbortSignal.timeout(GET_TIMEOUT_MS) : undefined),
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
      path !== "/api/guest/bootstrap" &&
      path !== "/api/access"
    ) {
      try {
        await performRequest("/api/auth/recover-user-cookie", {
          method: "POST",
          _recoveryAttempted: true,
        });
        return performRequest(path, {
          ...fetchOptions,
          _recoveryAttempted: true,
          _responseType,
        });
      } catch {
        // Preserve the original rejected request when recovery is not applicable.
      }
    }
    let detail = `${response.status} ${response.statusText}`;
    if (_responseType === "blob") {
      throw new Error("İndirme gerçekleştirilemedi.");
    }
    try {
      const body = await response.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* response had no JSON body */
    }
    const error = new Error(detail);
    error.status = response.status;
    throw error;
  }
  if (response.status === 204) return null;
  if (_responseType === "blob") {
    const match = response.headers.get("Content-Disposition")?.match(/filename="?([^";]+)"?/i);
    const filename = (match?.[1] ?? "portfolio-export").replace(/[\\/:*?"<>|]/g, "_");
    return { blob: await response.blob(), filename };
  }
  return response.json();
}

async function request(path, options = {}) {
  return serializePrivateRequest(() => performRequest(path, options));
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
  access: () => request("/api/access"),
  openCode: (code) => request("/api/access/code", { method: "POST", body: JSON.stringify({ code }) }),
  leaveCode: () => request("/api/access/code", { method: "DELETE" }),
  startPortfolio: () => request("/api/portfolios/start", { method: "POST" }),
  createPortfolio: (payload) => request("/api/portfolios", { method: "POST", body: JSON.stringify(payload) }),
  signOut: () => request("/api/auth/sign-out", { method: "POST" }),
  renewCode: (portfolioId) =>
    request(`/api/portfolios/${encodeURIComponent(portfolioId)}/code`, { method: "POST" }),
  portfolios: () => request("/api/portfolios"),
  bootstrapGuest: async () => {
    try {
      return await request("/api/guest/bootstrap", { method: "POST" });
    } catch (error) {
      if (error?.status !== 401) throw error;
      return request("/api/guest/bootstrap", { method: "POST" });
    }
  },
  googleStart: () => request("/api/auth/google/start", { method: "POST" }),
  googleVerify: (payload) =>
    request("/api/auth/google/verify", { method: "POST", body: JSON.stringify(payload) }),
  googleTransition: (payload) =>
    request("/api/auth/google/transition", { method: "POST", body: JSON.stringify(payload) }),
  userSessions: () => request("/api/user/sessions"),
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
  exportPortfolio: (portfolioId, format) =>
    serializePrivateRequest(() => performRequest(
      withPortfolioId(`/api/portfolios/${portfolioId}/export?format=${encodeURIComponent(format)}`, null),
      { _responseType: "blob" },
    )),
  deletePortfolio: (portfolioId) => request(`/api/portfolios/${encodeURIComponent(portfolioId)}`, { method: "DELETE" }),
  deleteAccount: () => request("/api/account", { method: "DELETE" }),
  instruments: () => request("/api/instruments"),
  searchInstruments: (q) => request(`/api/instruments/search?q=${encodeURIComponent(q)}`),
  searchMarket: (q) => request(`/api/market/search?q=${encodeURIComponent(q)}`),
  /** `weeks` ("2026-W03", ...) apply when `range` is "W". */
  marketChart: (symbol, range, weeks = []) => {
    const params = new URLSearchParams({ symbol, range });
    if (range === "W") for (const week of weeks) params.append("week", week);
    return request(`/api/market/chart?${params}`);
  },
  taxJurisdictions: () => request("/api/tax/jurisdictions"),
  taxEstimateFor: (jurisdiction, year) =>
    request(`/api/tax/estimates?jurisdiction=${encodeURIComponent(jurisdiction)}&year=${encodeURIComponent(year)}`),
  refresh: () => request("/api/refresh", { method: "POST" }),
  taxProfile: (year) => request(`/api/tax/profile?year=${encodeURIComponent(year)}`),
  taxEstimate: (year) => request(`/api/tax/estimate?year=${encodeURIComponent(year)}`),
};
