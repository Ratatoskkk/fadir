"""Official Turkey income tax tariffs (GVK Madde 103), one entry per tax year.

The service owns these figures so a User's Tax Profile fills itself in: nobody types a
source URL or bracket. Each year cites the Resmî Gazete text it was copied from. Add a
year only from the published Gelir Vergisi Genel Tebliği; the non-wage (ücret dışı)
tariff applies to securities gains.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.calc.tax import TaxBracket

TURKEY_DISCLAIMER = (
    "Yaklaşık tahmindir, vergi beyanı veya danışmanlığı değildir. "
    "Kesin hesap için YMM/SMMM'ye danışın."
)

TURKEY_ASSUMPTIONS = (
    "GVK md. 103 ücret dışı gelirler tarifesi uygulanır.",
    "Yalnızca seçilen yılda gerçekleşen FIFO satışları dahildir.",
    "Menkul kıymet kazançlarına GVK mük. md. 80 istisnası uygulanmaz.",
)


@dataclass(frozen=True)
class TaxYearSource:
    tax_year: int
    source_url: str
    source_version: str
    brackets: tuple[TaxBracket, ...]


def _brackets(*rows: tuple[int | None, str]) -> tuple[TaxBracket, ...]:
    return tuple(
        TaxBracket(None if upper is None else Decimal(upper), Decimal(rate)) for upper, rate in rows
    )


TURKEY_TAX_YEARS: dict[int, TaxYearSource] = {
    2025: TaxYearSource(
        tax_year=2025,
        source_url="https://www.resmigazete.gov.tr/eskiler/2024/12/20241230M2.htm",
        source_version="GVK Genel Tebliği Seri No: 329 (RG 30.12.2024/32768-2. Mük.)",
        brackets=_brackets(
            (158_000, "0.15"), (330_000, "0.20"), (800_000, "0.27"), (4_300_000, "0.35"), (None, "0.40")
        ),
    ),
    2026: TaxYearSource(
        tax_year=2026,
        source_url="https://www.resmigazete.gov.tr/eskiler/2025/12/20251231M5-30.pdf",
        source_version="GVK Genel Tebliği Seri No: 332 (RG 31.12.2025/33124-5. Mük.)",
        brackets=_brackets(
            (190_000, "0.15"), (400_000, "0.20"), (1_000_000, "0.27"), (5_300_000, "0.35"), (None, "0.40")
        ),
    ),
}


def turkey_tax_year(tax_year: int) -> TaxYearSource | None:
    return TURKEY_TAX_YEARS.get(tax_year)
