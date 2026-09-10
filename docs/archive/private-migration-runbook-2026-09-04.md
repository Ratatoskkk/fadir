# faðir private migration control plan through 2026-09-04

Historical reference, archived on 2026-09-10. Instructions, leases, model settings,
status claims, commands, and approval requests below describe past work only.
Use the [live board](../../plan/manager-open-beta.md) for current authority and the next assignment.
Email literals have been omitted. Original proof artifacts and their hashes are unchanged.

---

# faðir Private Migration Runbook

Status: Gate 2 PASS and conditional G3 PASS accepted on 2026-09-04.
Gate 0 remains approved as the control plan. Gate 1 covers the bounded synthetic scope only.

## Current authority — 2026-09-04

The owner authorized continued synthetic work through the [live manager board](../../plan/manager-open-beta-history.md#continued-execution-approval).
The Senior can assign product work, run synthetic disposable-VM tests, review evidence, and commit accepted work.
The board's DB-6B file and operational leases define the exact target, access, validation, transfer, evidence, and cleanup scope.
This authorization satisfies Gate 1 only for that bounded synthetic scope. It does not accept unfinished proof.
Quality classified Gate 2 and conditional G3 as PASS on 2026-09-04. The Senior accepted both verdicts.
The [G3 acceptance record](../../plan/manager-open-beta-history.md#g3-acceptance-and-g3-record) defines the accepted evidence and limits.
The completed DB-6B and G3-REVIEW leases grant no further operational authority.

Private access, identity inputs, snapshots, retention, cutover, public changes, and new destructive scope remain behind their applicable owner gates.
The synthetic authorization does not approve private source access, production cutover, live provider calls, a push, or public deployment.
Historical recommendations below do not require duplicate approval or extend the current lease.

G3 accepts a conditional private dry-run and rollback control plan, not a completed private dry run.
Private execution waits for Phase 4 Login Identity proof and Gate 3 approval.
The synthetic rehearsal does not claim Google identity validation. Public access still requires request identity and Portfolio scope.

DB-6C permits a confirmed rollback result only after rollback and row-state verification pass.
An unconfirmed commit, rollback, or verification raises the sanitized `MigrationOutcomeUnknown` exception instead.
The caller must verify the outcome before any retry or cleanup. Automatic retry and cleanup remain blocked for unknown outcomes.

The two out-of-lease temporary directories remain intact. Tool policy blocked removal of the host archive.
Guest source, archives, and evidence remain retained under the board's controls. Gate 2 acceptance does not authorize their removal.

## 1. Purpose

This runbook defines the gates for a future private SQLite-to-PostgreSQL migration.

It gives the owner a decision record before any private access or database connection occurs.

## 2. Scope

The runbook covers these stages:

1. Approve the owner decisions.
2. Complete a synthetic rehearsal.
3. Create a WAL-consistent source snapshot.
4. Complete a private dry run.
5. Validate the result.
6. Freeze writes.
7. Complete the cutover.
8. Roll back when an approved trigger occurs.

The migration creates one User, one Workspace, and one target Portfolio.

Each private Transaction and Snapshot must receive the target Portfolio identifier.

Instrument, PriceCache, FxCache, and CorporateAction remain shared data.

Shared data must not receive Portfolio ownership.

## 3. Non-goals

This draft excludes all migration actions and database connections.

This draft does not select an owner value.

This draft does not add request identity, Portfolio selection, or route integration.

This draft does not change models, migrations, configuration, services, tests, or deployment state.

This draft does not prove PostgreSQL, hosted, or public behavior.

## 4. Protected data

The operator must protect the private database, its WAL state, uploads, local configuration, and secrets.

The operator must protect private rows and the owner identity from logs, reports, prompts, and screenshots.

A copy of `fadir.db` alone is unsafe while WAL files exist.

The approved snapshot method must capture one consistent database state.

The operator must treat every snapshot and dry-run target as private data.

### WAL-consistent snapshot choices

The owner must select one method after a separate technical proof.

1. Use the SQLite Online Backup API to create one transactionally consistent copy.
2. Use `VACUUM INTO` to create one consistent copy in a new protected file.
3. Freeze writes, close all connections, complete an approved WAL checkpoint, and then copy the database.
4. Use an atomic storage snapshot that captures the database, WAL, and shared-memory files as one state.

Each choice needs a restore rehearsal with synthetic data.

The method choice is PENDING OWNER APPROVAL.

## 5. Proof classes

| Proof class | Meaning | Boundary |
|---|---|---|
| Local | Source review and tests on the development computer | Local proof cannot prove a hosted or public pass. |
| Synthetic | Tests with invented rows and isolated databases | Synthetic proof cannot prove private data state. |
| Private | Proof from the approved private snapshot or dry-run target | Private proof needs explicit access approval. |
| Hosted | Proof on the approved hosted PostgreSQL service | Hosted proof needs an approved service and connection window. |
| Public | Proof through the approved public service path | Public proof needs a separate public proof window. |

Each evidence record must name one proof class.

One proof class cannot replace another proof class.

## 6. Owner decision table

Pending entries apply to private execution unless marked synthetic. See the current authority section for the bounded synthetic authorization.

| Decision | Required owner value | Status |
|---|---|---|
| WAL-consistent snapshot method | Select one choice from the snapshot options in this runbook. | PENDING OWNER APPROVAL |
| Protected snapshot location | Select an encrypted location with restricted access. | PENDING OWNER APPROVAL |
| Snapshot retention period | Select the deletion date or retention rule. | PENDING OWNER APPROVAL |
| PostgreSQL target | Select the approved service and database. | PENDING OWNER APPROVAL |
| Secret delivery method | Select a method that keeps the secret out of files and command history. | PENDING OWNER APPROVAL |
| Google issuer and subject | Provide the verified durable identity keys through a protected channel. | PENDING OWNER APPROVAL |
| Target Workspace | Select the Workspace rule and expected ownership state. | PENDING OWNER APPROVAL |
| Target Portfolio name | Select the Portfolio name. | PENDING OWNER APPROVAL |
| Target Portfolio Base Currency | Select the three-letter Base Currency. | PENDING OWNER APPROVAL |
| Private-row mapping rule | Define which private rows receive the target Portfolio identifier. | PENDING OWNER APPROVAL |
| Invalid or unmatched row behavior | Select reject, quarantine, or another explicit result. | PENDING OWNER APPROVAL |
| Write-freeze window | Select the start, end, and maximum duration. | PENDING OWNER APPROVAL |
| Concurrent-write control | Select the control that blocks every private write. | PENDING OWNER APPROVAL |
| Validation checks and acceptance limits | Approve the checks and all pass limits. | PENDING OWNER APPROVAL |
| Rollback triggers and boundaries | Approve each trigger and the last safe rollback point. | PENDING OWNER APPROVAL |
| SQLite restore steps | Approve the exact restore sequence and authority. | PENDING OWNER APPROVAL |
| PostgreSQL cleanup steps | Approve the exact cleanup sequence and destructive authority. | PENDING OWNER APPROVAL |
| Private access approval | Approve who can access the source snapshot and private target. | PENDING OWNER APPROVAL |
| PostgreSQL connection window | Select the allowed connection start and end. | PENDING OWNER APPROVAL |
| Synthetic target type | Use the exact DB-6B target on the live board. | AUTHORIZED — BOUNDED SYNTHETIC SCOPE |
| Synthetic rollback cases | Use the DB-6B checks and DB-6C outcome contract on the live board. | AUTHORIZED — BOUNDED SYNTHETIC SCOPE |
| Cutover date | Select the date inside the approved write-freeze window. | PENDING OWNER APPROVAL |
| Evidence location and retention | Select a protected location and deletion rule. | PENDING OWNER APPROVAL |
| Migration implementation lease | Approve the exact files for the future migration tool. | PENDING OWNER APPROVAL |

## 7. Preconditions

The owner approved the runbook as the control plan on 2026-09-01.

The current authority section records Gate 1 authorization for the bounded synthetic rehearsal.

The following preconditions apply to later tasks:

1. The accepted Alembic chain remains unchanged.
2. The synthetic upgrade and rollback tests pass.
3. A later lease supplies a deterministic migration tool and synthetic tests.
4. The owner approves every required decision for the next stage.
5. Before private execution, the target User has a verified Google issuer and subject through the Phase 4 Login Identity model.
6. The target Workspace and Portfolio have approved definitions.
7. Every Transaction and Snapshot has one deterministic Portfolio result.
8. Shared Instrument and market-cache data stays outside Portfolio ownership.
9. Request identity and Portfolio selection use the accepted PortfolioScope module before public access.
10. The operator can restore the approved source snapshot before cutover starts.

Any failed precondition stops the next stage.

## 8. Synthetic rehearsal

The synthetic rehearsal must pass before any private dry run.

The rehearsal uses invented identities, rows, values, and temporary databases.

The rehearsal must complete these steps:

1. Create a temporary SQLite source with the accepted source structure.
2. Add synthetic shared rows and synthetic unowned private rows.
3. Create an isolated disposable target.
4. Apply the accepted Alembic chain to the target.
5. Create one synthetic User, Workspace, and Portfolio.
6. Copy shared data without a Portfolio identifier.
7. Copy each Transaction and Snapshot with the synthetic Portfolio identifier.
8. Apply the approved invalid-row rule to synthetic edge cases.
9. Run every approved validation category.
10. Exercise each rollback boundary with synthetic data.
11. Repeat the rehearsal from a new temporary source.

The two runs must produce the same protected result class.

The evidence record must contain pass or fail results without source values or row counts.

Gate 2 passed on 2026-09-04 for the completed DB-6B scope and acceptance limits on the board.

## 9. Private dry run

The private dry run needs a separate owner gate.

It must use an approved WAL-consistent snapshot, not the live private source.

The private dry run must complete these steps:

1. Confirm the private access approval.
2. Confirm the PostgreSQL connection window.
3. Create the approved protected snapshot.
4. Keep the live private source unchanged.
5. Apply the accepted schema to an isolated target.
6. Create the approved User, Workspace, and Portfolio roots.
7. Copy shared data without Portfolio ownership.
8. Assign the approved Portfolio identifier to every Transaction and Snapshot.
9. Apply the approved invalid-row rule.
10. Run all approved validation checks.
11. Record only protected pass or fail evidence.
12. Apply the approved target retention or cleanup result.

The dry-run target must not serve application traffic.

The owner must review the dry-run result before a write freeze or cutover.

## 10. Validation

Validation must use approved checks and acceptance limits.

The validation set must cover these categories:

1. Alembic revision and schema state.
2. User, Workspace, and Portfolio relationship integrity.
3. Google identity association with the approved User.
4. Portfolio ownership for every Transaction and Snapshot.
5. Absence of unowned private rows in the target result.
6. Foreign-key, unique, check, and index integrity.
7. Shared Instrument and market-cache separation.
8. Source-to-target row presence reconciliation.
9. Date, text, enum, Decimal, and null fidelity.
10. Cross-Workspace and cross-Portfolio denial.
11. Application health after the approved configuration change.
12. Rollback readiness before traffic changes.

The operator may compare private values and counts only inside the approved protected session.

The evidence record must store only a category, proof class, timestamp, and pass or fail result.

The evidence record must not store a private value, count, identity, path, URL, or secret.

The exact private checks and limits are PENDING OWNER APPROVAL. Use the current board scope for synthetic validation.

## 11. Write freeze

The owner must approve the write freeze before the operator activates it.

The approved control must block API jobs, background jobs, and operator writes.

The write-freeze stage must complete these steps:

1. Announce the approved maintenance window through the approved private channel.
2. Activate the approved concurrent-write control.
3. Confirm that all private writers obey the control.
4. Record the freeze start without private data.
5. Create the final WAL-consistent snapshot.
6. Keep the source unchanged until the owner accepts cutover or rollback.
7. Record the freeze end after the owner selects the final state.

The write-freeze window is PENDING OWNER APPROVAL.

The concurrent-write control is PENDING OWNER APPROVAL.

## 12. Cutover

Cutover needs explicit owner approval after the private dry run passes.

The cutover must complete these steps:

1. Confirm every precondition and approval gate.
2. Activate the approved write freeze.
3. Create the final approved source snapshot.
4. Apply the accepted Alembic chain to the approved target.
5. Load shared data without Portfolio ownership.
6. Load the approved User, Workspace, and Portfolio roots.
7. Load every Transaction and Snapshot with the approved Portfolio identifier.
8. Run the full approved validation set.
9. Keep application traffic on the source after any failed check.
10. Switch application configuration only after all checks pass.
11. Run the approved hosted health and scope checks.
12. Release the write freeze only after owner acceptance.
13. Preserve the source and snapshot through the approved rollback window.

The cutover date and target are PENDING OWNER APPROVAL.

## 13. Rollback

The owner must approve triggers, boundaries, and restore steps before cutover.

Possible trigger categories include these conditions:

1. An identity or ownership mismatch.
2. An unowned private target row.
3. A failed schema or constraint check.
4. A failed source-to-target reconciliation.
5. An unexpected write during the freeze.
6. A target connection or health failure.
7. A failed cross-Workspace or cross-Portfolio denial check.
8. A result outside an approved acceptance limit.

The owner must select the final triggers. The trigger set is PENDING OWNER APPROVAL.

The rollback boundaries are:

1. Before configuration changes, keep the source active and isolate the target.
2. After configuration changes but before target writes, restore the approved source configuration.
3. After target writes, use an approved reverse-copy or target-restore method.

The boundary after the first target write is PENDING OWNER APPROVAL.

The SQLite restore sequence must preserve one WAL-consistent database state.

The exact SQLite restore steps are PENDING OWNER APPROVAL.

The operator must preserve failed-target evidence before any cleanup.

The exact PostgreSQL cleanup steps are PENDING OWNER APPROVAL.

Any destructive cleanup needs a separate owner confirmation.

## 14. Secret handling

The owner must select a protected secret delivery method.

The operator must keep credentials out of repository files, command history, logs, screenshots, and evidence records.

The migration environment requires `FADIR_DATABASE_URL` for each Alembic command.

The operator must inject the value through the approved protected method.

The operator must report only whether the required secret is available.

The secret delivery method is PENDING OWNER APPROVAL.

## 15. Evidence handling

Each stage must create a short evidence record with these fields:

1. Stage name.
2. Proof class.
3. Start and end time.
4. Approved revision identifier.
5. Validation category results.
6. Approval reference.
7. Final state.

The record must use pass, fail, or inconclusive results.

The record must exclude private values, row counts, identities, paths, URLs, and secrets.

The private evidence location and retention rule are PENDING OWNER APPROVAL. Use the current board scope for synthetic evidence.

## 16. Approval gates

| Gate | Required approval | Status |
|---|---|---|
| Gate 0 | Approve this runbook and its owner decision table. | APPROVED 2026-09-01 — CONTROL PLAN ONLY |
| Gate 1 | Approve the synthetic rehearsal scope, target, and limits. | AUTHORIZED 2026-09-04 — BOUNDED BOARD SCOPE ONLY |
| Gate 2 | Accept the synthetic rehearsal evidence. | PASS ACCEPTED 2026-09-04 — SYNTHETIC SCOPE ONLY |
| Gate 3 | Approve private access, the snapshot method, and the dry-run window. | PENDING OWNER APPROVAL |
| Gate 4 | Accept the private dry-run evidence. | PENDING OWNER APPROVAL |
| Gate 5 | Approve the write freeze, target connection, and cutover. | PENDING OWNER APPROVAL |
| Gate 6 | Accept the hosted validation and release the write freeze. | PENDING OWNER APPROVAL |
| Gate 7 | Approve any rollback, restore, or destructive cleanup action. | PENDING OWNER APPROVAL |
| Gate 8 | Approve any public proof window. | PENDING OWNER APPROVAL |

No later gate can replace an earlier gate.

### Gate 0 approval record

The owner approved Gate 0 on 2026-09-01.

Gate 0 approves this runbook as the control plan only.

Gate 0 authorizes no migration action, database connection, private access, secret use, or destructive action.

The previous Gate 0 status was `PENDING OWNER APPROVAL`.

The focused failed proof returned this stale record before the edit:

```text
324:| Gate 0 | Approve this runbook and its owner decision table. | PENDING OWNER APPROVAL |
```

At the Gate 0 decision, Gate 1 and all later gates remained `PENDING OWNER APPROVAL`.
Every owner decision value was pending. The current authority section records the later synthetic authorization.

### Historical Gate 1 recommendation — DB-5C

The following subsections preserve the DB-5C proposals, including their original approval labels and retention recommendation.
They are historical, not current operational authority. Use the current authority section and live board for synthetic work.

#### Synthetic target comparison

| Choice | Risk coverage | Cost and limit | Proposal status |
|---|---|---|---|
| Temporary SQLite target | Proves mapping logic, result structure, repeatability, and rollback control. | It does not prove PostgreSQL types, constraints, transactions, identity columns, or driver behavior. | RECOMMENDATION ONLY |
| Disposable PostgreSQL target | Proves the migration logic against the target dialect and transaction behavior. | It needs an isolated service, an approved connection window, and cleanup proof. | RECOMMENDATION ONLY |

Target recommendation: `RECOMMENDATION ONLY` — Use a disposable PostgreSQL target with a temporary SQLite source.

This choice addresses the main SQLite-to-PostgreSQL migration risk.

It can expose dialect, constraint, transaction, and value-conversion differences before private access.

#### Migration module

Module recommendation: `RECOMMENDATION ONLY` — Add one deep module with this public interface:

```python
def run_private_migration(
    source: Connection,
    target: Connection,
    plan: MigrationPlan,
) -> MigrationResult:
    ...
```

The caller supplies open source and target dependencies.

The module creates no engine or database connection.

The module reads through the source dependency and writes through one target transaction.

The module copies shared rows separately from private rows.

The module assigns one Portfolio identifier to each Transaction and Snapshot.

The module returns a structured `MigrationResult` with these fields:

1. Status: `PASSED` or `ROLLED_BACK`.
2. Ordered validation results with stable category codes.
3. Failure code or `None`.
4. Target state: `COMMITTED` or `ROLLED_BACK`.

The result must contain no private value, row count, identity, path, URL, or secret.

Tests must call `run_private_migration` through the same interface as future callers.

Future lease recommendation: `RECOMMENDATION ONLY`

- `app/services/private_migration.py`
- `tests/test_private_migration.py`

DB-5C does not implement this module.

#### Synthetic validation checks and limits

Validation recommendation: `RECOMMENDATION ONLY`

| Result | Exact synthetic acceptance limit | Proposal status |
|---|---|---|
| Private ownership | 100% of synthetic Transaction and Snapshot rows have one non-null target Portfolio identifier. | RECOMMENDATION ONLY |
| Shared data separation | Zero Instrument, PriceCache, FxCache, or CorporateAction rows receive a Portfolio identifier. | RECOMMENDATION ONLY |
| Cross-Workspace denial | A scope for another Workspace returns exactly zero private rows. | RECOMMENDATION ONLY |
| Value fidelity | 100% of Decimal, date, text, enum, and null fields match their synthetic source values. | RECOMMENDATION ONLY |
| Decimal fidelity | Each value remains a `Decimal` and equals the source value at the model scale. | RECOMMENDATION ONLY |
| Repeatability | Two runs from one synthetic source into two fresh targets return equal structured results and equal target rows. | RECOMMENDATION ONLY |
| Planned rollback | 100% of planned failure cases return `ROLLED_BACK` with the expected stable failure code. | RECOMMENDATION ONLY |
| Partial target state | Each rollback leaves zero rows inserted by the migration module. | RECOMMENDATION ONLY |

#### Synthetic rollback cases

Rollback recommendation: `RECOMMENDATION ONLY` — Test each of these planned failures:

1. Reject one invalid or unmatched private row.
2. Reject one missing shared-row reference.
3. Reject one target constraint conflict.
4. Inject a source read failure.
5. Inject a target write failure after shared-row writes.
6. Inject a target write failure after the first private-row write.
7. Inject one validation mismatch before commit.
8. Detect a repeatability mismatch before commit.

Every case must return `ROLLED_BACK` and leave no inserted target row.

#### Synthetic evidence

Evidence location recommendation: `RECOMMENDATION ONLY` — Use a task-owned temporary directory outside the repository and protected directories.

Evidence retention recommendation: `RECOMMENDATION ONLY` — Keep raw synthetic artifacts through manager review and the Gate 2 decision.

Delete the raw artifacts after that decision or after seven calendar days, whichever occurs first.

Keep only test names, category results, and the structured non-private summary in the handoff.

#### Login Identity constraint

The current model has no Login Identity record.

The current schema cannot associate a User with a Google issuer and subject.

Google identity validation cannot pass through the current Gate 1 model.

Login Identity recommendation: `RECOMMENDATION ONLY` — Defer this check to Phase 4.

Gate 1 should record the Google identity check as `NOT APPLICABLE — MODEL ABSENT`.

Gate 3 must remain blocked until Phase 4 supplies and proves the Login Identity association.

This recommendation does not select an owner identity.

## 17. Facts

- The accepted Alembic chain has three revisions.
- The chain creates the baseline, domain roots, and nullable Portfolio ownership keys.
- Local synthetic tests prove upgrade, downgrade, and a second upgrade.
- PostgreSQL upgrade SQL has local offline proof without an engine connection.
- Transaction and Snapshot are the current private row types with Portfolio keys.
- Instrument, PriceCache, FxCache, and CorporateAction remain shared.
- PortfolioScope assigns and checks Portfolio ownership for private rows.
- Current routes do not use PortfolioScope.
- Request identity and Portfolio selection do not exist.
- The board records accepted DB-6A PostgreSQL schema proof and DB-6C synthetic outcome proof.
- Quality and the Senior accepted DB-6B rehearsal evidence at Gate 2 on 2026-09-04.
- G3 passed for the conditional Phase 3 scope on 2026-09-04. No private dry run has passed.

## 18. Limits

- This file is a draft only.
- This draft performs no migration action.
- This draft makes no private SQLite or PostgreSQL connection.
- This draft reads no private row, schema, count, database page, or WAL page.
- This draft records no real identity, email address, path, URL, or secret.
- This draft provides no private, hosted, or public pass.
- The accepted synthetic evidence does not prove actual network-loss recovery or complete artifact cleanup.
- Concurrent writers, large-data performance, historical SQLite precision loss, and alternate runtime versions remain outside that evidence.

## 19. Uncertainty

These private execution values remain pending. The current authority section covers the authorized synthetic scope only.

- Snapshot method: PENDING OWNER APPROVAL.
- Snapshot location: PENDING OWNER APPROVAL.
- Snapshot retention period: PENDING OWNER APPROVAL.
- PostgreSQL target: PENDING OWNER APPROVAL.
- Secret delivery method: PENDING OWNER APPROVAL.
- Google issuer and subject: PENDING OWNER APPROVAL.
- Target Workspace: PENDING OWNER APPROVAL.
- Target Portfolio name: PENDING OWNER APPROVAL.
- Target Portfolio Base Currency: PENDING OWNER APPROVAL.
- Private-row mapping rule: PENDING OWNER APPROVAL.
- Invalid or unmatched row behavior: PENDING OWNER APPROVAL.
- Write-freeze window: PENDING OWNER APPROVAL.
- Concurrent-write control: PENDING OWNER APPROVAL.
- Validation checks and acceptance limits: PENDING OWNER APPROVAL.
- Rollback triggers and boundaries: PENDING OWNER APPROVAL.
- SQLite restore steps: PENDING OWNER APPROVAL.
- PostgreSQL cleanup steps: PENDING OWNER APPROVAL.
- Private access approval: PENDING OWNER APPROVAL.
- PostgreSQL connection window: PENDING OWNER APPROVAL.
- Cutover date: PENDING OWNER APPROVAL.
- Evidence location and retention rule: PENDING OWNER APPROVAL.
- Migration implementation lease: PENDING OWNER APPROVAL.

## 20. Open work

1. Prepare Phase 4 identity and request-scope work through the live board.
2. Keep private execution blocked until Phase 4 Login Identity proof and the applicable private gates pass.
3. Preserve retained artifacts until their exact disposition has approval.

The owner must approve these items before a private migration task:

1. Every required private value in the owner decision table: PENDING OWNER APPROVAL.
2. Every pending private approval gate through the requested stage: PENDING OWNER APPROVAL.
3. The exact private access window: PENDING OWNER APPROVAL.
4. The exact PostgreSQL connection window: PENDING OWNER APPROVAL.
5. The exact migration implementation lease: PENDING OWNER APPROVAL.
6. The evidence location and retention rule: PENDING OWNER APPROVAL.
7. Any rollback, restore, or destructive cleanup action: PENDING OWNER APPROVAL.

The next task must stop when it reaches an unapproved value or gate.
