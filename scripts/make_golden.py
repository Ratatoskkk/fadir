"""Generate the reconciliation golden file (SPEC §12).

Deliberately **does not import `app.calc`**. The expected values are recomputed here from
first principles with plain `Decimal` arithmetic, spelled out formula by formula, so the
golden file is an independent check rather than a recording of whatever the engine
happened to produce. If the engine and this script ever disagree, one of them is wrong and
the reconciliation test says so.

    python scripts/make_golden.py            # regenerate
    python scripts/make_golden.py --check    # verify the committed file still matches
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal, localcontext
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
INPUT_PATH = FIXTURES / "reconciliation_input.json"
GOLDEN_PATH = FIXTURES / "reconciliation_golden.json"

PRECISION = 50
CENTS = Decimal("0.01")
RATIO = Decimal("0.000000001")


def d(value: str) -> Decimal:
    return Decimal(str(value))


def compute() -> dict:
    raw = json.loads(INPUT_PATH.read_text(encoding="utf-8"))

    with localcontext() as ctx:
        ctx.prec = PRECISION

        instruments = raw["instruments"]
        current_fx = {k: d(v) for k, v in raw["current_fx"].items()}
        current_prices = {k: d(v) for k, v in raw["current_prices"].items()}

        by_ticker: dict[str, list[dict]] = {}
        for txn in raw["transactions"]:
            by_ticker.setdefault(txn["ticker"], []).append(txn)

        positions = []
        total_cost = Decimal("0")
        total_mv = Decimal("0")
        total_price_effect = Decimal("0")
        total_fx_effect = Decimal("0")

        for ticker in sorted(by_ticker):
            txns = by_ticker[ticker]
            currency = instruments[ticker]["currency"]

            # All seed rows are BUYs, so every lot stays open: cost is a plain sum.
            qty = sum((d(t["quantity"]) for t in txns), Decimal("0"))
            cost_native = sum(
                (d(t["quantity"]) * d(t["price_native"]) + d(t["fees_native"]) for t in txns),
                Decimal("0"),
            )
            cost_try = sum(
                (
                    (d(t["quantity"]) * d(t["price_native"]) + d(t["fees_native"]))
                    * d(t["fx_rate_to_try"])
                    for t in txns
                ),
                Decimal("0"),
            )

            price = current_prices[ticker]
            rate = current_fx[currency]

            mv_native = qty * price
            mv_try = mv_native * rate

            # Weighted by native cost, per SPEC §6 — not by quantity.
            wavg_fx = cost_try / cost_native

            pnl_native = mv_native - cost_native
            pnl_try = mv_try - cost_try

            local_return = mv_native / cost_native
            fx_return = rate / wavg_fx
            total_return = local_return * fx_return

            price_effect = (mv_native - cost_native) * wavg_fx
            fx_effect = mv_native * (rate - wavg_fx)

            # Independent cross-checks on the identities before anything is written out.
            assert abs(price_effect + fx_effect - pnl_try) < CENTS, ticker
            assert abs(total_return - mv_try / cost_try) < RATIO, ticker

            positions.append(
                {
                    "ticker": ticker,
                    "currency": currency,
                    "quantity": str(qty.quantize(CENTS)),
                    "lot_count": len(txns),
                    "cost_native": str(cost_native.quantize(CENTS)),
                    "cost_try": str(cost_try.quantize(CENTS)),
                    "market_value_native": str(mv_native.quantize(CENTS)),
                    "market_value_try": str(mv_try.quantize(CENTS)),
                    "pnl_native": str(pnl_native.quantize(CENTS)),
                    "pnl_try": str(pnl_try.quantize(CENTS)),
                    "weighted_avg_cost_fx_rate": str(wavg_fx.quantize(Decimal("0.00000001"))),
                    "local_return": str(local_return.quantize(RATIO)),
                    "fx_return": str(fx_return.quantize(RATIO)),
                    "total_return": str(total_return.quantize(RATIO)),
                    "price_effect_try": str(price_effect.quantize(CENTS)),
                    "fx_effect_try": str(fx_effect.quantize(CENTS)),
                }
            )

            total_cost += cost_try
            total_mv += mv_try
            total_price_effect += price_effect
            total_fx_effect += fx_effect

        total_pnl = total_mv - total_cost
        assert abs(total_price_effect + total_fx_effect - total_pnl) < CENTS

        return {
            "_comment": [
                "Hand-checkable expected output for tests/test_reconciliation.py.",
                "Regenerate with `python scripts/make_golden.py`; verify with `--check`.",
                "Computed from first principles, independently of app.calc.",
            ],
            "as_of": raw["as_of"],
            "positions": positions,
            "totals": {
                "cost_try": str(total_cost.quantize(CENTS)),
                "market_value_try": str(total_mv.quantize(CENTS)),
                "pnl_try": str(total_pnl.quantize(CENTS)),
                "price_effect_try": str(total_price_effect.quantize(CENTS)),
                "fx_effect_try": str(total_fx_effect.quantize(CENTS)),
                "total_return": str((total_mv / total_cost).quantize(RATIO)),
            },
            "liquidation": {
                "haircut_pct": "0",
                "gross_proceeds_try": str(total_mv.quantize(CENTS)),
                "net_proceeds_try": str(total_mv.quantize(CENTS)),
                "total_invested_try": str(total_cost.quantize(CENTS)),
                "net_pnl_try": str(total_pnl.quantize(CENTS)),
            },
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify without rewriting")
    args = parser.parse_args()

    computed = compute()
    serialised = json.dumps(computed, indent=2, ensure_ascii=False) + "\n"

    if args.check:
        if not GOLDEN_PATH.exists():
            print(f"golden file missing: {GOLDEN_PATH}")
            return 1
        if GOLDEN_PATH.read_text(encoding="utf-8") != serialised:
            print("golden file is out of date; run `python scripts/make_golden.py`")
            return 1
        print("golden file matches.")
        return 0

    GOLDEN_PATH.write_text(serialised, encoding="utf-8")
    print(f"wrote {GOLDEN_PATH}")
    for position in computed["positions"]:
        print(
            f"  {position['ticker']:<6} pnl_try={position['pnl_try']:>14} "
            f"local={position['local_return']:>13} fx={position['fx_return']:>13}"
        )
    print(f"  {'TOTAL':<6} pnl_try={computed['totals']['pnl_try']:>14}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
