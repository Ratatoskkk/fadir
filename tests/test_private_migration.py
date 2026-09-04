from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum
from hashlib import sha256
import traceback
from typing import Mapping, Sequence, cast

import pytest

from app.services import private_migration as migration
from app.services.private_migration import (
    VALIDATION_CODES,
    MigrationPlan,
    MigrationResult,
    MigrationStatus,
    TargetConstraintConflictError,
    TargetState,
    TargetWriteError,
    ValidationState,
    run_private_migration,
)


class SyntheticSide(str, Enum):
    BUY = "BUY"


SYNTHETIC_SHARED_ROWS = (
    {"table": "instrument", "id": 10, "ticker": "SYN"},
    {
        "table": "price_cache",
        "id": 20,
        "instrument_id": 10,
        "close_native": Decimal("12.34000000"),
    },
    {
        "table": "fx_cache",
        "id": 21,
        "base": "USD",
        "quote": "TRY",
        "rate": Decimal("40.1000000000"),
        "rate_date": date(2026, 1, 2),
    },
    {
        "table": "corporate_action",
        "id": 22,
        "instrument_id": 10,
        "kind": "SPLIT",
        "ratio": Decimal("2.0000000000"),
    },
)

SYNTHETIC_PRIVATE_ROWS = (
    {
        "table": "transaction",
        "id": 30,
        "instrument_id": 10,
        "trade_date": date(2026, 1, 2),
        "side": SyntheticSide.BUY,
        "quantity": Decimal("2.50000000"),
        "note": "synthetic-private-text",
        "portfolio_id": None,
    },
    {
        "table": "snapshot",
        "snapshot_date": date(2026, 1, 3),
        "payload_json": "synthetic-private-payload",
        "optional_value": None,
        "portfolio_id": None,
    },
)


def assigned_private_rows(portfolio_id: int = 9001) -> tuple[dict[str, object], ...]:
    return tuple(
        {**row, "portfolio_id": portfolio_id} for row in SYNTHETIC_PRIVATE_ROWS
    )


def state_signature(
    shared_rows: Sequence[Mapping[str, object]],
    private_rows: Sequence[Mapping[str, object]],
) -> str:
    state = (tuple(map(dict, shared_rows)), tuple(map(dict, private_rows)))
    return sha256(repr(state).encode("utf-8")).hexdigest()


def migration_plan(*, expected_signature: str | None = None) -> MigrationPlan:
    return MigrationPlan(
        portfolio_id=9001,
        workspace_id=101,
        denied_workspace_id=202,
        expected_repeatability_signature=expected_signature,
    )


class SyntheticSource:
    def __init__(
        self,
        *,
        shared_rows: Sequence[Mapping[str, object]] = SYNTHETIC_SHARED_ROWS,
        private_rows: Sequence[Mapping[str, object]] = SYNTHETIC_PRIVATE_ROWS,
        fail_private_read: bool = False,
    ) -> None:
        self._shared_rows = shared_rows
        self._private_rows = private_rows
        self._fail_private_read = fail_private_read

    def read_shared_rows(self) -> Sequence[Mapping[str, object]]:
        return self._shared_rows

    def read_private_rows(self) -> Sequence[Mapping[str, object]]:
        if self._fail_private_read:
            raise RuntimeError("planned synthetic source failure")
        return self._private_rows


