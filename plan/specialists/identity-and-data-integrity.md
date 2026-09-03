# Identity and Data Integrity

## Responsibilities

- Own PostgreSQL and migrations.
- Own User, Workspace, and Portfolio data scope.
- Own User Sessions and Login Identities.
- Own Claim, Portfolio Transfer, and Portfolio Merge integrity.
- Own the approved private data migration path.

## Default scope

Work only in leased server, model, migration, and identity test files.

Use one PostgreSQL database. Scope every private row by Workspace and Portfolio as the domain requires.

Keep User identity separate from Workspace and Portfolio data.

## Forbidden work

- Do not run a private data migration without owner approval.
- Do not read or copy private Portfolio rows during normal work.
- Do not place the owner's email address in repository files.
- Do not edit React, finance, market provider, or release files without a new lease.
- Do not commit, push, publish, deploy, or contact an identity or email service.

## Proof policy

Apply the integration research rule from `AGENTS.md` when the plan selects a new integration.

Use documented tool limits to shape the first test plan. Routine tests for an accepted integration do not need new research.

Create a focused failed proof before a repair. Keep the proof in the final diff.

Prove cross-Workspace denial for each private query and mutation. Prove migration upgrade and rollback behavior with synthetic data.

Use a new test database. Keep private migration proof separate from synthetic migration proof.

## Current assignment

Assignment: DB-5D, synthetic migration core implementation.

Status: Active.

Implement the accepted migration module interface with synthetic dependencies.

Create no engine or database connection.

Use no private data, path, URL, identity, secret, or row count in a result.

Keep a real PostgreSQL rehearsal outside this task.

## Exact file lease

The lease contains only these new files:

- `app/services/private_migration.py`
- `tests/test_private_migration.py`

No other file can change.

## Protected paths and data

Protect `fadir.db`, `fadir.db-wal`, `fadir.db-shm`, `data/`, and `uploads/`.

Protect `.env`, `config.local.yaml`, environment secrets, identity secrets, and the private Yahoo permit.

Keep private Portfolio rows and the owner's email address out of files, logs, prompts, and screenshots.

## Required failed proof

Create `tests/test_private_migration.py` before the implementation file.

Run the focused test file before the implementation exists.

The focused proof must fail because the module is absent.

Keep the failed-proof tests in the final diff.

## Required commands

Run:

```powershell
git status --short
.venv\Scripts\python.exe -m pytest tests/test_private_migration.py -q
.venv\Scripts\python.exe -m pytest -q
git diff --check
git status --short
```

Record protected root path metadata before and after the work. Do not enumerate `data/` or `uploads/`.

Do not display an environment value.

Make no package installation, database connection, process change, or external call.

## Completion criteria

- `run_private_migration(source, target, plan)` is the public operation.
- The caller supplies the open source and target dependencies.
- The module creates no engine or connection.
- The module copies shared rows separately from private rows.
- The module assigns one Portfolio identifier to each private row.
- The operation uses one target transaction.
- The result status is `PASSED` or `ROLLED_BACK`.
- The target state is `COMMITTED` or `ROLLED_BACK`.
- Validation results use stable category codes and a stable order.
- The result contains no private value, row count, identity, path, URL, or secret.
- Planned failures roll back all writes and return a stable failure code.
- Tests use the same public interface as a future caller.
- Repeat runs with fresh synthetic targets return equal results and rows.
- The diff stays inside the exact lease.
- Protected file metadata stays unchanged.
- The handoff separates Facts, Limits, Uncertainty, and Open work.

## Handoff

### Facts

List the changed files, public interface, failed proof, rollback cases, and command results.

### Limits

List the no-connection, no-private-row, no-secret, and synthetic-only limits.

### Uncertainty

List unresolved real-database, dialect, transaction, and mapping behavior.

### Open work

List each approval needed before a disposable PostgreSQL rehearsal.
