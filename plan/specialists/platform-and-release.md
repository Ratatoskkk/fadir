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

Assignment: None.

Status: LAB-SUDO-FINAL-DIAG-1 passed for live access. The correct sudo file is active and exact.

Proposed next assignment: LAB-SSH-HARDEN-1 after owner approval.

Preserve the live sudo proof and the inconclusive candidate-disappearance result.

## Exact file lease

Exact repository file lease: None.

Exact host write lease: None.

Exact guest write lease: None.

Read-only access can verify:

- VM `fadir-control-lab-01`.
- Stable trust file `C:\ProgramData\fadir-agent-control\lab_known_hosts`.
- Dedicated private key metadata at `C:\ProgramData\fadir-agent-control\lab_ed25519`.
- Accepted final sudo evidence already recorded on the manager board.

Use these host files for strict SSH only:

- `C:\ProgramData\fadir-agent-control\lab_ed25519`
- `C:\ProgramData\fadir-agent-control\lab_known_hosts`

Do not display or copy the private-key content.

Treat every other guest path and every host object as protected state.

## Protected paths and data

Protect `fadir.db`, `fadir.db-wal`, `fadir.db-shm`, `data/`, and `uploads/`.

Protect `.env`, `config.local.yaml`, environment secrets, host secrets, backup keys, and the private Yahoo permit.

Keep private Portfolio rows and the owner's email address out of files, logs, prompts, and screenshots.

## Required failed proof

Preserve these failed proofs:

- The installer SSH policy permits passwords, root key login, terminal access, and forwarding.
- `sudo -n true` fails for `fadir-agent` with exit code `1`.
- `sudo -n true` still failed after stage 1 created the candidate.
- The live sudoers path remained absent after stage 1.
- The first console install attempt used `/usr/sbin/install` and failed.
- The console command omitted the explicit `-g root` argument.
- The displayed zero followed `echo $`, so it does not prove the install exit code.
- Password-free root access passed while the approved live sudoers path was absent.
- Diagnosis found the active equals-sign file with the exact approved content.
- The repair created and validated the correct file, then removed the equals-sign file.
- The staged candidate was absent at the next check.
- Direct final proof confirmed the correct file and password-free root access.
- No host-driven restart or checkpoint recovery path has passed.

## Required commands

Run no specialist command while the assignment is empty.

Keep candidate recreation, SSH hardening, packages, services, checkpoints, and unrelated system reads outside the empty lease.

## Completion criteria

- The owner accepts or rejects the missing transient candidate limit.
- The owner approves an exact new lease before SSH hardening.

## Handoff

### Facts

- Ubuntu Server 24.04.4 LTS boots from the approved VHDX.
- The guest uses `192.168.247.10` and host name `fadir-control-lab-01`.
- The `fadir-agent` password is locked and its approved public key is installed.
- The stable ED25519 host key matches the VM console proof.
- Strict key-only SSH passed through the stable trust file with exit code `0`.
- The account belongs only to group `fadir-agent`.
- `sudo -n true` failed with exit code `1`.
- Stage 1 created and validated the exact candidate.
- The candidate SHA-256 value matches the approved value.
- Root validation of the candidate passed at the VM console.
- The owner ran `/usr/bin/install` without an error message.
- Stage 2 proved password-free root access.
- Stage 2 proved that the approved live sudoers path is absent.
- Diagnosis identified `/etc/sudoers.d/90=fadir-agent-bootstrap` as the active source.
- The correct file passed exact checks after the misnamed file was removed.
- The staged candidate was then absent.
- Direct final proof passed global syntax, effective policy, sudo, root identity, and strict SSH checks.

### Limits

- The staged candidate absence remains a non-functional failed requirement.
- It does not prove recovery, PostgreSQL, hosted access, public access, or private-data safety.

### Uncertainty

- The candidate disappearance cause remains inconclusive.
- The permanent constrained sudo design still fails its prior Quality review.

### Open work

- Obtain owner acceptance or rejection of the missing transient candidate limit.
- Obtain an exact lease before SSH hardening.
- Remove the temporary bootstrap after a reviewed constrained control path passes.
- Prove host-driven restart and recovery before the lab receives product files, secrets, or private data.