class SyntheticTransaction:
    def __init__(self, target: SyntheticTarget) -> None:
        self._target = target
        self._shared_rows: list[dict[str, object]] = []
        self._private_rows: list[dict[str, object]] = []

    def write_shared_rows(
        self, rows: Sequence[Mapping[str, object]]
    ) -> None:
        self._target.shared_write_calls += 1
        self._shared_rows.extend(dict(row) for row in rows)

    def write_private_rows(
        self, rows: Sequence[Mapping[str, object]]
    ) -> None:
        self._target.private_write_calls += 1
        if self._target.failure_mode == "constraint":
            raise TargetConstraintConflictError
        if self._target.failure_mode == "write_after_shared":
            raise TargetWriteError(private_rows_written=False)
        for row in rows:
            staged_row = dict(row)
            if (
                self._target.failure_mode == "validation_mismatch"
                and staged_row["table"] == "transaction"
            ):
                staged_row["note"] = "changed-synthetic-text"
            if (
                self._target.failure_mode == "decimal_scale_mismatch"
                and staged_row["table"] == "transaction"
            ):
                staged_row["quantity"] = Decimal("2.5")
            self._private_rows.append(staged_row)
            if self._target.failure_mode == "write_after_private":
                raise TargetWriteError(private_rows_written=True)

    def read_staged_shared_rows(self) -> Sequence[Mapping[str, object]]:
        self._target.staged_shared_reads += 1
        return tuple(map(dict, self._shared_rows))

    def read_staged_private_rows(self) -> Sequence[Mapping[str, object]]:
        self._target.staged_private_reads += 1
        return tuple(map(dict, self._private_rows))

    def read_private_rows_for_workspace(
        self, workspace_id: int
    ) -> Sequence[Mapping[str, object]]:
        self._target.workspace_scope_reads += 1
        return tuple(
            dict(row)
            for row in self._private_rows
            if self._target.portfolio_workspaces.get(cast(int, row["portfolio_id"]))
            == workspace_id
        )

    def repeatability_signature(self) -> str:
        self._target.repeatability_reads += 1
        return state_signature(self._shared_rows, self._private_rows)

    def has_inserted_rows(self) -> bool:
        return bool(
            self._shared_rows
            or self._private_rows
            or self._target.shared_rows
            or self._target.private_rows
        )

    def commit(self) -> None:
        self._target.shared_rows = list(map(dict, self._shared_rows))
        self._target.private_rows = list(map(dict, self._private_rows))
        self._target.transaction_state = TargetState.COMMITTED

    def rollback(self) -> None:
        self._target.rollback_calls += 1
        self._shared_rows.clear()
        self._private_rows.clear()
        self._target.shared_rows = []
        self._target.private_rows = []
        self._target.transaction_state = TargetState.ROLLED_BACK


class SyntheticTarget:
    def __init__(
        self,
        *,
        failure_mode: str | None = None,
        portfolio_workspace_id: int = 101,
    ) -> None:
        self.failure_mode = failure_mode
        self.begin_calls = 0
        self.shared_write_calls = 0
        self.private_write_calls = 0
        self.rollback_calls = 0
        self.staged_shared_reads = 0
        self.staged_private_reads = 0
        self.workspace_scope_reads = 0
        self.repeatability_reads = 0
        self.portfolio_workspaces = {9001: portfolio_workspace_id}
        self.shared_rows: list[dict[str, object]] = []
        self.private_rows: list[dict[str, object]] = []
        self.transaction_state: TargetState | None = None
        self.transaction: SyntheticTransaction | None = None

    def begin(self) -> SyntheticTransaction:
        self.begin_calls += 1
        self.transaction = SyntheticTransaction(self)
        return self.transaction


def result_states(result: MigrationResult) -> dict[str, ValidationState]:
    return {item.code: item.state for item in result.validation_results}


def test_success_without_a_baseline_does_not_claim_repeatability() -> None:
    target = SyntheticTarget()

    result = run_private_migration(SyntheticSource(), target, migration_plan())

    states = result_states(result)
    assert result.status is MigrationStatus.PASSED
    assert result.target_state is TargetState.COMMITTED
    assert result.failure_code is None
    assert target.begin_calls == 1
    assert target.shared_rows == list(SYNTHETIC_SHARED_ROWS)
    assert {row["table"] for row in target.shared_rows} == {
        "instrument",
        "price_cache",
        "fx_cache",
        "corporate_action",
    }
    assert all("portfolio_id" not in row for row in target.shared_rows)
    assert [row["portfolio_id"] for row in target.private_rows] == [9001, 9001]
    assert target.private_rows == list(assigned_private_rows())
    assert target.staged_shared_reads > 0
    assert target.staged_private_reads > 0
    assert target.workspace_scope_reads == 2
    assert target.repeatability_reads == 0
    assert all(states[code] is ValidationState.PASSED for code in VALIDATION_CODES[:5])
    assert states["REPEATABILITY"] is ValidationState.NOT_RUN
    assert states["ROLLBACK"] is ValidationState.NOT_RUN
    assert states["PARTIAL_TARGET_STATE"] is ValidationState.NOT_RUN


