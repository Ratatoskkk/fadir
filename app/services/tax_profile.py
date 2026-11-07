from __future__ import annotations

import json
from datetime import date
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import TaxProfile, User, Workspace, Portfolio, Transaction, Side
from app.calc.tax import TaxConfig, TaxEstimate, estimate_tax
from app.calc.fifo import build_lot_book
from app.calc.types import TxnInput, Side as CalcSide
from decimal import Decimal


from app.calc.tax_sources import TURKEY_ASSUMPTIONS, TURKEY_DISCLAIMER, turkey_tax_year
from app.calc.jurisdictions import JURISDICTIONS, Gain, Result, estimate as jurisdiction_estimate

#: Stored on non-Turkey profiles; the interface shows its own translated disclaimer.
ESTIMATE_DISCLAIMER = "Estimate only; not a tax return or tax advice."


class RateLookup:
    """`currency`/TRY on a date; the FX service in production, a stub in tests."""

    def __call__(self, currency: str, on: date) -> Decimal:  # pragma: no cover - protocol
        raise NotImplementedError


@dataclass(frozen=True)
class TaxProfileData:
    jurisdiction: str
    tax_year: int
    currency: str
    source_url: str
    source_version: str
    assumptions: list[str]
    disclaimer: str


class TaxProfileService:
    def __init__(self, session: Session):
        self.session = session

    def get(self, user_id: int, jurisdiction: str, tax_year: int) -> TaxProfile | None:
        return self.session.scalar(select(TaxProfile).where(TaxProfile.user_id == user_id, TaxProfile.jurisdiction == jurisdiction, TaxProfile.tax_year == tax_year))

    def save(self, user_id: int, data: TaxProfileData) -> TaxProfile:
        known = JURISDICTIONS.get(data.jurisdiction)
        if known is None or known.currency != data.currency:
            raise ValueError("unsupported Tax Jurisdiction")
        profile = self.get(user_id, data.jurisdiction, data.tax_year)
        if profile is None:
            profile = TaxProfile(user_id=user_id, jurisdiction=data.jurisdiction, tax_year=data.tax_year, currency=data.currency, source_url=data.source_url, source_version=data.source_version, assumptions_json=json.dumps(data.assumptions, ensure_ascii=False), disclaimer=data.disclaimer)
            self.session.add(profile)
        else:
            profile.currency = data.currency
            profile.source_url = data.source_url
            profile.source_version = data.source_version
            profile.assumptions_json = json.dumps(data.assumptions, ensure_ascii=False)
            profile.disclaimer = data.disclaimer
        self.session.flush()
        return profile

    def ensure_turkey(self, user_id: int, tax_year: int) -> TaxProfile | None:
        """The User's Turkey profile for `tax_year`, created or refreshed from the official source.

        Returns None when the service has no published tariff for that year.
        """
        source = turkey_tax_year(tax_year)
        if source is None:
            return None
        profile = self.get(user_id, "TR", tax_year)
        if profile is not None and profile.source_version == source.source_version:
            return profile
        return self.save(user_id, TaxProfileData("TR", tax_year, "TRY", source.source_url, source.source_version, list(TURKEY_ASSUMPTIONS), TURKEY_DISCLAIMER))

    def ensure_profile(self, user_id: int, code: str, tax_year: int) -> TaxProfile | None:
        """The User's profile for one supported jurisdiction and year; None without rules."""
        if code == "TR":
            return self.ensure_turkey(user_id, tax_year)
        jurisdiction = JURISDICTIONS.get(code)
        rules = jurisdiction.years.get(tax_year) if jurisdiction else None
        if rules is None:
            return None
        profile = self.get(user_id, code, tax_year)
        if profile is not None and profile.source_version == rules.source_version:
            return profile
        return self.save(user_id, TaxProfileData(code, tax_year, jurisdiction.currency, rules.source_url, rules.source_version, [], ESTIMATE_DISCLAIMER))

    def _user_transactions(self, user_id: int, until: date) -> dict[tuple[int, str], list[TxnInput]]:
        stmt = (
            select(Transaction)
            .join(Portfolio)
            .join(Workspace)
            .where(Workspace.user_id == user_id, Transaction.trade_date <= until)
        )
        grouped: dict[tuple[int, str], list[TxnInput]] = {}
        for txn in self.session.scalars(stmt):
            grouped.setdefault((txn.portfolio_id, txn.instrument.ticker), []).append(TxnInput(id=txn.id, ticker=txn.instrument.ticker, currency=txn.instrument.currency, trade_date=txn.trade_date, side=CalcSide(txn.side.value), quantity=txn.quantity, price_native=txn.price_native, fees_native=txn.fees_native or Decimal("0"), fx_rate_to_try=txn.fx_rate_to_try, fx_rate_date=txn.fx_rate_date, fx_provider=txn.fx_provider, fee_currency=txn.fee_currency, fee_fx_rate_to_try=txn.fee_fx_rate_to_try, fee_fx_rate_date=txn.fee_fx_rate_date, fee_fx_provider=txn.fee_fx_provider))
        return grouped

    def jurisdiction_gains(self, user_id: int, code: str, tax_year: int, rate: RateLookup) -> list[Gain]:
        """Every sale in the jurisdiction's tax year, valued in its currency on each date.

        Cost uses the purchase-date rate and proceeds the sale-date rate, so a currency
        move between buying and selling is part of the gain, as these jurisdictions
        measure it.
        """
        jurisdiction = JURISDICTIONS[code]
        start, end = jurisdiction.period(tax_year)
        target = jurisdiction.currency
        gains: list[Gain] = []
        for (_, ticker), transactions in self._user_transactions(user_id, end).items():
            native = transactions[0].currency
            book = build_lot_book(ticker, native, transactions)
            for d in book.disposals:
                if not start <= d.sell_date <= end:
                    continue
                if native == target:
                    proceeds, cost = d.proceeds_native, d.cost_native
                else:
                    proceeds = d.proceeds_native * d.sell_fx_rate / rate(target, d.sell_date)
                    cost = d.cost_native * d.lot_fx_rate / rate(target, d.lot_date)
                gains.append(Gain(proceeds=proceeds, cost=cost, held_days=(d.sell_date - d.lot_date).days))
        return gains

    def estimate_jurisdiction(self, user_id: int, code: str, tax_year: int, rate: RateLookup) -> tuple[Result, Decimal]:
        return jurisdiction_estimate(code, tax_year, self.jurisdiction_gains(user_id, code, tax_year, rate))

    @staticmethod
    def portfolios_for_user(session: Session, user_id: int) -> list[int]:
        return list(session.scalars(select(Portfolio.id).join(Workspace).where(Workspace.user_id == user_id)))

    def estimate_for_user(
        self,
        user_id: int,
        portfolio_totals: dict[int, tuple[Decimal, Decimal]] | None,
        config: TaxConfig,
        tax_year: int | None = None,
    ) -> TaxEstimate:
        profile = self.get(user_id, "TR", tax_year) if tax_year is not None else self.session.scalar(select(TaxProfile).where(TaxProfile.user_id == user_id, TaxProfile.jurisdiction == "TR").order_by(TaxProfile.tax_year.desc()))
        if profile is None:
            raise LookupError("Tax Profile not found")
        owned = set(self.portfolios_for_user(self.session, user_id))
        if portfolio_totals is None:
            portfolio_totals = {}
            stmt = select(Transaction).join(Portfolio).join(Workspace).where(Workspace.user_id == user_id)
            if tax_year is not None:
                stmt = stmt.where(Transaction.trade_date <= date(tax_year, 12, 31))
            grouped: dict[tuple[int, str], list[TxnInput]] = {}
            for txn in self.session.scalars(stmt):
                grouped.setdefault((txn.portfolio_id, txn.instrument.ticker), []).append(TxnInput(id=txn.id, ticker=txn.instrument.ticker, currency=txn.instrument.currency, trade_date=txn.trade_date, side=CalcSide(txn.side.value), quantity=txn.quantity, price_native=txn.price_native, fees_native=txn.fees_native or Decimal("0"), fx_rate_to_try=txn.fx_rate_to_try, fx_rate_date=txn.fx_rate_date, fx_provider=txn.fx_provider, fee_currency=txn.fee_currency, fee_fx_rate_to_try=txn.fee_fx_rate_to_try, fee_fx_rate_date=txn.fee_fx_rate_date, fee_fx_provider=txn.fee_fx_provider))
            for (portfolio_id, ticker), transactions in grouped.items():
                book = build_lot_book(ticker, transactions[0].currency, transactions)
                year_disposals = [d for d in book.disposals if tax_year is None or d.sell_date.year == tax_year]
                proceeds = sum((d.proceeds_try for d in year_disposals), Decimal("0"))
                cost = sum((d.cost_try for d in year_disposals), Decimal("0"))
                old_proceeds, old_cost = portfolio_totals.get(portfolio_id, (Decimal("0"), Decimal("0")))
                portfolio_totals[portfolio_id] = (old_proceeds + proceeds, old_cost + cost)
        if not set(portfolio_totals) <= owned:
            raise PermissionError("portfolio is not owned by User")
        proceeds = sum((values[0] for values in portfolio_totals.values()), Decimal("0"))
        cost = sum((values[1] for values in portfolio_totals.values()), Decimal("0"))
        return estimate_tax(proceeds, cost, config)
