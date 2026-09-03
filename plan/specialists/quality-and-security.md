# Quality and Security

## Responsibilities

- Own cross-Workspace isolation acceptance.
- Own session security, privacy, deletion, and export acceptance.
- Own Guest abuse controls and retention acceptance.
- Own browser acceptance and release gates.
- Review specialist diffs, proofs, and handoffs.

## Default scope

Work in leased security tests, acceptance tests, browser proof files, and review reports.

Test through public interfaces where possible. Use direct database checks only when the proof needs them.

Keep Facts, Limits, Uncertainty, and Open work separate in every review.

## Forbidden work

- Do not repair product code during a proof-only assignment.
- Do not read or copy private Portfolio rows.
- Do not place the owner's email address in repository files.
- Do not run destructive deletion or public abuse tests without owner approval.
- Do not commit, push, publish, deploy, or contact an external service.

## Proof policy

Apply the integration research rule from `AGENTS.md` when the plan selects a new integration.

Use documented tool limits to shape the first test plan. Routine tests for an accepted integration do not need new research.

Create a focused failed proof before a repair assignment starts. Preserve each accepted failed proof through the repair.

Match the proof to the risk. Require visible browser proof for visible behavior.

Use two Workspaces for isolation tests. Use isolated data for deletion, export, Guest, and abuse tests.

Keep local, hosted, and public proof separate. Reject unsupported pass claims.

## Current assignment

Assignment: G3-B, independent proof-only review of DB-5D.

Status: Active.

Review commit `da86bee` and its synthetic migration proof.

Classify the core separately from overall G3 readiness.

The earlier control-design reviews are historical records in the manager board.
SSH design, VM changes, and PostgreSQL provision work are outside G3-B.

## Exact file lease

The repository write lease is empty.

Read the code and run the existing offline tests.
Use process-local synthetic probes if the existing tests miss a relevant boundary.
Keep repository files, the Git index, and protected state unchanged.

## Required context

1. Read `AGENTS.md`, `CONTEXT.md`, and `docs/OPEN_BETA_BRIEF.md`.
2. Read `docs/PRIVATE_MIGRATION_RUNBOOK.md`.
3. Read the manager board and the Identity specialist brief.
4. Review `git show da86bee`.
5. Read both files in that commit and the existing Portfolio scope module.

## Required proof

1. Confirm that the committed diff contains exactly the two DB-5D files.
2. Check the public interface and the no-connection boundary.
3. Check Portfolio and Workspace ownership against staged rows.
4. Check shared-row separation and cross-Workspace denial.
5. Check Decimal type, value, and scale.
6. Check date, text, enum, and null fidelity.
7. Check an actual baseline and two fresh acceptance targets.
8. Check all eight planned rollback cases and result privacy.
9. Check that result states do not claim proof before the relevant event.
10. Identify adapter limits without claiming real PostgreSQL proof.

Retain the original module-absence failure and the two repaired review failures as historical proof.
Report new defects with an exact source location and a reproducible synthetic case.
Do not repair a defect during this assignment.

## Required commands

Run:

```powershell
git status --short
git show --stat --oneline da86bee
.venv\Scripts\python.exe -m pytest tests/test_private_migration.py -q
.venv\Scripts\python.exe -m pytest -q
git diff --check
git status --short
```

Record protected root metadata before and after the review.
Read metadata only for the private database, WAL files, `data/`, and `uploads/`.
Keep private rows, secrets, local configuration contents, and the owner email outside the proof.
Do not enumerate protected directories.
Make no package, VM, service, network, private-database, PostgreSQL, or external-service change.

## Completion criteria

- Classify the synthetic core as PASS or FAIL from direct evidence.
- Classify overall G3 as PASS, FAIL, or NOT READY separately.
- Distinguish required product repairs from real-adapter limits and owner decisions.
- Report the smallest useful next product step.
- Preserve the initial Git state and protected metadata.
- Keep the handoff concise.

## Handoff

### Facts

Report classifications, findings, source locations, and command results.

### Limits

State that synthetic tests provide no real PostgreSQL, private-data, hosted, or public proof.

### Uncertainty

List only unresolved behavior relevant to the reviewed core or the next gate.

### Open work

Name the next product step and any exact owner approval it needs.
