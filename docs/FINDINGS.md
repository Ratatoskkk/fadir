# Findings — where reality diverges from SPEC.md

Recorded during the §2 "verify every symbol before building anything else" step and kept
current as implementation proceeded. Each item states what the spec assumed, what the data
actually shows, and what was built instead.

These are notes about Yahoo Finance, not about anyone's holdings. The symbols named are
whichever ones happened to expose the behaviour; every fix below is generic.

---

## F-1 — an exchange suffix can be plausible and still dead

**Spec §2 / Risk §11:** try a documented fallback symbol if the primary fails.

**Observed:** a Taiwanese instrument quoted as `<code>.TWO` (TPEx, over-the-counter)
returned no rows over any period tested — 5d, 3mo, max. The same instrument as `<code>.TW`
(TWSE) resolved cleanly with the expected currency. Yahoo gives no error for the dead form:
it returns an empty frame, which reads as "no trades" rather than "wrong symbol".

**Action:** `RegistryEntry` carries an ordered `fallbacks` tuple, and
`scripts/verify_symbols.py` tries each in turn. It exits **non-zero whenever a fallback is
used**, so a silent substitution can never pass unnoticed — a fallback is a fact to report,
not a repair to hide. Check your own symbols with `make verify` before you trust a figure
built on them.

---

## F-2 — `SEKTRY=X` and `TWDTRY=X` do not exist on Yahoo

**Spec §3:** "Pairs: `USDTRY=X`, `SEKTRY=X`, `EURTRY=X`, `TWDTRY=X`."

**Observed:** only `USDTRY=X` and `EURTRY=X` return data. `SEKTRY=X`, `TRYSEK=X`,
`TWDTRY=X` and `TRYTWD=X` are all empty. Yahoo publishes these currencies only against USD:
`SEKUSD=X`, `USDSEK=X`, `TWDUSD=X`, `USDTWD=X` all have full history back past inception.

**Tension:** §3 forbids triangulating through USD — but read in context, that prohibition is
about *silence*: "raise `UnsupportedCurrencyPair` for TWD rather than silently falling back
or triangulating through USD — **silent fallback would produce a series with mixed
provenance**." The objection is unlabelled mixed provenance, not the arithmetic.

**Action:** `YFinanceFxProvider` uses the direct pair where one exists and an explicit,
labelled USD triangulation where none does:

| Currency | Route | Recorded provenance |
|---|---|---|
| USD | `USDTRY=X` | `yfinance` |
| EUR | `EURTRY=X` | `yfinance` |
| SEK | `SEKUSD=X` × `USDTRY=X` | `yfinance:SEKUSD=X*USDTRY=X` |
| TWD | `TWDUSD=X` × `USDTRY=X` | `yfinance:TWDUSD=X*USDTRY=X` |

The provenance string is persisted per rate in `fx_cache.provider` and per transaction in
`transaction.fx_provider`, returned by `/api/health`, and shown in the UI. Nothing is
silent. `TcmbFxProvider` still raises `UnsupportedCurrencyPair` for TWD exactly as §3
requires — it never triangulates, because for TCMB the whole point is official single-source
rates.

---

## F-3 — most real splits predate the purchase, and must not be applied

**Spec §5:** written around an instrument that split *between* its purchases and today, so a
literal reading directs the adjustment to run on those lots.

**Observed:** in live data the far commoner shape is the opposite one. An instrument's only
split on record sits *months before* the first trade date. A price recorded after the
ex-date is already on the post-split basis, so it needs no adjustment at all — and Yahoo's
split feed hands you the action either way, with no hint about which side of it your trades
fall on.

**Why this matters:** applying a 5:1 adjustment to lots bought after the ex-date multiplies
quantity by five and divides price by five — 20 shares at ~92 become 100 at ~18.40 against a
live price above 100, overstating the position fivefold. That is precisely the corruption §5
exists to prevent, arrived at by obeying §5 too literally.

**Action:** the split machinery is built in full and is entirely generic. Splits are fetched
with `auto_adjust=False`, persisted to `corporate_action`, and applied **only** to
transactions whose `trade_date` precedes `action_date`. A
`(instrument_id, action_date, kind)` uniqueness constraint plus an `applied_to_transactions`
flag makes re-application impossible, and `quantity × price_native` is asserted invariant.
No instrument is special-cased. Against a portfolio whose splits all predate its trades it
correctly applies **nothing**.

The US-2.2 acceptance criteria are proven against a synthetic 5:1 fixture in
[tests/test_splits.py](tests/test_splits.py) — cost-basis invariance and idempotence both —
rather than against a NOW split that does not exist. The behaviour the spec wanted is
tested; the false premise is not baked into the data.

---

## F-5 — split invariance is a money-level property, not a bit-level one

**Spec §5.5:** "Total cost basis in native currency must be **invariant** across a split.
This is the assertion that catches the bug."

**Observed:** the assertion did catch a bug — a real one, on the first run. It also showed
that literal bit-exactness is unachievable in general. A 3-for-1 split turns a price of
100.00 into 33.333…, which has no finite decimal representation, so *some* rounding is
forced. The original `NUMERIC(24,8)` price column made it worse by silently truncating to
8 places, leaving a residual of ~2e-7 on a 1,000 basis.

