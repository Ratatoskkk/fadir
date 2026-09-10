# faðir coordination

The [manager board](manager-open-beta.md) is the only live work board.
The Senior uses Luna Max; specialists use Luna Medium, as specified in [AGENTS.md](../AGENTS.md).
Only one specialist runs at a time. The Senior reviews each specialist's changes and
evidence, then commits and pushes accepted work before dependent implementation.
See [Senior review and publication](../AGENTS.md#senior-review-and-publication).

## Stable roles

| Role | Responsibility | Brief |
|---|---|---|
| Product Experience | React interface and visible acceptance | [Product](specialists/product-experience.md) |
| Identity and Data Integrity | Ownership, sessions, transitions, PostgreSQL, migration | [Identity](specialists/identity-and-data-integrity.md) |
| Finance and Tax | Calculation rules, currency, fees, Tax Profiles | [Finance](specialists/finance-and-tax.md) |
| Market Data | Yahoo, symbols, prices, FX, shared caches and refresh | [Market](specialists/market-data.md) |
| Platform and Release | VM, services, Tunnel, deployment and operational recovery | [Platform](specialists/platform-and-release.md) |
| Quality and Security | Independent review, isolation, privacy and release acceptance | [Quality](specialists/quality-and-security.md) |

These briefs are stable role boundaries. Current status and leases belong only on the
board, so an old role handoff cannot accidentally become a new assignment.

## Dispatch contract

The Senior checks the worktree and supplies one small, complete assignment:

```text
Role and assignment ID:
Outcome and acceptance criteria:
Current checkpoint and retained failed proof:
Read paths: exact repository paths and evidence files; no default exploration.
Repository writes: exact paths, or Empty.
Operational writes/resources: exact paths, processes, databases, or services, or Empty.
Commands and proof: focused checks, affected regressions, required proof classes.
Excluded scope and stop conditions:
Handoff: one exact absent non-repository .md path.
Model: gpt-5.6-luna; reasoning effort: medium.
```

Name the role brief and any shared instructions the specialist needs in its read lease.
Check operational targets before mutation. A read-only review still needs an explicit
write lease for its handoff artifact. Do not overwrite a previous handoff to manufacture
completion; a resumed assignment gets a fresh artifact and links its checkpoint.

The handoff has exactly four sections: `### Facts`, `### Limits`, `### Uncertainty`,
and `### Open work`. Include a review verdict when applicable. The Senior verifies the
actual diff and required proof, records acceptance or a bounded follow-up, and releases
or resumes the lease. After acceptance, the Senior commits only the accepted paths,
pushes them, verifies the remote commit, and records it on the board. Specialists do
not publish an unreviewed candidate.

Reuse the stable role while context is sufficient. Before an interruption, preserve
the current diff, failed proof, final artifacts, and one next action. Start a fresh
specialist with that checkpoint if its accumulated context exceeds 400k or its remaining
budget cannot finish the bounded assignment. Do not overlap the old and new task.

## Keep the board small

Keep the objective, current authority, latest accepted state, one active or resumable
assignment, queued outcomes, and open acceptance gates on the board. Replace stale
status instead of appending another narrative. Move closed chronology to history and
leave a short evidence pointer. A new run starts at the checkpoint, not at phase one.

## Historical reference

Read only the named section when a current question needs it:

- [Earlier coordination history](manager-open-beta-history.md).
- [Board snapshot before the 2026-09-10 cleanup](archive/manager-open-beta-2026-09-10.md).
- [Original local manual and measurements](../docs/archive/local-v1-readme.md).
- [Earlier private migration control plan](../docs/archive/private-migration-runbook-2026-09-04.md).

These records preserve evidence and superseded instructions. They grant no active lease.
