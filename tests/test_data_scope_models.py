from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.db import make_engine


@pytest.fixture
def session(tmp_path):
    engine = make_engine(tmp_path / "data-scope.db")
    models.Base.metadata.create_all(engine)
    with Session(engine) as database_session:
        yield database_session
    engine.dispose()


def _domain_models():
    names = ("User", "Workspace", "Portfolio")
    missing = [name for name in names if not hasattr(models, name)]
    assert not missing, f"domain roots are absent: {', '.join(missing)}"
    return tuple(getattr(models, name) for name in names)


def test_domain_root_model_contract() -> None:
    User, Workspace, Portfolio = _domain_models()

    assert User.__tablename__ == "user"
    assert set(User.__table__.columns.keys()) == {"id", "created_at", "updated_at"}
    assert "email" not in User.__table__.columns

    assert Workspace.__tablename__ == "workspace"
    assert Workspace.__table__.c.user_id.nullable
    assert (
        next(iter(Workspace.__table__.c.user_id.foreign_keys)).ondelete == "CASCADE"
    )

    assert Portfolio.__tablename__ == "portfolio"
    assert not Portfolio.__table__.c.workspace_id.nullable
    assert (
        next(iter(Portfolio.__table__.c.workspace_id.foreign_keys)).ondelete
        == "CASCADE"
    )
    assert Portfolio.__table__.c.name.type.length == 128
    assert Portfolio.__table__.c.base_currency.type.length == 3
    assert {
        constraint.name for constraint in Portfolio.__table__.constraints
    } >= {
        "uq_portfolio_workspace_name",
        "ck_portfolio_base_currency_length",
    }


def test_one_user_controls_at_most_one_workspace(session) -> None:
    User, Workspace, _ = _domain_models()
    user = User(workspace=Workspace())
    session.add(user)
    session.commit()

    session.add(Workspace(user_id=user.id))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_multiple_guest_workspaces_can_exist(session) -> None:
    _, Workspace, _ = _domain_models()
    first = Workspace()
    second = Workspace()
    session.add_all([first, second])
    session.commit()

    assert first.id != second.id
    assert first.user_id is None
    assert second.user_id is None


def test_portfolio_names_are_unique_inside_each_workspace(session) -> None:
    _, Workspace, Portfolio = _domain_models()
    first_workspace = Workspace(
        portfolios=[Portfolio(name="Ana Portföy"), Portfolio(name="Uzun Vade")]
    )
    second_workspace = Workspace(portfolios=[Portfolio(name="Ana Portföy")])
    session.add_all([first_workspace, second_workspace])
    session.commit()

    assert len(first_workspace.portfolios) == 2
    assert len(second_workspace.portfolios) == 1

    session.add(Portfolio(workspace=first_workspace, name="Ana Portföy"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_base_currency_defaults_to_try(session) -> None:
    _, Workspace, Portfolio = _domain_models()
    portfolio = Portfolio(name="Ana Portföy")
    session.add(Workspace(portfolios=[portfolio]))
    session.commit()

    assert portfolio.base_currency == "TRY"


def test_user_delete_removes_workspace_and_portfolios(session) -> None:
    User, Workspace, Portfolio = _domain_models()
    workspace = Workspace(portfolios=[Portfolio(name="Ana Portföy")])
    user = User(workspace=workspace)
    session.add(user)
    session.commit()
    workspace_id = workspace.id
    portfolio_id = workspace.portfolios[0].id

    session.delete(user)
    session.commit()

    assert session.get(Workspace, workspace_id) is None
    assert session.get(Portfolio, portfolio_id) is None


def test_workspace_delete_removes_portfolios(session) -> None:
    _, Workspace, Portfolio = _domain_models()
    workspace = Workspace(portfolios=[Portfolio(name="Ana Portföy")])
    session.add(workspace)
    session.commit()
    portfolio_id = workspace.portfolios[0].id

    session.delete(workspace)
    session.commit()

    assert session.get(Portfolio, portfolio_id) is None
