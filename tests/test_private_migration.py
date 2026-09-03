from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum
from hashlib import sha256
from typing import Mapping, Sequence, cast

import pytest

from app.services.private_migration import (
    VALIDATION_CODES,
    MigrationPlan,
    MigrationResult,
    MigrationStatus,
    TargetConstraintConflictError,
    TargetState,
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
            raise RuntimeError("planned write failure after shared rows")
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
                raise RuntimeError("planned write failure after one private row")

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