def test_two_fresh_targets_produce_equal_results_and_rows() -> None:
    baseline_target = SyntheticTarget()
    first_target = SyntheticTarget()
    second_target = SyntheticTarget()

    baseline_result = run_private_migration(
        SyntheticSource(), baseline_target, migration_plan()
    )
    baseline_signature = state_signature(
        baseline_target.shared_rows,
        baseline_target.private_rows,
    )
    first_result = run_private_migration(
        SyntheticSource(),
        first_target,
        migration_plan(expected_signature=baseline_signature),
    )
    second_result = run_private_migration(
        SyntheticSource(),
        second_target,
        migration_plan(expected_signature=baseline_signature),
    )

    assert baseline_result.status is MigrationStatus.PASSED
    assert first_result == second_result
    assert result_states(first_result)["REPEATABILITY"] is ValidationState.PASSED
    assert first_target.shared_rows == second_target.shared_rows
    assert first_target.private_rows == second_target.private_rows


def test_wrong_workspace_state_fails_validation_and_rolls_back() -> None:
    target = SyntheticTarget(portfolio_workspace_id=303)

    result = run_private_migration(SyntheticSource(), target, migration_plan())

    assert result.failure_code == "VALIDATION_FAILED"
    assert result_states(result)["PRIVATE_OWNERSHIP"] is ValidationState.FAILED
    assert_rolled_back_without_rows(result, target)


def test_decimal_scale_only_mismatch_fails_validation_and_rolls_back() -> None:
    target = SyntheticTarget(failure_mode="decimal_scale_mismatch")

    result = run_private_migration(SyntheticSource(), target, migration_plan())

    states = result_states(result)
    assert states["VALUE_FIDELITY"] is ValidationState.PASSED
    assert states["DECIMAL_FIDELITY"] is ValidationState.FAILED
    assert result.failure_code == "VALIDATION_FAILED"
    assert_rolled_back_without_rows(result, target)


@pytest.mark.parametrize("invalid_id", [None, 0, -1, True, "9001"])
def test_invalid_portfolio_identifier_stops_before_a_target_write(
    invalid_id: object,
) -> None:
    target = SyntheticTarget()
    plan = MigrationPlan(
        portfolio_id=cast(int, invalid_id),
        workspace_id=101,
        denied_workspace_id=202,
        expected_repeatability_signature=None,
    )

    result = run_private_migration(SyntheticSource(), target, plan)

    assert result.failure_code == "INVALID_PORTFOLIO_ID"
    assert target.shared_write_calls == 0
    assert target.private_write_calls == 0
    assert_rolled_back_without_rows(result, target)


@pytest.mark.parametrize(
    "private_row",
    [
        {"table": []},
        {},
        {"table": None},
        {"table": {}},
        {"table": set()},
        {"table": 1},
        {"table": True},
        {"table": b"transaction"},
    ],
    ids=("list", "missing", "null", "dict", "set", "integer", "boolean", "bytes"),
)
def test_malformed_private_table_rolls_back_shared_rows(
    private_row: Mapping[str, object],
) -> None:
    target = SyntheticTarget()
    source = SyntheticSource(private_rows=(private_row,))

    try:
        result = run_private_migration(source, target, migration_plan())
    except TypeError as error:
        assert target.transaction is not None
        error.add_note(
            f"rollback_calls={target.rollback_calls}; "
            f"shared_rows_staged={bool(target.transaction.read_staged_shared_rows())}"
        )
        raise

    assert result.failure_code == "INVALID_PRIVATE_ROW"
    assert target.shared_write_calls == 1
    assert target.private_write_calls == 0
    assert_rolled_back_without_rows(result, target)


@pytest.mark.parametrize(
    "reference", [[], {}, set(), None, True, "10"],
    ids=("list", "dict", "set", "null", "boolean", "text"),
)
@pytest.mark.parametrize("location", ["shared-instrument", "private-reference"])
def test_malformed_instrument_identifier_rolls_back_shared_rows(
    reference: object, location: str,
) -> None:
    shared_rows = list(SYNTHETIC_SHARED_ROWS)
    private_rows = list(SYNTHETIC_PRIVATE_ROWS)
    if location == "shared-instrument":
        shared_rows[0] = {**shared_rows[0], "id": reference}
    else:
        private_rows[0] = {**private_rows[0], "instrument_id": reference}
    target = SyntheticTarget()

    result = run_private_migration(
        SyntheticSource(shared_rows=shared_rows, private_rows=private_rows),
        target,
        migration_plan(),
    )

    assert result.failure_code == "MISSING_SHARED_REFERENCE"
    assert target.shared_write_calls == 1
    assert target.private_write_calls == 0
    assert_rolled_back_without_rows(result, target)


