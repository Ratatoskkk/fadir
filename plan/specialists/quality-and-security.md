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

Assignment: G3-REVIEW, synthetic rehearsal and data-stage acceptance.

Status: Active. Read the DB-6B acceptance and G3-REVIEW section on the live board.

Exact file and operational write lease: Empty.
Review `5315496`, the accepted DB-6A/DB-6C evidence, the current runbook, and the retained DB-6B proof.
Read existing guest evidence and schema counts through strict SSH if needed. Create no new test or database artifact.
Keep source files, the Git index, private paths, and all host and guest resources unchanged.

## Completion criteria

1. Check the exact candidate, failed proofs, and independent test evidence.
2. Classify Gate 2 and G3 against the accepted conditional scope.
3. Keep private decisions pending and distinguish controlled faults from real transport loss.
4. Record artifact deviations without a cleanup-complete claim.
5. Separate Facts, Limits, Uncertainty, and Open work.

Send the handoff to the Senior task and include it in the final response.
This is not an SSH, public release, or private migration review.
