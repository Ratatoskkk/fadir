"""Opt-in DB-6B proof with synthetic sources and owned PostgreSQL schemas."""

from contextlib import contextmanager
import re
from uuid import uuid4

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, event, pool, select, text

from app.models import Base
from app.services.private_migration import (
    MigrationOutcomeUnknown, MigrationPlan, MigrationStatus, run_private_migration,
)
from app.services.private_migration_adapters import (
    SQLiteMigrationSource, PostgresqlMigrationTarget,
)
from test_postgresql_migrations import _selected_test_url
from test_private_migration_adapters import (
    ROOT, TABLES, STAMP, DAY, synthetic_rows, synthetic_source,
)


def _drop_owned_schema(connection, schema, marker, schema_oid, database):
    if re.fullmatch(r"db6b_[0-9a-f]{32}", schema) is None:
        raise RuntimeError("Cleanup refused: invalid task schema")
    record = connection.execute(text(
        "SELECT current_database(), n.oid, "
        "n.nspowner = (SELECT oid FROM pg_catalog.pg_roles "
        "WHERE rolname = current_user), "
        "pg_catalog.obj_description(n.oid, 'pg_namespace') "
        "FROM pg_catalog.pg_namespace AS n WHERE n.nspname = :schema"
    ), {"schema": schema}).one_or_none()
    if record is None or tuple(record) != (database, schema_oid, True, marker):
        raise RuntimeError("Cleanup refused: task schema ownership mismatch")
    connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))


@contextmanager
def pg_target(monkeypatch):
    __tracebackhide__ = True
    url = _selected_test_url()
    schema = "db6b_" + uuid4().hex
    marker = "DB-6B:" + uuid4().hex
    engine = create_engine(url, poolclass=pool.NullPool, hide_parameters=True)
    scoped = None
    oid = None
    unknown = False
    try:
        with engine.begin() as connection:
            assert connection.scalar(text("SELECT current_database()")) == url.database
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f"COMMENT ON SCHEMA \"{schema}\" IS '{marker}'"))
            oid = connection.scalar(text(
                "SELECT oid FROM pg_catalog.pg_namespace WHERE nspname=:name"
            ), {"name": schema})
        scoped_url = url.update_query_dict({"options": f"-csearch_path={schema},pg_catalog"})
        with monkeypatch.context() as env:
            env.setenv("FADIR_DATABASE_URL", scoped_url.render_as_string(hide_password=False))
            config = Config(str(ROOT / "alembic.ini"))
            config.set_main_option("script_location", str(ROOT / "migrations"))
            command.upgrade(config, "head")
        scoped = create_engine(scoped_url, poolclass=pool.NullPool, hide_parameters=True)
        with scoped.begin() as connection:
            connection.execute(Base.metadata.tables["user"].insert(),
                               dict(id=1, created_at=STAMP, updated_at=STAMP))
            connection.execute(Base.metadata.tables["workspace"].insert(), [
                dict(id=1, user_id=1, created_at=STAMP, updated_at=STAMP),
                dict(id=2, user_id=None, created_at=STAMP, updated_at=STAMP),
            ])
            connection.execute(Base.metadata.tables["portfolio"].insert(), [
                dict(id=i, workspace_id=i, name="Synthetic", base_currency="TRY",
                     created_at=STAMP, updated_at=STAMP) for i in (1, 2)
            ])
        yield scoped
    except MigrationOutcomeUnknown:
        unknown = True
        raise
    finally:
        if scoped is not None:
            scoped.dispose()
        try:
            if oid is not None and not unknown:
                with engine.begin() as connection:
                    _drop_owned_schema(connection, schema, marker, oid, url.database)
                with engine.connect() as connection:
                    assert connection.scalar(text(
                        "SELECT count(*) FROM pg_catalog.pg_namespace WHERE nspname=:name"
                    ), {"name": schema}) == 0
        finally:
            engine.dispose()


class ObservedTarget:
    def __init__(self, connection):
        self.target = PostgresqlMigrationTarget(connection)
        self.transaction = None

    def begin(self):
        self.transaction = self.target.begin()
        return self.transaction


def target_rows(engine):
    with engine.connect() as connection:
        return tuple(
            {"table": name, **dict(row)}
            for name in TABLES
            for row in connection.execute(select(Base.metadata.tables[name]).order_by(
                *Base.metadata.tables[name].primary_key.columns
            )).mappings()
        )


