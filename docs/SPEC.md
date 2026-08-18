# fadir — Multi-Currency Portfolio PnL Tracker

**Build spec for Claude Code.** Local-only server. No cloud, no auth, no external hosting.

---

## 0. Context for the implementing agent

The user is a Turkish investor holding foreign-listed equities across several
currencies. Every purchase is funded by converting TRY into the local currency at the rate
of the trade date.

This creates the central requirement: **total return in TRY is the product of local price
return and FX return.** The user needs these decomposed, not blended. A position can be
down 20% in SEK and up in TRY. Any design that stores a single pre-converted TRY cost
number destroys this information and fails the brief.

The app ships with no holdings. Which instruments exist, and in which currencies, is the
user's data — not a constant in the source. Treat the registry, the seed CSV and the
example below as illustrations of shape, never as a fixed set.

**Non-negotiable data rule:** transactions are stored in native currency. The TRY value of
any transaction is *always* derived at read time from `price_native × quantity × fx_rate`,
where `fx_rate` is a separately stored, separately sourced field. Never store a
TRY-denominated cost basis as the source of truth.

---

## 1. Stack

| Layer | Choice | Rationale |
|---|---|---|
| Backend | Python 3.11+, FastAPI, Uvicorn | Async, trivial local run, best finance library ecosystem |
| DB | SQLite via SQLAlchemy 2.x | Single file, zero setup, adequate for one portfolio |
| Market data | `yfinance` | Free, keyless, covers all six symbols and all four FX pairs |
| Frontend | React + Vite + Recharts | Chart quality matters here; Recharts handles the time series |
| Testing | `pytest`, `pytest-asyncio`, `respx` or `responses` | Network mocked in unit tests, one opt-in live integration test |
| Server | `uvicorn app.main:app --host 127.0.0.1 --port 8000` | Bind loopback only |

Frontend builds to static files served by FastAPI in production mode. Vite dev server
proxies `/api` during development. Single command to run: `make dev` / `make run`.

---

## 2. Instrument registry

`app/registry.py` ships empty. Instruments arrive from the transaction CSV or from the
dashboard, and the database is the source of truth once they exist. The registry is only a
pinned starting set for anyone who wants one.

`examples/seed_transactions.example.csv` shows the shape, against public symbols:

| Ticker | Exchange | yfinance symbol | Currency | Name |
|---|---|---|---|---|
| AAPL | NASDAQ | `AAPL` | USD | Apple Inc |
| KO | NYSE | `KO` | USD | Coca-Cola Co |
| IBM | NYSE | `IBM` | USD | International Business Machines |
| ERIC | STO | `ERIC-B.ST` | SEK | Telefonaktiebolaget LM Ericsson |
| SAP | ETR | `SAP.DE` | EUR | SAP SE |
| 2330 | TPE | `2330.TW` | TWD | Taiwan Semiconductor Manufacturing |

**Verify every symbol resolves before trusting a number from it.** Yahoo's naming is not
guessable: an exchange suffix can be wrong (`.TWO` is TPEx, `.TW` is TWSE) and a ticker can
differ from the company's obvious abbreviation. `scripts/verify_symbols.py` fetches one day
of history for each and prints currency + last close. Run it first. Report failures rather
than silently substituting.

---

## 3. FX architecture

### Interface

```python
class FxProvider(Protocol):
    def rate(self, base: str, quote: str, on: date) -> Decimal: ...
    def series(self, base: str, quote: str, start: date, end: date) -> dict[date, Decimal]: ...
```

### Default implementation: `YFinanceFxProvider`

Pairs: `USDTRY=X`, `SEKTRY=X`, `EURTRY=X`, `TWDTRY=X`.

### Optional implementation: `TcmbFxProvider`

TCMB EVDS API, free key from evds2.tcmb.gov.tr. Official Turkish Central Bank rates,
appropriate if figures are used for tax purposes.

