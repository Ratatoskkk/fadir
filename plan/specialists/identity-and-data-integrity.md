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

Assignment: DB-5C, Gate 0 record and Gate 1 decision proposal.

Status: Complete and accepted. The runbook lease is released.

Record the approved Gate 0 scope in the migration runbook.

The Gate 1 recommendations await Platform review and owner approval.

Mark every recommendation as `RECOMMENDATION ONLY`.

Keep Gate 1 and all later gates pending.

## Exact file lease

The proposed lease contains only this existing file:

- `docs/PRIVATE_MIGRATION_RUNBOOK.md`

No other file can change.

## Protected paths and data

Protect `fadir.db`, `fadir.db-wal`, `fadir.db-shm`, `data/`, and `uploads/`.

Protect `.env`, `config.local.yaml`, environment secrets, identity secrets, and the private Yahoo permit.

Keep private Portfolio rows and the owner's email address out of files, logs, prompts, and screenshots.

## Required failed proof

Before the edit, prove that Gate 0 still says `PENDING OWNER APPROVAL`.

Record that stale status as the focused failed proof.

Keep the failed proof in a Gate 0 approval record inside the runbook.

Do not change any other pending status to approved.

## Required commands

Run:

```powershell
git status --short
rg -n "Gate 0.*PENDING OWNER APPROVAL" docs/PRIVATE_MIGRATION_RUNBOOK.md
rg -n "Gate 0|APPROVED|Gate 1|RECOMMENDATION ONLY|Login Identity|PENDING OWNER APPROVAL" docs/PRIVATE_MIGRATION_RUNBOOK.md
$badWhitespace = Select-String -Path docs/PRIVATE_MIGRATION_RUNBOOK.md -Pattern '[ \t]+$'
if ($badWhitespace) { $badWhitespace; exit 1 }
git diff --check
git status --short
```

Record protected root path metadata before and after the work. Do not enumerate `data/` or `uploads/`.

Do not display an environment value.

Make no package installation, database connection, process change, or external call.

## Completion criteria

- The failed proof shows the stale Gate 0 status.
- The runbook records Gate 0 approval on 2026-09-01.
- The approval record states that Gate 0 accepts only the control plan.
- Gate 1 and all later gates stay pending.
- All private migration values stay pending.
- The Gate 1 proposal covers the synthetic target type.
- The proposal covers validation checks and exact acceptance limits.
- The proposal covers rollback cases and evidence rules.
- The proposal gives one exact future implementation lease.
- Every proposed choice says `RECOMMENDATION ONLY`.
- The proposal records the missing Login Identity model constraint.
- The runbook keeps local, synthetic, private, hosted, and public proof separate.
- The diff stays inside the exact lease.
- Protected file metadata stays unchanged.
- The handoff lists each Gate 1 owner choice.
- The handoff separates Facts, Limits, Uncertainty, and Open work.

## Handoff

### Facts

List the changed file, failed proof, Gate 0 record, Gate 1 recommendations, and command results.

### Limits

List the no-connection, no-private-row, no-secret, and recommendation-only limits.

### Uncertainty

List the Login Identity constraint and each unresolved Gate 1 choice.

### Open work

List each approval needed before the synthetic rehearsal implementation task.
