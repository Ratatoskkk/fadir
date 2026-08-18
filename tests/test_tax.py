"""Approximate Turkish capital gains tax (app/calc/tax.py).

Not a claim about anyone's actual liability — these pin the arithmetic and the stated
assumptions so the estimate cannot silently change shape.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.calc.tax import (
    DEFAULT_BRACKETS,
    TaxBracket,
    TaxConfig,
    disabled_estimate,
    estimate_tax,
    progressive_tax,
)

CENT = Decimal("0.01")


# -- the tariff ---------------------------------------------------------------------


def test_progressive_tax_within_the_first_bracket():
    tax, marginal = progressive_tax(Decimal("100000"), DEFAULT_BRACKETS)
    assert tax == Decimal("15000")
    assert marginal == Decimal("0.15")


def test_progressive_tax_spans_brackets():
    """250,000 = 158,000 @ 15% + 92,000 @ 20%."""
    tax, marginal = progressive_tax(Decimal("250000"), DEFAULT_BRACKETS)
    assert tax == Decimal("158000") * Decimal("0.15") + Decimal("92000") * Decimal("0.20")
    assert tax == Decimal("42100")
    assert marginal == Decimal("0.20")


def test_other_income_pushes_the_gain_into_higher_brackets():
    """The first lira of gain is taxed where existing income left off (GVK Md. 103)."""
    alone, _ = progressive_tax(Decimal("100000"), DEFAULT_BRACKETS)
    stacked, marginal = progressive_tax(
        Decimal("100000"), DEFAULT_BRACKETS, starting_at=Decimal("800000")
    )
    assert alone == Decimal("15000")
    # Entirely inside the 35% band once 800,000 of other income is already used up.
    assert stacked == Decimal("35000")
    assert marginal == Decimal("0.35")
    assert stacked > alone


def test_top_bracket_is_open_ended():
    tax, marginal = progressive_tax(Decimal("10000000"), DEFAULT_BRACKETS)
    assert marginal == Decimal("0.40")
    assert tax > Decimal("3000000")


def test_zero_and_negative_amounts_are_untaxed():
    assert progressive_tax(Decimal("0"), DEFAULT_BRACKETS) == (Decimal("0"), Decimal("0"))
    assert progressive_tax(Decimal("-5000"), DEFAULT_BRACKETS) == (Decimal("0"), Decimal("0"))


# -- the estimate --------------------------------------------------------------------


def test_gain_is_taxed_progressively():
    est = estimate_tax(Decimal("1000000"), Decimal("750000"), TaxConfig())
    assert est.gross_gain_try == Decimal("250000")
    assert est.taxable_gain_try == Decimal("250000")
    assert est.tax_try == Decimal("42100")
    assert est.net_after_tax_try == Decimal("1000000") - Decimal("42100")


def test_a_loss_produces_no_tax_and_no_negative_bill():
    est = estimate_tax(Decimal("600000"), Decimal("750000"), TaxConfig())
    assert est.gross_gain_try == Decimal("-150000")
    assert est.taxable_gain_try == Decimal("0")
    assert est.tax_try == Decimal("0")
    assert est.net_after_tax_try == Decimal("600000")
    assert any("zarar" in a for a in est.assumptions)


def test_securities_get_no_exemption_by_default():
    """GVK Mük. 80's exemption excludes securities, so the default must be zero."""
    config = TaxConfig()
    assert config.exemption_try == Decimal("0")
    est = estimate_tax(Decimal("1000000"), Decimal("900000"), config)
    assert est.taxable_gain_try == Decimal("100000")
    assert any("istisna" in a.lower() for a in est.assumptions)


def test_inflation_indexing_reduces_the_taxable_gain():
    """GVK Mük. 81 — the single largest factor in a high-inflation setting."""
    plain = estimate_tax(Decimal("1000000"), Decimal("750000"), TaxConfig())
    indexed = estimate_tax(
        Decimal("1000000"),
        Decimal("750000"),
        TaxConfig(indexing_enabled=True, indexing_rate=Decimal("0.30")),
    )

    # Cost indexed up by 30%: 750,000 -> 975,000, so the gain collapses to 25,000.
    assert indexed.indexing_applied is True
    assert indexed.indexed_cost_try == Decimal("975000")
    assert indexed.taxable_gain_try == Decimal("25000")
    assert indexed.tax_try == Decimal("3750")
    assert indexed.tax_try < plain.tax_try
    # The headline gain reported to the user is still the real, unindexed one.
    assert indexed.gross_gain_try == Decimal("250000")


def test_indexing_below_the_ten_percent_threshold_is_refused():
    """Indexing is only permitted once the Yİ-ÜFE rise reaches 10%."""
    est = estimate_tax(
        Decimal("1000000"),
        Decimal("750000"),
        TaxConfig(indexing_enabled=True, indexing_rate=Decimal("0.04")),
    )
    assert est.indexing_applied is False
    assert est.indexed_cost_try == Decimal("750000")
    assert est.taxable_gain_try == Decimal("250000")
    assert any("eşiğinin altında" in a for a in est.assumptions)


