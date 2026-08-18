"""Pure calculation engine (SPEC §6).

Zero I/O: no network, no DB, no clock. Every function takes its inputs explicitly,
including `as_of` dates, so the whole module is unit-testable in isolation. Money is
`Decimal` throughout — never float.
"""

from app.calc.attribution import (
    Attribution,
    LiquidationSummary,
    PortfolioTotals,
    PositionMetrics,
    attribute,
    liquidation,
    position_metrics,
    summarise_portfolio,
)
from app.calc.fifo import (
    Disposal,
    InsufficientLots,
    Lot,
    LotBook,
    RealizedPnl,
    build_lot_book,
)
from app.calc.history import HistoryPoint, PositionHistoryInput, build_history
from app.calc.tax import (
    DEFAULT_BRACKETS,
    TaxBracket,
    TaxConfig,
    TaxEstimate,
    disabled_estimate,
    estimate_tax,
    progressive_tax,
)
from app.calc.types import CALC_PRECISION, MarketQuote, Side, TxnInput

__all__ = [
    "CALC_PRECISION",
    "DEFAULT_BRACKETS",
    "TaxBracket",
    "TaxConfig",
    "TaxEstimate",
    "disabled_estimate",
    "estimate_tax",
    "progressive_tax",
    "Attribution",
    "Disposal",
    "HistoryPoint",
    "InsufficientLots",
    "LiquidationSummary",
    "Lot",
    "LotBook",
    "MarketQuote",
    "PortfolioTotals",
    "PositionHistoryInput",
    "PositionMetrics",
    "RealizedPnl",
    "Side",
    "TxnInput",
    "attribute",
    "build_history",
    "build_lot_book",
    "liquidation",
    "position_metrics",
    "summarise_portfolio",
]
