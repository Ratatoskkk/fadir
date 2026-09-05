"""Engine and session management.

SQLite stores NUMERIC loosely, so a `Decimal` written to a NUMERIC column can come back
as a float unless we intervene. Everything monetary in this project must survive the
round trip as `Decimal` (SPEC §4: "Never use float for money"), so the connection is
configured to hand back strings that SQLAlchemy's Numeric type then decimalises.
"""

from __future__ import annotations

import sqlite3
import os
from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.config import DEFAULT_DB_PATH, get_settings
from app.models import Base

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def _register_decimal_adapters() -> None:
    """Store Decimal as TEXT-compatible NUMERIC and read it straight back."""
    sqlite3.register_adapter(Decimal, lambda d: str(d))


def _repository_heads() -> tuple[str, ...]:
    root = Path(__file__).resolve().parents[1]
    directory = ScriptDirectory.from_config(Config(str(root / "alembic.ini")))
    return tuple(directory.get_heads())


def _validated_url(value: str) -> str:
    if not value or not value.strip():
        raise RuntimeError("database configuration is invalid")
    try:
        url = make_url(value)
        if url.get_backend_name() == "postgresql" and url.drivername != "postgresql+psycopg":
            raise ValueError
        if url.get_backend_name() not in {"sqlite", "postgresql"}:
            raise ValueError
    except Exception:
        error = RuntimeError("database configuration is invalid")
    else:
        return value
    raise error


def resolve_database_target(
    *, database_url: str | None = None, db_path: Path | str | None = None
) -> str | Path:
    """Select one explicit URL or the existing local SQLite path."""
    if database_url is None and "FADIR_DATABASE_URL" in os.environ:
        database_url = os.environ["FADIR_DATABASE_URL"]
    if database_url is not None:
        return _validated_url(database_url)
    if db_path is None:
        db_path = os.environ.get("FADIR_DB_PATH") or DEFAULT_DB_PATH
    return db_path


def make_engine(db_path: Path | str) -> Engine:
    is_url = isinstance(db_path, str) and "://" in db_path
    engine_target = db_path if is_url else f"sqlite+pysqlite:///{db_path}"
    if is_url:
        engine_target = _validated_url(db_path)
    is_sqlite = not is_url or make_url(engine_target).get_backend_name() == "sqlite"

    if not is_sqlite:
        return create_engine(engine_target, future=True, hide_parameters=True)

    _register_decimal_adapters()
    engine = create_engine(
        engine_target,
        future=True,
        hide_parameters=True,
        # SQLite's Decimal handling emits a noisy warning; our adapter makes it correct.
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_conn, _record):  # type: ignore[no-untyped-def]
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA journal_mode=WAL")
        # With WAL, NORMAL stops fsyncing on every commit without risking corruption —
        # the exposure is losing the last commits to an OS crash, and every one of those
        # is a re-fetchable price or FX row. A refresh writes a row per symbol per day.
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.close()

    return engine


def get_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        settings = get_settings()
        _engine = make_engine(
            resolve_database_target(
                database_url=settings.database_url,
                db_path=settings.db_path,
            )
        )
        _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    return _engine


def get_sessionmaker() -> sessionmaker[Session]:
    get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


def init_db(engine: Engine | None = None) -> None:
    """Initialize a local SQLite database for tests and local development."""
    target = engine or get_engine()
    if target.dialect.name != "sqlite":
        raise RuntimeError("local database initialization requires SQLite")
    Base.metadata.create_all(target)


def check_migration_heads(engine: Engine | None = None) -> None:
    """Fail closed when the database revision differs from the repository."""
    try:
        target = engine or get_engine()
        with target.connect() as connection:
            current = tuple(MigrationContext.configure(connection).get_current_heads())
        expected = _repository_heads()
        if current != expected:
            raise RuntimeError("database migration head check failed")
    except Exception:
        error = RuntimeError("database migration head check failed")
    else:
        return
    raise error


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional session. Commits on success, rolls back on exception."""
    factory = get_sessionmaker()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Iterator[Session]:
    """FastAPI dependency."""
    factory = get_sessionmaker()
    session = factory()
    try:
        yield session
    finally:
        session.close()


def reset_engine() -> None:
    """Drop cached engine/sessionmaker. Used by tests switching DB paths."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
