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
from sqlalchemy.orm import Session

from app import models
from app.services import guest_access, google_login_transition, login_transactions
from app.services.google_identity import VerifiedGoogleIdentity
from test_postgresql_google_login_transition import _selected_url


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 9, 8, tzinfo=timezone.utc)


class _CleanupGate:
    def __init__(self) -> None:
        self.passed = False

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_makereport(self, item, call) -> None:
        if call.when == "call":
            self.passed = call.excinfo is None


@pytest.fixture
def database(monkeypatch, request):
    url = _selected_url()
    schema = "gmerge1_" + uuid4().hex
    marker = "GOOGLE-MERGE-BRIDGE-1:" + uuid4().hex
    engine = create_engine(url, hide_parameters=True)
    scoped = None
    oid = None
    gate = _CleanupGate()
    request.config.pluginmanager.register(gate)
    try:
        with engine.begin() as connection:
            assert connection.scalar(text("SELECT current_database()")) == url.database
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f'COMMENT ON SCHEMA "{schema}" IS \'{marker}\''))
            oid = connection.scalar(text("SELECT oid FROM pg_catalog.pg_namespace WHERE nspname=:name"), {"name": schema})
        scoped_url = url.update_query_dict({"options": f"-csearch_path={schema},pg_catalog -cstatement_timeout=5s"})
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
        if gate.passed and oid is not None:
            with engine.begin() as connection:
                record = connection.execute(text("SELECT current_database(), n.oid, n.nspowner=(SELECT oid FROM pg_catalog.pg_roles WHERE rolname=current_user), pg_catalog.obj_description(n.oid, 'pg_namespace') FROM pg_catalog.pg_namespace n WHERE nspname=:name"), {"name": schema}).one_or_none()
                if record is None or tuple(record) != (url.database, oid, True, marker):
                    raise RuntimeError("Cleanup refused: schema ownership mismatch")
                if re.fullmatch(r"gmerge1_[0-9a-f]{32}", schema) is None:
                    raise RuntimeError("Cleanup refused: invalid schema")
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()
        request.config.pluginmanager.unregister(gate)


def _verified(session: Session, subject: str):
    issued = login_transactions.issue(session, clock=lambda: NOW)
    login_transactions.verify_pending(
        session,
        issued.state,
        issued.nonce,
        VerifiedGoogleIdentity(issuer="https://accounts.google.com", subject=subject),
        clock=lambda: NOW,
    )
    return issued


@pytest.mark.live
def test_merge_existing_identity_issues_session_and_retains_guest(database):
    with Session(database) as session, session.begin():
        user = models.User(workspace=models.Workspace())
        session.add(user)
        session.flush()
        session.add(models.LoginIdentity(user_id=user.id, issuer="https://accounts.google.com", subject="existing"))
        guest = guest_access.issue(session, clock=lambda: NOW)
        source_portfolio = models.Portfolio(workspace_id=guest.workspace_id, name="Guest Portfolio")
        session.add(source_portfolio)
        session.flush()
        issued = _verified(session, "existing")
        result = google_login_transition.transition(
            session,
            SimpleNamespace(mode="guest", workspace_id=guest.workspace_id),
            issued.state.get_secret_value(),
            guest.secret.get_secret_value(),
            "merge",
            clock=lambda: NOW,
        )
        assert result.action == "merge"
        assert result.public_id and result.secret.get_secret_value()
        assert session.get(models.Portfolio, source_portfolio.id).workspace_id == guest.workspace_id
        assert session.get(models.Workspace, guest.workspace_id).user_id is None
        assert session.get(models.GuestAccess, guest.workspace_id).revoked_at is None
        assert session.scalar(select(models.LoginTransaction.consumed_at)) == NOW
        assert session.scalar(select(models.UserSession.user_id)) == user.id


@pytest.mark.live
def test_merge_rejects_new_identity_and_rename_without_consuming(database):
    with Session(database) as session, session.begin():
        user = models.User(workspace=models.Workspace())
        session.add(user)
        session.flush()
        guest = guest_access.issue(session, clock=lambda: NOW)
        issued = _verified(session, "new-identity")
        with pytest.raises(google_login_transition.GoogleLoginTransitionError):
            google_login_transition.transition(
                session,
                SimpleNamespace(mode="guest", workspace_id=guest.workspace_id),
                issued.state.get_secret_value(),
                guest.secret.get_secret_value(),
                "merge",
                rename="not allowed",
                clock=lambda: NOW,
            )
        assert session.scalar(select(models.LoginTransaction.consumed_at)) is None
        assert session.get(models.GuestAccess, guest.workspace_id).revoked_at is None