def sequence_state(connection):
    return tuple(
        tuple(connection.execute(text(f'SELECT last_value, is_called FROM "{name}_id_seq"')).one())
        for name in TABLES if name != "snapshot"
    )


def assert_generated_ids(engine):
    with engine.begin() as connection:
        for name, rows in synthetic_rows().items():
            if name == "snapshot":
                continue
            row = {k: v for k, v in rows[-1].items() if k != "id"}
            if name == "instrument":
                row.update(ticker="NEW", yf_symbol="NEW")
            elif name == "price_cache":
                row["price_date"] = DAY.replace(day=3)
            elif name == "fx_cache":
                row["rate_date"] = DAY.replace(day=3)
            elif name == "corporate_action":
                row["action_date"] = DAY.replace(day=3)
            else:
                row["portfolio_id"] = 1
            table = Base.metadata.tables[name]
            generated = connection.scalar(table.insert().values(**row).returning(table.c.id))
            assert generated > max(r["id"] for r in rows)


@pytest.mark.live
@pytest.mark.parametrize("revision", ["0001_current_schema_baseline", "head"])
def test_real_transfer_repeatability_and_generated_ids(tmp_path, monkeypatch, revision):
    source_engine = synthetic_source(tmp_path, monkeypatch, revision)
    outcomes, copied = [], []
    signature = None
    try:
        with source_engine.connect() as source_connection:
            source_connection.exec_driver_sql("BEGIN")
            source = SQLiteMigrationSource(source_connection)
            before = (source.read_shared_rows(), source.read_private_rows())
            source_transaction = source_connection.get_transaction()
            for _ in range(3):
                with pg_target(monkeypatch) as engine:
                    with engine.connect() as connection:
                        target = ObservedTarget(connection)
                        result = run_private_migration(source, target,
                            MigrationPlan(1, 1, 2, signature))
                        assert result.status is MigrationStatus.PASSED
                        assert not connection.in_transaction()
                        signature = target.transaction.repeatability_signature()
                        assert not connection.in_transaction()
                        outcomes.append(result)
                    copied.append(target_rows(engine))
                    assert all(r["portfolio_id"] == 1 for r in copied[-1]
                               if r["table"] in ("transaction", "snapshot"))
                    assert all("portfolio_id" not in r for r in copied[-1]
                               if r["table"] not in ("transaction", "snapshot"))
                    assert_generated_ids(engine)
            assert outcomes[1] == outcomes[2]
            assert copied[0] == copied[1] == copied[2]
            assert (source.read_shared_rows(), source.read_private_rows()) == before
            assert source_connection.get_transaction() is source_transaction
            assert source_transaction.is_active
    finally:
        source_engine.dispose()


@pytest.mark.live
@pytest.mark.parametrize("mode", ["active", "nested", "autocommit", "raw_active", "closed", "invalidated"])
def test_target_rejects_unsafe_connection_without_caller_changes(monkeypatch, mode):
    with pg_target(monkeypatch) as engine:
        with engine.connect() as connection:
            if mode == "active":
                connection.begin()
            elif mode == "nested":
                connection.begin_nested()
            elif mode == "autocommit":
                connection.execution_options(isolation_level="AUTOCOMMIT")
            elif mode == "raw_active":
                connection.connection.driver_connection.execute("SELECT 1")
            elif mode == "closed":
                connection.close()
            else:
                connection.invalidate()
            transaction = connection.get_transaction()
            nested = connection.get_nested_transaction()
            with pytest.raises(ValueError):
                PostgresqlMigrationTarget(connection).begin()
            assert connection.get_transaction() is transaction
            assert connection.get_nested_transaction() is nested
            if transaction is not None:
                assert transaction.is_active
            if mode == "raw_active":
                assert connection.connection.driver_connection.info.transaction_status.name == "INTRANS"
                connection.connection.driver_connection.rollback()


