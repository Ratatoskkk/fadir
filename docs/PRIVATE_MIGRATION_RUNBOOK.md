# faðir private migration runbook

Updated: 2026-09-10. Move the owner's original SQLite portfolio into the existing
verified Google User's Workspace as `Ana Portföy`, with TRY Base Currency.
This administrator migration is separate from Guest Claim, Transfer, and Merge.

## Current authority and state

The [live board](../plan/manager-open-beta.md#current-authority) is the execution authority.
The owner already approved private row inspection, protected snapshot/dry-run defaults,
and proceeding to a live migration after the dry run and every required validation pass.
The owner explicitly approved `Ana Portföy`/TRY and mapping every legacy Transaction
and Snapshot to it. Do not ask for those choices again.

The retained snapshot and restore-copy checks passed. The source predates User,
Workspace, Portfolio, and LoginIdentity roots, which explains the need for the approved
reconstruction. The two private dry-run attempts stopped before target writes. Later
diagnostics located the running service's identity context, credential rotation passed,
and the owner completed a Google Transfer. No completed private migration is recorded.

The current product checkpoint is the unfinished session-hydration browser proof.
Resume migration afterward with a separate exact operational lease. Recheck the target
and source at execution time; an earlier classification is not a current identity binding.

## Settled choices and execution preconditions

| Item | Current decision or required evidence |
|---|---|
| Source | `C:/Games/Agents/dashboard C/fadir.db`; leave it and its WAL state intact |
| Snapshot | Approved SQLite Online Backup API default; retained protected snapshot/restore proof exists |
| Destination | Existing verified Google User and its Workspace in the running service's effective PostgreSQL context |
| Identity | Match verified issuer/subject inside the protected session; never infer identity from email or choose an arbitrary schema |
| Portfolio | `Ana Portföy`, TRY; all legacy Transactions and Snapshots map to it |
| Invalid rows | Reject invalid or unmatched rows; no silent drops, invented values, or implicit duplicates |
| Dry-run target | New isolated non-serving PostgreSQL target with exact ownership/marker/OID guards |
| Credentials | Existing protected injection; no URLs or credential values in command output |
| Retention | Preserve the source, restorable snapshot, and failed evidence; no destructive cleanup approval exists |
| Live execution | Conditional owner approval exists; the Senior must first accept every dry-run validation and name the exact cutover scope |
| Still to specify | Exact target and protected identity binding, fresh resource paths, writer/freeze control, snapshot freshness, validation results, rollback boundary, and operational window |

The Senior resolves technical prerequisites from the approved running service and
retained evidence. Ask the owner only when a concrete missing choice affects their
data or service; do not ask them to guess database schemas or repeat blanket Gate 3 approval.

## Preparation

1. Review the current board, worktree, accepted migration source, and retained dry-run
   handoffs. Name every repository read, operational resource, and output path.
2. Verify the actual service connection/search path through a protected channel. Prove
   exactly one eligible verified LoginIdentity joins the intended User and Workspace.
   A structural count alone does not prove that identity belongs to the owner.
3. Check the legacy source's current writers and the retained snapshot's suitability.
   Refresh the WAL-consistent snapshot if required; restore-test it before relying on it.
4. Verify the accepted schema and migration adapters against the actual source/target.
   Reuse accepted synthetic proof when applicable. Any necessary adapter repair needs
   its own focused failed proof, exact source lease, and affected regression checks.
5. Set strict validation criteria, deterministic mapping, target isolation, protected
   evidence location, and the rollback/unknown-outcome procedure before writing.

Do not copy the bare SQLite file while WAL is active. The SQLite source adapter needs
an actual snapshot transaction. The PostgreSQL target adapter needs the accepted idle
connection state; inspect its current contract before use.

## Private dry run

1. Read only the protected, restore-tested snapshot. Keep the live source unchanged.
2. Create the named isolated target outside the serving search path and apply the
   accepted schema. Establish the approved User/Workspace/Portfolio mapping there.
3. Copy shared market/reference rows without private Portfolio ownership. Map every
   legacy Transaction and Snapshot to the approved Portfolio. Reject invalid rows.
4. Run every validation category below and check the final transaction outcome.
5. Preserve the source and failed-target evidence. Return a concise sanitized handoff;
   the Senior accepts the dry-run result before opening the live-execution lease.

A dry run is source-read-only, but it writes its isolated target. Do not describe it
as globally read-only or connect it to application traffic.

## Validation contract

| Category | Required result |
|---|---|
| Schema | Accepted Alembic revision, required tables, constraints, indexes, and valid foreign keys |
| Identity | Exact approved Google identity binds to the intended User and its one Workspace |
| Private ownership | Every migrated Transaction/Snapshot has the intended non-null Portfolio owner |
| Shared separation | Instrument, PriceCache, FxCache, and CorporateAction remain shared |
| Reconciliation | Every intended source row is represented once; no loss, silent omission, or duplicate private rows |
| Value fidelity | Decimal, date, text, enum, null, native amount, fee, and FX/provenance fields match the approved source mapping |
| Isolation | Other Workspace/Portfolio authority cannot read or mutate the migrated private data |
| Failure behavior | Invalid row/reference, constraint, read/write failure, or validation mismatch stops migration without a false success |
| Outcome | Commit or rollback is confirmed; an unknown outcome blocks retry and cleanup |
| Source preservation | Original source and the restorable snapshot remain intact |
| Hosted acceptance | After live execution, health and authorized owner access pass without cross-Workspace disclosure |

Compare private values inside the protected session only. Ordinary handoffs use
category results, revision and artifact hashes, and sanitized counts only where the
lease permits them. Never include holdings, transaction values, secrets, or durable
identity values in repository Markdown or ordinary logs.

## Conditional live migration

The owner has already authorized proceeding after the dry run and all validations pass.
That authorization does not prove technical readiness or permit deleting the source.

1. The Senior accepts the dry-run handoff and names a separate exact live lease with
   the verified existing User/Workspace, target, writer controls, rollback boundary,
   and expected service effect. Reconfirm identity and target state before mutation.
2. Establish and verify the necessary write freeze for all relevant API, background,
   and administrator writers. Take a final consistent source snapshot if needed.
3. Execute the approved deterministic migration into the named target. Preserve the
   existing Google identity and Workspace; do not create a second User to avoid binding.
4. Run all validations before commit or exposing migrated data. Change service
   configuration only if the chosen cutover mechanism requires and leases it.
5. Prove hosted health, ownership isolation, and the owner's original portfolio access.
   Confirm refresh/session behavior. Release the write freeze according to the accepted lease.
6. Preserve the source, snapshot, and evidence through acceptance. Report the exact
   final state without presenting service reconstruction as lost-data recovery.

## Rollback and unknown outcomes

Stop on identity ambiguity, an ownership mismatch, unowned private rows, failed
reconciliation, unexpected concurrent writes, failed constraints, or unhealthy target state.
Before traffic changes, leave the existing service state intact and isolate the target.

The accepted migration core reports confirmed pass/rollback outcomes. An unconfirmed
commit, rollback, or verification raises sanitized `MigrationOutcomeUnknown`.
Verify the actual outcome before retrying, restoring, or cleaning up. Never infer rollback
from a connection error. After new target writes, the previous source may no longer be
current; reverse-copy, restore, or destructive cleanup needs its own concrete authority.

## Evidence and completion

Use the four handoff sections in [AGENTS.md](../AGENTS.md#proof-and-handoff).
Private snapshot evidence, synthetic rehearsal, hosted owner acceptance, public probes,
and service recovery are separate proof classes. Keep raw artifacts outside the repository.

This migration is complete only when the accepted source data is attached to the intended
Google User, the owner can use it after refresh, all mapping/isolation checks pass, and
the source remains restorable. Source or snapshot deletion is not a completion criterion.

Read the [earlier control plan](archive/private-migration-runbook-2026-09-04.md) only for
a named historical question. Its pending-approval tables and absent-identity assumptions
are superseded by this runbook and the live board. The [original conditional G3 record](../plan/manager-open-beta-history.md#g3-acceptance-and-g3-record)
preserves the scope of the earlier synthetic acceptance.
