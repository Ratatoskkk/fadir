from __future__ import annotations

import os
from decimal import Decimal
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session


@pytest.mark.live
def test_postgresql_tax_profile_behavior() -> None:
    if os.environ.get("FADIR_RUN_POSTGRESQL_TAX_PROFILE") != "1":
        pytest.skip("explicit tax profile proof opt-in required")
    raw = os.environ.get("FADIR_TEST_POSTGRESQL_URL")
    database = os.environ.get("FADIR_TEST_POSTGRESQL_DATABASE")
    if not raw or not database:
        raise ValueError("explicit synthetic PostgreSQL URL and database required")
    url = make_url(raw)
    if url.drivername != "postgresql+psycopg" or url.database != database or url.query:
        raise ValueError("synthetic PostgreSQL URL mismatch")
    schema = "tax1_" + uuid4().hex
    marker = "TAX1:" + uuid4().hex
    engine = create_engine(url)
    schema_oid = None
    try:
        with engine.begin() as connection:
            assert connection.scalar(text("SELECT current_database()")) == database
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f'COMMENT ON SCHEMA "{schema}" IS \'{marker}\''))
            schema_oid = connection.scalar(text("SELECT oid FROM pg_namespace WHERE nspname=:schema"), {"schema": schema})
        scoped = url.update_query_dict({"options": f"-csearch_path={schema},pg_catalog"})
        os.environ["FADIR_DATABASE_URL"] = scoped.render_as_string(hide_password=False)
        config = Config("alembic.ini")
        config.set_main_option("script_location", "migrations")
        command.upgrade(config, "head")
        scoped_engine = create_engine(scoped)
        try:
            with Session(scoped_engine) as session:
                from app.models import Instrument, Portfolio, Side, Transaction, User, Workspace
                from app.services.tax_profile import TaxProfileData, TaxProfileService
                from app.calc.tax import TaxBracket, TaxConfig
                user = User(workspace=Workspace(portfolios=[Portfolio(name="One"), Portfolio(name="Two")]))
                other = User(workspace=Workspace(portfolios=[Portfolio(name="Other")]))
                session.add_all([user, other]); session.flush()
                instrument = Instrument(ticker="TAX", exchange="X", yf_symbol="TAX.X", currency="TRY", name="Tax")
                session.add(instrument); session.flush()
                for portfolio in user.workspace.portfolios:
                    session.add_all([
                        Transaction(portfolio_id=portfolio.id, instrument_id=instrument.id, trade_date="2025-01-02", side=Side.BUY, quantity=1, price_native=80, fees_native=0, fx_rate_to_try=1, fx_rate_date="2025-01-02", fx_provider="synthetic"),
                        Transaction(portfolio_id=portfolio.id, instrument_id=instrument.id, trade_date="2025-02-02", side=Side.SELL, quantity=1, price_native=160, fees_native=0, fx_rate_to_try=1, fx_rate_date="2025-02-02", fx_provider="synthetic"),
                    ])
                session.flush()
                service = TaxProfileService(session)
                profile = service.save(user.id, TaxProfileData("TR", 2025, "TRY", "https://gib.gov.tr", "2026-02", ["combined"], "estimate"))
                config_tax = TaxConfig(brackets=(TaxBracket(Decimal("100"), Decimal("0.10")), TaxBracket(None, Decimal("0.20"))))
                estimate = service.estimate_for_user(user.id, None, config_tax, 2025)
                assert profile.currency == "TRY" and profile.tax_year == 2025 and estimate.tax_try == Decimal("22")
                assert service.get(user.id, "TR", 2024) is None
                with pytest.raises(PermissionError):
                    service.estimate_for_user(user.id, {other.workspace.portfolios[0].id: (Decimal("1"), Decimal("0"))}, config_tax, 2025)
        finally:
            scoped_engine.dispose()
    finally:
        with engine.begin() as connection:
            record = connection.execute(text("SELECT current_database(), n.oid, pg_catalog.obj_description(n.oid,'pg_namespace') FROM pg_namespace n WHERE n.nspname=:schema"), {"schema": schema}).one_or_none()
            if schema_oid is not None and record is not None and tuple(record) == (database, schema_oid, marker):
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()
