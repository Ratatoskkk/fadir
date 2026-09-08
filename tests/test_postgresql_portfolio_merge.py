"""Opt-in synthetic PostgreSQL proof for Portfolio merge."""

from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
import re
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.api.request_authority import RequestAuthority
from app.models import Instrument, Portfolio, Transaction, User, Workspace, Side
from app.services import guest_access
from app.services import portfolio_merge
from test_postgresql_migrations import _selected_test_url

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


class _CleanupGate:
    def __init__(self):
        self.passed = False

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_makereport(self, item, call):
        if call.when == "call":
            self.passed = call.excinfo is None


@pytest.fixture
def database(monkeypatch, request):
    url = _selected_test_url()
    schema = "merge1_" + uuid4().hex
    marker = "MERGE-1:" + uuid4().hex
    engine = create_engine(url, hide_parameters=True)
    gate = _CleanupGate()
    request.config.pluginmanager.register(gate)
    oid = None
    scoped = None
    try:
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f'COMMENT ON SCHEMA "{schema}" IS \'{marker}\''))
            oid = connection.scalar(text("SELECT oid FROM pg_catalog.pg_namespace WHERE nspname=:name"), {"name": schema})
        scoped_url = url.update_query_dict({"options": f"-csearch_path={schema},pg_catalog -clock_timeout=2s -cstatement_timeout=5s"})
        with monkeypatch.context() as env:
            env.setenv("FADIR_DATABASE_URL", scoped_url.render_as_string(hide_password=False))
            cfg = Config(str(ROOT / "alembic.ini"))
            cfg.set_main_option("script_location", str(ROOT / "migrations"))
            command.upgrade(cfg, "head")
        scoped = create_engine(scoped_url, hide_parameters=True)
        yield scoped
    finally:
        if scoped is not None:
            scoped.dispose()
        if oid is not None and gate.passed:
            with engine.begin() as connection:
                record = connection.execute(text("SELECT current_database(), n.oid, n.nspowner=(SELECT oid FROM pg_catalog.pg_roles WHERE rolname=current_user), pg_catalog.obj_description(n.oid, 'pg_namespace') FROM pg_catalog.pg_namespace n WHERE nspname=:schema"), {"schema": schema}).one_or_none()
                if record is None or tuple(record) != (url.database, oid, True, marker):
                    raise RuntimeError("Cleanup refused: schema ownership mismatch")
                if re.fullmatch(r"merge1_[0-9a-f]{32}", schema) is None:
                    raise RuntimeError("Cleanup refused: invalid schema")
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()
        request.config.pluginmanager.unregister(gate)


def _authority(workspace_id: int, user_id: int) -> RequestAuthority:
    return RequestAuthority(mode="user", user_id=user_id, workspace_id=workspace_id)