def rollback_case(case: str) -> tuple[SyntheticSource, SyntheticTarget, MigrationPlan, str]:
    if case == "invalid-private-row":
        invalid_rows = ({"table": "unmatched", "id": 31},)
        return (
            SyntheticSource(private_rows=invalid_rows),
            SyntheticTarget(),
            migration_plan(),
            "INVALID_PRIVATE_ROW",
        )
    if case == "missing-shared-reference":
        missing_reference = (
            {**SYNTHETIC_PRIVATE_ROWS[0], "instrument_id": 999},
            SYNTHETIC_PRIVATE_ROWS[1],
        )
        return (
            SyntheticSource(private_rows=missing_reference),
            SyntheticTarget(),
            migration_plan(),
            "MISSING_SHARED_REFERENCE",
        )
    if case == "target-constraint-conflict":
        return (
            SyntheticSource(),
            SyntheticTarget(failure_mode="constraint"),
            migration_plan(),
            "TARGET_CONSTRAINT_CONFLICT",
        )
    if case == "source-read-failure":
        return (
            SyntheticSource(fail_private_read=True),
            SyntheticTarget(),
            migration_plan(),
            "SOURCE_READ_FAILED",
        )
    if case == "target-write-after-shared":
        return (
            SyntheticSource(),
            SyntheticTarget(failure_mode="write_after_shared"),
            migration_plan(),
            "TARGET_WRITE_FAILED_AFTER_SHARED",
        )
    if case == "target-write-after-private":
        return (
            SyntheticSource(),
            SyntheticTarget(failure_mode="write_after_private"),
            migration_plan(),
            "TARGET_WRITE_FAILED_AFTER_PRIVATE",
        )
    if case == "validation-mismatch":
        return (
            SyntheticSource(),
            SyntheticTarget(failure_mode="validation_mismatch"),
            migration_plan(),
            "VALIDATION_FAILED",
        )
    if case == "repeatability-mismatch":
        baseline_target = SyntheticTarget()
        baseline_result = run_private_migration(
            SyntheticSource(), baseline_target, migration_plan()
        )
        assert baseline_result.status is MigrationStatus.PASSED
        signature = state_signature(
            baseline_target.shared_rows,
            baseline_target.private_rows,
        )
        different_rows = (
            {**SYNTHETIC_PRIVATE_ROWS[0], "quantity": Decimal("9")},
            SYNTHETIC_PRIVATE_ROWS[1],
        )
        return (
            SyntheticSource(private_rows=different_rows),
            SyntheticTarget(),
            migration_plan(expected_signature=signature),
            "REPEATABILITY_FAILED",
        )
    raise AssertionError(case)


@pytest.mark.parametrize(
    "case",
    (
        "invalid-private-row",
        "missing-shared-reference",
        "target-constraint-conflict",
        "source-read-failure",
        "target-write-after-shared",
        "target-write-after-private",
        "validation-mismatch",
        "repeatability-mismatch",
    ),
)
def test_each_planned_failure_rolls_back_all_staged_rows(case: str) -> None:
    source, target, plan, expected_code = rollback_case(case)

    result = run_private_migration(source, target, plan)

    assert result.failure_code == expected_code
    assert_rolled_back_without_rows(result, target)
    states = result_states(result)
    assert states["ROLLBACK"] is ValidationState.PASSED
    assert states["PARTIAL_TARGET_STATE"] is ValidationState.PASSED


def assert_rolled_back_without_rows(
    result: MigrationResult, target: SyntheticTarget
) -> None:
    assert result.status is MigrationStatus.ROLLED_BACK
    assert result.target_state is TargetState.ROLLED_BACK
    assert target.begin_calls == 1
    assert target.rollback_calls == 1
    assert target.transaction_state is TargetState.ROLLED_BACK
    assert target.shared_rows == []
    assert target.private_rows == []
    assert target.transaction is not None
    assert target.transaction.read_staged_shared_rows() == ()
    assert target.transaction.read_staged_private_rows() == ()
    assert not target.transaction.has_inserted_rows()