FAILURES = [
    ("invalid", "INVALID_PRIVATE_ROW"),
    ("reference", "MISSING_SHARED_REFERENCE"),
    ("constraint", "TARGET_CONSTRAINT_CONFLICT"),
    ("source", "SOURCE_READ_FAILED"),
    ("shared", "TARGET_WRITE_FAILED_AFTER_SHARED"),
    ("private", "TARGET_WRITE_FAILED_AFTER_PRIVATE"),
    ("validation", "VALIDATION_FAILED"),
    ("repeatability", "REPEATABILITY_FAILED"),
    ("workspace", "VALIDATION_FAILED"),
]


@pytest.mark.live
@pytest.mark.parametrize(("failure", "code"), FAILURES)
def test_real_failure_rolls_back_rows_and_sequences(tmp_path, monkeypatch, failure, code):
    source_engine = synthetic_source(tmp_path, monkeypatch)
    try:
        with pg_target(monkeypatch) as engine:
            with engine.begin() as connection:
                sentinel = dict(synthetic_rows()["instrument"][-1], id=900,
                                ticker="SENTINEL", yf_symbol="SENTINEL")
                connection.execute(Base.metadata.tables["instrument"].insert(), sentinel)
                if failure == "constraint":
                    connection.execute(Base.metadata.tables["instrument"].insert(),
                                       synthetic_rows()["instrument"][-1])
                connection.exec_driver_sql('ALTER SEQUENCE "instrument_id_seq" RESTART WITH 1000')
            before = target_rows(engine)
            with engine.connect() as connection:
                sequences = sequence_state(connection)
            with source_engine.connect() as source_connection, engine.connect() as connection:
                source_connection.exec_driver_sql("BEGIN")
                source = SQLiteMigrationSource(source_connection)
                read_private = source.read_private_rows
                if failure in ("invalid", "reference"):
                    def changed_rows():
                        rows = [dict(r) for r in read_private()]
                        rows[0]["table" if failure == "invalid" else "instrument_id"] = (
                            "invalid" if failure == "invalid" else 999
                        )
                        return rows
                    monkeypatch.setattr(source, "read_private_rows", changed_rows)
                if failure == "source":
                    def fail_read(*args):
                        raise RuntimeError("Synthetic source failure")
                    event.listen(source_connection, "before_cursor_execute", fail_read)
                if failure in ("shared", "private"):
                    def fail_write(conn, cursor, statement, parameters, context, many):
                        table = "corporate_action" if failure == "shared" else "snapshot"
                        if context.isinsert and context.compiled.statement.table.name == table:
                            raise RuntimeError("Synthetic write failure")
                    event.listen(connection, "before_cursor_execute", fail_write)
                target = ObservedTarget(connection)
                if failure == "validation":
                    begin = target.begin
                    def altered_begin():
                        transaction = begin()
                        monkeypatch.setattr(transaction, "read_staged_private_rows", lambda: ())
                        return transaction
                    monkeypatch.setattr(target, "begin", altered_begin)
                plan = MigrationPlan(1, 2 if failure == "workspace" else 1, 2,
                                     "mismatch" if failure == "repeatability" else None)
                result = run_private_migration(source, target, plan)
                assert result.status is MigrationStatus.ROLLED_BACK
                assert result.failure_code == code
                assert not connection.in_transaction()
                assert target.transaction.has_inserted_rows() is False
                assert not connection.in_transaction()
            assert target_rows(engine) == before
            with engine.connect() as connection:
                assert sequence_state(connection) == sequences
    finally:
        source_engine.dispose()


@pytest.mark.live
def test_real_constraint_after_private_write_has_confirmed_rollback(tmp_path, monkeypatch):
    source_engine = synthetic_source(tmp_path, monkeypatch)
    try:
        with pg_target(monkeypatch) as engine:
            with engine.begin() as connection:
                connection.execute(Base.metadata.tables["snapshot"].insert(),
                                   dict(synthetic_rows()["snapshot"][0], portfolio_id=2))
            before = target_rows(engine)
            with source_engine.connect() as source_connection, engine.connect() as connection:
                source_connection.exec_driver_sql("BEGIN")
                result = run_private_migration(SQLiteMigrationSource(source_connection),
                    PostgresqlMigrationTarget(connection), MigrationPlan(1, 1, 2))
                assert result.failure_code == "TARGET_CONSTRAINT_CONFLICT"
                assert result.status is MigrationStatus.ROLLED_BACK
                assert not connection.in_transaction()
            assert target_rows(engine) == before
    finally:
        source_engine.dispose()


