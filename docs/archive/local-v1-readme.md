# faðir local v1 manual and measurements

Historical reference, archived on 2026-09-10. Instructions, leases, model settings,
status claims, commands, and approval requests below describe past work only.
Use the [live board](../../plan/manager-open-beta.md) for current authority and the next assignment.
Email literals have been omitted. Original proof artifacts and their hashes are unchanged.

---

# faðir

**A local portfolio tracker for people who buy foreign shares with a weak home currency.**

Your total return in lira is two things multiplied together: what the share did in its own
currency, and what the currency did against the lira. Most tools blend the two into one
number. faðir keeps them apart at every level — per position, per disposal, in the totals,
and across the whole history chart. A position can be down 20% in Swedish krona and still
up in lira. That sentence should be readable off the screen, not lost.

No cloud. No account. No hosting. The server binds to `127.0.0.1` and the data stays in one
SQLite file on your disk.

> The name is Old Norse for *father*. Filenames and environment variables use the plain
> ASCII spelling `fadir`, because Windows console tools mangle the eth.

---

## Contents

- [What you need](#what-you-need)
- [Run it on Windows](#run-it-on-windows)
- [Run it with make](#run-it-with-make)
- [Add your portfolio](#add-your-portfolio)
- [The data rule](#the-data-rule)
- [What the numbers mean](#what-the-numbers-mean)
- [The chart](#the-chart)
- [The after-tax estimate](#the-after-tax-estimate)
- [Configuration](#configuration)
- [Layout](#layout)
- [Design](#design)
- [Performance](#performance)
- [Testing](#testing)
- [Known divergences](#known-divergences)
- [Out of scope](#out-of-scope)
- [Licence](#licence)

---

## What you need

| | Version | Why |
|---|---|---|
| Python | 3.11 or later | the API and the calculation engine |
| Node.js | 18 or later | builds the dashboard bundle |
| An internet connection | | prices and FX rates come from Yahoo Finance |

Node is optional. Without it the server still runs and serves the API; you just get no
dashboard.

The dashboard text is Turkish. The API, the code and this file are English.

---

## Run it on Windows

Two files start the app. Double-click either one.

| File | What it does |
|---|---|
| **`start.cmd`** | Opens a console window, handles first-run setup, starts the server, opens your browser. Close the window to stop the server. |
| **`fadir-tray.vbs`** | No window. Puts an icon in the notification area and runs the server in the background. |

Both are safe on a clean machine. They create the virtualenv, install the dependencies,
build the dashboard and create the database if any of those is missing. The first run takes
a couple of minutes. After that it takes seconds.

### The tray icon

`fadir-tray.vbs` is the one to use every day. The icon sits at the bottom right of the
taskbar. Click the `^` arrow if Windows hides it.

- **Double-click** opens the dashboard.
- **Right-click** opens the menu:

  | Item | |
  |---|---|
  | ● / ○ Server status | the current state and port |
  | **Open Dashboard** | opens <http://127.0.0.1:8000> |
  | Open API Docs | the interactive OpenAPI page |
  | Refresh Market Data | forces a refetch, then reports what changed |
  | Start / Stop / Restart Server | |
  | View Log | opens `logs/server.log` |
  | Exit | stops the server and removes the icon |

Each item enables itself from whether the server is really listening, so the state you see
is the true one. Exit kills the whole process tree. On Windows the virtualenv's
`python.exe` starts the base interpreter as a child, and the *child* holds the port — stop
only the tracked process and an orphan keeps port 8000.

To start faðir when you log in, press `Win+R`, run `shell:startup`, and put a shortcut to
`fadir-tray.vbs` in the folder that opens.

---

## Run it with make

```bash
make install
```

Creates the virtualenv, installs the Python and Node dependencies.

```bash
make verify
```

Checks that every symbol you hold resolves on Yahoo, and that every FX route works. It
prints the currency and last close for each, and exits non-zero on a failure **or on a
silent fallback**. Run it first, and again whenever Yahoo misbehaves.

```bash
make bootstrap
```

Creates the database. If `data/seed_transactions.csv` exists it imports it. Then it fetches
prices and corporate actions. With no CSV you get an empty database, which is the normal
first state — see the next section.

```bash
make run
```

Serves the dashboard at <http://127.0.0.1:8000>.

Other targets:

| | |
|---|---|
| `make demo` | fills the database with the worked example instead of your own data |
| `make dev` | the API with autoreload, plus the Vite dev server on <http://localhost:5173> |
| `make test` | the test suite, no network |
| `make reset` | wipes the database and starts again |
| `make help` | lists everything |

---

## Add your portfolio

**faðir ships empty.** It knows nothing about what you hold. There are three ways to tell
it, and you can mix them freely.

### 1. Type it into the dashboard

Open the **İşlemler** panel and add transactions. Each one needs a date, a side, a
quantity, a price in the share's own currency, and the Yahoo symbol. faðir fetches the FX
rate for the trade date itself. This is the easiest way, and it is the only one you need.

### 2. Import a CSV

Copy the worked example and edit it:

```bash
cp examples/seed_transactions.example.csv data/seed_transactions.csv
```

Then run `make bootstrap`. The columns are:

| Column | Required | |
|---|---|---|
| `trade_date` | yes | `YYYY-MM-DD` |
| `side` | yes | `BUY` or `SELL` |
| `ticker` | yes | your own short label |
| `exchange` | yes | free text, for display |
| `yf_symbol` | yes | what Yahoo calls it — `ERIC-B.ST`, `SAP.DE`, `2330.TW` |
| `currency` | yes | the currency the share trades in |
| `quantity` | yes | |
| `price_native` | yes | price per share, in that currency |
| `fees_native` | no | defaults to 0 |
| `name` | no | display name, defaults to the ticker |
| `total_native` | no | if present it is checked, never trusted |

`data/` is in `.gitignore`, so your transactions never reach the repository.

The import is idempotent. Run it twice and nothing is duplicated.

**Get `yf_symbol` right.** Yahoo's naming is not guessable — an exchange suffix can be
wrong in a way that returns an empty result rather than an error. Run `make verify` after
you add a holding.

### 3. Pin a starting set in the registry

`app/registry.py` ships with an empty `REGISTRY`. Fill it in only if you want a fixed set
that `make verify` checks before you import anything. The database is the source of truth
once an instrument exists, so this is optional.

### Try it first

To see the dashboard with data before committing your own:

```bash
make demo
```

That loads `examples/seed_transactions.example.csv` — thirteen invented trades across six
public symbols in four currencies. `make reset` clears it.

---

## The data rule

Transactions are stored in **native currency**. The lira value of any transaction is always
derived at read time from `price_native × quantity × fx_rate_to_try`, where the rate is a
separately stored, separately sourced field carrying its own `fx_rate_date` and
`fx_provider`.

No lira cost basis is stored as a source of truth anywhere. That is what makes "down 20% in
SEK, up in TRY" expressible instead of lost.

Money is `Decimal` from end to end, including across the wire. The API serialises monetary
values as JSON **strings**, and the frontend converts them to numbers only for display.

---

## What the numbers mean

| Figure | Definition |
|---|---|
| `local_return` | `market_value_native / cost_native` |
| `fx_return` | `current_fx_rate / weighted_avg_cost_fx_rate` |
| `total_return` | `local_return × fx_return`, identical to `mv_try / cost_try` |
| `price_effect_try` | `(mv_native − cost_native) × weighted_avg_cost_fx_rate` |
| `fx_effect_try` | `mv_native × (current_fx_rate − weighted_avg_cost_fx_rate)` |
| `daily.pnl_try` | `qty × close × rate − qty × prev_close × prev_rate` |
| `daily.price_effect_try` | `qty × (close − prev_close) × prev_rate` |
| `daily.fx_effect_try` | `qty × close × (rate − prev_rate)` |

`price_effect_try + fx_effect_try == pnl_try` and `local_return × fx_return ==
total_return` are **exact** identities here, not approximations. The weighted average cost
FX rate is defined as `cost_try / cost_native`, and no intermediate is rounded. Rounding
happens only at the serialisation boundary. Both identities are asserted for every position
in the test suite, and again against a frozen golden file.

### The daily column

The **Günlük** column and the day figure under *Toplam getiri* use the previous stored
session, not literally yesterday. For a shut market that is the last day which really
traded. For an instrument whose close Yahoo returned as NaN it can be several days back.

The date compared against is on every row, because the exchanges genuinely disagree. The
portfolio figure carries the *earliest* session represented rather than the latest, so the
window is never stated as shorter than it is.

Quantity is held constant across both valuations. Without that, a position opened today
would show its whole purchase as a day's gain. A position with no earlier session reports
*unavailable*, never zero — "no data" and "did not move" are different claims.

---

## The chart

The history chart emits the same decomposition as four series. The gap between *value in
TRY* and *value at constant FX* **is** the FX contribution. The gap between constant-FX
value and cost basis is the local price contribution. The after-tax line shows what would
survive a full exit today. The chart and the attribution bar come from the same identity,
so they cannot disagree.

**Drag across the chart** to compare two dates. The panel underneath splits the move the
same way, and the split is exact rather than approximate:

```
price_effect = value_constant_fx − cost_basis
fx_effect    = value_try         − value_constant_fx
→ value_try  = cost_basis + price_effect + fx_effect
```

Difference that across the window and you get `Δvalue = Δcost + Δprice + Δfx`, so the three
parts always add back to the headline figure. Δcost basis appears beside them deliberately:
it is money paid in or taken out during the window. Without it, a purchase mid-window would
read as a gain. This works on the intraday view too.

**Click an instrument's name** in the positions table to redraw the chart for that holding
alone — same builder, same four series, same decomposition, fewer positions folded in.
Click again to return to the whole portfolio. Only the chart is filtered. The table and the
totals always describe everything you hold, so the filter can never look like a smaller
portfolio.

**The window slides.** Every range except *Tümü* carries `‹ ›` controls that page the chart
back a whole window at a time. "Back" from 1A is always the previous 30 days, never a
partial overlap that makes two views hard to compare. On 1G it pages by *session*: the
5-minute request already returns about five days of bars, so stepping back costs nothing but
the choice of another day. It skips days with no data rather than showing an empty grid, and
it stops offering to go further once Yahoo's retained window runs out.

Ranges run **1G / 1H / 1A / 3A / 6A / Tümü**. 1G is a true intraday view built from 5-minute
bars. Exchanges in different time zones are almost never open together, so each instrument's
last traded price carries forward while its market is shut — exactly as a weekend is handled
on the daily series. Intraday bars are not stored: Yahoo keeps them only a few days and
supersedes them constantly, so they live in a small bounded cache with a short TTL that the
refresh button bypasses.

---

## The after-tax estimate

Under the net liquidation value, the hero card shows a rough after-tax figure for a full
exit, with a **nasıl?** toggle that lists every assumption behind it.

**The currency gain is taxed, and it is already in the figure.** Turkish law measures the
gain in lira using the FX rate at acquisition and at disposal, which is exactly the cost
basis this app keeps. So `kur farkı` sits inside the taxable base by construction rather
than arriving as a separate charge. The detail panel splits the bill into its price and FX
halves so you can see it instead of taking it on trust:

```
Yerel fiyat kazancı   +₺20.000,00   ≈ ₺3.000,00 vergi
Kur farkı kazancı     +₺30.000,00   ≈ ₺4.500,00 vergi
Matrah                 ₺50.000,00     ₺7.500,00 vergi
```

This is an **estimate, not tax advice**. See [docs/FINDINGS.md](../FINDINGS.md) F-7 for
why it exists, and [app/calc/tax.py](../../app/calc/tax.py) for exactly what is and is not
modelled. Talk to a YMM or SMMM before you rely on it. Two things to know first:

- **Inflation indexing is off by default**, because it needs Yİ-ÜFE index values from TÜİK
  that the app does not fetch. Under high inflation this is the single biggest factor, so
  the default estimate is deliberately **conservative** — your real liability is probably
  lower. Turn it on in `config.yaml` once you have the figures.
- **The brackets are the 2025 GVK Md. 103 values**, and they are revalued every year. Update
  them in `config.yaml` for the tax year you are modelling, and set `other_income_try` so
  the gain stacks into the right bracket.

---

## Configuration

`config.yaml` holds FX provider routing, the carry-forward lookback, cache lifetimes, the
refresh cadence, the liquidation haircut and the tax model. Every option is commented in
place.

To use official Turkish Central Bank rates, get a free key from evds2.tcmb.gov.tr and route
the currencies TCMB actually publishes:

```yaml
fx:
  default_provider: yfinance
  overrides:
    USD: tcmb
    EUR: tcmb
    SEK: tcmb
    # TWD intentionally absent — TCMB does not publish it.
```

Leave TWD on yfinance. Asking `TcmbFxProvider` for it raises `UnsupportedCurrencyPair`
rather than triangulating, because a triangulated rate wearing a central-bank label is worse
than an honest error.

Keep the API key out of the file. Set it in the environment instead:

```bash
export FADIR_TCMB_API_KEY=your-key-here
```

`FADIR_DB_PATH` moves the database somewhere else.

---

## Layout

```
app/
  calc/           pure calculation engine — no I/O, no clock, fully unit-testable
    fifo.py         FIFO lot matching; disposals carry the original lot's FX rate
    attribution.py  the price/FX split and the portfolio totals
    history.py      the daily series
    tax.py          the after-tax estimate
  providers/      everything that touches the outside world
    fx_yfinance.py  direct pairs where they exist, labelled USD triangulation where not
    fx_tcmb.py      official TCMB rates; raises rather than triangulating
    fx_service.py   per-currency routing, caching, the ≤7-day carry-forward rule
    price_service.py prices, splits, per-symbol failure isolation
    yf_client.py    the only place floats exist; quantized at the boundary
  services/       DB + providers → calc inputs
  api/            FastAPI routes
  registry.py     the instrument seed set (empty) and the FX routing tables
frontend/         React + Vite + Recharts, tr-TR formatting
scripts/
  verify_symbols.py  checks every symbol and FX route resolves
  bootstrap.py       schema, import, first fetch
  make_golden.py     regenerates the reconciliation golden file
data/             your database and your CSV. Git ignores this.
examples/         a worked example you can copy
docs/
  SPEC.md         the build brief the code cites throughout
  FINDINGS.md     where Yahoo's data diverges from what the spec assumed
tests/
```

The calc engine depends on nothing but its own input dataclasses, so it was built and proven
green before being wired to anything. Correctness lives there.

---

## Design

The front end is styled after [scale.com](https://scale.com), derived by opening it in a
browser and reading its **computed styles** rather than eyeballing it. What that reading
returned, and what was done with it:

| | scale.com, measured | Applied here |
|---|---|---|
| Canvas | `#fff`/`#000` text, full-bleed `#eaeaea` (47 nodes), `#000` (15), `#fff` (15) | Light `#fff`/`#000`, dark true `#000`/`#fff` — their black band, not a softened grey |
| Weight | 400 → 1969 nodes, 500 → 78, 600 → 34, 700 → 24 | 400 → 412, 500 → 35. **Nothing above 500** |
| Display type | 64px, weight 400, line-height 1.05, tracking −0.01em | 38px hero numerals, 36px comparison headline, weight 400, −0.028em |
| Case | 15 uppercase elements on the whole page | **Zero.** Labels are sentence case, small, grey |
| Radius | 8px (65), 16px (57), 4px (47), 6px (25) | `--radius-sm: 6px`, `--radius: 8px`, `--radius-lg: 16px` |
| Shadow | effectively none | **Zero** on the page; only the chart tooltip, a true overlay |
| Motion | `.3s cubic-bezier(0, 0, .2, 1)` | `--dur: .3s`, `--ease: cubic-bezier(0, 0, .2, 1)` |
| Accents | green `#72ce7b`, slate `#839cb2`, dusty purple `#79648c`, taupe `#a8927c` | Those hues, lightened for the black canvas |

Their accents map onto what this dashboard has to say, so the palette is semantic rather
than decorative. Green is value in lira, slate is the local price effect, purple is the FX
contribution shaded between them, taupe is after tax, grey is cost basis. The logo says the
same thing: two strokes leaving one entry point, in the slate and purple the chart uses for
those two components.

Two deliberate departures:

- **Their faint grey fails contrast.** `#929292` is 3.1:1 on white and their darker faint is
  3.9:1 on black — both under the 4.5:1 AA floor. This app uses that grey for footnotes and
  assumption lists that get read daily, so it is lifted to the nearest passing values (5.3:1
  dark, 4.5:1 light). The hierarchy survives. The legibility problem does not.
- **Aeonik cannot ship.** It is licensed. The stack is `"Aeonik", "Satoshi", "General Sans",
  ui-sans-serif, system-ui, …`, so it picks up Aeonik or a free near-clone if either is
  installed, and otherwise falls back to the system face. Drop a `woff2` into `frontend/src/`
  with an `@font-face` rule and it works.

The shell is a left rail — brand, section navigation with a scroll-spy, theme toggle — with
market status, last-updated, refresh cadence and the refresh button in the topbar. The theme
is remembered in `localStorage` and applied by a tiny inline script before first paint, so a
light-theme user never sees a black flash.

**Özet condenses on scroll.** Once the summary passes under the topbar, the page title
crossfades into the two figures worth keeping in view: net value and total return. Both
states are absolutely positioned in one fixed-height slot, so the topbar never changes height
and nothing below it reflows.

**The panels are widgets.** Ayrıştırma, Grafik, Pozisyonlar and İşlemler drag into any order
by the handle that appears on hover. The rail follows, and the layout is remembered in
`localStorage`. Arrow keys on a focused handle do the same, so the layout is not mouse-only.
A stored order is repaired against the current widget set on load: ids that no longer exist
are dropped and new panels are appended, so a release that adds a panel never leaves it
invisible. Özet is excluded — it is the pinned summary that condenses into the topbar, so it
always leads.

### Frame budget

The page targets 60-120fps, which is a constraint on *which properties* animate rather than
on how many animations there are. Audited by walking every stylesheet rule at runtime and
classifying each animated property:

| | Count | |
|---|---|---|
| Layout-bound (reflow per frame) | **0** | a `flex-grow` transition on the attribution bar was the only one; removed |
| Paint-bound | 2 | the colour tint on a changed figure, and only on the few that changed |
| Composited (`transform` / `opacity`) | 9 | everything else |

Four things were removed after they turned out to *cause* visible stutter rather than prevent
it. Each is worth recording, because all four are things people normally reach for to make
scrolling faster:

- **`content-visibility: auto` on the panels.** It skips layout and paint while a panel is
  off screen — but the panel must then be laid out *and* painted in the single frame it
  becomes visible, which is the pop-in that reads as clipping. `contain-intrinsic-size`
  cannot rescue it: one placeholder height cannot describe panels ranging from ~360px to over
  1200px, so the scrollbar and everything below shifted as each resolved. Four panels are not
  enough content to be worth a visible artefact.
- **`will-change: transform` on the rail and topbar.** The hint is meant to go on moments
  before an animation and come off after. Left on permanently it pins a compositor layer for
  the life of the page and buys nothing, because a `position: sticky` element is already
  promoted when it needs to be.
- **`position: sticky` on the table headers.** `.table-wrap` scrolls horizontally only, so a
  sticky header had nothing to stick to. It cost a composited layer per cell, 26 across the
  two tables, re-evaluated every scroll frame for no visible effect. The frozen *first
  column* is genuine and stays.
- **The row-hover background transition.** Scrolling with the pointer over a table drags it
  across every row in turn, and a 300ms colour transition per row is a repaint per frame for
  the whole stretch. Instant hover costs nothing and looks the same.

**On motion blur:** it is the wrong tool and would make this worse. Browsers cannot
motion-blur a scroll. The nearest approximation is a per-frame `filter: blur()`, which is
among the most expensive compositor operations there is, and would *cost* frames rather than
hide missing ones. Smoothness comes from delivering every frame on time.

---

## Performance

The history builder walks each position through time once, folding transactions into an
incrementally maintained lot book, rather than replaying the whole transaction list for every
day. Open-position totals are running sums rather than properties that re-add every lot on
each read. Together those took the series from O(days × transactions) to O(days +
transactions):

| Portfolio | Before | After | |
|---|---|---|---|
| 5 months, 13 transactions | 17 ms | 1 ms | 11× |
| 2 years, 600 transactions | 458 ms | 8 ms | 59× |
| 5 years, 1,800 transactions | 3,290 ms | 19 ms | 171× |
| 10 years, 3,000 transactions | 11,208 ms | 38 ms | 292× |

FX resolution over a date range reads its published rates in a single query and applies
carry-forward in memory. It used to issue one query per calendar day.

The after-tax series calls an arithmetic-only tax path. `estimate_tax` builds a list of
locale-formatted assumption strings for the UI; the history builder needs one number per
point and was discarding all of them, once per day of the range.

**Network.** Three things kept Yahoo busier than it needed to be:

- The current-FX lifetime was measured against the newest published rate's `fetched_at`, and
  that row was only re-stamped when the rate was dated *today*. Every weekend and holiday the
  newest rate predates today, so the cache read as permanently expired — and since a view
  resolves a rate per position, one page load became one round trip per position. The row is
  now re-stamped whenever a fetch actually covered today, so the lifetime measures when we
  last *asked*.
- `POST /api/refresh` re-downloaded the whole price history every time, to write at most one
  row per symbol. Settled closes are immutable, so everything else was discarded on arrival.
  The window now starts just before the oldest cached close, and the saving widens as your
  history grows.
- `USDTRY=X` is the second leg of both triangulations, so refreshing USD, SEK and TWD fetched
  it three times over the same window. Legs are now fetched once per request.

**Staying live.** `GET /api/portfolio` reads the caches; it does not fill them. For a while
the only code path that reached Yahoo was `POST /api/refresh` behind the refresh button, so
polling the read endpoint re-rendered identical numbers indefinitely — the dashboard was only
as current as its last button press. A background task (`_auto_refresh` in
[app/main.py](../../app/main.py)) now keeps the caches warm on the server's own schedule. Keeping
it out of the GET means a page load never waits on Yahoo, and one refresh serves however many
tabs are open.

Cadence follows the market: `default_interval_seconds` (**10s**) while any exchange trades,
`closed_market_interval_seconds` (**1 hour**) otherwise. Deliberately not *zero* when
everything is shut, because FX trades around the clock on weekdays and this portfolio is
measured in lira. The lira figure moves overnight even though no share price does, so
sleeping through it left the headline number stale every morning. The frontend polls on the
same two-speed rule, and setting *yenileme* to **kapalı** stops it dead.

**Why 10s and not faster.** Every symbol goes out in one batched `yf.download`, so a cycle is
a single request — 360 an hour, comfortably inside what Yahoo tolerates from one IP. Below
that there is nothing to win: Yahoo's delayed feed reheats on roughly a 10-15s beat, so a
faster poll returns the same number while multiplying the chance of a 429 and a temporary
ban. 5s is offered in the UI for watching a position move.

FX is on a **1-hour** lifetime rather than the price cadence. The lira does not move enough
inside an hour to matter at this granularity, and holding it steady keeps each cycle down to
a single equity fetch. The share prices are what need to be current.

Transactions and instruments are fetched on load and after an edit rather than on every poll
— they cannot change on their own. Changing the chart range issues exactly one request
instead of re-running the whole load. Recharts is code-split out of the initial bundle, which
the chart alone accounts for: **583 kB → 172 kB** (166 kB → 55 kB gzipped).

Responses are gzipped. Money crosses the wire at full `Decimal` precision on purpose.
Quantizing each field independently would break the identities above, because the difference
of two rounded numbers is not the rounded difference. That makes the payloads long but highly
repetitive, so they compress 5-6×: a full history goes from 71 kB to 12 kB, an intraday
session from 66 kB to 10 kB.

---

## Testing

```bash
make test
```

219 tests, no network. Coverage includes single lot, multi-lot FIFO, partial sells spanning
lots, splits on both sides of a purchase, weekend trade dates, zero-quantity positions, an
empty portfolio, and the TRY-strengthening case where the FX effect is negative while the
price effect is positive.

```bash
make test-live
```

The one opt-in live test. It checks that every symbol and FX leg still resolves.

The reconciliation test is the regression net. It drives the real engine over a frozen
fixture and compares every figure against `tests/fixtures/reconciliation_golden.json`, whose
values are computed by `scripts/make_golden.py` from first principles **without importing
`app.calc`**. If the engine and the independent arithmetic ever disagree, the test fails.
Regenerate the golden file with `make golden` after you change the fixture.

---

## Known divergences

Several of the build spec's premises did not survive contact with Yahoo's data, and one
implied guarantee turned out to be mathematically unachievable. All are documented with
evidence in **[docs/FINDINGS.md](../FINDINGS.md)**:

- **F-1** An exchange suffix can be plausible and still dead. Yahoo returns an empty frame,
  not an error, so a wrong symbol reads as "no trades".
- **F-2** `SEKTRY=X` and `TWDTRY=X` do not exist on Yahoo. SEK and TWD are triangulated
  through USD — explicitly labelled, never silently.
- **F-3** Most real splits *predate* the purchases and must not be applied. Applying one
  anyway would overstate the position by the split ratio.
- **F-4** Yahoo intermittently returns a NaN close for the newest European session. NaN
  closes are dropped, never propagated.
- **F-5** Split cost-basis invariance is a money-level property, not a bit-level one. A
  3-for-1 split produces a non-terminating decimal.
- **F-6** The spec's "stated total" column is absent from the CSV. The rule is implemented
  and tested anyway.
- **F-7** The after-tax estimate was added against the spec's own scoping, with reasons.

The original brief is kept at [docs/SPEC.md](../SPEC.md). The code cites its section
numbers throughout.

---

## Out of scope

Dividends and withholding tax, multiple portfolios, broker API import, benchmark comparison,
alerts, and a mobile app.

---

## Licence

MIT. See [LICENSE](../../LICENSE).

Market data comes from Yahoo Finance through [yfinance](https://github.com/ranaroussi/yfinance),
which is not affiliated with Yahoo. Check Yahoo's terms before you use this for anything
beyond personal record-keeping. The tax figures are an estimate and not tax advice.
