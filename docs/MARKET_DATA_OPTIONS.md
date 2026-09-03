# Market Data Options for the faðir Open Beta

Date: 2026-08-31

## Owner decision

The beta will keep the current direct Yahoo integration under the owner's written permit. The team will defer the provider seam until a source change becomes necessary.

The comparison below remains the fallback record.

## Purpose

This report compares market-data sources for the public faðir service.

The first beta serves users in Turkey. It must also support global equities and a base currency per Portfolio.

The target infrastructure budget is about EUR 50 each month. This target includes more than the data source.

This report uses provider pages, provider terms, provider documents, and official exchange pages only.

## Result

**Assumption**

The project owner has a written Yahoo grant for the beta. This report does not review that private grant.

**Recommendation**

Keep the approved Yahoo source for the beta, subject to the exact written grant.

Add a provider-neutral seam before public release. This seam makes a later source change safe.

Run a short sales check with Marketstack, Twelve Data, and EODHD.

- Marketstack is the only studied source near the target budget.
- Its paid plans state commercial use.
- Its public pages do not clearly grant customer display or redistribution.
- Twelve Data gives the clearest Borsa Istanbul and global FX fit.
- Its first business plan costs USD 499 each month, before redistribution add-ons.
- EODHD has a strong global API and Borsa Istanbul data.
- Its public commercial plans start at USD 399 each month.

**Inference**

No studied source gives a confirmed global, customer-display license near EUR 50 each month.

## License rule

Commercial use and redistribution are different rights.

A plan can permit internal commercial use and still prohibit customer display.

The service must get these rights in a contract or a clear plan term:

- Automated server access
- Server cache storage
- Public or customer display
- Data redistribution to signed-in users and guests
- Use in a free beta
- Use after the beta becomes a paid service
- Coverage for each exchange
- Corporate-action storage
- Historical data storage after contract end
- Required source labels

Do not use a retail plan as proof of these rights.

## Current faðir behavior

The current code uses one `yfinance` boundary for equity prices, intraday bars, split events, and symbol currency.

The code stores raw daily closes. It requests `auto_adjust=False` and applies split events to stored transactions.

The code sends one batch request for all equity symbols. It retries a failed symbol separately.

The code keeps daily prices in the database. It keeps intraday bars in a short process cache.

The intraday cache uses a 120-second default. The configured quote cache uses 60 seconds.

The code supports 5-minute, 15-minute, and 1-hour Yahoo intervals.

The FX service already has a provider protocol. It supports Yahoo and TCMB providers.

The current registry supports USD, EUR, SEK, and TWD against TRY.

The code uses direct Yahoo pairs for USD and EUR. It routes SEK and TWD through USD.

Sources: [Yahoo wrapper](../app/providers/yf_client.py), [price service](../app/providers/price_service.py), [intraday service](../app/providers/intraday.py), [FX service](../app/providers/fx_service.py), [FX registry](../app/registry.py), and [configuration](../app/config.py).

## Short-list

### 1. Marketstack, subject to a written display grant

**Confirmed facts**

- The Basic plan costs USD 9.99 each month and permits 10,000 requests each month.
- The Professional plan costs USD 49.99 each month and permits 100,000 requests each month.
- Both plans state `Commercial Use`.
- The service offers global end-of-day data, split data, dividend data, and US intraday data.
- The service states 15 or more years of history on the Professional plan.
- The service says its intraday source is IEX and applies to US tickers.
- Its public page states 70 exchanges and more than 170,000 symbols.