@pytest.mark.live
def test_sequence_already_ahead_stays_ahead(tmp_path, monkeypatch):
    source_engine = synthetic_source(tmp_path, monkeypatch)
    try:
        with pg_target(monkeypatch) as engine:
            with engine.begin() as connection:
                for name in TABLES:
                    if name != "snapshot":
                        connection.exec_driver_sql(f'ALTER SEQUENCE "{name}_id_seq" RESTART WITH 1000')
                        connection.scalar(text(f"SELECT nextval('{name}_id_seq')"))
            with source_engine.connect() as source_connection, engine.connect() as connection:
                source_connection.exec_driver_sql("BEGIN")
                result = run_private_migration(SQLiteMigrationSource(source_connection),
                    PostgresqlMigrationTarget(connection), MigrationPlan(1, 1, 2))
                assert result.status is MigrationStatus.PASSED
            with engine.connect() as connection:
                assert sequence_state(connection) == ((1001, False),) * 5
            assert_generated_ids(engine)
    finally:
        source_engine.dispose()


def test_cleanup_rejects_non_task_schema_before_sql():
    with pytest.raises(RuntimeError, match="invalid task schema"):
        _drop_owned_schema(None, "public", "marker", 1, "fadir_test")


@pytest.mark.live
def test_lost_commit_reply_requires_separate_durable_verification(tmp_path, monkeypatch):
    source_engine = synthetic_source(tmp_path, monkeypatch)
    try:
        with pg_target(monkeypatch) as engine:
            with source_engine.connect() as source_connection, engine.connect() as connection:
                source_connection.exec_driver_sql("BEGIN")
                source = SQLiteMigrationSource(source_connection)
                expected = (*source.read_shared_rows(), *(
                    {**row, "portfolio_id": 1} for row in source.read_private_rows()
                ))
                target = ObservedTarget(connection)
                begin = target.begin
                def lost_reply_begin():
                    transaction = begin()
                    commit = transaction.commit
                    def lost_reply():
                        commit()
                        raise RuntimeError("Synthetic lost commit reply")
                    def forbidden_rollback():
                        pytest.fail("The core attempted rollback after an unknown commit")
                    monkeypatch.setattr(transaction, "commit", lost_reply)
                    monkeypatch.setattr(transaction, "rollback", forbidden_rollback)
                    return transaction
                monkeypatch.setattr(target, "begin", lost_reply_begin)
                with pytest.raises(MigrationOutcomeUnknown) as caught:
                    run_private_migration(source, target, MigrationPlan(1, 1, 2))
                assert caught.value.__context__ is None
                assert caught.value.__cause__ is None
                assert "Synthetic lost" not in str(caught.value)
                try:
                    if target_rows(engine) != expected:
                        raise MigrationOutcomeUnknown()
                except Exception:
                    raise MigrationOutcomeUnknown() from None
                assert not connection.in_transaction()
    finally:
        source_engine.dispose()


@pytest.mark.live
def test_bounded_batches_preserve_complete_rows(tmp_path, monkeypatch):
    source_engine = synthetic_source(tmp_path, monkeypatch)
    try:
        with source_engine.begin() as connection:
            connection.execute(Base.metadata.tables["transaction"].insert(), [
                dict(synthetic_rows()["transaction"][0], id=value)
                for value in range(100, 555)
            ])
        with pg_target(monkeypatch) as engine:
            with source_engine.connect() as source_connection, engine.connect() as connection:
                source_connection.exec_driver_sql("BEGIN")
                source = SQLiteMigrationSource(source_connection)
                result = run_private_migration(source, PostgresqlMigrationTarget(connection),
                                               MigrationPlan(1, 1, 2))
                assert result.status is MigrationStatus.PASSED
                actual = [row for row in target_rows(engine) if row["table"] == "transaction"]
                expected = [{**row, "portfolio_id": 1} for row in source.read_private_rows()
                            if row["table"] == "transaction"]
                assert actual == expected
    finally:
        source_engine.dispose()


