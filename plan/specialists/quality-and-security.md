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

Assignment: G3-CTRL-3, proof-only exact control design review.

Status: FAIL and complete. The empty lease is released.

Review the complete PLAT-CTRL-4 final handoff and current coordination files.

Quality classified the design as FAIL.

Do not repair the design or run a live control test.

## Exact file lease

Exact file lease: Empty. This is a read-only proof assignment.

Do not edit repository files. Treat all current changes as owner work.

## Protected paths and data

Protect `fadir.db`, `fadir.db-wal`, `fadir.db-shm`, `data/`, and `uploads/`.

Protect `.env`, `config.local.yaml`, environment secrets, session secrets, and the private Yahoo permit.

Keep private Portfolio rows and the owner's email address out of files, logs, prompts, and screenshots.

## Required failed proof

Preserve the G3-CTRL-2 FAIL as the focused failed proof.

Confirm that no Hyper-V VM or proven agent-control path exists.

Review the design without a repair.

## Required commands

Run only these read-only commands:

```powershell
git status --short
$PSVersionTable.PSVersion.ToString()
$tools = 'wsl','ssh','ssh-keygen','ssh-keyscan','scp','vmconnect'
$tools | ForEach-Object { [pscustomobject]@{ Name = $_; Available = [bool](Get-Command $_ -ErrorAction SilentlyContinue) } }
$wslNames = @(wsl.exe --list --quiet 2>$null)
[pscustomobject]@{ DistributionCount = @($wslNames | Where-Object { $_ }).Count; UbuntuPresent = [bool]($wslNames -match 'Ubuntu') }
$vms = @(Get-VM -ErrorAction SilentlyContinue)
[pscustomobject]@{ VMCount = $vms.Count; RunningCount = @($vms | Where-Object State -eq 'Running').Count }
Get-NetTCPConnection -LocalPort 22,5432 -ErrorAction SilentlyContinue | Select-Object LocalAddress,LocalPort,State,OwningProcess
git diff --check
git status --short
```

Reuse the accepted 2026-09-02 integration research record.

Do not browse unless a material integration condition changed.

Record protected root metadata before and after the review.

Do not enumerate `data/` or `uploads/`.

Do not start WSL or a VM.

Make no package, key, credential, process, network, database, or external change.

## Completion criteria

- The review checks the full PLAT-CTRL-4 handoff.
- The review checks all four complete control programs.
- The review checks POSIX shell syntax and exact command parsing.
- The review checks each Linux user, group, directory, mode, and file creation right.
- The review checks each dispatcher, wrapper, action, and negative boundary.
- The review checks the process timeout, input stream, output streams, disposal, and failure cleanup.
- The review checks the private-key and known-host ACL rules.
- The review checks strict host-key pinning and effective SSH values for both users.
- The review checks the transfer boundary, archive trust, checksum, and repeat-transfer behavior.
- The review checks every PostgreSQL role, database, restore, backup, and cleanup action.
- The review checks address inputs, subnet validation, conflict checks, and both address proofs.
- The review checks host storage, guest iSCSI, checkpoint evidence, and recovery commands.
- The review checks every negative test for an exact executable form and expected result.
- The review keeps PostgreSQL backup proof separate from checkpoint proof.
- The review confirms that every failed check blocks product, secret, and private data entry.
- The review checks every destructive action and owner approval stop.
- The review states why the design is PASS, FAIL, or NOT READY.
- Protected file metadata stays unchanged.
- No pass claim exceeds its evidence.
- The review records each limit and unresolved risk.
- The handoff separates Facts, Limits, Uncertainty, and Open work.

## Handoff

### Facts

- All four proposed control programs failed review.
- Backup and inspection cannot use the proposed directory permissions.
- Database and transfer actions are not repeat-safe or concurrency-safe.
- The process helper has failed-start, stream, and memory-boundary defects.
- Only one of 24 negative tests has an executable test command.
- No Hyper-V VM or proven control path exists.
- Initial and final Git states match.
- Protected root metadata stayed unchanged.
- The review changed no repository file or host resource.

### Limits

- No proposed program ran in Linux.
- No SSH, sudo, transfer, PostgreSQL, checkpoint, or recovery control received a live test.
- The review provides local design evidence only.

### Uncertainty

- Some static defects need repair before installation.
- Other behavior needs a disposable Linux environment.
- Production-checkpoint event evidence remains unresolved.
- Console-free recovery remains unproved.

### Open work

- Pause another full paper-only repair until the owner chooses the strategy.
- The manager recommends a disposable Hyper-V Ubuntu lab with synthetic data only.
