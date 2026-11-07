"""Capital gains Tax Estimates for each supported Tax Jurisdiction (ADR 0012).

Each jurisdiction measures gains in its own currency, over its own tax year, and owns its
published figures with a citation. Turkey keeps its detailed model in `app.calc.tax`;
this module adds the United Kingdom, Germany, the United States and France with the
simplest defensible model for a private investor, every assumption stated as a key the
interface translates.

**These are estimates, not tax advice.** Each one names what it leaves out.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Callable

ZERO = Decimal("0")
CENT = Decimal("0.01")


@dataclass(frozen=True)
class Gain:
    """One disposal measured in the jurisdiction currency."""

    proceeds: Decimal
    cost: Decimal
    held_days: int

    @property
    def amount(self) -> Decimal:
        return self.proceeds - self.cost


@dataclass(frozen=True)
class YearRules:
    tax_year: int
    source_url: str
    source_version: str
    params: dict[str, Decimal | tuple]


@dataclass(frozen=True)
class Result:
    gross_gain: Decimal
    taxable_gain: Decimal
    tax: Decimal
    marginal_rate: Decimal
    assumptions: tuple[str, ...]


@dataclass(frozen=True)
class Jurisdiction:
    code: str
    currency: str
    years: dict[int, YearRules]
    compute: Callable[[list[Gain], YearRules], Result] | None
    #: First day of tax year N; the year ends the day before year N+1 starts.
    starts: tuple[int, int] = (1, 1)

    def period(self, tax_year: int) -> tuple[date, date]:
        month, day = self.starts
        start = date(tax_year, month, day)
        next_start = date(tax_year + 1, month, day)
        return start, date.fromordinal(next_start.toordinal() - 1)


def _d(value: str | int) -> Decimal:
    return Decimal(str(value))


def _net(gains: list[Gain]) -> Decimal:
    return sum((g.amount for g in gains), ZERO)


def _progressive(amount: Decimal, bands: tuple, starting_at: Decimal = ZERO) -> tuple[Decimal, Decimal]:
    """Tax on `amount` stacked on top of `starting_at`; bands are (upper or None, rate)."""
    tax = ZERO
    marginal = ZERO
    lower = ZERO
    end = starting_at + amount
    for upper, rate in bands:
        low = max(lower, starting_at)
        high = end if upper is None else min(upper, end)
        if high > low:
            tax += (high - low) * rate
            marginal = rate
        if upper is None:
            break
        lower = upper
    return tax, marginal


# -- United Kingdom ----------------------------------------------------------------


def _uk(gains: list[Gain], rules: YearRules) -> Result:
    p = rules.params
    gross = _net(gains)
    taxable = max(ZERO, gross - p["annual_exempt"])
    tax, marginal = _progressive(taxable, ((p["basic_band"], p["basic_rate"]), (None, p["higher_rate"])))
    return Result(gross, taxable, tax, marginal, ("gb.rates", "gb.exempt", "gb.no_income", "gb.no_pooling"))


# -- Germany -----------------------------------------------------------------------


def _de(gains: list[Gain], rules: YearRules) -> Result:
    p = rules.params
    gross = _net(gains)
    taxable = max(ZERO, gross - p["saver_allowance"])
    rate = p["flat_rate"] * (1 + p["solidarity"])
    return Result(gross, taxable, taxable * rate, rate if taxable > ZERO else ZERO, ("de.flat", "de.allowance", "de.no_church"))


# -- United States -----------------------------------------------------------------

#: The IRS holding-period rule: more than one year is long-term.
LONG_TERM_DAYS = 365


def _us(gains: list[Gain], rules: YearRules) -> Result:
    p = rules.params
    short = sum((g.amount for g in gains if g.held_days <= LONG_TERM_DAYS), ZERO)
    long_ = sum((g.amount for g in gains if g.held_days > LONG_TERM_DAYS), ZERO)
    # A net loss in one class offsets a net gain in the other.
    if short < ZERO < long_:
        long_, short = max(ZERO, long_ + short), ZERO
    elif long_ < ZERO < short:
        short, long_ = max(ZERO, short + long_), ZERO
    short, long_ = max(ZERO, short), max(ZERO, long_)
    gross = _net(gains)

    deduction = p["standard_deduction"]
    ordinary = max(ZERO, short - deduction)
    deduction = max(ZERO, deduction - short)
    preferential = max(ZERO, long_ - deduction)

    ordinary_tax, ordinary_marginal = _progressive(ordinary, p["ordinary_bands"])
    lt_bands = ((p["ltcg_zero_to"], ZERO), (p["ltcg_fifteen_to"], _d("0.15")), (None, _d("0.20")))
    lt_tax, lt_marginal = _progressive(preferential, lt_bands, starting_at=ordinary)

    magi = short + long_
    niit_base = min(short + long_, max(ZERO, magi - p["niit_threshold"]))
    niit = niit_base * p["niit_rate"]

    marginal = max(ordinary_marginal, lt_marginal) + (p["niit_rate"] if niit > ZERO else ZERO)
    return Result(
        gross,
        ordinary + preferential,
        ordinary_tax + lt_tax + niit,
        marginal,
        ("us.single", "us.no_income", "us.holding", "us.niit", "us.federal_only"),
    )


# -- France ------------------------------------------------------------------------


def _fr(gains: list[Gain], rules: YearRules) -> Result:
    p = rules.params
    gross = _net(gains)
    taxable = max(ZERO, gross)
    rate = p["income_tax"] + p["social_levies"]
    return Result(gross, taxable, taxable * rate, rate if taxable > ZERO else ZERO, ("fr.pfu", "fr.no_bareme", "fr.no_carryforward"))


JURISDICTIONS: dict[str, Jurisdiction] = {
    "TR": Jurisdiction(code="TR", currency="TRY", years={}, compute=None),
    "GB": Jurisdiction(
        code="GB",
        currency="GBP",
        starts=(4, 6),
        compute=_uk,
        years={
            year: YearRules(
                tax_year=year,
                source_url="https://www.gov.uk/guidance/capital-gains-tax-rates-and-allowances",
                source_version=f"HMRC Capital Gains Tax rates and allowances {year}-{str(year + 1)[2:]}",
                params={
                    "annual_exempt": _d(3000),
                    "basic_band": _d(37700),
                    "basic_rate": _d("0.18"),
                    "higher_rate": _d("0.24"),
                },
            )
            for year in (2025, 2026)
        },
    ),
    "DE": Jurisdiction(
        code="DE",
        currency="EUR",
        compute=_de,
        years={
            year: YearRules(
                tax_year=year,
                source_url="https://www.gesetze-im-internet.de/estg/__32d.html",
                source_version=f"EStG §32d, §20 Abs. 9; SolZG §4 ({year})",
                params={"flat_rate": _d("0.25"), "solidarity": _d("0.055"), "saver_allowance": _d(1000)},
            )
            for year in (2025, 2026)
        },
    ),
    "US": Jurisdiction(
        code="US",
        currency="USD",
        compute=_us,
        years={
            2025: YearRules(
                tax_year=2025,
                source_url="https://www.irs.gov/pub/irs-drop/rp-24-40.pdf",
                source_version="IRS Rev. Proc. 2024-40; standard deduction per P.L. 119-21",
                params={
                    "standard_deduction": _d(15750),
                    "ordinary_bands": (
                        (_d(11925), _d("0.10")), (_d(48475), _d("0.12")), (_d(103350), _d("0.22")),
                        (_d(197300), _d("0.24")), (_d(250525), _d("0.32")), (_d(626350), _d("0.35")),
                        (None, _d("0.37")),
                    ),
                    "ltcg_zero_to": _d(48350),
                    "ltcg_fifteen_to": _d(533400),
                    "niit_threshold": _d(200000),
                    "niit_rate": _d("0.038"),
                },
            ),
            2026: YearRules(
                tax_year=2026,
                source_url="https://www.irs.gov/pub/irs-drop/rp-25-32.pdf",
                source_version="IRS Rev. Proc. 2025-32",
                params={
                    "standard_deduction": _d(16100),
                    "ordinary_bands": (
                        (_d(12400), _d("0.10")), (_d(50400), _d("0.12")), (_d(105700), _d("0.22")),
                        (_d(201775), _d("0.24")), (_d(256225), _d("0.32")), (_d(640600), _d("0.35")),
                        (None, _d("0.37")),
                    ),
                    "ltcg_zero_to": _d(49450),
                    "ltcg_fifteen_to": _d(545500),
                    "niit_threshold": _d(200000),
                    "niit_rate": _d("0.038"),
                },
            ),
        },
    ),
    "FR": Jurisdiction(
        code="FR",
        currency="EUR",
        compute=_fr,
        years={
            2026: YearRules(
                tax_year=2026,
                source_url="https://www.impots.gouv.fr/particulier/questions/comment-sont-imposees-les-plus-values-de-cession-de-valeurs-mobilieres",
                source_version="CGI art. 200 A; LFSS 2026 art. 12 (CSG +1,4 pt)",
                params={"income_tax": _d("0.128"), "social_levies": _d("0.186")},
            ),
        },
    ),
}


def estimate(code: str, tax_year: int, gains: list[Gain]) -> tuple[Result, Decimal]:
    """The jurisdiction's estimate and the year's total proceeds, both in its currency."""
    jurisdiction = JURISDICTIONS[code]
    rules = jurisdiction.years[tax_year]
    result = jurisdiction.compute(gains, rules)
    proceeds = sum((g.proceeds for g in gains), ZERO)
    return result, proceeds