def test_result_contains_only_control_evidence() -> None:
    result = run_private_migration(
        SyntheticSource(), SyntheticTarget(), migration_plan()
    )

    assert isinstance(result, MigrationResult)
    assert set(result.__dataclass_fields__) == {
        "status",
        "validation_results",
        "failure_code",
        "target_state",
    }
    result_text = repr(result)
    for protected_value in (
        "9001",
        "synthetic-private-text",
        "synthetic-private-payload",
        "postgresql",
        "fadir.db",
    ):
        assert protected_value not in result_text


def test_write_failure_rolls_back_before_any_target_read(monkeypatch) -> None:
    target = SyntheticTarget()
    events = []
    original_rollback = SyntheticTransaction.rollback

    def fail_write(self, rows):
        events.append("write")
        raise RuntimeError("synthetic-write-detail")

    def failed_transaction_read(self):
        events.append("read")
        raise RuntimeError("synthetic-aborted-transaction")

    def rollback(self):
        events.append("rollback")
        original_rollback(self)

    monkeypatch.setattr(SyntheticTransaction, "write_private_rows", fail_write)
    monkeypatch.setattr(
        SyntheticTransaction, "read_staged_private_rows", failed_transaction_read
    )
    monkeypatch.setattr(SyntheticTransaction, "rollback", rollback)

    try:
        result = run_private_migration(SyntheticSource(), target, migration_plan())
    except Exception as error:
        error.add_note(f"rollback_calls={target.rollback_calls}; events={events}")
        raise

    assert events == ["write", "rollback"]
    assert result.status is MigrationStatus.ROLLED_BACK
    assert result.failure_code == "TARGET_WRITE_FAILED"
    assert target.rollback_calls == 1
    assert target.transaction is not None
    assert not target.transaction.has_inserted_rows()


def assert_sanitized_unknown(error: Exception | None) -> None:
    assert error is not None, "An unconfirmed outcome must not return a normal result"
    assert type(error).__name__ == "MigrationOutcomeUnknown"
    assert isinstance(error, migration.MigrationOutcomeUnknown)
    assert str(error) == (
        "Migration outcome is unknown. Do not retry or clean up automatically."
    )
    assert error.__cause__ is None
    assert error.__context__ is None
    assert "synthetic-secret" not in "".join(traceback.format_exception(error))
    assert "synthetic-secret" not in repr(error)


def test_lost_commit_reply_never_reports_rollback(monkeypatch) -> None:
    target = SyntheticTarget()
    original_commit = SyntheticTransaction.commit
    original_rollback = SyntheticTransaction.rollback

    def commit_then_lose_reply(self):
        original_commit(self)
        raise RuntimeError("synthetic-secret-commit-reply")

    def rollback_cannot_undo_commit(self):
        shared = list(target.shared_rows)
        private = list(target.private_rows)
        original_rollback(self)
        target.shared_rows = shared
        target.private_rows = private

    monkeypatch.setattr(SyntheticTransaction, "commit", commit_then_lose_reply)
    monkeypatch.setattr(SyntheticTransaction, "rollback", rollback_cannot_undo_commit)
    result = None
    caught = None
    try:
        result = run_private_migration(SyntheticSource(), target, migration_plan())
    except Exception as error:
        caught = error

    assert result is None, "The core reported rollback while committed rows remain"
    assert_sanitized_unknown(caught)
    assert target.begin_calls == 1
    assert target.rollback_calls == 0
    assert target.transaction_state is TargetState.COMMITTED
    assert target.shared_rows == list(SYNTHETIC_SHARED_ROWS)
    assert target.private_rows == list(assigned_private_rows())


@pytest.mark.parametrize(
    "failure", ["rollback", "verification", "remaining-rows", "invalid-verification"]
)
def test_unconfirmed_rollback_raises_sanitized_unknown(monkeypatch, failure) -> None:
    target = SyntheticTarget(failure_mode="write_after_shared")
    verification_calls = []
    original_rollback = SyntheticTransaction.rollback
    original_verify = SyntheticTransaction.has_inserted_rows

    def rollback(self):
        if failure == "rollback":
            target.rollback_calls += 1
            raise RuntimeError("synthetic-secret-rollback")
        if failure == "remaining-rows":
            target.rollback_calls += 1
            return
        original_rollback(self)

    def verify(self):
        verification_calls.append("verify")
        if failure == "verification":
            raise RuntimeError("synthetic-secret-verification")
        if failure == "invalid-verification":
            return None
        return original_verify(self)

    monkeypatch.setattr(SyntheticTransaction, "rollback", rollback)
    monkeypatch.setattr(SyntheticTransaction, "has_inserted_rows", verify)
    caught = None
    result = None
    try:
        result = run_private_migration(SyntheticSource(), target, migration_plan())
    except Exception as error:
        caught = error

    assert result is None, "An unverified rollback must not return a normal result"
    assert_sanitized_unknown(caught)
    assert target.begin_calls == 1
    assert target.rollback_calls == 1
    assert len(verification_calls) == (0 if failure == "rollback" else 1)


