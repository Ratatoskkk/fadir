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

Assignment: G3-PRECHECK, acceptance prerequisite review.

Status: Active. Read the G3-PRECHECK section on the live board. The DB-6B-REVIEW lease is released.

Exact file and operational write lease: Empty.
Read the current board, beta brief, runbook, and accepted DB-6A/DB-6C evidence.
Keep the review on gate prerequisites. DB-6B implementation and tests belong to Identity until handoff.
Keep repository files, the Git index, private paths, and all host and guest resources unchanged.

## Completion criteria

1. List the remaining evidence required after DB-6B.
2. Separate approved synthetic tests from pending private execution gates.
3. Explain the Phase 3 and Phase 4 dependency without an unsupported gate pass.
4. Name a narrow document correction or a real owner decision only if necessary.
5. Separate Facts, Limits, Uncertainty, and Open work.

Send the handoff to the Senior task and include it in the final response.
This is not an SSH, public release, or private migration review.