@pytest.mark.live
@pytest.mark.parametrize("workspace", [None, True, "1"])
def test_invalid_workspace_never_bypasses_scope(tmp_path, monkeypatch, workspace):
    source_engine = synthetic_source(tmp_path, monkeypatch)
    try:
        with pg_target(monkeypatch) as engine:
            with source_engine.connect() as source_connection, engine.connect() as connection:
                source_connection.exec_driver_sql("BEGIN")
                result = run_private_migration(SQLiteMigrationSource(source_connection),
                    PostgresqlMigrationTarget(connection), MigrationPlan(1, workspace, 2))
                assert result.status is MigrationStatus.ROLLED_BACK
                assert result.failure_code == "VALIDATION_FAILED"
            assert target_rows(engine) == ()
    finally:
        source_engine.dispose()


@pytest.mark.live
def test_success_preserves_unrelated_private_rows(tmp_path, monkeypatch):
    source_engine = synthetic_source(tmp_path, monkeypatch)
    try:
        with pg_target(monkeypatch) as engine:
            with engine.begin() as connection:
                connection.execute(Base.metadata.tables["instrument"].insert(),
                    dict(synthetic_rows()["instrument"][-1], id=900,
                         ticker="SENTINEL", yf_symbol="SENTINEL"))
                connection.execute(Base.metadata.tables["transaction"].insert(),
                    dict(synthetic_rows()["transaction"][-1], id=900,
                         instrument_id=900, portfolio_id=2))
                connection.execute(Base.metadata.tables["snapshot"].insert(),
                    dict(synthetic_rows()["snapshot"][-1], snapshot_date=DAY.replace(day=3),
                         portfolio_id=2))
            before = target_rows(engine)
            with source_engine.connect() as source_connection, engine.connect() as connection:
                source_connection.exec_driver_sql("BEGIN")
                result = run_private_migration(SQLiteMigrationSource(source_connection),
                    PostgresqlMigrationTarget(connection), MigrationPlan(1, 1, 2))
                assert result.status is MigrationStatus.PASSED
            after = target_rows(engine)
            assert all(row in after for row in before)
            assert_generated_ids(engine)
    finally:
        source_engine.dispose()


@pytest.mark.live
def test_unconfirmed_first_private_statement_has_no_false_progress(tmp_path, monkeypatch):
    source_engine = synthetic_source(tmp_path, monkeypatch)
    try:
        with pg_target(monkeypatch) as engine:
            with source_engine.connect() as source_connection, engine.connect() as connection:
                source_connection.exec_driver_sql("BEGIN")
                def fail(conn, cursor, statement, parameters, context, many):
                    if context.isinsert and context.compiled.statement.table.name == "transaction":
                        raise RuntimeError("Synthetic statement failure")
                event.listen(connection, "after_cursor_execute", fail)
                result = run_private_migration(SQLiteMigrationSource(source_connection),
                    PostgresqlMigrationTarget(connection), MigrationPlan(1, 1, 2))
                assert result.status is MigrationStatus.ROLLED_BACK
                assert result.failure_code == "TARGET_WRITE_FAILED"
                assert not connection.in_transaction()
            assert target_rows(engine) == ()
    finally:
        source_engine.dispose()


@pytest.mark.live
@pytest.mark.parametrize("phase", ["shared", "sequence"])
def test_typed_unknown_bypasses_automatic_rollback(tmp_path, monkeypatch, phase):
    source_engine = synthetic_source(tmp_path, monkeypatch)
    try:
        with pg_target(monkeypatch) as engine:
            with source_engine.connect() as source_connection, engine.connect() as connection:
                source_connection.exec_driver_sql("BEGIN")
                rollbacks = []
                event.listen(connection, "rollback", lambda conn: rollbacks.append(True))
                def fail(conn, cursor, statement, parameters, context, many):
                    if ((phase == "shared" and context.isinsert)
                            or (phase == "sequence" and statement.startswith("ALTER SEQUENCE"))):
                        raise MigrationOutcomeUnknown()
                event.listen(connection, "before_cursor_execute", fail)
                with pytest.raises(MigrationOutcomeUnknown):
                    run_private_migration(SQLiteMigrationSource(source_connection),
                        PostgresqlMigrationTarget(connection), MigrationPlan(1, 1, 2))
                assert rollbacks == []
                assert connection.in_transaction()
                event.remove(connection, "before_cursor_execute", fail)
                connection.rollback()
                assert rollbacks == [True]
                if target_rows(engine) != ():
                    raise MigrationOutcomeUnknown()
    finally:
        source_engine.dispose()