@pytest.mark.live
def test_merge_preview_confirm_preserves_rows_and_pairs_duplicates(database):
    with Session(database) as session, session.begin():
        user = User(workspace=Workspace())
        session.add(user)
        session.flush()
        issued = guest_access.issue(session, clock=lambda: datetime.now(timezone.utc))
        source_workspace = session.get(Workspace, issued.workspace_id)
        assert source_workspace is not None
        source = Portfolio(workspace_id=source_workspace.id, name="Guest")
        target = Portfolio(workspace_id=user.workspace.id, name="Target", base_currency="USD")
        session.add_all([source, target])
        session.flush()
        instrument = Instrument(ticker="MERGE", exchange="SYN", yf_symbol="MERGE", currency="USD", name="Synthetic")
        session.add(instrument)
        session.flush()

        def add(portfolio, *, fees, fx="30", trade_date=date(2026, 1, 1), fx_date=None, provider="manual", note="n"):
            row = Transaction(portfolio_id=portfolio.id, instrument_id=instrument.id, trade_date=trade_date, side=Side.BUY, quantity=Decimal("2"), price_native=Decimal("10"), fees_native=Decimal(fees), fx_rate_to_try=Decimal(fx), fx_rate_date=fx_date or trade_date, fx_provider=provider, note=note)
            session.add(row)
            session.flush()
            return row

        source_one = add(source, fees="1", note="one")
        source_two = add(source, fees="2", fx="31", note="two")
        add(target, fees="9", fx="31", fx_date=date(2026, 1, 2), provider="other", note="target-one")
        add(target, fees="2", fx="31", note="target-two")
        movable = add(source, fees="0", trade_date=date(2026, 2, 1), note="move")
        authority = _authority(user.workspace.id, user.id)
        plan = portfolio_merge.preview(session, authority=authority, guest_secret=issued.secret.get_secret_value(), source_portfolio_id=source.id, target_portfolio_id=target.id)
        assert len(plan.candidates) == 2
        assert plan.candidates[0].source.id == source_one.id
        assert {d.field for candidate in plan.candidates for d in candidate.differences} == {"fees_native", "fx_rate_to_try", "fx_rate_date", "fx_provider"}
        assert [row.id for row in plan.movable_source_rows] == [movable.id]
        result = portfolio_merge.confirm(session, authority=authority, guest_secret=issued.secret.get_secret_value(), source_portfolio_id=source.id, target_portfolio_id=target.id, revision_token=plan.revision_token, decisions=[{"source_transaction_id": source_one.id, "action": "keep"}, {"source_transaction_id": source_two.id, "action": "skip"}])
        assert result.moved_count == 2 and result.skipped_count == 1
        session.expire_all()
        assert session.scalar(select(Transaction.portfolio_id).where(Transaction.id == source_one.id)) == target.id
        assert session.scalar(select(Transaction.portfolio_id).where(Transaction.id == source_two.id)) == source.id
        assert session.scalar(select(Transaction.portfolio_id).where(Transaction.id == movable.id)) == target.id
        assert session.scalar(select(Portfolio.base_currency).where(Portfolio.id == target.id)) == "USD"
        preserved = session.get(Transaction, source_one.id)
        assert preserved.price_native == Decimal("10") and preserved.fx_rate_to_try == Decimal("30") and preserved.note == "one"
        assert session.get(Portfolio, source.id) is not None


@pytest.mark.live
def test_merge_rejects_stale_and_cross_workspace(database):
    with Session(database) as session, session.begin():
        user = User(workspace=Workspace()); other = User(workspace=Workspace())
        session.add_all([user, other]); session.flush()
        issued = guest_access.issue(session, clock=lambda: datetime.now(timezone.utc))
        source_workspace = session.get(Workspace, issued.workspace_id)
        assert source_workspace is not None
        source = Portfolio(workspace_id=source_workspace.id, name="Guest"); target = Portfolio(workspace_id=user.workspace.id, name="Target"); other_target = Portfolio(workspace_id=other.workspace.id, name="Other")
        session.add_all([source, target, other_target]); session.flush()
        instrument = Instrument(ticker="STALE", exchange="SYN", yf_symbol="STALE", currency="USD", name="Synthetic"); session.add(instrument); session.flush()
        row = Transaction(portfolio_id=source.id, instrument_id=instrument.id, trade_date=date(2026,1,1), side=Side.BUY, quantity=Decimal("1"), price_native=Decimal("1"), fees_native=Decimal("0"), fx_rate_to_try=Decimal("30"), fx_rate_date=date(2026,1,1), fx_provider="manual"); session.add(row); session.flush()
        authority = _authority(user.workspace.id, user.id)
        plan = portfolio_merge.preview(session, authority=authority, guest_secret=issued.secret.get_secret_value(), source_portfolio_id=source.id, target_portfolio_id=target.id)
        row.note = "changed"; session.flush()
        with pytest.raises(portfolio_merge.PortfolioMergeError):
            portfolio_merge.confirm(session, authority=authority, guest_secret=issued.secret.get_secret_value(), source_portfolio_id=source.id, target_portfolio_id=target.id, revision_token=plan.revision_token, decisions=[])
        with pytest.raises(portfolio_merge.PortfolioMergeError):
            portfolio_merge.preview(session, authority=authority, guest_secret=issued.secret.get_secret_value(), source_portfolio_id=source.id, target_portfolio_id=other_target.id)