def test_shared_constraint_rejection_keeps_its_failure_category(monkeypatch) -> None:
    def reject_constraint(self, rows):
        raise TargetConstraintConflictError("synthetic-secret-constraint")

    monkeypatch.setattr(SyntheticTransaction, "write_shared_rows", reject_constraint)
    target = SyntheticTarget()
    result = run_private_migration(SyntheticSource(), target, migration_plan())

    assert result.failure_code == "TARGET_CONSTRAINT_CONFLICT"
    assert_rolled_back_without_rows(result, target)


@pytest.mark.parametrize(
    ("owner", "method"),
    [
        (SyntheticTarget, "begin"),
        (SyntheticSource, "read_shared_rows"),
        (SyntheticTransaction, "write_shared_rows"),
        (SyntheticSource, "read_private_rows"),
        (SyntheticTransaction, "write_private_rows"),
        (SyntheticTransaction, "read_staged_shared_rows"),
        (SyntheticTransaction, "read_staged_private_rows"),
        (SyntheticTransaction, "read_private_rows_for_workspace"),
        (SyntheticTransaction, "repeatability_signature"),
        (SyntheticTransaction, "commit"),
        (SyntheticTransaction, "rollback"),
        (SyntheticTransaction, "has_inserted_rows"),
    ],
)
def test_typed_unknown_bypasses_normal_failure_paths(monkeypatch, owner, method) -> None:
    during_rollback = method in ("rollback", "has_inserted_rows")
    target = SyntheticTarget(
        failure_mode="write_after_shared" if during_rollback else None
    )
    calls = []

    def unknown(self, *args):
        calls.append(method)
        if method == "rollback":
            target.rollback_calls += 1
        raise migration.MigrationOutcomeUnknown() from RuntimeError("synthetic-secret")

    monkeypatch.setattr(owner, method, unknown)
    caught = None
    try:
        run_private_migration(
            SyntheticSource(),
            target,
            migration_plan(
                expected_signature="baseline"
                if method == "repeatability_signature"
                else None
            ),
        )
    except Exception as error:
        caught = error

    assert_sanitized_unknown(caught)
    assert calls == [method]
    assert target.rollback_calls == int(during_rollback)


@pytest.mark.parametrize(
    ("mode", "expected_code"),
    [
        ("write_after_shared", "TARGET_WRITE_FAILED_AFTER_SHARED"),
        ("write_after_private", "TARGET_WRITE_FAILED_AFTER_PRIVATE"),
    ],
)
def test_typed_write_progress_needs_no_failed_transaction_read(
    monkeypatch, mode, expected_code,
) -> None:
    target = SyntheticTarget(failure_mode=mode)

    def reject_read(self):
        raise AssertionError("A failed transaction must not supply write progress")

    monkeypatch.setattr(SyntheticTransaction, "read_staged_private_rows", reject_read)
    result = run_private_migration(SyntheticSource(), target, migration_plan())

    assert result.failure_code == expected_code
    assert result.status is MigrationStatus.ROLLED_BACK
    assert target.rollback_calls == 1
    assert target.transaction is not None
    assert not target.transaction.has_inserted_rows()


def test_generic_commit_failure_is_unknown_without_durable_state_proof(monkeypatch) -> None:
    target = SyntheticTarget()

    def fail_commit(self):
        raise RuntimeError("synthetic-secret-unconfirmed-commit")

    monkeypatch.setattr(SyntheticTransaction, "commit", fail_commit)
    caught = None
    try:
        run_private_migration(SyntheticSource(), target, migration_plan())
    except Exception as error:
        caught = error

    assert_sanitized_unknown(caught)
    assert target.begin_calls == 1
    assert target.rollback_calls == 0
    assert target.shared_rows == []
    assert target.private_rows == []
    assert target.transaction is not None
    assert target.transaction.has_inserted_rows()
