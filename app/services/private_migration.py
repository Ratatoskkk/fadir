"""Run a caller-controlled private migration through supplied dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Mapping, Protocol, Sequence


VALIDATION_CODES = (
    "PRIVATE_OWNERSHIP",
    "SHARED_DATA_SEPARATION",
    "CROSS_WORKSPACE_DENIAL",
    "VALUE_FIDELITY",
    "DECIMAL_FIDELITY",
    "REPEATABILITY",
    "ROLLBACK",
    "PARTIAL_TARGET_STATE",
)

PRIVATE_TABLES = frozenset(("transaction", "snapshot"))


class TargetConstraintConflictError(RuntimeError):
    pass


class TargetWriteError(RuntimeError):
    """Carry write progress from memory, without a query after failure."""

    def __init__(self, *, private_rows_written: bool) -> None:
        super().__init__("Target write failed")
        self.private_rows_written = private_rows_written


class MigrationOutcomeUnknown(RuntimeError):
    """Require explicit outcome verification before retry or cleanup."""

    def __init__(self) -> None:
        super().__init__(
            "Migration outcome is unknown. Do not retry or clean up automatically."
        )


class MigrationStatus(str, Enum):
    PASSED = "PASSED"
    ROLLED_BACK = "ROLLED_BACK"


class TargetState(str, Enum):
    COMMITTED = "COMMITTED"
    ROLLED_BACK = "ROLLED_BACK"


class ValidationState(str, Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    NOT_RUN = "NOT_RUN"


@dataclass(frozen=True)
class MigrationPlan:
    portfolio_id: int
    workspace_id: int
    denied_workspace_id: int
    expected_repeatability_signature: str | None = None


@dataclass(frozen=True)
class ValidationResult:
    code: str
    state: ValidationState


@dataclass(frozen=True)
class MigrationResult:
    status: MigrationStatus
    validation_results: tuple[ValidationResult, ...]
    failure_code: str | None
    target_state: TargetState


class MigrationSource(Protocol):
    def read_shared_rows(self) -> Sequence[Mapping[str, object]]: ...

    def read_private_rows(self) -> Sequence[Mapping[str, object]]: ...


class MigrationTransaction(Protocol):
    def write_shared_rows(
        self, rows: Sequence[Mapping[str, object]]
    ) -> None: ...

    def write_private_rows(
        self, rows: Sequence[Mapping[str, object]]
    ) -> None: ...

    def read_staged_shared_rows(self) -> Sequence[Mapping[str, object]]: ...

    def read_staged_private_rows(self) -> Sequence[Mapping[str, object]]: ...

    def read_private_rows_for_workspace(
        self, workspace_id: int
    ) -> Sequence[Mapping[str, object]]: ...

    def repeatability_signature(self) -> str: ...

    def has_inserted_rows(self) -> bool: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...


class MigrationTarget(Protocol):
    def begin(self) -> MigrationTransaction: ...


def _validation_results(
    states: Mapping[str, ValidationState] | None = None,
) -> tuple[ValidationResult, ...]:
    return tuple(
        ValidationResult(
            code,
            states.get(code, ValidationState.NOT_RUN)
            if states is not None
            else ValidationState.NOT_RUN,
        )
        for code in VALIDATION_CODES
    )


def _rollback_result(
    transaction: MigrationTransaction,
    failure_code: str,
    states: Mapping[str, ValidationState] | None = None,
) -> MigrationResult:
    completed_states = dict(states or {})
    try:
        transaction.rollback()
    except MigrationOutcomeUnknown:
        raise
    except Exception:
        raise MigrationOutcomeUnknown() from None
    try:
        remaining_rows = transaction.has_inserted_rows()
    except MigrationOutcomeUnknown:
        raise
    except Exception:
        raise MigrationOutcomeUnknown() from None
    if remaining_rows is not False:
        raise MigrationOutcomeUnknown()
    completed_states["ROLLBACK"] = ValidationState.PASSED
    completed_states["PARTIAL_TARGET_STATE"] = ValidationState.PASSED
    return MigrationResult(
        status=MigrationStatus.ROLLED_BACK,
        validation_results=_validation_results(completed_states),
        failure_code=failure_code,
        target_state=TargetState.ROLLED_BACK,
    )


def _decimals_match(
    expected_rows: Sequence[Mapping[str, object]],
    actual_rows: Sequence[Mapping[str, object]],
) -> bool:
    if len(expected_rows) != len(actual_rows):
        return False
    for expected, actual in zip(expected_rows, actual_rows, strict=True):
        for key, expected_value in expected.items():
            if isinstance(expected_value, Decimal):
                actual_value = actual.get(key)
                if (
                    type(actual_value) is not Decimal
                    or actual_value != expected_value
                    or actual_value.as_tuple().exponent
                    != expected_value.as_tuple().exponent
                ):
                    return False
    return True


def _private_rows_are_valid(
    private_rows: Sequence[Mapping[str, object]],
) -> bool:
    return all(
        type(row.get("table")) is str and row.get("table") in PRIVATE_TABLES
        for row in private_rows
    )


def _private_references_exist(
    shared_rows: Sequence[Mapping[str, object]],
    private_rows: Sequence[Mapping[str, object]],
) -> bool:
    instrument_ids: set[int] = set()
    for row in shared_rows:
        if row.get("table") == "instrument":
            instrument_id = row.get("id")
            if type(instrument_id) is not int:
                return False
            instrument_ids.add(instrument_id)
    return all(
        row.get("table") != "transaction"
        or (
            type(row.get("instrument_id")) is int
            and row.get("instrument_id") in instrument_ids
        )
        for row in private_rows
    )


def _precommit_validation(
    transaction: MigrationTransaction,
    plan: MigrationPlan,
    shared_rows: Sequence[Mapping[str, object]],
    private_rows: Sequence[Mapping[str, object]],
) -> dict[str, ValidationState]:
    staged_shared_rows = tuple(
        dict(row) for row in transaction.read_staged_shared_rows()
    )
    staged_private_rows = tuple(
        dict(row) for row in transaction.read_staged_private_rows()
    )
    workspace_rows = tuple(
        dict(row)
        for row in transaction.read_private_rows_for_workspace(
            plan.workspace_id
        )
    )
    denied_rows = tuple(
        transaction.read_private_rows_for_workspace(plan.denied_workspace_id)
    )

    states = {
        "PRIVATE_OWNERSHIP": ValidationState.PASSED
        if len(staged_private_rows) == len(private_rows)
        and workspace_rows == staged_private_rows
        and all(
            row.get("portfolio_id") == plan.portfolio_id
            and row.get("portfolio_id") is not None
            for row in staged_private_rows
        )
        else ValidationState.FAILED,
        "SHARED_DATA_SEPARATION": ValidationState.PASSED
        if all("portfolio_id" not in row for row in staged_shared_rows)
        else ValidationState.FAILED,
        "CROSS_WORKSPACE_DENIAL": ValidationState.PASSED
        if not denied_rows
        else ValidationState.FAILED,
        "VALUE_FIDELITY": ValidationState.PASSED
        if staged_shared_rows == tuple(shared_rows)
        and staged_private_rows == tuple(private_rows)
        else ValidationState.FAILED,
        "DECIMAL_FIDELITY": ValidationState.PASSED
        if _decimals_match(shared_rows, staged_shared_rows)
        and _decimals_match(private_rows, staged_private_rows)
        else ValidationState.FAILED,
        "REPEATABILITY": ValidationState.NOT_RUN
        if plan.expected_repeatability_signature is None
        else (
            ValidationState.PASSED
            if transaction.repeatability_signature()
            == plan.expected_repeatability_signature
            else ValidationState.FAILED
        ),
    }
    return states


def run_private_migration(
    source: MigrationSource,
    target: MigrationTarget,
    plan: MigrationPlan,
) -> MigrationResult:
    """Return confirmed outcomes; raise sanitized uncertainty without cleanup."""
    try:
        return _run_private_migration(source, target, plan)
    except MigrationOutcomeUnknown:
        pass
    raise MigrationOutcomeUnknown() from None


def _run_private_migration(
    source: MigrationSource,
    target: MigrationTarget,
    plan: MigrationPlan,
) -> MigrationResult:
    transaction = target.begin()

    if type(plan.portfolio_id) is not int or plan.portfolio_id <= 0:
        return _rollback_result(transaction, "INVALID_PORTFOLIO_ID")

    try:
        shared_rows = tuple(dict(row) for row in source.read_shared_rows())
    except MigrationOutcomeUnknown:
        raise
    except Exception:
        return _rollback_result(transaction, "SOURCE_READ_FAILED")

    try:
        transaction.write_shared_rows(shared_rows)
    except MigrationOutcomeUnknown:
        raise
    except TargetConstraintConflictError:
        return _rollback_result(transaction, "TARGET_CONSTRAINT_CONFLICT")
    except Exception:
        return _rollback_result(transaction, "TARGET_WRITE_FAILED_AFTER_SHARED")

    try:
        source_private_rows = tuple(
            dict(row) for row in source.read_private_rows()
        )
    except MigrationOutcomeUnknown:
        raise
    except Exception:
        return _rollback_result(transaction, "SOURCE_READ_FAILED")

    if not _private_rows_are_valid(source_private_rows):
        return _rollback_result(transaction, "INVALID_PRIVATE_ROW")
    if not _private_references_exist(shared_rows, source_private_rows):
        return _rollback_result(transaction, "MISSING_SHARED_REFERENCE")

    private_rows = tuple(
        {**row, "portfolio_id": plan.portfolio_id}
        for row in source_private_rows
    )

    try:
        transaction.write_private_rows(private_rows)
    except MigrationOutcomeUnknown:
        raise
    except TargetConstraintConflictError:
        return _rollback_result(transaction, "TARGET_CONSTRAINT_CONFLICT")
    except TargetWriteError as error:
        failure_code = (
            "TARGET_WRITE_FAILED_AFTER_PRIVATE"
            if error.private_rows_written
            else "TARGET_WRITE_FAILED_AFTER_SHARED"
        )
        return _rollback_result(transaction, failure_code)
    except Exception:
        return _rollback_result(transaction, "TARGET_WRITE_FAILED")

    try:
        validation_states = _precommit_validation(
            transaction,
            plan,
            shared_rows,
            private_rows,
        )
    except MigrationOutcomeUnknown:
        raise
    except Exception:
        return _rollback_result(transaction, "VALIDATION_FAILED")

    failed_codes = tuple(
        code
        for code, state in validation_states.items()
        if state is ValidationState.FAILED
    )
    if failed_codes:
        failure_code = (
            "REPEATABILITY_FAILED"
            if failed_codes == ("REPEATABILITY",)
            else "VALIDATION_FAILED"
        )
        return _rollback_result(transaction, failure_code, validation_states)

    try:
        transaction.commit()
    except MigrationOutcomeUnknown:
        raise
    except Exception:
        raise MigrationOutcomeUnknown() from None

    return MigrationResult(
        status=MigrationStatus.PASSED,
        validation_results=_validation_results(validation_states),
        failure_code=None,
        target_state=TargetState.COMMITTED,
    )
