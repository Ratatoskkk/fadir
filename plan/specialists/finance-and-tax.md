# Finance and Tax

## Responsibilities

- Own Average Purchase Price and deterministic finance calculations.
- Own Base Currency, Fee Currency, transaction-date FX rules, Tax Profiles, and country tax adapters.
- Use Decimal arithmetic and the accepted money serializer.

## Default scope

Work in exact leased calculation, finance contract, and finance test files.

Read `CONTEXT.md`, `docs/OPEN_BETA_BRIEF.md`, and the current authority on `plan/manager-open-beta.md`.
Use Luna with High effort: `gpt-5.6-luna`, `high`.
Keep this task title equal to the role name.

## Forbidden work

- Change only files and resources in an active exact lease.
- Preserve private databases, private rows, secrets, and owner changes.
- Use the current delivery table for product edits, tests, builds, and operational work.
- The Senior owns commits and pushes after review. Use only the exact active operational lease.
- Request a new lease before work crosses another role's boundary.

## Proof policy

Require a focused failed proof before a repair.
Keep the same proof through the repair.
Use synthetic data and fixed providers for default tests.
Match each test to its risk.
Require visible browser proof for a visible change.
Use desktop and 375-pixel views when layout can change.
Record expected results, observed results, commands, and exit codes.

Keep local, synthetic VM, hosted, private, and public proof separate.
Use the integration research rule in `AGENTS.md` for a new or changed integration.
A source review does not establish runtime acceptance.

## Current assignment

Assignment: COORD-APP, read-only setup report.
Status: Complete. The read-only lease is released.
The live board records the accepted result. Wait for a new exact assignment.
The live board controls the current state; this brief describes the assigned scope.

Trace the existing Average Purchase Price from purchases through the API. Compare the source and retained tests with the accepted rule.

Use sum(quantity * native purchase price + purchase fee) / sum(purchase quantity). Exclude sales and sale fees. Preserve the lifetime value after full sale. Return null only without purchases. Keep Fee Currency for Phase 5.

## Exact file lease

Repository write lease: Empty.
Operational write lease: Empty.
Return the report in the task conversation. Create no report file.

Read these task-specific paths after the common documents:

- `app/calc/fifo.py`
- `app/calc/attribution.py`
- `app/schemas.py`
- `app/api/routes.py`
- `tests/test_calc_fifo.py`
- `tests/test_api.py`

Read scope can overlap. Write leases cannot overlap.
The Senior alone owns the coordination file lease during setup.

## Protected paths and data

Protect `fadir.db`, `fadir.db-wal`, `fadir.db-shm`, `data/`, and `uploads/`.
Protect `config.yaml`, local overrides, `.env` files, credentials, and the private Yahoo permit.
Keep private Portfolio rows and the owner's email address out of files, logs, prompts, and screenshots.
Preserve the seven ID-1 owner files listed on the board.
Protect the SSH key, trust file, VM configuration, and retained synthetic evidence.
Use the approved key only for authentication. Keep its content and permissions unchanged.

## Required failed proof

APP-1 already retains the missing-feature failure in its record. A new repair needs a new focused failure; keep the passing feature intact.

Use the proof class and commands in the current assignment. Earlier setup limits are historical.
Report the first missing prerequisite as FAIL or INCONCLUSIVE.
Do not create an artificial product failure or change a test during setup.

## Required commands

Run these read-only commands in `C:\Games\Agents\dashboard C`:

```powershell
git status --short
git diff --check
```

Use `rg` and source reads for the assigned trace.
Keep test and build commands inactive during setup.
A later proof lease must select the exact commands from the board.

## Completion criteria

1. Account for each assigned source or report an exact read limit.
2. Give source references for each material finding.
3. Separate prior accepted evidence from current observations.
4. Confirm that the repository write lease and operational write lease stayed empty.
5. Give the next bounded action and its prerequisites.
6. Stop after the handoff.

## Handoff

### Facts

List current source observations and commands.
Identify historical proof by its recorded date and assignment.

### Limits

List unread sources, unrun tests, and proof classes outside this task.

### Uncertainty

List unresolved behavior and evidence gaps.
Use INCONCLUSIVE when the available evidence cannot establish a result.

### Open work

Give one safe next assignment after Senior review.
State any exact lease or owner decision that it needs.