def test_indexing_can_turn_a_gain_into_no_taxable_gain():
    est = estimate_tax(
        Decimal("1000000"),
        Decimal("750000"),
        TaxConfig(indexing_enabled=True, indexing_rate=Decimal("0.60")),
    )
    assert est.indexed_cost_try == Decimal("1200000")
    assert est.taxable_gain_try == Decimal("0")
    assert est.tax_try == Decimal("0")


def test_effective_rate_is_measured_against_the_real_gain():
    est = estimate_tax(Decimal("1000000"), Decimal("750000"), TaxConfig())
    assert est.effective_rate == est.tax_try / Decimal("250000")
    # Progressive, so the effective rate sits below the marginal rate.
    assert est.effective_rate < est.marginal_rate


def test_estimate_always_carries_its_assumptions_and_disclaimer():
    """Nothing about this figure may be presented without its caveats."""
    est = estimate_tax(Decimal("1000000"), Decimal("750000"), TaxConfig())
    assert len(est.assumptions) >= 3
    assert "YMM" in est.disclaimer or "SMMM" in est.disclaimer
    assert any("Geçici 67" in a for a in est.assumptions)
    assert any("endeksleme" in a.lower() or "yİ-üfe" in a.lower() for a in est.assumptions)


def test_fx_gain_is_inside_the_taxable_base_not_added_on_top():
    """Turkish law measures the gain in lira at acquisition- and disposal-date rates.

    The cost basis this app keeps is already lira-denominated at the trade-date rate, so
    the currency gain is part of the base by construction. Charging it again would
    double-count — this pins that it is counted exactly once.
    """
    price_effect = Decimal("18656.19")
    fx_effect = Decimal("27134.67")
    cost = Decimal("769353.58")
    proceeds = cost + price_effect + fx_effect

    est = estimate_tax(
        proceeds, cost, TaxConfig(), price_effect_try=price_effect, fx_effect_try=fx_effect
    )

    # The base is exactly price + FX, counted once.
    assert est.gross_gain_try == price_effect + fx_effect
    assert est.taxable_gain_try == price_effect + fx_effect
    # And the reported split adds back up to the whole bill.
    assert est.tax_on_price_try + est.tax_on_fx_try == est.tax_try
    assert est.tax_on_fx_try > 0


def test_fx_share_of_the_bill_tracks_its_share_of_the_gain():
    est = estimate_tax(
        Decimal("1100000"),
        Decimal("1000000"),
        TaxConfig(),
        price_effect_try=Decimal("25000"),
        fx_effect_try=Decimal("75000"),
    )
    # FX is three quarters of the gain, so three quarters of the tax.
    assert est.tax_on_fx_try == est.tax_try * Decimal("3") / Decimal("4")
    assert est.fx_portion_try == Decimal("75000")
    assert est.price_portion_try == Decimal("25000")


def test_fx_contribution_is_called_out_in_the_assumptions():
    """It must be stated, not merely computed — the user cannot see it otherwise."""
    est = estimate_tax(
        Decimal("1100000"),
        Decimal("1000000"),
        TaxConfig(),
        price_effect_try=Decimal("25000"),
        fx_effect_try=Decimal("75000"),
    )
    assert any("Kur farkı" in a for a in est.assumptions)


def test_split_handles_opposite_signed_effects():
    """TRY strengthening: price up, FX down. Shares must stay sane, not blow up."""
    est = estimate_tax(
        Decimal("1080000"),
        Decimal("1000000"),
        TaxConfig(),
        price_effect_try=Decimal("200000"),
        fx_effect_try=Decimal("-120000"),
    )
    assert est.gross_gain_try == Decimal("80000")
    assert est.tax_on_price_try + est.tax_on_fx_try == est.tax_try
    assert est.tax_on_price_try >= 0
    assert est.tax_on_fx_try >= 0


def test_split_is_absent_when_components_are_not_supplied():
    est = estimate_tax(Decimal("1000000"), Decimal("750000"), TaxConfig())
    assert est.tax_on_price_try == Decimal("0")
    assert est.tax_on_fx_try == Decimal("0")
    # The tax itself is unaffected by whether the breakdown was requested.
    assert est.tax_try == Decimal("42100")


def test_disabled_estimate_leaves_proceeds_untouched():
    est = disabled_estimate(Decimal("815144.45"))
    assert est.applicable is False
    assert est.tax_try == Decimal("0")
    assert est.net_after_tax_try == Decimal("815144.45")


def test_custom_brackets_are_honoured():
    flat = (TaxBracket(None, Decimal("0.25")),)
    est = estimate_tax(
        Decimal("1000000"), Decimal("750000"), TaxConfig(brackets=flat)
    )
    assert est.tax_try == Decimal("62500")
    assert est.marginal_rate == Decimal("0.25")


@pytest.mark.parametrize("gain", ["1", "5000", "157999", "158001", "4299999", "9999999"])
def test_tax_never_exceeds_the_gain(gain):
    proceeds = Decimal("10000000")
    cost = proceeds - Decimal(gain)
    est = estimate_tax(proceeds, cost, TaxConfig())
    assert Decimal("0") <= est.tax_try <= Decimal(gain)


def test_config_yaml_top_bracket_is_open_ended():
    """A closed top bracket would let a very large gain fall through untaxed."""
    from app.config import load_settings

    settings = load_settings()
    assert settings.tax.brackets[-1].upper is None
