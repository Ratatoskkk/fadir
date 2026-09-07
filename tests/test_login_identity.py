from __future__ import annotations

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app import models


def test_login_identity_model_supports_two_identities_and_no_email(tmp_path):
    from app.db import make_engine
    from sqlalchemy.orm import Session

    engine = make_engine(tmp_path / "login-identity.db")
    models.Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            user = models.User()
            user.login_identities.extend(
                [
                    models.LoginIdentity(
                        issuer="https://accounts.google.com", subject="sub-a"
                    ),
                    models.LoginIdentity(
                        issuer="https://accounts.google.com", subject="sub-b"
                    ),
                ]
            )
            session.add(user)
            session.commit()
            assert len(user.login_identities) == 2
            assert "email" not in inspect(models.LoginIdentity).columns
    finally:
        engine.dispose()


def test_duplicate_issuer_subject_and_empty_claims_fail(tmp_path):
    from app.db import make_engine
    from sqlalchemy.orm import Session

    engine = make_engine(tmp_path / "login-identity-constraints.db")
    models.Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            user = models.User()
            user.login_identities.append(
                models.LoginIdentity(issuer="https://accounts.google.com", subject="sub-a")
            )
            session.add(user)
            session.commit()
            session.add(
                models.LoginIdentity(
                    issuer="https://accounts.google.com", subject="sub-a", user=user
                )
            )
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()

            session.add(models.LoginIdentity(issuer="", subject="sub-c", user=user))
            with pytest.raises(IntegrityError):
                session.commit()
    finally:
        engine.dispose()