Source: [Marketstack price page](https://marketstack.com/pricing) and [Marketstack API document](https://marketstack.com/documentation).

**Unclear items**

- The public price page does not define `Commercial Use` as customer display.
- The public service agreement does not give a clear redistribution grant.
- The public pages do not confirm Borsa Istanbul symbol coverage.
- The stock API exposes currency metadata. It does not state a full historical FX-rate feed.
- The public pages give monthly quotas but no clear per-second limit.

Source: [Marketstack service agreement](https://marketstack.com/agreement), [Marketstack price page](https://marketstack.com/pricing), and [Marketstack API document](https://marketstack.com/documentation).

**Inference**

Marketstack is the best budget candidate only with a written customer-display grant.

The beta will also need a separate FX source if Marketstack cannot supply historical FX rates.

### 2. Twelve Data, if the budget can increase

**Confirmed facts**

- Twelve Data lists Borsa Istanbul as an end-of-day exchange.
- The Grow individual plan covers Borsa Istanbul.
- The Venture business plan covers Borsa Istanbul.
- The Venture plan starts at USD 499 each month.
- Business plans can permit commercial display.
- External redistribution needs a separate Twelve Data agreement or add-on.
- Non-US commercial data can need extra approval.
- The API has time series, FX, split, and dividend endpoints.
- The FX service covers 140 world currencies.
- The end-of-day service covers more than 100 exchanges.

Sources: [Twelve Data exchanges](https://twelvedata.com/exchanges), [Twelve Data business use rules](https://support.twelvedata.com/en/articles/5332349-commercial-and-personal-usage), [Twelve Data terms](https://twelvedata.com/terms), [Twelve Data business prices](https://twelvedata.com/news/march-2026-updates), [Twelve Data API document](https://twelvedata.com/docs/advanced/api-usage), [Twelve Data FX overview](https://support.twelvedata.com/en/articles/5544954-twelve-data-overview), and [Twelve Data end-of-day document](https://support.twelvedata.com/en/articles/12682324-end-of-day-eod-pricing-market-data).

**Unclear items**

- The public pages do not give a price for the redistribution add-on.
- The public pages do not confirm the Borsa Istanbul display fee for this service.
- The API uses credits. The final rate depends on the endpoints and the number of symbols.

**Inference**

Twelve Data has the best stated technical fit for Borsa Istanbul, global equities, FX, and corporate actions.

Its confirmed base business price is about ten times the target data budget.

### 3. EODHD, if sales offers a small public-display plan

**Confirmed facts**

- EODHD covers more than 150,000 symbols across 70 or more exchanges.
- It provides over 30 years of history.
- It has global end-of-day prices, intraday data, FX data, splits, and dividends.
- Its exchange documents include Istanbul Stock Exchange support.
- Its personal All World plan costs USD 19.99 each month.
- Its personal extended plan costs USD 29.99 each month.
- Those retail plans permit personal use only.
- The commercial Internal Use plan costs USD 399 each month.
- The Enterprise plan costs USD 2,499 each month.
- The Internal Use plan prohibits public display and external data access.
- A Custom plan can permit client data downloads.
- The commercial plans state 1,000 requests each minute.

Sources: [EODHD quick start](https://eodhd.com/financial-apis/quick-start-with-our-financial-data-apis), [EODHD exchange API](https://eodhd.com/financial-apis/exchanges-api-list-of-tickers-and-trading-hours), [EODHD Istanbul notice](https://eodhd.com/financial-apis-blog/new-symbols-philippines-stock-exchange), [EODHD split and dividend API](https://eodhd.com/financial-apis/api-splits-dividends), [EODHD FX API](https://eodhd.com/financial-apis/list-supported-forex-currencies), [EODHD personal prices](https://eodhd.com/pricing), and [EODHD commercial prices](https://eodhd.com/commercial-pricing).

**Unclear items**

- The public commercial table does not clearly map the Enterprise plan to customer display.
- A Custom agreement appears necessary for a public application.
- The public pages do not give a small startup price for that right.

**Inference**

EODHD is a strong technical fallback. Its confirmed commercial price does not fit the beta budget.

## Full comparison

### Alpha Vantage

**Confirmed facts**

- The API offers global daily equity data and 20 or more years of history.
- It offers intraday equity data, FX data, dividends, and splits.
- The free limit is 25 requests each day.
- Premium plans remove the daily limit and set a requests-per-minute limit.
- The public page does not show the plan prices in readable page text.
- Alpha Vantage requires a sales contact for commercial use.
- Its standard license is non-sublicensable and non-transferable.

Sources: [Alpha Vantage API document](https://www.alphavantage.co/documentation/), [Alpha Vantage premium page](https://www.alphavantage.co/premium/), and [Alpha Vantage terms](https://www.alphavantage.co/terms_of_service/).

**Unclear items**

- The public symbol examples do not confirm Borsa Istanbul coverage.
- The public pages do not give a public-display price.
- The public pages do not grant redistribution under a normal premium plan.

**Reason not to select now**

The provider needs a commercial quote and an exact Borsa Istanbul test.

### Financial Modeling Prep

**Confirmed facts**

- FMP puts display and redistribution in its Enterprise plan.
- The Enterprise plan uses a sales quote.
- It states 3,000 or more calls each minute.
- It states more than 30 years of history.
- The plan includes real-time data, historical data, FX, intraday charts, dividends, and splits.
- FMP requires a specific display and license agreement.

Sources: [FMP commercial price page](https://intelligence.financialmodelingprep.com/developer/docs/pricing?planType=commercial), [FMP API document](https://intelligence.financialmodelingprep.com/developer/docs), and [FMP terms](https://intelligence.financialmodelingprep.com/terms-of-service).

**Unclear items**

- FMP gives no public Enterprise price.
- The public page does not confirm Borsa Istanbul data.
- The agreement terms and exchange fees need a sales quote.

**Reason not to select now**

FMP has no confirmed budget fit and no confirmed Borsa Istanbul fit.

### Tiingo

**Confirmed facts**

- Tiingo EOD data covers US and Chinese markets.
- It states 80,000 or more tickers and history back to 1962.
- EOD rows include raw prices, adjusted prices, dividends, and split factors.
- Tiingo offers a separate real-time IEX feed for US equities.
- Its FX feed covers more than 140 pairs and starts in January 2020.
- The internal Commercial plan costs USD 50 each month.
- Internal plans prohibit public display.
- The EOD plus IEX redistribution plan costs USD 250 each month for startups.
- That redistribution plan states 80,000 requests each hour and 1,200,000 requests each day.
- A redistribution grant requires special approval and a source label.

Sources: [Tiingo EOD product](https://www.tiingo.com/products/end-of-day-stock-price-data), [Tiingo EOD API document](https://www.tiingo.com/documentation/end-of-day), [Tiingo FX product](https://www.tiingo.com/products/forex-api), [Tiingo terms](https://api.tiingo.com/tos/), and [Tiingo API rules](https://www.tiingo.com/documentation/general).

**Reason not to select now**

Tiingo does not provide the required Borsa Istanbul coverage. Its redistribution plan also exceeds the target budget.

### Massive, formerly Polygon.io

**Confirmed facts**

- The standard stock product covers US equities.
- The Business stock plan costs USD 2,499 each month.
- The Business plan covers commercial display rights.
- Individual plans permit personal and non-professional use.
- The stock service has REST, WebSocket, flat files, corporate actions, and long history.
- Other asset classes use separate plans.
- The standard market-data terms prohibit third-party display and redistribution without written consent.

Sources: [Massive stock product and prices](https://massive.com/stocks), [Massive API document](https://massive.com/docs), and [Massive market-data terms](https://massive.com/legal/market-data-terms-of-service).

**Reason not to select now**

Massive has no Borsa Istanbul fit. Its commercial plan also exceeds the budget by a large amount.

### Finnhub

**Confirmed facts**

- Finnhub offers global stock symbols, stock candles, FX rates, splits, and dividends.
- Daily stock candles use split-adjusted data.
- Intraday stock candles use raw data.
- The service sets a 30-calls-per-second ceiling above each plan limit.
- Finnhub classifies all public plans as personal unless it says otherwise.
- Public display and redistribution need written approval.
- Data must be deleted when a data subscription ends.

Sources: [Finnhub API document](https://finnhub.io/docs/api), [Finnhub terms](https://finnhub.io/terms-of-service), and [Finnhub price page](https://finnhub.io/pricing).

**Unclear items**

- The public price page does not expose a clear commercial display price.
- The public documents do not confirm Borsa Istanbul price coverage.
- International real-time quotes need an Enterprise partner feed.

**Reason not to select now**

Finnhub needs a written license, a sales quote, and a Borsa Istanbul proof.

### Marketstack

See the short-list section. It remains a conditional candidate.

### Twelve Data

See the short-list section. It remains the best technical candidate.

### EODHD

See the short-list section. It remains a strong technical fallback.

## Official Borsa Istanbul path

Borsa Istanbul sells historical data through DataStore.

Its DataStore terms prohibit robot access without prior written permission.

Borsa Istanbul sends real-time, delayed, and end-of-day data through licensed data vendors.

A direct real-time distribution license needs a Borsa Istanbul Data Distribution Agreement.

Sources: [Borsa Istanbul DataStore](https://datastore.borsaistanbul.com/), [Borsa Istanbul data dissemination](https://www.borsaistanbul.com/en/data/data-dissemination), [Borsa Istanbul distribution agreement](https://www.borsaistanbul.com/en/data/data-dissemination/borsa-istanbul-data-distribution-agreement), and [licensed vendor directory](https://www.borsaistanbul.com/en/data/data-dissemination/data-vendors-directory).

**Inference**

DataStore is not a simple server API replacement. A licensed vendor can be a later Turkey-specific source.

Ask Borsa Istanbul for a vendor that supports a small public portfolio service.

## Rejection summary

| Provider | Current result | Main reason |
|---|---|---|
| Marketstack | Conditional short-list | Public-display rights and Borsa Istanbul coverage remain unclear. |
| Twelve Data | Technical short-list | The USD 499 business price exceeds the target. Redistribution costs extra. |
| EODHD | Technical short-list | Commercial plans start at USD 399. Public display needs a clear agreement. |
| Alpha Vantage | Hold | Commercial price and Borsa Istanbul coverage remain unclear. |
| FMP | Hold | Enterprise quote and Borsa Istanbul proof are required. |
| Tiingo | Reject for this beta | The equity feed does not cover Turkey. |
| Massive | Reject for this beta | The stock feed is US-only and costs USD 2,499 for business use. |
| Finnhub | Hold | Written approval, a quote, and a Turkey proof are required. |
| Borsa Istanbul direct | Later option | It needs an exchange agreement or a licensed data vendor. |

## Questions for sales

Send the same questions to each short-list provider.

1. Does the plan permit quote display to guests and signed-in users?
2. Does the plan permit free open-beta use?
3. Does the plan permit a later paid service?
4. Does the plan permit a shared server cache?
5. Can the service store daily prices for the life of each Portfolio?
6. Must the service delete cached history after contract end?
7. Does the plan permit derived Portfolio values and return charts?
8. Does the plan permit direct quote values in the user interface?
9. Which Borsa Istanbul symbols and instrument types are covered?
10. What is the Borsa Istanbul delay?
11. Do exchange fees apply per user or per device?
12. Does the plan cover global daily prices and corporate actions?
13. Does the plan provide raw and adjusted prices as separate fields?
14. Does it provide split factors and ex-dates?
15. Does it provide historical and current FX rates to TRY?
16. What attribution must the service show?
17. What API and bandwidth limits apply?
18. Can one request contain many symbols?
19. What price applies at 1,000 monthly users and 100 active symbols?
20. Will the provider sign a display and redistribution addendum?

## Migration seam

Do not replace `yfinance` calls with another provider throughout the code.

Add these provider-neutral interfaces:

```python
class ReferenceDataProvider(Protocol):
    def search(self, query: str) -> list[InstrumentMatch]: ...
    def resolve(self, instrument: InstrumentKey) -> ProviderSymbol: ...

class DailyPriceProvider(Protocol):
    def closes(
        self, symbols: list[ProviderSymbol], start: date, end: date
    ) -> dict[ProviderSymbol, list[DailyBar]]: ...

class IntradayPriceProvider(Protocol):
    def bars(
        self, symbols: list[ProviderSymbol], interval: str, start: datetime, end: datetime
    ) -> dict[ProviderSymbol, list[IntradayBar]]: ...

class CorporateActionProvider(Protocol):
    def splits(self, symbol: ProviderSymbol, start: date, end: date) -> list[SplitEvent]: ...
    def dividends(self, symbol: ProviderSymbol, start: date, end: date) -> list[DividendEvent]: ...
```

Keep the current `FxProvider` protocol. Extend it beyond a fixed TRY quote currency.

Use a provider-neutral instrument key:

- Native symbol
- MIC exchange code
- Native currency
- ISIN or FIGI when available

Store provider symbols in a separate map. Do not keep `yf_symbol` as the durable identity.

Each market-data row must include these fields:

- Provider name
- Provider symbol
- Source time
- Fetch time
- Price currency
- Adjustment mode
- Delay class
- License policy version

The adapter must return raw daily closes. The current split process depends on raw prices.

The adapter must isolate one bad symbol. It must not fail the full Portfolio.

The service must own cache policy. The provider adapter must only fetch and normalize data.

Add contract tests against fixed adapter fixtures. Keep the current Yahoo adapter as the first fixture source.

Run the new provider beside Yahoo before the switch. Compare dates, raw closes, currencies, and split events.

## Recommended beta decision

1. Keep Yahoo under the written beta grant.
2. Record the exact grant terms outside the public repository.
3. Convert those terms into a short internal policy.
4. Add the provider-neutral seam before public traffic.
5. Ask Marketstack for a written customer-display grant.
6. Ask Twelve Data for a Borsa Istanbul redistribution quote.
7. Ask EODHD for its smallest public-display Custom quote.
8. Select a replacement only after a symbol and license proof.

The beta can use delayed or end-of-day Borsa Istanbul data. It does not need real-time exchange data.

This choice reduces the license cost and the server request rate.

The service should show each price time and source. It should not label delayed data as live data.
