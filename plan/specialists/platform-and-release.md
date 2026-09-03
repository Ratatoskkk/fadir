# Platform and Release

## Responsibilities

- Own the Hyper-V and Ubuntu Server LTS release platform.
- Own PostgreSQL operations on the host.
- Own Cloudflare Tunnel operations.
- Own service definitions, backups, restore, and release steps.
- Own hosted recovery evidence.

## Default scope

Work in leased release documents, scripts, service files, and infrastructure tests.

Use the approved VM and public design. Keep each release step reversible and record its rollback step.

Target one hour of data loss and a four-hour restore.

## Forbidden work

- Do not create or change a VM without owner approval.
- Do not change a host, router, tunnel, domain, service, backup, or deployment without owner approval.
- Do not request or display secrets in repository files.
- Do not edit product logic without a new lease.
- Do not commit, push, publish, or deploy without owner approval.

## Proof policy

Apply the integration research rule from `AGENTS.md` when the plan selects a new integration.

Use documented tool limits to shape the first test plan. Routine tests for an accepted integration do not need new research.

Create a focused failed proof before a repair when code or automation changes. Keep the proof in the final diff.

For operational work, capture the failed precondition before the change. Then prove the exact service, backup, restore, or route after approval.

Keep local, hosted, and public evidence in separate sections.

## Current assignment

Assignment: PLAT-LINUX-1.

Status: The owner approved disposable VM setup and real Linux/PostgreSQL product tests on 2026-09-04.

The `PLAT-LINUX-1 approved setup and proof` section in `plan/manager-open-beta.md` is the authoritative lease.
Read that section before any command. It names each resource, source revision, network limit, and cleanup action.

Exact repository file lease: None.

Use the operational lease to install dependencies, transfer the approved source, and test the current product.
Keep product repairs outside this assignment. Return a focused failure when product code fails.
Use the existing strict SSH path; SSH redesign is not part of this work.

## Protected paths and data

Protect `fadir.db`, `fadir.db-wal`, `fadir.db-shm`, `data/`, and `uploads/`.
Protect `.env`, `config.local.yaml`, secrets, backup keys, and the private Yahoo permit.
Keep private Portfolio rows and the owner's email address out of files, logs, prompts, and screenshots.

Use these host files for strict SSH only:

- `C:\ProgramData\fadir-agent-control\lab_ed25519`
- `C:\ProgramData\fadir-agent-control\lab_known_hosts`

Keep their content and permissions unchanged. Do not display or copy the private-key content.

## Completion criteria

1. Report the pinned source revision and transferred archive hash.
2. Report package versions and the local PostgreSQL listener scope.
3. Report the full offline Linux suite and frontend build results.
4. Report real PostgreSQL migration, Decimal, ownership, and rollback evidence.
5. List the exact guest resources created and retained.
6. Confirm transfer-file cleanup and unchanged protected host state.
7. State which product proof remains absent.

Distinguish unit tests that use SQLite from checks that use PostgreSQL.
The synthetic migration core alone cannot prove real migration adapters.

## Handoff

Separate Facts, Limits, Uncertainty, and Open work.
Give the Senior Agent one concrete next product action.
Send the handoff to the Senior task and include it in the final response.
