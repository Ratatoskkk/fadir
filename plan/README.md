# faðir open beta coordination

The [manager board](manager-open-beta.md) is the only live work board.
Its current authority section controls assignments, leases, gates, and owner decisions.
The accepted beta brief and ADRs control product decisions.

## Stable roles

| Role | Brief | Task |
|---|---|---|
| Product Experience | [product-experience.md](specialists/product-experience.md) | `01a0576b-208f-7b10-bdef-91dbf0a69abe` |
| Identity and Data Integrity | [identity-and-data-integrity.md](specialists/identity-and-data-integrity.md) | `01a059a5-e2b6-71d0-b045-abd010e0f492` |
| Finance and Tax | [finance-and-tax.md](specialists/finance-and-tax.md) | `01a056f1-7e78-7b70-a153-de6ec5bcf18f` |
| Market Data | [market-data.md](specialists/market-data.md) | `01a070ed-793e-7360-8575-155af877f4d8` |
| Platform and Release | [platform-and-release.md](specialists/platform-and-release.md) | `01a05ef0-3faa-7b52-ad69-52a851bb56c9` |
| Quality and Security | [quality-and-security.md](specialists/quality-and-security.md) | `01a05777-bcc9-7ed0-b66d-292eff0f6d9c` |

Use `gpt-5.6-luna` with `high` effort for every specialist task.
Keep each task title equal to its role name.
Reuse an existing role task when possible.
Each role can have one active assignment at most.

## Assignment procedure

1. Read the current authority and worktree status.
2. Select one bounded assignment.
3. Record its exact file lease and operational lease on the board.
4. Send the specialist its assignment and stable brief.
5. Review its diff, retained failed proof, final proof, and handoff.
6. Release its lease before dependent work starts.

The current delivery table defines each specialist lease. Earlier setup leases are released.
The Senior alone edits the nine coordination files.
Return specialist reports in the task conversation.
The Senior records accepted results on the board.

Use the [work rules](manager-open-beta.md#work-rules) and [protected state](manager-open-beta.md#protected-state) for all work.
Use the [test commands](manager-open-beta.md#current-test-instructions) only within an active proof lease.
