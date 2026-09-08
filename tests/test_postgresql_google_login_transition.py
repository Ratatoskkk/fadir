from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import re
from types import SimpleNamespace
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session

from app import models
from app.services import google_login_transition, guest_access, login_transactions
from app.services.google_identity import VerifiedGoogleIdentity


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 9, 8, tzinfo=timezone.utc)


def _selected_url() -> URL:
    if os.environ.get("FADIR_RUN_POSTGRESQL_GOOGLE_LOGIN_TRANSITION") != "1":
        pytest.skip("Set FADIR_RUN_POSTGRESQL_GOOGLE_LOGIN_TRANSITION=1 for approved live proof")
    raw = os.environ.get("FADIR_TEST_POSTGRESQL_URL")
    database = os.environ.get("FADIR_TEST_POSTGRESQL_DATABASE")
    if not raw or not database:
        raise ValueError("An explicit synthetic URL and database are required")
    url = make_url(raw)
    if url.drivername != "postgresql+psycopg" or url.database != database or url.query:
        raise ValueError("Select a matching synthetic PostgreSQL database without URL options")
    if re.fullmatch(r"fadir_test(?:_[a-z0-9_]+)?", database) is None:
        raise ValueError("Synthetic database selection is unsafe")
    return url


class _CleanupGate:
    def __init__(self) -> None:
        self.call_passed = False

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_makereport(self, item, call) -> None:
        if call.when == "call":
            self.call_passed = call.excinfo is None


@pytest.fixture
def database(monkeypatch, request):
    url = _selected_url()
    schema = "gtrans1_" + uuid4().hex
    marker = "GOOGLE-LOGIN-TRANSITION-1:" + uuid4().hex
    engine = create_engine(url, hide_parameters=True)
    scoped = None
    schema_oid = None
    gate = _CleanupGate()
    request.config.pluginmanager.register(gate)
    try:
        with engine.begin() as connection:
            assert connection.scalar(text("SELECT current_database()")) == url.database
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f'COMMENT ON SCHEMA "{schema}" IS \'{marker}\''))
            schema_oid = connection.scalar(
                text("SELECT oid FROM pg_catalog.pg_namespace WHERE nspname=:name"),
                {"name": schema},
            )
        scoped_url = url.update_query_dict(
            {"options": f"-csearch_path={schema},pg_catalog -cstatement_timeout=5s"}
        )
        with monkeypatch.context() as env:
            env.setenv("FADIR_DATABASE_URL", scoped_url.render_as_string(hide_password=False))
            config = Config(str(ROOT / "alembic.ini"))
            config.set_main_option("script_location", str(ROOT / "migrations"))
            command.upgrade(config, "head")
        scoped = create_engine(scoped_url, hide_parameters=True)
        yield scoped
    finally:
        if scoped is not None:
            scoped.dispose()
        if gate.call_passed and schema_oid is not None:
            with engine.begin() as connection:
                record = connection.execute(
                    text(
                        "SELECT current_database(), n.oid, "
                        "n.nspowner=(SELECT oid FROM pg_catalog.pg_roles WHERE rolname=current_user), "
                        "pg_catalog.obj_description(n.oid, 'pg_namespace') "
                        "FROM pg_catalog.pg_namespace n WHERE nspname=:name"
                    ),
                    {"name": schema},
                ).one_or_none()
                assert record == (url.database, schema_oid, True, marker)
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()
        request.config.pluginmanager.unregister(gate)


def _issue_verified(session: Session, subject: str = "synthetic-subject"):
    issued = login_transactions.issue(session, clock=lambda: NOW)
    identity = VerifiedGoogleIdentity(
        issuer="https://accounts.google.com", subject=subject
    )
    login_transactions.verify_pending(
        session, issued.state, issued.nonce, identity, clock=lambda: NOW
    )
    return issued


@pytest.mark.live
def test_claim_attaches_guest_and_issues_user_session(database):
    with Session(database) as session, session.begin():
        guest = guest_access.issue(session, clock=lambda: NOW)
        session.add(models.Portfolio(workspace_id=guest.workspace_id, name="Guest", base_currency="TRY"))
        session.flush()
        issued = _issue_verified(session)
        result = google_login_transition.transition(
            session,
            SimpleNamespace(mode="guest", workspace_id=guest.workspace_id),
            issued.state.get_secret_value(),
            guest.secret.get_secret_value(),
            "claim",
            clock=lambda: NOW,
        )
        assert result.action == "claim"
        assert result.public_id and result.secret.get_secret_value()
        user = session.execute(select(models.User)).scalar_one()
        assert session.execute(select(models.LoginIdentity)).scalar_one().subject == "synthetic-subject"
        assert session.execute(select(models.Workspace)).scalar_one().user_id == user.id
        assert session.execute(select(models.GuestAccess)).scalar_one().revoked_at == NOW


@pytest.mark.live
def test_transfer_moves_portfolios_without_rewriting_transactions(database):
    with Session(database) as session, session.begin():
        user = models.User(workspace=models.Workspace())
        session.add(user)
        session.flush()
        session.add(models.LoginIdentity(
            user_id=user.id, issuer="https://accounts.google.com", subject="existing-subject"
        ))
        target = models.Portfolio(workspace_id=user.workspace.id, name="Shared", base_currency="TRY")
        session.add(target)
        guest = guest_access.issue(session, clock=lambda: NOW)
        source = models.Portfolio(workspace_id=guest.workspace_id, name="Shared", base_currency="USD")
        session.add(source)
        session.flush()
        issued = _issue_verified(session, subject="existing-subject")
        result = google_login_transition.transition(
            session,
            SimpleNamespace(mode="guest", workspace_id=guest.workspace_id),
            issued.state.get_secret_value(), guest.secret.get_secret_value(), "transfer",
            rename="Imported", clock=lambda: NOW,
        )
        assert result.action == "transfer"
        assert session.get(models.Portfolio, source.id).workspace_id == user.workspace.id
        assert session.get(models.Portfolio, source.id).name == "Imported"


@pytest.mark.live
def test_invalid_transfer_preserves_pending_transaction_and_guest_data(database):
    with Session(database) as session, session.begin():
        user = models.User(workspace=models.Workspace())
        session.add(user)
        session.flush()
        session.add(models.LoginIdentity(
            user_id=user.id, issuer="https://accounts.google.com", subject="existing-subject"
        ))
        session.add(models.Portfolio(workspace_id=user.workspace.id, name="Shared", base_currency="TRY"))
        guest = guest_access.issue(session, clock=lambda: NOW)
        source = models.Portfolio(workspace_id=guest.workspace_id, name="Shared", base_currency="USD")
        session.add(source)
        session.flush()
        issued = _issue_verified(session, subject="existing-subject")
        with pytest.raises(google_login_transition.GoogleLoginTransitionError):
            google_login_transition.transition(
                session,
                SimpleNamespace(mode="guest", workspace_id=guest.workspace_id),
                issued.state.get_secret_value(), guest.secret.get_secret_value(), "transfer",
                clock=lambda: NOW,
            )
        row = session.execute(select(models.LoginTransaction)).scalar_one()
        assert row.consumed_at is None
        assert session.get(models.Portfolio, source.id).workspace_id == guest.workspace_id
