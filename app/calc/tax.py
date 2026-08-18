"""Approximate Turkish capital gains tax on a full liquidation.

SPEC §14 puts Turkish capital gains tax out of scope for v1, noting that inflation
indexing "is genuinely complex and deserves its own spec". That judgement was right, and
nothing here should be mistaken for a tax return. What this module provides is a
*rough indication* of what a full exit might cost, computed from figures the app already
holds, with every assumption stated and configurable.

**This is an estimate, not tax advice.** Consult a YMM/SMMM before acting on it.

Why the app can attempt this at all: Turkish law taxes the gain measured in **lira**,
using the exchange rate at acquisition and at disposal. That is exactly the cost basis
this app maintains (SPEC §0) — native price times the trade-date FX rate — so the FX
component of the gain is already inside the taxable base, which is the part people most
often get wrong.

## What is modelled

* **Regime.** Gains on *foreign-listed* shares held by a Turkish tax resident are
  "değer artış kazancı" under GVK Mükerrer Madde 80, declared on the annual return.
  The Geçici 67 withholding regime does not reach them — it applies to Turkish-listed
  instruments held through a local intermediary.

* **No securities exemption.** GVK Mük. 80's annual exemption explicitly excludes gains
  from disposing of securities and other capital-market instruments, so the default
  exemption here is zero. It is configurable only because the law is not frozen.

* **Inflation indexing (endeksleme, GVK Mük. Madde 81).** Acquisition cost may be
  indexed by the rise in the domestic PPI (Yİ-ÜFE) between the month before acquisition
  and the month before disposal, **but only if that rise is at least 10%**. In a
  high-inflation setting this is the single largest factor, and ignoring it can overstate
  the tax dramatically. It is *off* by default because it requires real Yİ-ÜFE index
  values, which this app does not fetch — supply them in `config.yaml` to switch it on.

* **Progressive brackets (GVK Madde 103).** The gain stacks on top of any other income
  declared for the year, so `other_income_try` shifts which bracket the first lira of
  gain lands in. Brackets are configurable because they are revalued annually.

* **Losses offset gains** within the same category before tax is applied.

## What is deliberately not modelled

Dividend withholding, the one-year holding rules that apply to unlisted or Turkish-listed
shares, stamp duty, wealth or inheritance tax, double-taxation relief on foreign tax
already withheld, and the separate treatment of derivative instruments. A position
already sold during the year is included at its realized gain; anything sold in an
earlier tax year is not, since this models a liquidation *today*.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, localcontext

from app.calc.types import CALC_PRECISION, ZERO


@dataclass(frozen=True)
class TaxBracket:
    """One slice of the GVK Madde 103 tariff."""

    #: Upper bound of the bracket in TRY; None for the top, open-ended bracket.
    upper: Decimal | None
    rate: Decimal


@dataclass(frozen=True)
class TaxConfig:
    enabled: bool = True
    brackets: tuple[TaxBracket, ...] = ()
    #: Other declared income for the year; the gain stacks on top of it.
    other_income_try: Decimal = ZERO
    #: Zero for securities — see the module docstring.
    exemption_try: Decimal = ZERO
    #: Inflation indexing of the acquisition cost (GVK Mük. 81).
    indexing_enabled: bool = False
    #: Rise in Yİ-ÜFE over the holding period, as a fraction (0.42 = 42%).
    indexing_rate: Decimal = ZERO
    #: Indexing is only permitted when the rise reaches this threshold.
    indexing_threshold: Decimal = Decimal("0.10")
    #: Free-text label describing where the numbers came from.
    basis_note: str = ""


@dataclass(frozen=True)
class TaxEstimate:
    applicable: bool
    gross_gain_try: Decimal
    indexed_cost_try: Decimal
    indexing_applied: bool
    indexing_rate: Decimal
    exemption_applied_try: Decimal
    taxable_gain_try: Decimal
    tax_try: Decimal
    effective_rate: Decimal
    marginal_rate: Decimal
    net_after_tax_try: Decimal

    # -- how the taxable base splits (SPEC §6 attribution, carried into the tax view) --
    #
    # The currency gain is taxable in full: Turkish law measures the gain in lira, using
    # the FX rate at acquisition and the rate at disposal, so a position flat in its own
    # currency still produces a taxable gain when the lira weakens. That falls straight
    # out of the cost basis this app already keeps (native price x trade-date rate), so
    # the FX component is inside `gross_gain_try` rather than being a separate charge —
    # these fields exist so the UI can show that instead of leaving it to be guessed at.
    price_portion_try: Decimal = ZERO
    fx_portion_try: Decimal = ZERO
    tax_on_price_try: Decimal = ZERO
    tax_on_fx_try: Decimal = ZERO
    #: Human-readable assumptions, surfaced in the UI so nothing is hidden.
    assumptions: list[str] = field(default_factory=list)
    disclaimer: str = (
        "Yaklaşık tahmindir, vergi beyanı veya danışmanlığı değildir. "
        "Kesin hesap için YMM/SMMM'ye danışın."
    )


#: GVK Madde 103 tariff, 2025 values (TRY). Revalued annually — override in config.yaml
#: for the tax year in question rather than trusting these to stay current.
DEFAULT_BRACKETS: tuple[TaxBracket, ...] = (
    TaxBracket(Decimal("158000"), Decimal("0.15")),
    TaxBracket(Decimal("330000"), Decimal("0.20")),
    TaxBracket(Decimal("800000"), Decimal("0.27")),
    TaxBracket(Decimal("4300000"), Decimal("0.35")),
    TaxBracket(None, Decimal("0.40")),
)


def progressive_tax(
    amount: Decimal, brackets: tuple[TaxBracket, ...], starting_at: Decimal = ZERO
) -> tuple[Decimal, Decimal]:
    """Tax on `amount` stacked on top of `starting_at` income.

    Returns (tax, marginal_rate). Walking the tariff from `starting_at` is what makes
    other income matter: the first lira of a gain is taxed at whatever bracket that
    income has already reached, not at 15%.
    """
    if amount <= ZERO:
        return ZERO, ZERO

    with localcontext() as ctx:
        ctx.prec = CALC_PRECISION

        tax = ZERO
        lower = starting_at
        remaining = amount
        marginal = brackets[-1].rate if brackets else ZERO

        for bracket in brackets:
            if remaining <= ZERO:
                break
            if bracket.upper is None:
                tax += remaining * bracket.rate
                marginal = bracket.rate
                remaining = ZERO
                break
            if lower >= bracket.upper:
                continue  # already above this bracket entirely
            room = bracket.upper - lower
            taxed_here = min(remaining, room)
            tax += taxed_here * bracket.rate
            marginal = bracket.rate
            remaining -= taxed_here
            lower += taxed_here

        return tax, marginal


@dataclass(frozen=True)
class _TaxableBase:
    """The arithmetic half of an estimate, with none of the narrative."""

    indexed_cost: Decimal
    indexing_applied: bool
    gross_gain: Decimal
    gain_after_indexing: Decimal
    taxable: Decimal
    tax: Decimal
    marginal: Decimal


def _compute(proceeds_try: Decimal, cost_try: Decimal, config: TaxConfig) -> _TaxableBase:
    """Indexing, exemption and the progressive tariff — the figures, nothing else.

    Split out from `estimate_tax` because the historical series values the portfolio
    after tax on *every* point, and it needs only `tax`. Building the assumption strings
    for a figure nobody reads is the single most expensive thing a long series can do:
    seven locale-formatted strings per day, discarded immediately.
    """
    with localcontext() as ctx:
        ctx.prec = CALC_PRECISION

        indexed_cost = cost_try
        indexing_applied = False
        if config.indexing_enabled and config.indexing_rate >= config.indexing_threshold:
            indexed_cost = cost_try * (Decimal("1") + config.indexing_rate)
            indexing_applied = True

        gross_gain = proceeds_try - cost_try
        gain_after_indexing = proceeds_try - indexed_cost

        taxable = gain_after_indexing - config.exemption_try
        if taxable < ZERO:
            taxable = ZERO

        tax, marginal = progressive_tax(
            taxable, config.brackets or DEFAULT_BRACKETS, config.other_income_try
        )

        return _TaxableBase(
            indexed_cost=indexed_cost,
            indexing_applied=indexing_applied,
            gross_gain=gross_gain,
            gain_after_indexing=gain_after_indexing,
            taxable=taxable,
            tax=tax,
            marginal=marginal,
        )


def net_after_tax(proceeds_try: Decimal, cost_try: Decimal, config: TaxConfig) -> Decimal:
    """Proceeds net of the estimated tax. The figure only, for series work.

    `estimate_tax` is the right call wherever the assumptions are shown to someone; this
    is for the history and intraday builders, which plot one number per point.
    """
    return proceeds_try - _compute(proceeds_try, cost_try, config).tax


def estimate_tax(
    proceeds_try: Decimal,
    cost_try: Decimal,
    config: TaxConfig,
    *,
    price_effect_try: Decimal | None = None,
    fx_effect_try: Decimal | None = None,
) -> TaxEstimate:
    """Approximate tax on disposing of everything at `proceeds_try`.

    `cost_try` is the acquisition cost already expressed in lira at trade-date rates,
    which is the basis Turkish law uses — so the currency gain is inside the base by
    construction, not bolted on afterwards.

    `price_effect_try` and `fx_effect_try` are the §6 attribution components. They do not
    change the tax; they let the estimate report how much of the bill is attributable to
    the currency move, which is otherwise invisible.
    """
    base = _compute(proceeds_try, cost_try, config)

    with localcontext() as ctx:
        ctx.prec = CALC_PRECISION

        assumptions: list[str] = []

        # -- inflation indexing (GVK Mük. 81) --------------------------------------
        indexed_cost = base.indexed_cost
        indexing_applied = base.indexing_applied
        if config.indexing_enabled:
            if indexing_applied:
                assumptions.append(
                    f"Maliyet, Yİ-ÜFE artışı %{config.indexing_rate * 100:.1f} ile "
                    f"endekslendi (GVK Mük. 81)."
                )
            else:
                assumptions.append(
                    f"Yİ-ÜFE artışı %{config.indexing_rate * 100:.1f}, "
                    f"%{config.indexing_threshold * 100:.0f} eşiğinin altında olduğu için "
                    f"endeksleme uygulanmadı."
                )
        else:
            assumptions.append(
                "Enflasyon endekslemesi kapalı. Yİ-ÜFE verisi girilirse vergi belirgin "
                "şekilde düşebilir (GVK Mük. 81)."
            )

        gross_gain = base.gross_gain
        gain_after_indexing = base.gain_after_indexing

        # -- exemption --------------------------------------------------------------
        exemption = config.exemption_try
        if exemption > ZERO:
            assumptions.append(
                f"{exemption:,.0f} TL istisna düşüldü. Dikkat: GVK Mük. 80 istisnası "
                f"menkul kıymet kazançlarını kapsamaz."
            )
        else:
            assumptions.append(
                "İstisna uygulanmadı — GVK Mük. 80 istisnası menkul kıymet satış "
                "kazançlarını kapsamıyor."
            )

        taxable = base.taxable

        # A loss is not a negative tax bill; it carries against other gains instead.
        if gain_after_indexing <= ZERO:
            assumptions.append(
                "Endekslemeden sonra kazanç oluşmadığı için vergi hesaplanmadı; "
                "zarar diğer değer artış kazançlarına mahsup edilebilir."
            )

        if config.other_income_try > ZERO:
            assumptions.append(
                f"Kazanç, {config.other_income_try:,.0f} TL diğer gelirin üzerine "
                f"eklenerek dilimlendi (GVK Md. 103)."
            )
        else:
            assumptions.append(
                "Başka gelir beyan edilmediği varsayıldı; diğer geliriniz varsa "
                "kazanç daha üst dilimden vergilenir."
            )

        tax, marginal = base.tax, base.marginal

        effective = (tax / gross_gain) if gross_gain > ZERO else ZERO

        assumptions.append(
            "Yurt dışı borsada işlem gören hisseler için yıllık beyan esas alındı; "
            "Geçici 67 stopajı kapsam dışıdır."
        )

        # -- split the bill between the price move and the currency move ---------------
        price_portion = price_effect_try if price_effect_try is not None else ZERO
        fx_portion = fx_effect_try if fx_effect_try is not None else ZERO
        tax_on_price = ZERO
        tax_on_fx = ZERO

        if price_effect_try is not None and fx_effect_try is not None:
            # Apportion the single progressive bill across the two components in
            # proportion to their contribution. Splitting by magnitude keeps the shares
            # meaningful when the two effects have opposite signs.
            magnitude = abs(price_portion) + abs(fx_portion)
            if magnitude > ZERO and tax > ZERO:
                tax_on_price = tax * abs(price_portion) / magnitude
                tax_on_fx = tax - tax_on_price

            if fx_portion > ZERO:
                assumptions.insert(
                    0,
                    f"Kur farkı kazancı ({fx_portion:,.0f} TL) matraha dahildir — "
                    f"Türk vergi mevzuatı kazancı TL cinsinden, alış ve satış günü "
                    f"kurlarıyla ölçer. Verginin yaklaşık {tax_on_fx:,.0f} TL'si "
                    f"kur farkından kaynaklanıyor.",
                )

        return TaxEstimate(
            applicable=True,
            gross_gain_try=gross_gain,
            indexed_cost_try=indexed_cost,
            indexing_applied=indexing_applied,
            indexing_rate=config.indexing_rate,
            exemption_applied_try=exemption if taxable > ZERO else ZERO,
            taxable_gain_try=taxable,
            tax_try=tax,
            effective_rate=effective,
            marginal_rate=marginal,
            net_after_tax_try=proceeds_try - tax,
            price_portion_try=price_portion,
            fx_portion_try=fx_portion,
            tax_on_price_try=tax_on_price,
            tax_on_fx_try=tax_on_fx,
            assumptions=assumptions,
        )


def disabled_estimate(proceeds_try: Decimal) -> TaxEstimate:
    return TaxEstimate(
        applicable=False,
        gross_gain_try=ZERO,
        indexed_cost_try=ZERO,
        indexing_applied=False,
        indexing_rate=ZERO,
        exemption_applied_try=ZERO,
        taxable_gain_try=ZERO,
        tax_try=ZERO,
        effective_rate=ZERO,
        marginal_rate=ZERO,
        net_after_tax_try=proceeds_try,
        assumptions=["Vergi tahmini kapalı (config.yaml -> tax.enabled)."],
    )