**Critical limitation to encode:** TCMB's published basket does **not include TWD**. The
provider must raise `UnsupportedCurrencyPair` for TWD rather than silently falling back or
triangulating through USD — silent fallback would produce a series with mixed provenance.
The config layer resolves this by allowing per-currency provider assignment:

```yaml
fx:
  default_provider: yfinance
  overrides:
    USD: tcmb
    EUR: tcmb
    SEK: tcmb
    # TWD intentionally absent — TCMB does not publish it
```

### Weekend / holiday handling

Trade dates may fall on days with no published rate. Rule: **use the most recent prior
published rate, look back up to 7 calendar days, then fail loudly.** Never interpolate
forward, never average. Store the actual `rate_date` used alongside the rate so the UI can
show when a rate was carried forward. All four of the 2026 trade dates that fall on
weekends must surface this.

---

## 4. Data model

```
instrument(id, ticker, exchange, yf_symbol, currency, name, active)

transaction(id, instrument_id, trade_date, side, quantity, price_native,
            fees_native, fx_rate_to_try, fx_rate_date, fx_provider,
            note, created_at, updated_at)

price_cache(instrument_id, price_date, close_native, is_adjusted, fetched_at)
fx_cache(base, quote, rate_date, rate, provider, fetched_at)
corporate_action(instrument_id, action_date, kind, ratio)  -- kind: SPLIT | DIVIDEND
snapshot(snapshot_date, payload_json)  -- optional daily materialisation
```

`side` is an enum: `BUY | SELL`. Quantity always positive; sign derived from side.
All monetary values `NUMERIC`, handled as `Decimal` in Python. **Never use float for money.**

---

## 5. The split-adjustment trap — read this carefully

Any instrument may split between a purchase and today. The recorded purchase price is
then a **pre-split raw price** while the current market price is post-split. yfinance's
default `history()` returns **back-adjusted** prices, which silently rewrites history and
makes the cost basis appear catastrophically wrong.

Required handling:

1. Fetch with `auto_adjust=False` and separately pull `Ticker.splits`.
2. Persist splits into `corporate_action`.
3. On any split, adjust the **stored share quantity and price_native of affected
   transactions** — do not adjust the market price to match history.
4. Adjustment must be idempotent: applying the same split twice is a bug. Guard with a
   uniqueness constraint on `(instrument_id, action_date, kind)` and an
   `applied_to_transactions` boolean.
5. Total cost basis in native currency must be **invariant** across a split. This is the
   assertion that catches the bug.

Assume every instrument may split. Special-case none of them.

---

## 6. Calculation engine

Pure functions, zero I/O, in `app/calc/`. This module must be unit-testable without
network, DB, or clock access — inject `as_of` dates.

### Cost basis
FIFO lot matching. Each `SELL` consumes the oldest open lots. Produces realized PnL per
disposal, carrying the original lot's FX rate so realized FX gain is separable.

### Per-position metrics

```
qty                     = Σ open lot quantities
cost_native             = Σ (lot_qty × lot_price + fees)
cost_try                = Σ (lot_qty × lot_price + fees) × lot_fx_rate
market_value_native     = qty × current_price
market_value_try        = market_value_native × current_fx_rate

pnl_native              = market_value_native - cost_native
pnl_try                 = market_value_try - cost_try
```

### Return attribution — the headline feature

```
local_return  = market_value_native / cost_native
fx_return     = current_fx_rate / weighted_avg_cost_fx_rate
total_return  = local_return × fx_return          # must equal mv_try / cost_try

price_effect_try = (market_value_native - cost_native) × weighted_avg_cost_fx_rate
fx_effect_try    = market_value_native × (current_fx_rate - weighted_avg_cost_fx_rate)
```

`price_effect_try + fx_effect_try` must equal `pnl_try` to within rounding. **Assert this
in tests.** Weighted average cost FX rate is weighted by native cost, not by quantity.

### Liquidation figure

