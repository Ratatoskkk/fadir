from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import re
import secrets
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session

from app.services import login_transactions
from app.services.google_identity import VerifiedGoogleIdentity


ROOT = Path(__file__).resolve().parents[1]


def _selected_url() -> URL:
    if os.environ.get("FADIR_RUN_POSTGRESQL_LOGIN_TRANSACTION") != "1":
        pytest.skip("Set FADIR_RUN_POSTGRESQL_LOGIN_TRANSACTION=1 for approved live proof")
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


@pytest.mark.live
def test_postgresql_login_transaction_issue_consume_and_cleanup(monkeypatch) -> None:
    url = _selected_url()
    schema = "reqauth1_" + uuid4().hex
    marker = "LOGIN-TRANSACTION-1:" + uuid4().hex
    engine = create_engine(url, hide_parameters=True)
    schema_oid = None
    scoped_engine = None
    try:
        with engine.begin() as connection:
            assert connection.scalar(text("SELECT current_database()")) == url.database
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f'COMMENT ON SCHEMA "{schema}" IS \'{marker}\''))
            schema_oid = connection.scalar(
                text("SELECT oid FROM pg_catalog.pg_namespace WHERE nspname = :schema"),
                {"schema": schema},
            )
        scoped_url = url.update_query_dict({"options": f"-csearch_path={schema},pg_catalog"})
        monkeypatch.setenv("FADIR_DATABASE_URL", scoped_url.render_as_string(hide_password=False))
        config = Config(str(ROOT / "alembic.ini"))
        config.set_main_option("script_location", str(ROOT / "migrations"))
        command.upgrade(config, "head")
        scoped_engine = create_engine(scoped_url, hide_parameters=True)
        now = datetime(2026, 9, 8, tzinfo=timezone.utc)

        with Session(scoped_engine) as session, session.begin():
            issued = login_transactions.issue(session, clock=lambda: now)
            state = issued.state.get_secret_value()
            nonce = issued.nonce.get_secret_value()
            stored = session.execute(
                text("SELECT state_digest, nonce_digest FROM login_transaction")
            ).one()
            assert state.encode() not in stored and nonce.encode() not in stored
            consumed = login_transactions.consume(
                session, issued.state, issued.nonce, clock=lambda: now + timedelta(minutes=1)
            )
            assert consumed.expires_at == issued.expires_at
            with pytest.raises(login_transactions.LoginTransactionConsumed):
                login_transactions.consume(
                    session, state, nonce, clock=lambda: now + timedelta(minutes=2)
                )
            pending = login_transactions.issue(
                session, clock=lambda: now + timedelta(minutes=2)
            )
            identity = VerifiedGoogleIdentity(
                issuer="https://accounts.google.com", subject="synthetic-subject"
            )
            verified = login_transactions.verify_pending(
                session,
                pending.state,
                pending.nonce,
                identity,
                clock=lambda: now + timedelta(minutes=3),
            )
            assert verified.issuer == identity.issuer
            assert verified.subject == identity.subject
            repeated = login_transactions.verify_pending(
                session,
                pending.state,
                pending.nonce,
                identity,
                clock=lambda: now + timedelta(minutes=4),
            )
            assert repeated.verified_at == verified.verified_at
            with pytest.raises(login_transactions.LoginTransactionInvalid):
                login_transactions.verify_pending(
                    session,
                    pending.state,
                    pending.nonce,
                    VerifiedGoogleIdentity(
                        issuer=identity.issuer, subject="different-subject"
                    ),
                    clock=lambda: now + timedelta(minutes=4),
                )
            consumed_verified = login_transactions.consume_verified(
                session, pending.state, clock=lambda: now + timedelta(minutes=5)
            )
            assert consumed_verified.consumed_at == now + timedelta(minutes=5)
            assert consumed_verified.issuer == identity.issuer
            assert consumed_verified.subject == identity.subject
            with pytest.raises(login_transactions.LoginTransactionConsumed):
                login_transactions.consume_verified(
                    session, pending.state, clock=lambda: now + timedelta(minutes=6)
                )
            follow_up = login_transactions.issue(
                session, clock=lambda: now + timedelta(minutes=2)
            )
            assert follow_up.expires_at == now + timedelta(minutes=12)
            with pytest.raises(login_transactions.LoginTransactionInvalid):
                login_transactions.consume(
                    session,
                    follow_up.state,
                    secrets.token_urlsafe(32),
                    clock=lambda: now + timedelta(minutes=3),
                )

        with Session(scoped_engine) as session, session.begin():
            expired = login_transactions.issue(session, clock=lambda: now)
            with pytest.raises(login_transactions.LoginTransactionExpired):
                login_transactions.consume(
                    session,
                    expired.state,
                    expired.nonce,
                    clock=lambda: now + timedelta(minutes=11),
                )
            assert login_transactions.issue(session, clock=lambda: now).created_at == now
    finally:
        if scoped_engine is not None:
            scoped_engine.dispose()
        try:
            with engine.begin() as connection:
                record = connection.execute(
                    text(
                        "SELECT current_database(), n.oid, n.nspowner = "
                        "(SELECT oid FROM pg_catalog.pg_roles WHERE rolname = current_user), "
                        "pg_catalog.obj_description(n.oid, 'pg_namespace') "
                        "FROM pg_catalog.pg_namespace AS n WHERE n.nspname = :schema"
                    ),
                    {"schema": schema},
                ).one_or_none()
                if record != (url.database, schema_oid, True, marker):
                    raise RuntimeError("Cleanup refused: synthetic schema ownership mismatch")
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        finally:
            engine.dispose()


def test_postgresql_login_transaction_requires_opt_in(monkeypatch) -> None:
    monkeypatch.delenv("FADIR_RUN_POSTGRESQL_LOGIN_TRANSACTION", raising=False)
    with pytest.raises(pytest.skip.Exception):
        _selected_url()
