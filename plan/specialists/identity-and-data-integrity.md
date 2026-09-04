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

Assignment: ID-1, internal Guest access foundation.

Status: Active with the seven-file and operational leases on the live board.

The ID-1 foundation section in `plan/manager-open-beta.md` defines the scope and completion criteria.
Read that section before any change.

Implement the six accepted review corrections and all additional controls before the older proposal details.
Keep the service PostgreSQL-only and retain SQLite model/migration compatibility. Expose no HTTP route or cookie.

## Proof and handoff

Preserve the focused failed proof before product code. Use real PostgreSQL for authorization and concurrency tests.
Run the full offline suite with an explicit non-live filter. Keep all proof inside the operational lease.

Protect the root private database, WAL files, uploads, local overrides, secrets, and the owner's email address.
Change only the seven leased files. Preserve caller work, secret boundaries, and earlier regressions.
The Senior Agent reviews and commits accepted work.

Separate Facts, Limits, Uncertainty, and Open work.
Send the final handoff to the Senior task as well as the final response.
