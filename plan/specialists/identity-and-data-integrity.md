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

Assignment: DB-6A, PostgreSQL migration version-field repair.

Status: The candidate is complete. The write lease is released for Senior review and real PostgreSQL proof.

The DB-6A section in `plan/manager-open-beta.md` defines the exact lease and completion criteria.
Read that section before any change.

Exact repository file lease:

- `migrations/env.py`
- `tests/test_migrations.py`
- `tests/test_postgresql_migrations.py` (new)

Preserve existing revision identifiers and the explicit database URL requirement.
Use a documented extension point that works with the declared Alembic minimum.
Keep this repair separate from private migration adapters and other model changes.

## Proof and handoff

Preserve the focused failed proof before the product edit.
Run the focused and full offline suites with an explicit `-m "not live"` filter.
Add an opt-in real PostgreSQL regression for the later VM review.
The current assignment has no guest, service, package, host-resource, or real database write lease.

Protect the root private database, WAL files, uploads, local overrides, secrets, and the owner's email address.
Check protected path metadata before and after the work without any private-row read.
Keep the diff inside the three-file lease. The Senior Agent reviews and commits accepted work.

Separate Facts, Limits, Uncertainty, and Open work.
Send the final handoff to the Senior task as well as the final response.
