"""Adapt caller-owned SQLite and PostgreSQL connections to the migration core."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
import hashlib
import json

from sqlalchemy import inspect, select, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from app.models import Base, Portfolio
from app.services.private_migration import (
    MigrationOutcomeUnknown, TargetConstraintConflictError, TargetWriteError,
)


_SHARED = ("instrument", "price_cache", "fx_cache", "corporate_action")
_PRIVATE = ("transaction", "snapshot")
_TABLES = {name: Base.metadata.tables[name] for name in (*_SHARED, *_PRIVATE)}
_BATCH_SIZE = 200


def _batches(values):
    for start in range(0, len(values), _BATCH_SIZE):
        yield values[start:start + _BATCH_SIZE]


def _key(name):
    return next(iter(_TABLES[name].primary_key.columns))


class SQLiteMigrationSource:
    """Read legacy columns without changes to the caller's stable transaction."""

    def __init__(self, connection: Connection):
        self.connection = connection
        self._require_snapshot()

    def _require_snapshot(self):
        connection = self.connection
        if connection.closed or connection.invalidated:
            raise ValueError("The source must remain open and valid")
        if connection.dialect.name != "sqlite":
            raise ValueError("The source must use SQLite")
        # Legacy sqlite3 SELECT does not start a database transaction.
        if not connection.connection.driver_connection.in_transaction:
            raise ValueError("The caller must start a real SQLite snapshot transaction")

    def _read(self, names):
        self._require_snapshot()
        inspector = inspect(self.connection)
        rows = []
        for name in names:
            table = _TABLES[name]
            physical = {column["name"] for column in inspector.get_columns(name)}
            columns = [column for column in table.columns if column.name != "portfolio_id" and column.name in physical]
            for row in self.connection.execute(select(*columns).order_by(_key(name))).mappings():
                values = dict(row)
                for column in table.columns:
                    if column.name != "portfolio_id" and column.name not in values:
                        values[column.name] = None
                rows.append({"table": name, **values})
        return tuple(rows)

    def read_shared_rows(self):
        return self._read(_SHARED)

    def read_private_rows(self):
        return self._read(_PRIVATE)


class PostgresqlMigrationTarget:
    """Require an idle psycopg connection; leave caller work untouched."""

    def __init__(self, connection: Connection):
        self.connection = connection

    def begin(self):
        connection = self.connection
        if connection.closed or connection.invalidated:
            raise ValueError("The target must be open and valid")
        if (connection.dialect.name, connection.dialect.driver) != ("postgresql", "psycopg"):
            raise ValueError("The target must use PostgreSQL with psycopg")
        if connection.in_transaction() or connection.in_nested_transaction():
            raise ValueError("The target must have no caller transaction")
        driver = connection.connection.driver_connection
        if driver.autocommit or driver.info.transaction_status.name != "IDLE":
            raise ValueError("The target must be idle without autocommit")
        return _TargetTransaction(connection)


def _canonical_value(value):
    if value is None:
        return ["null"]
    if isinstance(value, Enum):
        return ["enum", type(value).__name__, value.value]
    if isinstance(value, Decimal):
        return ["decimal", str(value)]
    if isinstance(value, datetime):
        return ["datetime", value.isoformat(timespec="microseconds")]
    if isinstance(value, date):
        return ["date", value.isoformat()]
    if type(value) is bool:
        return ["bool", value]
    if type(value) is int:
        return ["int", str(value)]
    if type(value) is str:
        return ["text", value]
    raise ValueError("Unsupported migration value type")