Top-line card: total TRY proceeds if every position were sold at the current market price
and fully converted back to TRY today, minus total TRY invested. Configurable optional
haircut for FX spread and commission (default 0%, exposed in settings), clearly labelled as
an estimate and excluding tax.

### Historical series

Daily portfolio value from 2026-03-29 to today. For each date: value only lots held on that
date, at that date's close and that date's FX rate. Emit three series — value in TRY, value
in native-blend (constant-FX, i.e. FX held at cost), and cost basis in TRY. The gap between
series one and two *is* the FX contribution, which makes the attribution visually obvious.

---

## 7. API

```
GET    /api/portfolio                 current positions + totals + attribution
GET    /api/portfolio/history?from=&to=&freq=   daily/weekly series
GET    /api/transactions
POST   /api/transactions              auto-fetches fx_rate for trade_date
PATCH  /api/transactions/{id}
DELETE /api/transactions/{id}
POST   /api/refresh                   force cache invalidation + refetch
GET    /api/instruments
POST   /api/instruments               validates symbol against yfinance before insert
GET    /api/health                    per-provider status, last successful fetch, cache age
```

`POST /api/transactions` accepts an optional `fx_rate_override` for when the broker's actual
executed rate is known and differs from the published reference rate. When overridden, set
`fx_provider = 'manual'` so the UI can flag it.

---

## 8. Caching and refresh

| Data | TTL | Notes |
|---|---|---|
| Intraday quote | 60s | |
| Daily close (past dates) | Permanent | Historical closes are immutable once settled |
| FX historical | Permanent | Same reasoning |
| FX current | 300s | |

Auto-refresh: frontend polls `/api/portfolio` on a user-configurable interval (default 60s,
selectable 15s/30s/60s/5min/off). Manual refresh button calls `POST /api/refresh` then
re-polls, with a spinner and a "last updated HH:MM:SS" timestamp.

**Market-hours awareness:** the four exchanges span roughly UTC+0 to UTC+8. Outside a given
exchange's session, poll it at a slow rate and mark the position "closed — last traded
{date}" rather than implying a live price. Do not present a stale Taipei close as live at
20:00 Istanbul time.

Rate limiting: batch all symbols into a single `yf.download()` call per refresh. Exponential
backoff on failure. **Never fail the whole dashboard because one symbol errored** — return
partial data with a per-position error flag.

---

## 9. Frontend

Single page, dark theme, dense but readable. Turkish number formatting (`1.234,56`),
`tr-TR` locale, TRY as `₺`.

**Layout order:**
1. Hero card — liquidation-to-TRY value, absolute PnL, % return, colour-coded
2. Attribution bar — price effect vs FX effect split, as a stacked horizontal bar
3. Positions table — sortable, with per-row native PnL and TRY PnL as *separate columns*
4. History chart — the three series from §6, with a range selector (1M / 3M / All)
5. Transaction manager — table with inline add/edit/delete, currency-aware inputs

Accessibility: colour must not be the sole PnL indicator — use +/− signs and arrows too.

---

## 10. Backlog

### Epic 1 — Foundation
- **US-1.1** As the owner, I want my transactions stored in native currency with the
  trade-date FX rate recorded separately, so TRY figures are always reproducible.
  - *Given* a BUY of 300 shares at 85.20 SEK, *when* saved, *then* the row stores
    `price_native=85.20`, `currency=SEK`, and a fetched `fx_rate_to_try` with its
    `fx_rate_date` and `fx_provider`.
  - *Given* the example seed CSV, *when* imported, *then* 13 transactions exist and every
    one has a non-null FX rate.
- **US-1.2** As the owner, I want totals recomputed from quantity × price, not trusted from
  input, so arithmetic errors in my source data don't propagate.
  - *Given* a row where the stated total (18,373.00) disagrees with 800 × 22.97
    (18,376.00), *then* the system uses 18,376.00 and logs the discrepancy.