**Action:** `transaction.price_native` widened to `NUMERIC(28,12)`, and
`apply_pending_splits` now quantizes the divided price to that scale *before* checking the
invariant — so the guard tests the value that will actually be persisted rather than a
full-precision intermediate that hides storage rounding. The tolerance is relative
(`max(1e-8, |basis| x 1e-12)`), keeping the residual far below a cent at any realistic
size. Quantity scales by exact multiplication and is unaffected.

Ratios that *do* terminate in decimal (2, 4, 5, 0.1 — which is nearly all real splits) are
still bit-exact, and `test_clean_ratio_splits_are_bit_exact` pins that down separately from
the money-tolerance case.

---

## F-6 — US-1.2's "stated total" column is absent from the seed CSV

**Spec US-1.2:** "*Given* the 2026-04-15 row where the stated total (18,373.00) disagrees
with 800 x 22.97 (18,376.00), *then* the system uses 18,376.00 and logs the discrepancy."

**Observed:** `examples/seed_transactions.example.csv` has columns `trade_date, side, ticker,
exchange, yf_symbol, currency, quantity, price_native` — there is no total column, so
there is no stated total to disagree with. The referenced 18,373.00 figure does not appear
anywhere in the supplied data.

**Action:** the importer implements the rule regardless: it accepts an optional
`total_native` / `total` column, always recomputes from `quantity x price_native`, uses the
recomputed figure, and logs a warning naming the row and both values when they differ.
Against the supplied CSV the check is a no-op because the column is absent. The behaviour
is proven in `test_seed_import.py` against a fixture carrying the exact 18,373.00 /
18,376.00 discrepancy from the spec.

---

## F-7 — after-tax estimate added, against §14's scoping

**Spec §14** puts "Turkish capital gains tax computation (inflation indexing under Turkish
rules is genuinely complex and deserves its own spec)" out of scope for v1.

**Why it is now in:** the owner asked for an approximate after-tax figure under the net
liquidation value. The §14 reasoning was sound and has not been ignored — it is why this
is a clearly-labelled *estimate* built from configurable assumptions rather than a
computation presented as authoritative.

**What makes the app able to attempt it:** Turkish law measures the gain in **lira**,
using the FX rate at acquisition and at disposal. That is precisely the cost basis this
app already maintains (§0), so the FX component of the gain — the part most often got
wrong — is already inside the taxable base.

**Modelled** (see [app/calc/tax.py](../app/calc/tax.py) for the full statement): the GVK
Mük. 80 "değer artış kazancı" regime for foreign-listed shares declared on the annual
return; no securities exemption, because Mük. 80's exemption explicitly excludes
securities; optional inflation indexing of cost under Mük. 81 with its statutory 10%
threshold; and the progressive Md. 103 tariff, with other declared income shifting which
bracket the first lira of gain lands in.

**Deliberately not modelled:** dividend withholding, Geçici 67 (which does not reach
foreign-listed shares), double-taxation relief on foreign tax already withheld, stamp
duty, and derivative-instrument treatment.

**On the currency gain:** it is taxable, and it was already being taxed — the base is
`proceeds_try - cost_try`, and because cost is held in lira at the trade-date rate, the FX
gain is inside it by construction. It was simply invisible: the single tax figure could not
show that 59% of the bill came from the lira's move rather than from the shares. Adding it
"again" would have double-counted and overstated the tax by that same 59%. Instead
`estimate_tax` now takes the §6 attribution components and reports how the one bill splits
between them, which the hero card renders as a three-line table. The tax itself is
unchanged; `test_fx_gain_is_inside_the_taxable_base_not_added_on_top` pins that it is
counted exactly once.

**Two honest limitations, both surfaced in the UI rather than hidden:**

1. **Inflation indexing is off by default.** It needs real Yİ-ÜFE index values from TÜİK,
   which the app does not fetch. In a high-inflation setting this is the single largest
   factor, so the default estimate is *conservative* — the real liability is likely lower.
   The UI says so in the assumptions list.
2. **Brackets are the 2025 figures.** They are revalued annually and live in
   `config.yaml` for exactly that reason.

Every figure ships with its assumptions and a "not tax advice, consult a YMM/SMMM"
disclaimer, and `test_tax_estimate_always_ships_its_caveats` fails if the number is ever
served without them.

---

## F-4 — Yahoo returns a NaN close for the most recent European session

**Observed:** for European symbols (`.ST` and `.DE` among them), the most recent daily row
sometimes carries a valid Open, High, Low and Volume but `Close = NaN` (and
`Adj Close = NaN`). US symbols were unaffected. The condition is transient and Yahoo-side.

**Action:** the price layer drops NaN closes rather than propagating them, carries the last
valid close forward, and marks the position stale with the true `last_traded` date — which
feeds the §8 market-hours requirement directly. A NaN never reaches the calc engine, and a
carried-forward price is never presented as live.
