# Add four Tax Jurisdictions and four interface languages

## Decision — 2026-11-08

The owner added Tax Estimates for the United Kingdom, Germany, the United States and France next to Turkey. This replaces the earlier rule that another country waits for Turkey's public beta acceptance ([ADR 0008](0008-turkey-first-with-tax-jurisdiction-adapters.md)).

Tax has its own page. A signed-in User picks a Tax Jurisdiction and a tax year, and the estimate covers all of the User's Portfolios in that jurisdiction's currency. Each sale is valued with the purchase-date and sale-date exchange rates, so currency moves count as gains, as these jurisdictions measure them. The UK tax year runs from 6 April; the others follow the calendar.

Each jurisdiction uses the simplest defensible model for a private investor and cites its published figures:

| Jurisdiction | Model | Source |
|---|---|---|
| United Kingdom | £3,000 annual exempt amount, 18% / 24% around a £37,700 basic band, no other income, FIFO lots | HMRC CGT rates and allowances |
| Germany | 25% Abgeltungsteuer plus 5.5% Soli after the €1,000 Sparer-Pauschbetrag, no church tax | EStG §32d, §20 Abs. 9; SolZG §4 |
| United States | Federal only, single filer, standard deduction, no other income; short-term at ordinary brackets, long-term 0/15/20%, 3.8% NIIT | IRS Rev. Proc. 2024-40 and 2025-32 |
| France | 31.4% PFU (12.8% income tax + 18.6% social levies), 2026 only | CGI art. 200 A; LFSS 2026 art. 12 |

The estimate lists each assumption in the interface. It remains an estimate, not tax advice.

The rebuilt interface speaks Turkish, English, German, French and Spanish. The first visit follows the browser's language, then the region picks the default Tax Jurisdiction; a choice in Hesap is remembered on that browser. Numbers and dates follow the same locale. The classic interface stays Turkish.

## Not decided

France 2025 is left out because sources disagree on whether the higher social levies reach 2025 gains. Other filing statuses, other income, church tax and HMRC share pooling are not modelled.