### Epic 2 — Market data
- **US-2.1** Every symbol resolves and returns the expected currency.
  - *Given* `verify_symbols.py`, *then* each symbol returns a price and its currency matches
    the registry; mismatches fail the run.
- **US-2.2** Splits never corrupt cost basis.
  - *Given* a split after a purchase, *when* adjustment runs, *then* `cost_native` is
    unchanged and `quantity × price_native` is invariant.
  - *Given* adjustment runs twice, *then* the second run is a no-op.

### Epic 3 — Calculation
- **US-3.1** Return attribution is exact.
  - *Given* any position, *then* `price_effect_try + fx_effect_try == pnl_try` within 0.01.
  - *Given* any position, *then* `local_return × fx_return == total_return` within 1e-9.
- **US-3.2** Liquidation figure.
  - *Given* all positions priced, *then* the hero card shows total TRY proceeds and net PnL,
    labelled as excluding tax and FX spread.

### Epic 4 — History
- **US-4.1** Daily series from the earliest transaction, with correct as-of holdings.
  - *Given* a date between two purchases, *then* only the earlier lot is valued.
  - *Given* a non-trading day, *then* the prior close is carried forward and flagged.

### Epic 5 — Live dashboard
- **US-5.1** Auto-refresh on configurable interval with visible last-updated time.
- **US-5.2** Manual refresh forces a cache bypass.
- **US-5.3** One failing symbol degrades one row, not the page.

### Epic 6 — Transaction management
- **US-6.1** Add a transaction; FX rate auto-fetched for the chosen date, with manual
  override available.
- **US-6.2** Delete a transaction; historical series and FIFO lots recompute.
- **US-6.3** Record a SELL; realized PnL appears, split into price and FX components.

---

## 11. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Split back-adjustment corrupts basis | **High** — wrong headline number | §5; invariance assertion in tests |
| A symbol unresolvable on yfinance | High — position untrackable | Verify first; try the documented fallback, then manual price entry |
| TCMB lacks TWD | Medium — inconsistent provenance | Per-currency provider config; raise, never silently triangulate |
| yfinance breaks on Yahoo API change | Medium | Provider interface abstracted; cached history survives outage |
| Float rounding in money | Medium | `Decimal` everywhere; lint rule banning float in calc module |
| Reference FX ≠ broker's executed rate | Low-Medium — small persistent skew | `fx_rate_override` field per transaction |
| Stale price shown as live | Low | Market-hours awareness, §8 |

---

## 12. Testing

**Unit** — calc module, no I/O. Fixtures covering: single lot, multi-lot FIFO, partial sell,
split, weekend trade date, zero-quantity edge, TRY-strengthening scenario (FX effect
negative while price effect positive — this case must be explicitly tested, not assumed).

**Integration** — FX and price providers against recorded fixtures via `respx`. One live
test marked `@pytest.mark.live`, excluded from the default run.

**Reconciliation** — a golden-file test asserting the full portfolio output against
hand-checked expected values for a frozen `as_of` date. This is the regression net.

**Definition of done:** `pytest` green, `verify_symbols.py` clean, reconciliation test
passing, `make run` serves a working dashboard on `127.0.0.1:8000`, and the attribution
identity holds for every position.

---

## 13. Suggested agent decomposition

Parallelisable:
- **Agent A** — data layer: models, migrations, seed import, caches
- **Agent B** — providers: yfinance + TCMB adapters, split handling, symbol verification
- **Agent C** — calc engine: FIFO, attribution, history (pure, testable independently)
- **Agent D** — API + frontend

A and B share the schema contract in §4; C depends only on the interfaces, not the
implementations, so it can be built and fully tested in parallel against fixtures.
Integrate after C's test suite is green — the calc engine is where correctness lives, and it
should be proven before it is wired to anything.

---

## 14. Out of scope (v1)

Dividends and withholding tax, multi-portfolio support, broker API import, benchmark
comparison, Turkish capital gains tax computation (inflation indexing under Turkish rules
is genuinely complex and deserves its own spec), alerts, mobile app.
