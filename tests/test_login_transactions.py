from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import CheckConstraint, UniqueConstraint, create_engine, inspect
from sqlalchemy.orm import Session

from app import models


def test_login_transaction_model_and_service_exist():
    from app.services import login_transactions

    assert hasattr(models, "LoginTransaction")
    assert callable(login_transactions.issue)
    assert callable(login_transactions.consume)
    assert callable(login_transactions.verify_pending)
    assert callable(login_transactions.consume_verified)
    assert "email" not in inspect(models.LoginTransaction).columns
    table = models.LoginTransaction.__table__
    assert {c.name for c in table.constraints if isinstance(c, UniqueConstraint)} == {
        "uq_login_transaction_state_digest"
    }
    assert {
        c.name for c in table.constraints if isinstance(c, CheckConstraint)
    } == {
        "ck_login_transaction_state_digest_length",
        "ck_login_transaction_nonce_digest_length",
        "ck_login_transaction_expiry_after_creation",
        "ck_login_transaction_verified_issuer_nonempty",
        "ck_login_transaction_verified_subject_nonempty",
    }


def test_login_transaction_rejects_sqlite_without_sql_or_commit():
    from app.services import login_transactions

    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    try:
        with Session(engine) as session, session.begin():
            with pytest.raises(login_transactions.LoginTransactionUnsupported):
                login_transactions.issue(
                    session, clock=lambda: datetime.now(timezone.utc)
                )
            assert session.get_transaction() is not None
    finally:
        engine.dispose()


def test_malformed_login_transaction_secrets_fail_closed():
    from app.services import login_transactions

    with pytest.raises(login_transactions.LoginTransactionInvalid) as error:
        login_transactions.consume(
            None, "not-a-state", "not-a-nonce", clock=lambda: datetime.now(timezone.utc)
        )
    assert str(error.value) == "login transaction rejected"
    assert error.value.__context__ is None


def test_consumed_verified_result_recovers_identity_for_later_transition():
    from app.services import login_transactions

    assert {"issuer", "subject"} <= set(
        login_transactions.ConsumedLoginTransaction.model_fields
    )