class _TargetTransaction:
    def __init__(self, connection):
        self.connection = connection
        self.transaction = connection.begin()
        self.baseline = {name: {} for name in _TABLES}
        self.inserted = {name: [] for name in _TABLES}
        self.state = "active"

    def _read_keys(self, name, keys, workspace_id=None):
        table = _TABLES[name]
        rows = []
        for batch in _batches(sorted(set(keys))):
            statement = select(table).where(_key(name).in_(batch))
            if workspace_id is not None:
                statement = statement.join(
                    Portfolio.__table__, table.c.portfolio_id == Portfolio.id
                ).where(Portfolio.workspace_id == workspace_id)
            rows.extend(dict(row) for row in self.connection.execute(
                statement.order_by(_key(name))
            ).mappings())
        return rows

    def _write(self, rows, allowed):
        if self.state != "active":
            raise ValueError("The target transaction is not active")
        private_statement_pending = False
        try:
            grouped = {name: [] for name in allowed}
            for row in rows:
                name = row.get("table")
                if type(name) is not str or name not in grouped:
                    raise ValueError("Invalid migration table")
                values = {key: value for key, value in row.items() if key != "table"}
                if set(values) != set(_TABLES[name].columns.keys()):
                    raise ValueError("The migration row must contain every target column")
                grouped[name].append(values)
            for name, values in grouped.items():
                key = _key(name).name
                for batch in _batches(values):
                    keys = [row[key] for row in batch]
                    unseen = [value for value in keys if value not in self.baseline[name]]
                    occupied = {row[key]: row for row in self._read_keys(name, unseen)}
                    self.baseline[name].update((value, occupied.get(value)) for value in unseen)
                    private_statement_pending = name in _PRIVATE
                    self.connection.execute(_TABLES[name].insert().values(batch))
                    self.inserted[name].extend(keys)
                    private_statement_pending = False
        except MigrationOutcomeUnknown:
            raise
        except IntegrityError:
            raise TargetConstraintConflictError("Target constraint conflict") from None
        except Exception:
            if private_statement_pending and not any(self.inserted[name] for name in _PRIVATE):
                raise RuntimeError("Target write progress is unconfirmed") from None
            raise TargetWriteError(
                private_rows_written=any(self.inserted[name] for name in _PRIVATE)
            ) from None

    def write_shared_rows(self, rows: Sequence[Mapping[str, object]]):
        self._write(rows, _SHARED)

    def write_private_rows(self, rows: Sequence[Mapping[str, object]]):
        self._write(rows, _PRIVATE)
        try:
            self._restart_sequences()
            self.signature = self.repeatability_signature()
        except MigrationOutcomeUnknown:
            raise
        except IntegrityError:
            raise TargetConstraintConflictError("Target constraint conflict") from None
        except Exception:
            raise TargetWriteError(
                private_rows_written=any(self.inserted[name] for name in _PRIVATE)
            ) from None

    def _restart_sequences(self):
        quote = self.connection.dialect.identifier_preparer.quote_identifier
        for name, table in _TABLES.items():
            if name == "snapshot" or not self.inserted[name]:
                continue
            sequence = self.connection.execute(text(
                "SELECT n.nspname, c.relname, s.seqmin, s.seqmax, s.seqincrement, s.seqcycle "
                "FROM pg_catalog.pg_sequence s "
                "JOIN pg_catalog.pg_class c ON c.oid=s.seqrelid "
                "JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace "
                "WHERE s.seqrelid=pg_catalog.pg_get_serial_sequence(:table, 'id')::regclass"
            ), {"table": quote(name)}).one()
            schema, sequence_name, minimum, maximum, increment, cycle = sequence
            if increment != 1 or cycle:
                raise ValueError("The target sequence must be ascending without a cycle")
            qualified = f"{quote(schema)}.{quote(sequence_name)}"
            last, called = self.connection.execute(text(
                f"SELECT last_value, is_called FROM {qualified}"
            )).one()
            highest = self.connection.scalar(select(table.c.id).order_by(table.c.id.desc()).limit(1))
            restart = max(minimum, last + int(called), (highest or 0) + 1)
            if restart > maximum:
                raise ValueError("The target sequence has no available identifier")
            # PostgreSQL RESTART rolls back with the row writes; setval does not.
            self.connection.execute(text(f"ALTER SEQUENCE {qualified} RESTART WITH {restart}"))

    def _read_staged(self, names, workspace_id=None):
        return tuple(
            {"table": name, **row}
            for name in names
            for row in self._read_keys(name, self.inserted[name], workspace_id)
        )

    def read_staged_shared_rows(self):
        return self._read_staged(_SHARED)

    def read_staged_private_rows(self):
        return self._read_staged(_PRIVATE)

    def read_private_rows_for_workspace(self, workspace_id):
        if type(workspace_id) is not int or workspace_id <= 0:
            raise ValueError("The Workspace identifier must be a positive integer")
        return self._read_staged(_PRIVATE, workspace_id)

    def repeatability_signature(self):
        if self.state == "committed":
            return self.signature
        rows = self._read_staged(_TABLES)
        canonical = [
            [row["table"], [[column.name, _canonical_value(row[column.name])]
                            for column in _TABLES[row["table"]].columns]]
            for row in rows
        ]
        encoded = json.dumps(["fadir-migration-v1", canonical],
                             ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def has_inserted_rows(self):
        if (self.state != "rolled_back" or self.connection.closed
                or self.connection.invalidated or self.connection.in_transaction()):
            raise MigrationOutcomeUnknown()
        with self.connection.begin() as verification:
            try:
                for name, baseline in self.baseline.items():
                    key = _key(name).name
                    actual = {row[key]: row for row in self._read_keys(name, list(baseline))}
                    if any(actual.get(value) != previous for value, previous in baseline.items()):
                        return True
                return False
            finally:
                verification.rollback()

    def commit(self):
        self.state = "unknown"
        self.transaction.commit()
        self.state = "committed"

    def rollback(self):
        if self.state != "active":
            raise MigrationOutcomeUnknown()
        self.state = "unknown"
        self.transaction.rollback()
        self.state = "rolled_back"
