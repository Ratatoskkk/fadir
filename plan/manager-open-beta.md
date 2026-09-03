# faðir open beta manager board

Date: 2026-09-04

This file is the only live work board. The stable role briefs define long-term specialist boundaries.

## Coordination state

- Current phase: 3. PostgreSQL and private data scopes.
- Current status: G3-B independent review of the committed synthetic migration core.
- Active specialist assignments: Quality and Security owns G3-B. The DB-5D lease is released.
- Active file leases: Empty. G3-B is proof-only.
- Proposed next assignment: Select the next bounded product step from the G3-B result.
- Next release gate: G3, PostgreSQL migrations and private data scope acceptance.

## Current review

### DB-5D completion record

- Commit `da86bee` contains only the migration core and its tests.
- The original failed proof reported an absent migration module.
- Two review rounds found validation and proof gaps before acceptance.
- The final standards and specification reviews passed independently.
- The Senior Agent reproduced 18 focused tests and 272 full offline tests.
- The suite reported one existing Starlette deprecation warning.
- The diff check passed, and the workspace was clean after the commit.
- This acceptance covers synthetic dependencies only, not real database adapters or PostgreSQL.
- G3-B will classify the committed core separately from overall G3 readiness.

### Facts

- `CONTEXT.md` defines Average Purchase Price and the open beta terms.
- `docs/OPEN_BETA_BRIEF.md` sets the nine delivery phases.
- ADR 0010 keeps direct Yahoo access for the beta. The owner holds the permit outside the repository.
- The APP-1 diff contains only its six leased files.
- APP-1 adds `average_purchase_price_native` to the calculation and portfolio API.
- The APP-1 failed proof had four missing-feature failures.
- The specialist focused suite passed 57 tests.
- The specialist full offline suite passed 223 tests.
- The manager re-ran both suites with the same pass results.
- Both passing suites reported one Starlette deprecation warning.
- The APP-2 diff contains only `frontend/src/components/PositionsTable.jsx`.
- APP-2 adds the sortable `Ort. alış` column and the lifetime-rule footnote.
- The APP-2 source proof failed before the edit and passed after it.
- The APP-2 frontend build passed.
- The APP-2 focused suite passed 57 tests.
- Local browser proof passed at 1440 by 900 and 375 by 812.
- The browser proof used synthetic data and made no provider refresh call.
- The manager reproduced the source check, build, focused suite, and 223-test full suite.
- Quality and Security classified G2 as PASS.
- Quality reviewed all seven APP-1 and APP-2 files.
- Quality passed 57 focused tests and 223 full offline tests.
- Quality passed the frontend build and `git diff --check`.
- Quality passed independent browser proof at 1440 by 900 and 375 by 812.
- Quality used synthetic data and did not edit repository files.
- The current owner documents are untracked. They include `CONTEXT.md`, the beta brief, the market report, and all ADR files.
- The README and Makefile define `make test` as the non-network test command.
- The Makefile defines `make test-live` as the network test command.
- Pytest uses a new temporary SQLite database for each database test.
- The private root database and its WAL files exist. The setup pass did not read their rows.
- DB-1 stayed inside `requirements.txt`, `app/db.py`, and `tests/test_db.py`.
- DB-1 preserved `make_engine` as the database module interface.
- DB-1 accepts SQLite paths and full SQLAlchemy URLs.
- DB-1 keeps Decimal adapters and PRAGMA statements inside the SQLite branch.
- The DB-1 failed proof showed the unwanted SQLite prefix and connection options.
- The DB-1 focused suite passed three tests during specialist and manager review.
- The DB-1 full offline suite passed 226 tests during specialist and manager review.
- The manager confirmed that protected SQLite file metadata did not change.
- DB-2 stayed inside its six-file lease.
- The DB-2 failed proof had four missing-framework failures.
- DB-2 added Alembic with no default database URL.
- Every DB-2 migration command requires `FADIR_DATABASE_URL`.
- The DB-2 SQLite migration suite passed four tests during manager review.
- The DB-2 full offline suite passed 230 tests during specialist and manager review.
- PostgreSQL upgrade SQL generated offline without an engine connection.
- `pip check` passed after the approved Alembic and psycopg installation.
- The manager confirmed that protected SQLite file metadata did not change after DB-2 proof.
- DB-3A stayed inside its four-file lease.
- The DB-3A failed proof had 11 expected failures and two accepted passes.
- DB-3A added User, Workspace, and Portfolio domain roots.
- A User can control at most one Workspace.
- More than one Guest Workspace can exist without a User.
- Portfolio names are unique inside one Workspace.
- User and Workspace deletion cascades passed with synthetic data.
- The DB-3A focused suite passed 13 tests during specialist and manager review.
- The DB-3A full offline suite passed 239 tests during specialist and manager review.
- The manager confirmed that protected SQLite file metadata did not change after DB-3A proof.
- DB-3B stayed inside its four-file lease.
- The DB-3B failed proof had eight expected failures and six accepted passes.
- Transaction and Snapshot now have nullable Portfolio ownership keys.
- The DB-3B migration preserved unowned synthetic rows through upgrade and rollback.
- Portfolio deletion cascades to associated Transaction and Snapshot rows.
- Instrument and market cache models remain shared.
- The DB-3B focused suite passed 14 tests during specialist and manager review.
- The DB-3B full offline suite passed 247 tests during specialist and manager review.
- The manager confirmed that protected SQLite file metadata did not change after DB-3B proof.
- DB-4A stayed inside `app/services/portfolio_scope.py` and `tests/test_portfolio_scope.py`.
- The DB-4A failed proof had seven expected failures because the scope module was absent.
- The module validates the Workspace and Portfolio identifiers together.
- The module scopes Transaction and Snapshot reads and mutations by Portfolio.
- Missing and cross-Workspace Portfolios have the same not-found result.
- The DB-4A focused suite passed seven tests during manager review.
- The DB-4A full offline suite passed 254 tests during specialist and manager review.
- The manager confirmed that protected SQLite file metadata did not change after DB-4A proof.
- DB-5A changed no repository file.
- DB-5A classified three prerequisites as PASS and seven as FAIL.
- The focused failure proved that current routes do not use `PortfolioScope`.
- The DB-5A focused suite passed 15 tests during specialist and manager review.
- The DB-5A full offline suite passed 254 tests during specialist and manager review.
- The manager confirmed that protected SQLite file metadata did not change after DB-5A proof.
- DB-5B changed only `docs/PRIVATE_MIGRATION_RUNBOOK.md`.
- The DB-5B failed proof showed that the runbook was absent.
- The runbook contains all 20 required sections.
- The runbook contains 81 explicit owner approval markers.
- The runbook defines synthetic, private, hosted, and public proof boundaries.
- The runbook performs no migration action and selects no owner value.
- The manager confirmed that protected SQLite file metadata did not change after DB-5B review.
- Quality and Security classified G3 as NOT READY.
- The G3-A focused Phase 3 suite passed 31 tests.
- The G3-A full offline suite passed 254 tests.
- The manager reproduced both pass results.
- Quality confirmed all 20 runbook sections and 81 owner approval markers.
- Quality confirmed the accepted `NO_ROUTE_SCOPE_USE` Phase 4 limit.
- Quality found no new Phase 3 defect.
- Protected SQLite file metadata stayed unchanged after G3-A proof.
- The owner approved runbook Gate 0 on 2026-09-01.
- Gate 0 accepts the runbook as the control plan only.
- Gate 0 does not approve private access, secrets, database connections, migration work, or destructive actions.
- DB-5C changed only `docs/PRIVATE_MIGRATION_RUNBOOK.md`.
- DB-5C recorded Gate 0 approval and kept Gates 1 through 8 pending.
- DB-5C added 18 Gate 1 recommendation markers.
- DB-5C recommends a disposable PostgreSQL target with a temporary SQLite source.
- DB-5C recommends one deep migration module with injected connections and a structured result.
- DB-5C proposes a two-file future implementation lease.
- The manager found no local Docker, Podman, PostgreSQL client, or PostgreSQL control tool.
- Protected SQLite file metadata stayed unchanged after DB-5C review.
- PLAT-PG-1 changed no repository file or host resource.
- PLAT-PG-1 confirmed that Docker, Podman, `psql`, and `pg_ctl` are absent.
- PLAT-PG-1 confirmed that WSL and the Windows SSH client are available.
- Three WSL distributions exist, but no Ubuntu distribution exists.
- No Hyper-V VM exists, and no process listens on local port 5432.
- PLAT-PG-1 did not prove protected root metadata equality.
- The owner requires complete agent command control for each agent-run Linux environment.
- A Hyper-V console without an agent-accessible command path does not meet that requirement.
- PLAT-CTRL-1 changed no repository file or host resource.
- PLAT-CTRL-1 defined a WSL2 command path and a Hyper-V SSH command path.
- The Hyper-V path uses strict host-key checks, one dedicated key, limited password-free sudo, and exact synthetic transfers.
- The recovery path uses Windows Hyper-V commands to inspect, restart, or restore the VM without its console.
- The owner permits a VM when the agent-control gate proves normal and recovery access.
- Quality and Security classified G3-CTRL-1 as FAIL.
- The focused failure is the unsafe `ssh-keygen` empty-passphrase argument.
- Quality found 17 command, access, transfer, sudo, and recovery defects.
- The initial and final Git states match after the Quality review.
- The Quality review changed no repository file or host resource.
- Protected root metadata stayed unchanged during the Quality command proof.
- PLAT-CTRL-2 returned a revised design and changed no repository file or host resource.
- The owner requires scenario research when the plan selects a new integration.
- Official Microsoft, OpenSSH, sudo, Ubuntu, GNU, and PostgreSQL sources were reviewed on 2026-09-02.
- The official-source review found 17 new blocking defects in PLAT-CTRL-2.
- The user private-key ACL contradicts Microsoft Win32 OpenSSH guidance.
- The process helpers can deadlock because they read redirected streams in sequence.
- OpenSSH first-value behavior can defeat the late configuration snippet.
- The SSH design does not disable StreamLocal forwarding.
- The transfer directory creation step is absent.
- `pg_restore --list` does not establish archive trust.
- The restore targets do not use `template0` or `--single-transaction`.
- Hyper-V guest IP reporting is not reliable as the only address proof.
- The WSL mount check does not create a hard isolation boundary.
- PLAT-CTRL-3 returned a revised control design for all 17 source defects.
- The revised design requires PowerShell 7 and asynchronous process stream reads.
- It limits each private key to the current user and disables all SSH forwarding.
- It defines fixed PostgreSQL, transfer, address, backup, and checkpoint controls.
- It keeps archive trust separate from checksums and archive parsing.
- PLAT-CTRL-3 changed no repository file or host resource.
- The initial and final Git states match after PLAT-CTRL-3.
- G3-CTRL-2 classified the revised design as FAIL.
- Quality classified 13 source defects as resolved.
- Quality classified three source defects as unresolved.
- Quality found one new address-control blocker.
- Quality found 21 missing executable or proof controls.
- Initial and final Git states match after G3-CTRL-2.
- Protected root metadata stayed unchanged during G3-CTRL-2.
- G3-CTRL-2 changed no repository file or host resource.
- PLAT-CTRL-4 defines all four custom control programs.
- It defines exact dispatch, transfer, checksum, PostgreSQL, address, storage, and timeout controls.
- It uses PostgreSQL 16 and Ubuntu 24.04 official version sources.
- The production-checkpoint event proof remains blocked because Microsoft documents no accepted event schema.
- Initial and final Git states match after PLAT-CTRL-4.
- PLAT-CTRL-4 changed no repository file or host resource.
- G3-CTRL-3 classified every proposed control program as FAIL.
- Quality found permission, repeat-operation, concurrency, process, ACL, SSH, and recovery defects.
- Only the process-timeout negative test had an executable test command.
- The other 23 negative-test entries were input descriptions only.
- Initial and final Git states match after G3-CTRL-3.
- Protected root metadata stayed unchanged during G3-CTRL-3.
- G3-CTRL-3 changed no repository file or host resource.
- The owner approved the disposable Hyper-V lab strategy.
- The owner approved a read-only preflight only.
- The owner withheld approval for VM creation or any host change.
- Ubuntu Server 24.04.4 LTS boots from the approved VHDX at `192.168.247.10`.
- The installed guest uses host name `fadir-control-lab-01`.
- The `fadir-agent` password is locked and its approved public key is installed with mode `600`.
- The VM console and Windows host reported the same ED25519 host-key fingerprint.
- Win32 OpenSSH 9.5 `ssh-keyscan` reproduced its documented unsupported-KEX defect.
- Normal `ssh.exe` captured the host key in an isolated file before authentication.
- Strict key-only SSH passed with passwords, keyboard authentication, unknown hosts, and other private keys disabled.
- The stable trust file is `C:\ProgramData\fadir-agent-control\lab_known_hosts`.
- The stable SSH proof returned user `fadir-agent`, host `fadir-control-lab-01`, and exit code `0`.
- `sudo -n true` failed with exit code `1`; the agent account has no non-interactive administrator path.

### Limits

- G2 is a local gate. It provides no hosted or public proof.
- G2 browser proof covered only the Codex in-app Chromium browser.
- The direct Yahoo permit remains outside the repository.
- The market report recommends a provider seam in two later sections.
- ADR 0010 and the beta brief defer that seam. Those two records control the beta plan.
- Current routes do not use the Portfolio scope module.
- DB-4A provides local SQLite proof only.
- DB-5A did not connect to the private SQLite database or PostgreSQL.
- DB-5A provides source review and synthetic local proof only.
- DB-5B is a draft. It provides no private, hosted, or public proof.
- G3-A provides local and synthetic proof only.
- G3 cannot pass before the owner approves a dry run and rollback plan.
- DB-5C provides document proof only.
- The disposable PostgreSQL target does not exist yet.
- PLAT-PG-1 is a qualified audit because it omitted required protected metadata proof.
- Strict key-only Windows-to-VM command access has passed local lab proof.
- PLAT-CTRL-1 is a qualified design because it did not test WSL, SSH, a VM, PostgreSQL, or recovery.
- Literal 100 percent availability is not possible during host power, Windows, or hardware failure.
- No administrator, restart, checkpoint, PostgreSQL, hosted, private, or public pass exists.
- Official-source research is document evidence. It does not prove live behavior.
- PLAT-CTRL-3 did not prove protected root metadata equality directly.
- PLAT-CTRL-3 did not test a key, ACL, SSH server, wrapper, VM, database, or checkpoint.
- PLAT-CTRL-3 contained prose requirements for custom wrappers, not complete wrapper code.
- G3-CTRL-2 provides local design proof only.
- No dispatcher, wrapper, transfer, database, checkpoint, or recovery control has live proof.
- PLAT-CTRL-4 provides design evidence only.
- PLAT-CTRL-4 did not prove protected root metadata equality directly.
- G3-CTRL-3 provides local design evidence only.
- No proposed program ran in Linux.
- No limited provision proof is approved.

### Uncertainty

- Native touch gestures and screen-reader announcements remain untested.
- The target PostgreSQL service and its secret remain owner choices.
- The private owner, Workspace, and Portfolio mapping remains an owner choice.
- A WAL-consistent private snapshot and rollback method needs owner approval.
- Alembic 1.19.1 and psycopg 3.3.5 are installed only in the local virtual environment.
- Later infrastructure details need owner choices before Phase 8.
- The static VM address still needs an owner choice and a conflict check.
- The production-checkpoint type proof remains unresolved.
- The PLAT-CTRL-4 program text needs an independent feasibility and security review.
- Linux directory permissions and PostgreSQL file creation need direct review.
- The production-checkpoint evidence rule still blocks a live control pass.
- The backup and review directory permissions cannot support the proposed PostgreSQL writes.
- Backup and restore actions are not repeat-safe.
- Transfer and database actions have no concurrency locks.
- The paper-only process has reached diminishing returns.

### Open work

- Gate 1 target, connection window, rehearsal limits, rollback proof, and evidence rules remain open.
- A disposable SSH-controlled Hyper-V Ubuntu VM is the proposed Phase 3 rehearsal path.
- A dedicated WSL2 Ubuntu distribution remains the local fallback path.
- LAB-PREFLIGHT-1 must recommend exact VM, disk, network, ISO, and bootstrap values.
- The owner must approve that exact provision plan before any host change.
- Keep product files, secrets, and private data outside the lab until administrator and recovery controls pass review.
- A later owner-approved task must prove the synthetic rehearsal and rollback plan.
- Phase 4 request identity must integrate routes with the accepted scope module.

## Work rules

1. Review `git status --short` before each lease.
2. Treat every current change outside the lease as owner work.
3. Give each assignment an exact and non-overlapping file lease.
4. Give each specialist one active assignment at most.
5. Apply the integration research rule from `AGENTS.md` when the plan selects a new integration.
6. Use documented tool limits to shape the first test plan.
7. Require a focused failed proof before a repair.
8. Keep the failed proof in the final diff.
9. Require tests that match the risk.
10. Require visible browser proof for a visible interface change.
11. Review each diff, proof, command result, and handoff before dependent work starts.
12. Keep local, hosted, and public proof separate.
13. Stop for an owner choice, a secret, a public change, or a destructive action.
14. The Senior Agent can commit accepted agent work after review.
15. Get owner approval before a push, deployment, public change, destructive action, or external service call.

## Protected state

Protect these paths and data during all phases:

- `fadir.db`
- `fadir.db-wal`
- `fadir.db-shm`
- `data/`
- `uploads/`, if it exists
- `config.local.yaml`, if it exists
- `.env`, if it exists
- Environment secrets
- The private Yahoo permit
- Private Portfolio rows
- The owner's email address

Use isolated test data. Do not copy private rows into fixtures, logs, reports, prompts, screenshots, or repository files.

## Phase plan and gates

| Order | Phase | Lead roles | Depends on | Release gate |
|---|---|---|---|---|
| 1 | Coordination baseline | Senior Agent | None | G1: All coordination files agree with the beta brief. The first conflict-free lease awaits owner approval. |
| 2 | Average Purchase Price | Finance and Tax; Product Experience; Quality and Security | G1 | G2: The formula, API, detailed table, tests, and visible browser proof pass locally. |
| 3 | PostgreSQL and private data scopes | Identity and Data Integrity; Quality and Security | G2 | G3: Migrations prove User, Workspace, and Portfolio scope. A private migration has an approved dry run and rollback plan. |
| 4 | Guest access and identity | Identity and Data Integrity; Product Experience; Quality and Security | G3 | G4: Guest, Google, magic link, Claim, Transfer, Merge, and session proofs pass. |
| 5 | Multiple Portfolios, currencies, and Tax Profiles | Finance and Tax; Identity and Data Integrity; Product Experience | G4 | G5: Portfolio scope, Base Currency, Fee Currency, and Turkey Tax Profile proofs pass. |
| 6 | Public market-data behavior | Market Data; Quality and Security | G5 | G6: Yahoo permission, symbols, prices, FX, caches, quotas, timestamps, and corporate actions pass for public traffic. |
| 7 | Security, privacy, export, deletion, and abuse controls | Quality and Security; Identity and Data Integrity | G6 | G7: Isolation, sessions, privacy, deletion, export, retention, Guest quotas, and abuse controls pass. |
| 8 | Hyper-V VM and public release | Platform and Release; Quality and Security | G7, owner approval, and agent-control proof | G8: Agent control, VM, PostgreSQL operations, tunnel, services, backup, restore, and release checks pass on the host. |
| 9 | Full acceptance and recovery proof | Quality and Security; Platform and Release; all other roles as needed | G8 | G9: Local, browser, hosted, public, backup, and recovery evidence passes with clear proof labels. |

## Dependency map

- APP-1 defines the calculation and API contract.
- APP-2 depends on APP-1 acceptance. It adds the detailed table column and browser proof.
- Phase 3 depends on G2. It changes the data foundation after the first isolated product change.
- Phase 4 depends on User, Workspace, and Portfolio scope from Phase 3.
- Phase 5 depends on both data scope and identity transitions.
- Phase 6 depends on stable Portfolio currencies and public request shapes.
- Phase 7 depends on all private data and public traffic paths.
- Phase 8 depends on all local security and product gates.
- Phase 9 starts only after a hosted release exists.

## Proof classes

### Research proof

Research proof applies when the plan selects a new integration.

It uses current official primary documentation to select the best path for the current scenario.

It records the source URL, retrieval date, version scope, and tool limits that shape the first test plan.

Routine tests for an accepted integration do not need new research.

Research proof can block an unsafe design or test. It cannot replace local, hosted, private, or public proof.

### Local proof

Local proof uses isolated data and local processes. It includes unit, API, integration, build, and visible local browser evidence.

### Hosted proof

Hosted proof runs on the approved VM. It includes service, PostgreSQL, backup, restore, and private network evidence.

### Public proof

Public proof uses the approved Cloudflare path. It includes public TLS, ingress, rate, privacy, and browser evidence.

Each report must name its proof class. A lower proof class cannot satisfy a higher gate.

## Active leases

No specialist has an active lease.

### Completed lease: APP-1

Role: Finance and Tax

Status: Accepted and released.

Exact files:

- `app/calc/fifo.py`
- `app/calc/attribution.py`
- `app/schemas.py`
- `app/api/routes.py`
- `tests/test_calc_fifo.py`
- `tests/test_api.py`

The APP-1 changes remain as owner work. Future leases must not include these files without a new reason.

### Completed lease: APP-2

Role: Product Experience

Status: Accepted and released.

Exact file:

- `frontend/src/components/PositionsTable.jsx`

The APP-2 change remains as owner work. Future leases must not include this file without a new reason.

APP-2 adds the Average Purchase Price column and local visible browser proof. It does not change the API contract or styles.

### Completed lease: G2 review

Role: Quality and Security

Status: PASS. The empty lease is released.

Exact file lease: Empty. This is a read-only proof assignment.

Quality edited no repository file.

### Completed lease: DB-1

Role: Identity and Data Integrity

Status: Accepted and released.

Exact files:

- `requirements.txt`
- `app/db.py`
- `tests/test_db.py`

The DB-1 changes remain as owner work. Future leases must not include these files without a new reason.

DB-1 creates the database engine seam. It accepts a SQLite path or a PostgreSQL URL through the existing `make_engine` interface.

DB-1 does not wire configuration, add migrations, change models, connect to PostgreSQL, or move private data.

### Completed lease: DB-2

Role: Identity and Data Integrity

Status: Accepted and released.

Exact files:

- `requirements-migrate.txt`
- `alembic.ini`
- `migrations/env.py`
- `migrations/script.py.mako`
- `migrations/versions/0001_current_schema_baseline.py`
- `tests/test_migrations.py`

The DB-2 changes remain as owner work. Future leases must not include these files without a new reason.

DB-2 adds an Alembic framework and a static baseline for the current six tables.

DB-2 requires an explicit `FADIR_DATABASE_URL`. It must not fall back to `fadir.db`.

DB-2 can install only Alembic and psycopg after the owner dispatches its approved prompt.

DB-2 does not edit models, engine code, configuration, callers, private data, or deployment state.

### Completed lease: DB-3A

Role: Identity and Data Integrity

Status: Accepted and released.

Exact files:

- `app/models.py`
- `migrations/versions/0002_user_workspace_portfolio_roots.py`
- `tests/test_data_scope_models.py`
- `tests/test_migrations.py`

The DB-3A changes remain as owner work. Future leases must not include these files without a new reason.

`tests/test_migrations.py` is accepted DB-2 work. DB-3A can extend it only for the new head revision.

DB-3A adds the User, Workspace, and Portfolio domain roots. It does not add ownership keys to current private rows.

DB-3A does not edit routes, services, configuration, current migration files, or private data.

### Completed lease: DB-3B

Role: Identity and Data Integrity

Status: Accepted and released.

Exact files:

- `app/models.py`
- `migrations/versions/0003_portfolio_ownership_keys.py`
- `tests/test_portfolio_ownership_models.py`
- `tests/test_migrations.py`

The DB-3B changes remain as owner work. Future leases must not include these files without a new reason.

`app/models.py` and `tests/test_migrations.py` contain accepted work. DB-3B can extend them only for Portfolio ownership keys.

DB-3B adds nullable transition keys to `Transaction` and `Snapshot`.

DB-3B does not backfill private rows, enforce route scope, or change the current Snapshot primary key.

### Proposed lease: DB-4A

Role: Identity and Data Integrity

Status: Proposed. Do not start before owner approval.

Exact files:

- `app/services/portfolio_scope.py`
- `tests/test_portfolio_scope.py`

Both paths are absent in the current worktree. This lease does not cross accepted work.

DB-4A adds one Portfolio scope module for Transaction and Snapshot reads and mutations.

DB-4A proves denial across two Workspaces. It does not edit or integrate routes.

## APP-1 trace

### Facts

- `app/calc/fifo.py` includes purchase fees in each open lot cost.
- A sale removes consumed cost from the open lot totals.
- A fully sold Stock Group keeps realized disposal data.
- A fully sold Stock Group loses its open cost basis and weighted FX average.
- `app/calc/attribution.py` builds each `PositionMetrics` value from the lot book.
- `app/schemas.py` has no Average Purchase Price field on `PositionOut`.
- `app/api/routes.py` maps `PositionMetrics` to the portfolio response.
- `frontend/src/components/PositionsTable.jsx` has no Average Purchase Price column.
- Current FIFO tests cover purchase fees, partial sales, and a zero position.
- Current API tests check the portfolio shape and string money values.

### Limits

- APP-1 does not edit the React interface.
- APP-1 does not add Fee Currency.
- APP-1 does not change a database model or migration.
- APP-1 does not use private Portfolio data.

### Uncertainty

- The final Turkish column label and table width need APP-2 browser review.
- The manager accepted `average_purchase_price_native` as the API field.

### Open work

- APP-1 completed the calculation and API contract.
- APP-2 must add the detailed table column after APP-1 acceptance.
- Quality and Security must review the combined G2 evidence.

## APP-1 accepted rule

- Return Average Purchase Price for every Stock Group.
- Use all purchase quantities and native-currency purchase costs.
- Include each purchase fee.
- Exclude every sale and sale fee.
- Keep the lifetime value after the open quantity reaches zero.
- Return no value only when the group has no purchase.
- Keep Fee Currency outside APP-1.

The proposed formula is:

`sum(purchase quantity * purchase price + purchase fee) / sum(purchase quantity)`

The proposed API field is `average_purchase_price_native`. It must use the existing string money serializer.

## APP-1 failed proof and commands

The specialist must first add focused tests to the leased test files. The tests must fail because the calculation and API field do not exist.

The failed proof must cover these cases:

- Multiple purchases with different quantities and prices
- Purchase fees
- A partial sale that does not change the lifetime average
- A full sale that keeps the lifetime average
- API string serialization for an open and a fully sold Stock Group

Run this focused command before and after the repair:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_calc_fifo.py tests/test_api.py -q
```

Run this local regression command after the focused proof passes:

```powershell
.venv\Scripts\python.exe -m pytest -q
```

Do not run `make test-live` without owner approval. It contacts Yahoo.

## APP-1 completion criteria

- The focused proof fails for the missing behavior before product edits.
- The same focused proof passes after the repair.
- The full non-network suite passes.
- The diff contains only the six leased files.
- The API keeps Decimal values as JSON strings.
- The handoff separates Facts, Limits, Uncertainty, and Open work.
- The specialist makes no commit or external call.

## APP-1 acceptance

### Facts

- The first proof failed because the calculation property and API field did not exist.
- The formula includes purchase prices and purchase fees.
- Sales and sale fees do not change the lifetime average.
- A fully sold Stock Group keeps the value.
- The API serializes the value as a JSON string.
- The focused suite passed 57 tests.
- The full offline suite passed 223 tests.
- The manager reproduced both pass results.
- The diff stays inside the six-file lease.

### Limits

- The React table does not show the value yet.
- No browser, hosted, or public proof exists.
- The API keeps the existing Decimal scale.

### Uncertainty

- No APP-1 arithmetic uncertainty remains.
- APP-2 must prove table width and the compact Turkish label.

### Open work

- Product Experience must complete APP-2.
- Quality and Security must review the combined G2 evidence.

## APP-2 accepted behavior

- Add one sortable `Ort. alış` column after `Fiyat`.
- Use `average_purchase_price_native` from the accepted API contract.
- Format the value in the Stock Group native currency.
- Show `—` only when the API value is `null`.
- Show the value even when current market data for the row failed.
- Keep the value visible for a fully sold Stock Group.
- Keep the footer column spans aligned.
- Explain the lifetime rule in the table footnote.
- Keep Fee Currency outside APP-2.

## APP-2 proof and commands

Before the edit, preserve a focused source failure and a visible local browser failure in the task record.

The browser proof must use synthetic data in a fresh temporary database. It must contain one open group and one fully sold group.

The specialist must stub all external provider calls. The specialist must not use the private database or a current private server.

Run the frontend build and the accepted APP-1 focused suite after the edit.

Prove the table at a desktop viewport and at 375 pixels. Prove the column, native currency, full-sale value, sorting, and horizontal access.

## APP-2 acceptance

### Facts

- The source proof failed before the edit because the table did not use the API field.
- The pre-edit browser proof showed 14 headers and no `Ort. alış` column.
- The final source proof passed.
- The frontend build passed.
- The focused suite passed 57 tests.
- The full offline suite passed 223 tests during manager review.
- Desktop proof passed at 1440 by 900.
- Mobile proof passed at 375 by 812.
- Open and fully sold Stock Groups showed native-currency values.
- Sorting passed in both directions.
- Header, row, footer, and frozen-column alignment passed.
- Horizontal access passed on the mobile viewport.
- The proof used a synthetic temporary database.
- The proof made no provider refresh call.
- All owned processes stopped, and the temporary proof files were removed.

### Limits

- Browser proof covered only the Codex in-app Chromium browser.
- Hosted and public proof remain outside Phase 2.

### Uncertainty

- Native touch gestures remain untested.
- Screen-reader announcements remain untested.

### Open work

- Quality and Security completed the proof-only G2 review.
- G2 passed, so Phase 3 can start.

## G2 acceptance

### Facts

- Quality and Security classified G2 as PASS.
- The review accounted for all seven changed product and test files.
- Both accepted failed proofs remain in the diff.
- The focused suite passed 57 tests.
- The full offline suite passed 223 tests.
- The frontend build passed with 840 transformed modules.
- Independent desktop and mobile browser proof passed.
- The proof covered native currency, full-sale retention, null display, sorting, alignment, and mobile access.
- The proof used a fresh synthetic database and blocked provider calls.
- Quality stopped all owned processes and removed all temporary proof files.

### Limits

- G2 is local proof only.
- Browser proof covered only the Codex in-app Chromium browser.
- Native touch gestures and screen-reader announcements remain untested.

### Uncertainty

- No unresolved G2 calculation, API, table, sort, or alignment behavior remains.

### Open work

- Phase 3 starts with DB-1.

## Phase 3 assignment sequence

1. DB-1 adds the database engine seam for SQLite paths and PostgreSQL URLs.
2. DB-2 adds the migration framework and a baseline migration.
3. DB-3A adds the User, Workspace, and Portfolio domain roots.
4. DB-3B adds Portfolio ownership keys to current private rows.
5. DB-4A adds one Portfolio scope module with two-Workspace denial proof.
6. DB-5 prepares the private migration dry run, rollback plan, and owner approval gate.

Each assignment needs a new worktree review and an exact lease. No assignment can use private rows as test data.

## DB-1 trace

### Facts

- `app/db.py` prefixes every engine target with `sqlite+pysqlite:///`.
- SQLite Decimal adapters and PRAGMA statements apply to every current engine.
- `get_engine`, `session_scope`, and `get_session` form a small caller interface.
- No migration directory or migration tool exists.
- `requirements.txt` has no PostgreSQL driver.
- The current virtual environment has no `psycopg` or `alembic` package.

### Limits

- DB-1 does not change `app/config.py` or a caller.
- DB-1 does not make PostgreSQL the active database.
- DB-1 does not install a package or contact PyPI.
- The PostgreSQL test must not connect to a server.

### Uncertainty

- The PostgreSQL host, database, user, and secret remain owner choices for a later phase.
- The package install proof remains open until the owner approves a package download.

### Open work

- DB-1 must prove the engine target seam.
- DB-2 must add the migration framework after DB-1 acceptance.

## DB-1 accepted behavior

- Keep `make_engine` as the module interface.
- Accept a `Path` or a path-like string as a SQLite database target.
- Accept a full SQLAlchemy URL without rewriting its scheme.
- Apply SQLite Decimal adapters and PRAGMA statements only to SQLite.
- Keep the existing SQLite behavior and caller interface.
- Add `psycopg[binary]>=3.2` to `requirements.txt` without a package download.
- Do not log or display a database password.

## DB-1 failed proof and commands

Add `tests/test_db.py` before the product edit. The first focused run must fail because `make_engine` rewrites a PostgreSQL URL as SQLite.

Use a PostgreSQL URL without a password. Mock engine creation for this test and do not connect to a server.

Prove the existing SQLite path behavior with a fresh temporary database.

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_db.py -q
.venv\Scripts\python.exe -m pytest -q
git diff --check
```

## DB-1 acceptance

### Facts

- The failed proof had one expected failure and one passing SQLite test.
- The failure showed a PostgreSQL URL with an unwanted SQLite prefix and SQLite options.
- The final PostgreSQL mock proof passed without a PostgreSQL connection.
- SQLite path and path-string cases kept Decimal values, foreign keys, and WAL mode.
- The focused suite passed three tests.
- The full offline suite passed 226 tests.
- The manager reproduced both pass results.
- `git diff --check` passed with line-ending warnings in three earlier owner files.
- The manager confirmed that the private SQLite file metadata did not change.

### Limits

- The PostgreSQL driver remains uninstalled.
- No migration framework or baseline exists yet.
- Configuration and callers still select the SQLite path.
- No real PostgreSQL server proof exists.
- This acceptance is local proof only.

### Uncertainty

- Actual psycopg initialization and PostgreSQL server behavior remain untested.
- The private database baseline and rollback path remain untested.

### Open work

- DB-2 added and proved the migration framework with synthetic databases.
- DB-3A must add the User, Workspace, and Portfolio domain roots.
- DB-3B must add Portfolio ownership keys after DB-3A acceptance.

## DB-2 accepted behavior

- Add a separate migration dependency file that includes `requirements.txt`.
- Add Alembic without a private database default.
- Require an explicit `FADIR_DATABASE_URL` for every migration command.
- Add one static baseline revision for the current six model tables.
- Keep revision code independent from future `Base.metadata` changes.
- Support SQLite upgrade and rollback proof with a fresh temporary database.
- Generate PostgreSQL upgrade SQL without a server connection.
- Do not stamp, upgrade, downgrade, or inspect the private database.

## DB-2 failed proof and commands

The specialist must install the two approved packages before the failed proof.

The specialist must then create `tests/test_migrations.py`. The first focused run must fail because the migration framework is absent.

The kept proof must test a fresh SQLite upgrade, schema match, downgrade, second upgrade, and PostgreSQL offline SQL.

Run:

```powershell
.venv\Scripts\python.exe -m pip check
.venv\Scripts\python.exe -m pytest tests/test_migrations.py -q
.venv\Scripts\python.exe -m pytest -q
git diff --check
```

## DB-2 acceptance

### Facts

- The failed proof had four failures because the framework and baseline were absent.
- The migration configuration contains no database URL.
- The migration environment requires `FADIR_DATABASE_URL`.
- The static baseline creates the six current application tables.
- A temporary SQLite database upgraded, downgraded, and upgraded again.
- Schema proof covered columns, keys, unique constraints, checks, and indexes.
- PostgreSQL upgrade SQL generated in offline mode without engine creation.
- The focused migration suite passed four tests.
- The full offline suite passed 230 tests.
- The manager reproduced the package, focused, full, and diff checks.
- Protected SQLite file metadata stayed unchanged.

### Limits

- The application still uses its current configuration and `init_db` path.
- No real PostgreSQL server proof exists.
- No private database migration or stamp exists.
- This acceptance is local proof only.

### Uncertainty

- PostgreSQL upgrade, rollback, and transaction behavior remain untested.
- Hosted Linux package behavior remains untested.
- Minimum package versions can resolve to different future releases.

### Open work

- DB-3A must add the User, Workspace, and Portfolio domain roots.
- DB-3B must add Portfolio ownership keys to private rows.

## DB-3A accepted behavior

- Add a `User` domain root without an email or Login Identity field.
- Let one User control at most one Workspace.
- Let a Workspace remain a Guest Workspace with no User.
- Let one Workspace contain many Portfolios.
- Require each Portfolio name to be unique inside its Workspace.
- Allow the same Portfolio name in different Workspaces.
- Give each Portfolio a three-letter Base Currency with `TRY` as the temporary default.
- Cascade User deletion to its Workspace and Portfolios.
- Cascade Workspace deletion to its Portfolios.
- Keep identity, Guest secrets, sessions, and private-row ownership outside DB-3A.

## DB-3A failed proof and commands

Create `tests/test_data_scope_models.py` and extend `tests/test_migrations.py` before the model or revision edit.

The first focused run must fail because the three domain roots and second revision are absent.

Keep all failed-proof tests through the repair.

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_data_scope_models.py tests/test_migrations.py -q
.venv\Scripts\python.exe -m pytest -q
git diff --check
```

## DB-3A acceptance

### Facts

- The failed proof had 11 expected failures and two accepted DB-2 passes.
- The failures showed the absent roots and second revision.
- The final model defines User, Workspace, and Portfolio relationships.
- Database constraints enforce one Workspace per User and unique Portfolio names per Workspace.
- Synthetic cascade tests passed for User, Workspace, and Portfolio deletion.
- An intermediate test mutated foreign-key metadata. The specialist repaired the test to use a read-only check.
- The focused suite passed 13 tests.
- The full offline suite passed 239 tests.
- The manager reproduced both pass results.
- Protected SQLite file metadata stayed unchanged.

### Limits

- `Transaction` and `Snapshot` have no Portfolio ownership key.
- Routes and configuration remain unchanged.
- `TRY` is an ORM default, not a server default.
- This acceptance is local proof only.

### Uncertainty

- Real PostgreSQL schema and cascade behavior remain untested.
- Portfolio name comparison follows the database collation.
- Case-insensitive name behavior remains open for Phase 5.

### Open work

- DB-3B added transitional Portfolio ownership keys.
- DB-4A must prove Portfolio-scoped queries and mutations through one module.

## DB-3B accepted behavior

- Add nullable `portfolio_id` keys to `Transaction` and `Snapshot`.
- Link both keys to `portfolio.id` with database cascade deletion.
- Add matching ORM relationships without competing transaction orphan ownership.
- Add a Portfolio-aware transaction index.
- Add a Portfolio-aware Snapshot index.
- Keep Instrument, PriceCache, FxCache, and CorporateAction shared.
- Preserve existing unscoped rows with null ownership keys.
- Keep the current Snapshot primary key during this transition.
- Do not backfill private rows or enforce route scope.

## DB-3B failed proof and commands

Create `tests/test_portfolio_ownership_models.py` and extend `tests/test_migrations.py` before product edits.

The first focused run must fail because ownership keys and the third revision are absent.

Keep all failed-proof tests through the repair.

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_portfolio_ownership_models.py tests/test_migrations.py -q
.venv\Scripts\python.exe -m pytest -q
git diff --check
```

## DB-3B acceptance

### Facts

- The failed proof had eight expected failures and six accepted passes.
- The failures showed the absent ownership keys and third revision.
- Transaction and Snapshot have nullable Portfolio foreign keys.
- Both keys use named constraints and database cascade deletion.
- Both private models have Portfolio-aware indexes.
- Existing unowned synthetic rows survived upgrade, downgrade, and second upgrade.
- The final migration schema matches model metadata.
- PostgreSQL offline SQL includes both ownership changes without engine creation.
- The focused suite passed 14 tests.
- The full offline suite passed 247 tests.
- The manager reproduced both pass results.
- Protected SQLite file metadata stayed unchanged.

### Limits

- Both ownership keys remain nullable.
- No private backfill exists.
- Current routes do not use Portfolio scope.
- Snapshot still has a global date primary key.
- This acceptance is local proof only.

### Uncertainty

- Real PostgreSQL migration and cascade behavior remain untested.
- Concurrent writes during a future private backfill remain untested.
- Request identity does not exist yet.

### Open work

- DB-4A must prove one Portfolio scope module across two Workspaces.
- DB-5 must prepare the private migration dry run and rollback plan.

## DB-4A accepted behavior

- Add one deep Portfolio scope module with an explicit Workspace and Portfolio interface.
- Return the same not-found result for a missing Portfolio and a cross-Workspace Portfolio.
- Scope every Transaction and Snapshot read by `portfolio_id`.
- Scope every Transaction and Snapshot mutation by `portfolio_id`.
- Assign ownership to new private rows inside the module.
- Reject a new row that already names another Portfolio.
- Keep transaction control with the caller. The module must not commit.
- Prove isolation with two Workspaces and two Portfolios.
- Keep routes, identity, models, migrations, and private data unchanged.

## DB-4A failed proof and commands

Create `tests/test_portfolio_scope.py` before the module.

The first focused run must fail because the Portfolio scope module is absent.

Keep the failed-proof tests through the repair.

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_portfolio_scope.py -q
.venv\Scripts\python.exe -m pytest -q
git diff --check
```

## DB-4A acceptance

### Facts

- The failed proof had seven expected failures because the module was absent.
- The final module exposes one validated Workspace and Portfolio scope.
- Missing and cross-Workspace Portfolios raise the same error and message.
- Transaction reads use trade date and row identifier order inside one Portfolio.
- Snapshot reads use snapshot date order inside one Portfolio.
- New Transaction and Snapshot rows receive the selected Portfolio identifier.
- Cross-Portfolio, persistent, detached, deleted, and unsupported rows fail closed.
- Delete operations cannot see a row from another Portfolio.
- The module does not commit, roll back, or close the Session.
- The focused suite passed seven tests.
- The full offline suite passed 254 tests.
- The manager reproduced both pass results.
- `git diff --check` passed with warnings in three earlier owner files.
- Protected SQLite file metadata stayed unchanged.

### Limits

- Current routes do not use the module.
- Request identity and Portfolio selection do not exist.
- No private backfill exists.
- No real PostgreSQL proof exists.
- This acceptance is local proof only.

### Uncertainty

- Concurrent Portfolio deletion after scope validation remains untested.
- PostgreSQL query and lock behavior remains untested.
- Route error translation remains undefined.

### Open work

- DB-5A must audit private migration readiness without a private database connection.
- A later owner-approved task must create and prove the dry run and rollback plan.

## DB-5A proposed audit

- Use Identity and Data Integrity for a proof-only readiness audit.
- Use an empty file lease. The specialist must not edit a repository file.
- Inspect code, migrations, tests, Git state, and protected file metadata only.
- Do not connect to the private SQLite database or any PostgreSQL server.
- Do not read a private row, schema, count, database page, WAL page, or secret value.
- Classify each migration prerequisite as PASS, FAIL, or INCONCLUSIVE.
- Identify the first failed prerequisite as the focused failed proof.
- Propose the smallest safe DB-5B lease after the audit.
- Stop when the next action needs private access, a secret, a service, a write freeze, a backup, or an owner choice.

## DB-5A acceptance

### Facts

- The audit changed no repository file.
- The Alembic chain, synthetic rollback proof, and nullable ownership transition passed review.
- Seven migration prerequisites failed.
- The focused failure proved that no current route imports or calls `PortfolioScope`.
- Request identity and Portfolio selection do not exist.
- No WAL-consistent snapshot procedure exists.
- No PostgreSQL target or secret is available.
- No deterministic private owner and Portfolio mapping exists.
- No write freeze, rollback trigger, or restore procedure exists.
- The focused suite passed 15 tests.
- The full offline suite passed 254 tests.
- The manager reproduced both pass results and the focused route failure.
- Protected SQLite file metadata stayed unchanged.

### Limits

- The audit did not connect to the private SQLite database or PostgreSQL.
- The audit did not inspect private schema, rows, counts, pages, or WAL pages.
- The results provide local source and synthetic proof only.

### Uncertainty

- Private data state remains unproved.
- Real PostgreSQL behavior remains unproved.
- Every private migration owner decision remains open.

### Open work

- DB-5B must draft a decision-ready runbook with explicit approval blanks.
- DB-5B must not select an owner value or perform a migration action.

## DB-5B proposed runbook

- Use Identity and Data Integrity.
- Lease only the new `docs/PRIVATE_MIGRATION_RUNBOOK.md` file.
- Record each unresolved choice as `PENDING OWNER APPROVAL`.
- Define the synthetic rehearsal, private dry run, validation, cutover, and rollback stages.
- Separate synthetic, private, hosted, and public proof.
- Do not name a real identity, path, database URL, secret, or private value.
- Do not connect to a database or contact an external service.
- Stop after the draft and wait for owner review.

## DB-5B acceptance

### Facts

- The initial path proof returned `False`.
- The specialist created only `docs/PRIVATE_MIGRATION_RUNBOOK.md`.
- The runbook contains all 20 required sections.
- The runbook defines each migration stage and approval gate.
- The runbook lists four WAL-consistent snapshot choices.
- The runbook does not select a snapshot method.
- Every unresolved value uses `PENDING OWNER APPROVAL`.
- The manager found no real identity, path, database URL, or secret pattern.
- The trailing-whitespace check passed.
- `git diff --check` passed with three earlier line-ending warnings.
- Protected SQLite file metadata stayed unchanged.

### Limits

- The runbook is a draft only.
- No database connection or migration action occurred.
- No private, hosted, or public proof exists.
- The document check did not test a migration tool.

### Uncertainty

- All owner values in the decision table remain open.
- Gate 0 remains unapproved.
- The synthetic rehearsal implementation lease remains open.

### Open work

- G3-A must review the full Phase 3 proof and runbook.
- The owner must review Gate 0 after the G3-A handoff.

## G3-A proposed review

- Use Quality and Security for a proof-only Phase 3 gate review.
- Use an empty file lease.
- Review DB-1 through DB-5B evidence and current files.
- Re-run the focused Phase 3 suite and the full offline suite.
- Confirm the accepted route-scope failure remains visible.
- Review the runbook gates, privacy rules, rollback stops, and proof boundaries.
- Classify G3 as PASS, FAIL, or NOT READY.
- Do not repair code or edit a repository file.
- Do not connect to the private database or PostgreSQL.

## G3-A review result

### Facts

- Quality and Security reviewed every Phase 3 leased file.
- Each accepted failed proof matches its final proof.
- The focused Phase 3 suite passed 31 tests.
- The full offline suite passed 254 tests.
- `git diff --check` passed with three earlier line-ending warnings.
- The accepted route search returned `NO_ROUTE_SCOPE_USE`.
- The runbook contains 20 sections and 81 owner approval markers.
- WAL safety, secret rules, evidence limits, and rollback stops passed review.
- The initial and final Git states match.
- Protected SQLite file metadata stayed unchanged.
- Quality classified G3 as NOT READY.
- The manager reproduced the proof and accepted the result.

### Limits

- No proof connected to the private SQLite database or PostgreSQL.
- No private snapshot or private dry run occurred.
- Real PostgreSQL and hosted Linux behavior remain untested.
- Current routes do not enforce `PortfolioScope`.
- This review provides no private, hosted, or public proof.

### Uncertainty

- All runbook gates remain unapproved.
- The deterministic private-row mapping lacks owner approval.
- The synthetic rehearsal scope and lease remain open.

### Open work

- DB-5C must record the Gate 0 approval in the runbook.
- DB-5C must prepare recommendations for every Gate 1 choice.
- DB-5C must keep Gate 1 and all later gates pending.

## Gate 0 owner decision

### Facts

- The owner approved Gate 0 on 2026-09-01.
- The owner accepted the migration runbook as the control plan only.
- The approval authorizes no database connection or migration action.

### Limits

- Gate 1 and all later gates remain pending.
- Every private migration value remains pending.

### Uncertainty

- The runbook still shows Gate 0 as pending until DB-5C updates its approval record.
- The current model has no Login Identity record for the required Google identity association.

### Open work

- DB-5C must record Gate 0 and prepare a Gate 1 decision proposal.
- The owner must review Gate 1 after DB-5C manager acceptance.

## DB-5C proposed assignment

- Use Identity and Data Integrity.
- Lease only `docs/PRIVATE_MIGRATION_RUNBOOK.md`.
- Record Gate 0 as approved on 2026-09-01.
- State that Gate 0 approves the control plan only.
- Keep the owner decision table, Gate 1, and all later gates pending.
- Add recommendations for the synthetic target, checks, limits, rollback cases, evidence rules, and future implementation lease.
- Mark each recommendation as `RECOMMENDATION ONLY`.
- Record the missing Login Identity model as a Gate 1 constraint.
- Do not perform a migration action or connect to a database.

## DB-5C acceptance

### Facts

- The focused proof found the stale Gate 0 pending status.
- The runbook preserves that stale record as evidence.
- Gate 0 now says `APPROVED 2026-09-01 — CONTROL PLAN ONLY`.
- Gates 1 through 8 remain pending.
- Every private migration value remains pending.
- The runbook compares temporary SQLite and disposable PostgreSQL targets.
- The recommendation selects disposable PostgreSQL as `RECOMMENDATION ONLY`.
- The recommended module accepts source and target connections.
- The recommended module returns a structured result.
- The future lease contains `app/services/private_migration.py` and `tests/test_private_migration.py`.
- The runbook defines eight synthetic rollback cases.
- The runbook defers Google identity validation to Phase 4 as `RECOMMENDATION ONLY`.
- The trailing-whitespace and `git diff --check` checks passed.
- Protected SQLite file metadata stayed unchanged.

### Limits

- No database connection or migration action occurred.
- The Gate 1 choices remain recommendations only.
- No local disposable PostgreSQL tool is available through the current command path.
- This acceptance provides document proof only.

### Uncertainty

- The safe local PostgreSQL provision path remains unknown.
- The current model has no Login Identity record.
- Gate 1 and its connection window remain unapproved.

### Open work

- PLAT-PG-1 finished with a qualified result.
- PLAT-CTRL-1 must define the agent-control design before the owner reviews Gate 1.

## PLAT-PG-1 review

### Facts

- The specialist completed the read-only option audit.
- The initial and final Git states match.
- The audit changed no repository file or host resource.
- WSL, Hyper-V commands, and the Windows SSH client are available.
- Docker, Podman, `psql`, and `pg_ctl` are absent.
- Three WSL distributions exist, but no Ubuntu distribution exists.
- No Hyper-V VM exists.
- No process listens on local port 5432.

### Limits

- The audit omitted the required protected root metadata proof.
- The audit did not start WSL or test a Linux command path.
- The audit did not test SSH, PostgreSQL, a VM network, or cleanup.
- The Hyper-V recommendation does not satisfy the new agent-control requirement by itself.
- All evidence is local host evidence.

### Uncertainty

- A dedicated WSL2 Ubuntu import remains unproved.
- A host-to-VM SSH control path remains unproved.
- Package install, service control, isolation, and cleanup remain unproved.

### Open work

- PLAT-CTRL-1 must define the exact WSL2 and SSH control gates.
- The owner must approve any download, install, start, network, credential, or deletion action.

## PLAT-CTRL-1 review

### Facts

- The specialist completed the read-only control design.
- The initial and final Git states match.
- `wsl`, `ssh`, `ssh-keygen`, `scp`, and Hyper-V commands are available.
- The design gives exact non-interactive WSL2 and SSH command forms.
- The SSH path pins the VM host key and uses one dedicated agent key.
- The SSH path disables password login, root login, terminal allocation, and forwarding.
- The design limits password-free sudo to approved PostgreSQL, log, cleanup, and shutdown commands.
- The design uses Windows Hyper-V commands for restart and checkpoint recovery.
- The task changed no repository file or host resource.

### Limits

- No Ubuntu WSL distribution or Hyper-V VM exists.
- No control gate has passed.
- No SSH key, host key, network, sudo policy, PostgreSQL service, backup, or restore proof exists.
- The specialist did not prove protected root metadata equality.
- The design provides local document evidence only.

### Uncertainty

- PowerShell quoting and OpenSSH option behavior need independent review.
- The minimum safe sudo command set needs independent review.
- Static VM address, virtual switch, firewall, and recovery checkpoint details remain open.
- Host, Windows, power, and hardware failure can still stop all agent access.

### Open work

- G3-CTRL-1 must review the design before any provision task.
- Provision work needs explicit owner approval for every host and external change.

## G3-CTRL-1 proposed review

- Use Quality and Security for a proof-only control design review.
- Use an empty file lease.
- Review the PLAT-CTRL-1 final handoff and current coordination files.
- Check SSH key creation, host-key pinning, BatchMode, limited sudo, exact transfers, and recovery commands.
- Check that no console action is needed after the control gate passes.
- Check that a failed control check blocks product, secret, and private data entry.
- Classify the design as PASS, FAIL, or NOT READY.
- Do not start WSL, create a VM, install a package, create a key, or change a host resource.

## G3-CTRL-1 review result

### Facts

- Quality and Security reviewed the complete PLAT-CTRL-1 handoff.
- The review classified the design as FAIL.
- The unsafe `ssh-keygen` passphrase argument is the focused failed proof.
- The design lacks exact key and known-host ACL commands.
- The design lacks an exact SSH server configuration and validation commands.
- The design lacks exact root-owned sudo rules and negative tests.
- Broad `psql` access can exceed the required task boundary.
- The transfer example does not enforce the local source boundary or compare checksums.
- The PostgreSQL SSH section contains an executable placeholder.
- Checkpoint creation, approval, restore, restart, and post-restore SSH proof are incomplete.
- The review changed no repository file or host resource.

### Limits

- Quality did not create a key, VM, account, network, service, database, or checkpoint.
- Quality did not test WSL, SSH, SCP, sudo, PostgreSQL, or recovery.
- The review provides local design evidence only.

### Uncertainty

- Exact PowerShell native argument behavior still needs safe design.
- The minimum PostgreSQL wrapper and sudo boundary remain undefined.
- The technical synthetic transfer boundary remains undefined.
- VM network, address, package, and checkpoint details remain open.

### Open work

- PLAT-CTRL-2 repaired the Quality defects, but official research found 17 new blockers.
- A second Quality review must pass before any provision task.

## PLAT-CTRL-2 proposed repair

- Use Platform and Release for a design-only repair.
- Use an empty file lease.
- Preserve the G3-CTRL-1 focused failure and defect list.
- Replace the unsafe key command with an exact argument-safe form.
- Add exact Windows ACL, SSH server, forced-command, sudo, checksum, and recovery controls.
- Replace each placeholder with an exact command.
- Add negative tests for root shells, changed arguments, unauthorized transfers, and stale host keys.
- Add separate owner approval stops before checkpoint restore, cleanup, and deletion.
- Do not create a key, start WSL, create a VM, install a package, or change a host resource.

## Official-source review of PLAT-CTRL-2

Retrieval date: 2026-09-02

### Facts

- Modern .NET `ArgumentList` supports an empty argument, but the design must require PowerShell 7.
- Microsoft warns that sequential reads of redirected process streams can deadlock.
- Microsoft Win32 OpenSSH guidance does not permit other users or groups on a user private key.
- OpenSSH uses the first obtained configuration value.
- `DisableForwarding yes` disables TCP, agent, X11, and StreamLocal forwarding.
- A root-owned wrapper can enforce the action allowlist after sudo accepts the wrapper path.
- The transfer design omits creation of its temporary directory.
- PostgreSQL warns that an untrusted dump can execute arbitrary code during restore.
- `template0` creates a clean database, and `--single-transaction` makes a small restore atomic.
- Hyper-V `ProductionOnly` does not fall back to a standard checkpoint.
- Hyper-V guest IP reporting can return no address and cannot be the sole address proof.
- WSL can still mount Windows drives when automatic mounting is disabled.

Official sources:

- [.NET ArgumentList](https://learn.microsoft.com/en-us/dotnet/api/system.diagnostics.processstartinfo.argumentlist)
- [.NET redirected stream warning](https://learn.microsoft.com/en-us/dotnet/api/system.diagnostics.processstartinfo.redirectstandarderror)
- [Microsoft OpenSSH key management](https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh_keymanagement)
- [Win32 OpenSSH file protection](https://github.com/PowerShell/Win32-OpenSSH/wiki/Security-protection-of-various-files-in-win32-openssh)
- [OpenSSH server configuration](https://man.openbsd.org/sshd_config)
- [Ubuntu OpenSSH configuration](https://ubuntu.com/server/docs/how-to/security/openssh-server/)
- [Official sudoers source](https://github.com/sudo-project/sudo/blob/main/docs/sudoers.man.in)
- [PostgreSQL pg_restore](https://www.postgresql.org/docs/current/app-pgrestore.html)
- [PostgreSQL createdb](https://www.postgresql.org/docs/current/app-createdb.html)
- [PostgreSQL dropdb](https://www.postgresql.org/docs/current/app-dropdb.html)
- [Hyper-V checkpoints](https://learn.microsoft.com/en-us/windows-server/virtualization/hyper-v/checkpoints)
- [Hyper-V Ubuntu support](https://learn.microsoft.com/en-us/windows-server/virtualization/hyper-v/supported-ubuntu-virtual-machines-on-hyper-v)
- [Hyper-V guest IP limits](https://learn.microsoft.com/en-us/troubleshoot/windows-server/virtualization/get-vmnetworkadapter-doesnt-report-ip-addresses)
- [WSL configuration](https://learn.microsoft.com/en-us/windows/wsl/wsl-config)
- [WSL file access](https://learn.microsoft.com/en-us/windows/wsl/filesystems)

### Limits

- The research checked documentation and source text only.
- It ran no live command and changed no repository or host resource.
- It did not prove the future Ubuntu, OpenSSH, sudo, PostgreSQL, Hyper-V, or PowerShell versions.

### Uncertainty

- The final Ubuntu LTS version remains open.
- The VM address reservation method remains open.
- The trusted origin of the synthetic PostgreSQL archive remains open.
- The checkpoint disk layout remains open.

### Open work

- PLAT-CTRL-3 returned a revised design for all 17 official-source blockers.
- G3-CTRL-2 reviewed the source matrix and classified the design as FAIL.
- PLAT-CTRL-4 returned a revised design for the remaining blockers.
- G3-CTRL-3 must review that design before any live test.

## PLAT-CTRL-3 proposed repair

- Use Platform and Release for a research-led design repair.
- Use an empty file lease.
- Use official primary documentation to select the safest control path for this Hyper-V, OpenSSH, and PostgreSQL integration.
- Record the tool limits that shape the design and the first test plan.
- Require PowerShell 7 and safe redirected-stream handling.
- Restrict each user private key to its owner only.
- Fix SSH first-value precedence and disable all forwarding.
- Create the transfer directory with exact ownership and mode.
- Define a trusted synthetic archive origin and SQL inspection rule.
- Use `template0`, `--single-transaction`, and an active-connection cleanup rule.
- Remove the undocumented `postgres` account shell change.
- Add a second deterministic VM address proof.
- Keep PostgreSQL recovery proof separate from checkpoint proof.
- Treat WSL as a convenience boundary and reject unsafe checkpoint storage.
- Do not run a live test or change a repository or host resource.

## PLAT-CTRL-3 review result

### Facts

- Platform and Release completed the design-only repair.
- The handoff includes a source matrix for all 17 defects.
- The handoff preserves the private-key ACL contradiction as the failed proof.
- The design uses an empty file lease.
- Initial and final Git states match.
- The task changed no repository file or host resource.

### Limits

- The specialist did not read the requested repository files during the task.
- The specialist did not obtain the complete G3-CTRL-1 handoff independently.
- The specialist did not prove protected root metadata equality directly.
- No proposed control received a live test.
- The design has local document evidence only.

### Uncertainty

- The custom dispatchers and root wrapper do not have complete executable definitions.
- The owner-only private-key ACL needs Win32 OpenSSH proof.
- The fixed VM address needs owner approval and a conflict check.
- Production-checkpoint type evidence remains unresolved.
- Console-free recovery needs an end-to-end proof.

### Open work

- G3-CTRL-2 reviewed the full handoff and classified the design as FAIL.
- PLAT-CTRL-4 is complete for review.
- Provision work remains blocked until G3-CTRL-3 passes.

## G3-CTRL-2 proposed review

- Use Quality and Security for a proof-only design review.
- Use an empty file lease.
- Reuse the accepted 2026-09-02 integration research record.
- Review all 17 source defects against the PLAT-CTRL-3 repair matrix.
- Review every command and each project control.
- Check whether each custom wrapper has an exact executable definition.
- Check the private-key ACL, SSH precedence, forwarding blocks, and host-key proof.
- Check archive trust, PostgreSQL version rules, restore, cleanup, and backup separation.
- Check both VM address proofs and all checkpoint storage limits.
- Classify the design as PASS, FAIL, or NOT READY.
- Do not repair the design or run a live control test.

## G3-CTRL-2 review result

### Facts

- Quality and Security classified PLAT-CTRL-3 as FAIL.
- Thirteen official-source defects are resolved in the design.
- Three defects remain unresolved.
- The fixed-address repair created one new blocker.
- Quality listed 21 missing executable or proof controls.
- Initial and final Git states match.
- Protected root metadata stayed unchanged.
- The review changed no repository file or host resource.

### Limits

- No key, ACL, SSH server, dispatcher, wrapper, sudo rule, or transfer received a live test.
- No WSL distribution or Hyper-V VM started.
- No PostgreSQL, backup, restore, checkpoint, or recovery test ran.
- The review has local design evidence only.

### Uncertainty

- PostgreSQL 16 claims need PostgreSQL 16 source scope.
- The installed Win32 OpenSSH ACL behavior needs live proof.
- Ubuntu SSH socket behavior needs release-specific proof.
- The production-checkpoint event rule needs an exact source and command.
- The static interface, address choice, and conflict check remain open.

### Open work

- PLAT-CTRL-4 defined all four custom control programs.
- It returned a negative-test matrix and missing command sequences.
- G3-CTRL-3 must pass before any provision work.

## PLAT-CTRL-4 proposed repair

- Use Platform and Release for an exact design repair.
- Use an empty file lease.
- Preserve the G3-CTRL-2 failed proof and all 21 blockers.
- Supply complete executable definitions for all four custom control programs.
- Supply exact negative tests for actions, arguments, shells, paths, and transfer limits.
- Define the host-key trust sequence and both checksum commands.
- Define every PostgreSQL action and post-restore command.
- Define the control directory creation and ACL checks.
- Replace fixed addresses with owner-approved parameters and a conflict gate.
- Define the checkpoint event proof and host storage checks.
- Add a process timeout and failure cleanup.
- Use targeted official research only for material version-specific gaps.
- Do not provision, install, or run a live control test.

## PLAT-CTRL-4 review result

### Facts

- Platform and Release returned complete text for all four control programs.
- The design includes exact dispatch, wrapper, transfer, checksum, and PostgreSQL commands.
- It replaces hardcoded addresses with owner inputs and a conflict gate.
- It adds process timeout and process-tree termination.
- It adds control directory, key, known-host, storage, and address checks.
- It uses targeted PostgreSQL 16, Ubuntu 24.04, Win32 OpenSSH, and Hyper-V sources.
- Initial and final Git states match.
- The task changed no repository file or host resource.

### Limits

- The specialist did not read the required repository files independently.
- The specialist did not obtain the G3-CTRL-2 handoff independently.
- The specialist did not prove protected root metadata equality directly.
- No proposed program or command received a live test.
- No key, account, VM, WSL target, database, or checkpoint exists.

### Uncertainty

- Linux user and directory permissions need a command-feasibility review.
- Shell portability and failure cleanup need a command-feasibility review.
- Win32 OpenSSH must accept the key ACL in a live proof.
- Ubuntu SSH socket behavior needs a live proof.
- Production-checkpoint type evidence has no approved event schema.
- Console-free recovery remains unproved.

### Open work

- G3-CTRL-3 must review every program and command sequence.
- Quality must classify the design as PASS, FAIL, or NOT READY.
- Provision work remains blocked.

## G3-CTRL-3 proposed review

- Use Quality and Security for a proof-only design review.
- Use an empty file lease.
- Review the full PLAT-CTRL-4 handoff.
- Reuse the accepted integration and version research.
- Check every program for exact parsing and fail-closed behavior.
- Check Linux users, groups, directories, modes, and file creation rights.
- Check every PostgreSQL action and cleanup boundary.
- Check the PowerShell timeout, stream, input, and disposal paths.
- Check address validation, host-key trust, storage, and checkpoint controls.
- Check every negative test for an exact executable form.
- Separate design readiness from live control proof.
- Do not repair the design or run a live control test.

## G3-CTRL-3 review result

### Facts

- Quality and Security classified the PLAT-CTRL-4 design as FAIL.
- All four control programs failed the review.
- Backup and inspection cannot use the proposed directory permissions.
- Database and transfer actions are not repeat-safe or concurrency-safe.
- The process helper has failed-start, stream, and memory-boundary defects.
- SSH, ACL, address, storage, and recovery command sequences remain incomplete.
- Only one of 24 negative tests has an executable test command.
- Initial and final Git states match.
- Protected root metadata stayed unchanged.
- The review changed no repository file or host resource.

### Limits

- No proposed program ran in a Linux environment.
- No SSH, sudo, transfer, PostgreSQL, checkpoint, or recovery control received a live test.
- The review provides local design evidence only.
- It provides no hosted, private, or public proof.

### Uncertainty

- Some static defects need repair before program installation.
- Other behavior needs a real disposable Linux environment.
- The production-checkpoint event proof has no accepted schema.
- Literal 100 percent access remains impossible during host or hardware failure.

### Open work

- The owner approved the disposable VM lab strategy.
- LAB-PREFLIGHT-1 must return the exact provision proposal.

## Proposed strategy change: disposable VM lab

- Pause PLAT-CTRL-5.
- Create no VM until the owner approves exact host changes.
- Use a separate Generation 2 Hyper-V Ubuntu Server 24.04 LTS lab.
- Keep product files, secrets, private data, and public traffic outside the lab.
- Use one owner-controlled console bootstrap for Ubuntu and the first SSH key.
- Prove key-only SSH from the Windows task shell.
- Prove host-driven VM state checks, restart, and address discovery.
- Use the proven SSH path to repair and test the control programs inside the lab.
- Use synthetic files and a synthetic PostgreSQL database only.
- Rebuild or delete the disposable lab if its bootstrap or control proof fails.
- Keep final production acceptance separate from lab proof.

### Lab access target

- Agents have command access whenever the Windows host, Hyper-V service, network path, and VM are available.
- The Windows host provides recovery when guest SSH fails.
- A host outage, power loss, or hardware failure remains outside the access target.
- The lab is not a hosted or public pass.

## LAB-PREFLIGHT-1 approved preflight

- Use Platform and Release for a read-only host and source audit.
- Use an empty file lease.
- Use a read-only host lease.
- Research the new Hyper-V internal-switch and NAT integration in current official documentation.
- Confirm the current Ubuntu Server 24.04 LTS ISO and checksum source.
- Inspect Hyper-V readiness, elevation, host capacity, candidate storage, and exact-name conflicts.
- Inspect network and route overlap without reporting unrelated addresses or names.
- Recommend one exact VM name, disk path, switch name, NAT name, subnet, host address, and guest address.
- Recommend exact CPU, memory, disk, Secure Boot, and checkpoint settings.
- Define the one-time console bootstrap and the first Windows-to-VM SSH proof.
- Define exact rollback and cleanup targets.
- Change no repository file or host resource.
- Stop before any download, directory creation, VM creation, network change, key creation, or service change.

## LAB-PREFLIGHT-1 review result

### Facts

- Platform and Release completed the read-only preflight.
- The initial and final Git states match.
- Protected root metadata stayed unchanged.
- The task changed no repository file or host resource.
- The host has 28 logical processors and about 34.2 GB of memory.
- The C drive had about 196.9 GB free during the audit.
- Hyper-V and its management services are available.
- No Hyper-V VM or WinNAT object existed during the audit.
- The shell was not elevated.
- The proposed VM, switch, NAT, VHDX, and ISO names had no conflict.
- `192.168.247.0/24` had no observed route, address, or NAT overlap.
- The proposed host and guest addresses had no observed conflict.
- Ubuntu publishes the proposed 24.04.4 Server ISO.
- The manager confirmed its SHA-256 value from Ubuntu on 2026-09-02.
- Microsoft supports Ubuntu 24.04 on Hyper-V Generation 2.
- Microsoft identifies the Linux Secure Boot template as `MicrosoftUEFICertificateAuthority`.
- Microsoft documents one WinNAT network per host.
- The owner approved the proposed resource values and provision direction.
- The owner reported `IsAdministrator=True` from the elevated Codex CLI on 2026-09-02.

### Limits

- The preflight ran no elevated command.
- It did not download an ISO or create a host resource.
- It did not prove SSH, NAT, Secure Boot, checkpoints, or recovery.
- Address silence does not prove global address availability.
- The proposed static MAC needs a final exact-name conflict check.
- The plan gives local evidence only.

### Uncertainty

- The guest DNS server remains open.
- The installer will reveal the initial guest interface name.
- The proposed interface rename needs an exact Netplan rule.
- The bootstrap account needs an owner-held secret.
- The agent account must remain password-locked.
- The Windows key directory needs an exact owner-only ACL.
- The rollback address removal must name the exact lab adapter.

### Open work

- Dispatch LAB-PROVISION-1A-CONT. Preserve the accepted key resources and stop at the first Ubuntu installer page.
- The owner must enter the bootstrap secret at the VM console.
- LAB-PROVISION-1B must prove strict key-only SSH before other lab work.
- Select DNS before the guest contacts an Ubuntu package service.
- Keep every rollback and destructive action behind a separate approval.

## LAB-PROVISION-1A proposed assignment

- Use Platform and Release for the host-side lab build.
- Use an empty repository file lease.
- Use only the exact host resource lease in the stable specialist brief.
- Require an elevated shell before the first state change.
- Preserve the missing-resource and missing-SSH failed proof.
- Download only the approved Ubuntu ISO from the official Ubuntu host.
- Verify the exact SHA-256 value before VM creation.
- Create the approved directories, key, ACL, switch, host address, NAT object, VHDX, and VM.
- Keep the agent account password-locked in the later console stage.
- Start the VM and open its console at the installer.
- Stop before the owner enters the bootstrap secret.
- Do not install a package, create a checkpoint, or run a recovery test.
- Do not use a product file, secret, private row, or public service.
- Report every created resource and every partial failure.
- Leave failed partial resources in place until the owner approves cleanup.

## LAB-PROVISION-1A attempt 1 review

### Facts

- PowerShell 7.6.5 and administrator checks passed.
- The focused missing-resource proof passed before the first state change.
- The task created only the approved control directory and ED25519 key pair.
- The directory has three explicit ACL rules and inheritance disabled.
- The private key has one explicit ACL rule and inheritance disabled.
- The ACL verification compared translated account names with SID text and returned false.
- No ISO, switch, NAT object, VHDX, or VM was created.
- Protected metadata and the Git state stayed unchanged.

### Limits

- The false ACL comparison does not prove that the ACL is unsafe.
- No installer, SSH, NAT, VM, recovery, hosted, public, or private proof exists.
- The three partial resources remain in place.

### Uncertainty

- The actual owner SIDs and access-rule SIDs need direct read-only proof.
- The current ACL can be correct or incorrect.

### Open work

- Run PLAT-ACL-DIAG-1 with an empty file lease and a three-path read lease.
- Keep repair and cleanup outside the diagnosis task.

## PLAT-ACL-DIAG-1 proposed assignment

- Use Platform and Release for a proof-only ACL diagnosis.
- Use an empty repository file lease.
- Read only ACL and root item metadata for the existing control directory and key pair.
- Convert each owner and access identity to `SecurityIdentifier` before comparison.
- Report SID values only. Do not report translated account names.
- Test the directory owner, exact three-SID rule set, protection, rule type, rights, and inheritance.
- Test the private-key owner, owner-only SID rule set, protection, rule type, rights, and inheritance.
- Preserve the prior false comparison as the focused failed proof.
- Change no ACL, file, directory, network object, Hyper-V object, service, process, or repository file.
- Classify the original failure as a verification defect or a real ACL defect.
- Stop after the handoff. Do not resume provisioning.

## PLAT-ACL-DIAG-1 review result

### Facts

- Platform and Release classified the prior failure as `VERIFICATION_DEFECT`.
- The directory owner SID matches the current user SID.
- The directory has the exact current-user, SYSTEM, and Administrators SID rules.
- All three directory rules grant explicit `Allow` and `FullControl` access.
- The directory access rules are protected and not inherited.
- The private-key owner SID matches the current user SID.
- The private key has one explicit current-user `Allow` and `FullControl` rule.
- The private-key access rules are protected and not inherited.
- Protected metadata and the Git state stayed unchanged.
- The diagnosis changed no host or repository state.

### Limits

- The proof covers local ACL metadata only.
- It does not prove SSH client acceptance, VM behavior, hosted access, public access, or private data handling.

### Uncertainty

- The later live SSH proof must confirm that the Windows SSH client accepts the private key.

### Open work

- Continue LAB-PROVISION-1A after the accepted key step.
- Preserve the key pair and use SID-based verification.

## LAB-PROVISION-1A-CONT proposed assignment

- Use Platform and Release for the remaining host-side lab build.
- Use an empty repository file lease.
- Keep the accepted control directory and key pair read-only.
- Re-run the accepted SID-based ACL proof before other state changes.
- Preserve the focused absence proof for the ISO, switch, NAT object, VHDX, VM, and SSH path.
- Download and verify only the approved Ubuntu ISO.
- Create only the remaining approved Hyper-V directories, switch, host address, NAT object, VHDX, and VM.
- Create `C:\Hyper-V` only as the parent for the approved lab directories.
- Start the VM and open one visible console.
- Stop at the first Ubuntu installer page.
- Leave every partial resource in place after a failure.
- Keep cleanup, Ubuntu installation, secrets, checkpoints, packages, SSH proof, and recovery outside this assignment.

## LAB-PROVISION-1A-CONT attempt 1 review

### Facts

- PowerShell 7, administrator, accepted-key, and SID-based ACL gates passed.
- The required parent `C:\Hyper-V` did not exist and was outside the lease.
- The specialist stopped before every new state change.
- No ISO, network object, VHDX, VM, or console was created.
- Protected metadata and the Git state stayed unchanged.
- The owner approved creation of only `C:\Hyper-V` on 2026-09-02.

### Limits

- This attempt provides local prerequisite proof only.
- It provides no installer, SSH, recovery, hosted, public, or private proof.

### Uncertainty

- No parent-path uncertainty remains after the owner approval.

### Open work

- Restart LAB-PROVISION-1A-CONT from the initial Git check.
- Create `C:\Hyper-V` only as the parent for the approved child directories.

## LAB-PROVISION-1A-CONT attempt 2 review

### Facts

- PowerShell 7, administrator, ACL, conflict, capacity, and Hyper-V service gates passed.
- The task created only the approved lab directories, ISO, switch, host address, NAT object, VHDX, and VM.
- The Ubuntu ISO size and SHA-256 value passed.
- The switch, host address, and NAT checks passed.
- The VM creation command reported the approved VM, VHDX, DVD, and configuration.
- The verification command failed to parse with `An empty pipe element is not allowed.`
- The failed command piped a `foreach` language statement directly to `Format-Table`.
- No verification statement ran.
- The VM stayed off and no console opened.
- Protected metadata and the Git state stayed unchanged.

### Limits

- The task did not prove the exact VM settings or ISO boot order.
- It provides local host proof only.
- It provides no installer, SSH, recovery, hosted, public, or private proof.

### Uncertainty

- The existing VM can match or differ from one or more approved settings.
- The task shell might not see the visible console page.

### Open work

- Dispatch LAB-VM-VERIFY-1 with an empty repository file lease.
- Verify the existing lab without repair or recreation.
- Start the VM only if every exact check passes.
- Stop at the first Ubuntu installer page.

## LAB-VM-VERIFY-1 proposed assignment

- Use Platform and Release for a verification-only continuation.
- Use the exact lease in the stable specialist brief.
- Preserve the prior parser failure as the focused failed proof.
- Prove the old parser form fails and the corrected variable form parses.
- Do not execute the invalid script.
- Verify every exact host, network, VM, firmware, disk, ISO, and boot value.
- Keep the VM off if one check fails.
- Do not repair, recreate, or remove a lab resource.
- After all checks pass, start only `fadir-control-lab-01`.
- Open one visible VM console and stop at the first Ubuntu installer page.
- Request owner visual confirmation if the task cannot see the console.
- Keep Ubuntu installation, secrets, packages, SSH, checkpoints, and recovery outside this task.

## LAB-VM-VERIFY-1 review result

### Facts

- The prior parser failure stayed in the proof.
- The invalid parser form failed without execution.
- The corrected variable form parsed.
- PowerShell 7, administrator, and SID-based key ACL gates passed.
- All 42 host, network, VM, firmware, disk, ISO, and boot checks passed.
- The VM changed from `Off` to `Running` after every check passed.
- One visible `vmconnect.exe` console opened.
- The Senior Agent inspected that console from the desktop task.
- The console showed the first Ubuntu installer language page with English selected.
- The task made no repair, cleanup, checkpoint, package, account, service, or database change.
- Protected metadata and the Git state stayed unchanged.

### Limits

- This is local host and console proof only.
- It provides no Ubuntu installation, SSH, recovery, hosted, public, or private-data proof.

### Uncertainty

- The installer exposes the actual guest interface name during network setup.
- The planned `fadir0` rename still needs a later exact Netplan rule and proof.
- Strict key-only SSH and host recovery remain unproved.

### Open work

- Obtain owner approval for guest DNS and the Ubuntu installation.
- Run LAB-INSTALL-1 through the VM console.
- Keep the bootstrap secret outside every prompt, file, and log.
- Dispatch LAB-PROVISION-1B only after the installed guest reaches the login console.

## LAB-INSTALL-1 proposed assignment

- Use the owner-controlled VM console for the Ubuntu installation.
- Use an empty repository file lease.
- Change only the virtual disk for `fadir-control-lab-01`.
- Use Ubuntu Server 24.04.4 LTS, English, and the US keyboard.
- Use the full 64 GiB virtual disk with LVM and no disk encryption.
- Use host name `fadir-control-lab-01` and bootstrap account `fadir-bootstrap`.
- Let the owner enter and retain the bootstrap secret.
- Configure `192.168.247.10/24` with gateway `192.168.247.1` on the installer interface.
- Use owner-approved DNS servers before package-service contact.
- Install OpenSSH Server and no optional server snap.
- Stop after the first successful reboot and login-console proof.
- Keep the agent account, key installation, SSH hardening, checkpoints, packages, and recovery outside this assignment.

## LAB-INSTALL-1 integration research

Research date: 2026-09-02.

Version scope: Windows 11 Hyper-V WinNAT and Ubuntu Server 24.04 LTS installer.

- Microsoft states that WinNAT does not assign guest IP, gateway, or DNS values. Source: https://learn.microsoft.com/en-us/windows-server/virtualization/hyper-v/setup-nat-network
- Ubuntu states that the server installer can continue without a network. Source: https://ubuntu.com/server/docs/tutorial/basic-installation/
- Cloudflare publishes `1.1.1.1` and `1.0.0.1` for its unfiltered public resolver. Source: https://developers.cloudflare.com/1.1.1.1/setup/

Tool limits:

- WinNAT provides routing but no guest DHCP or DNS assignment.
- An offline install delays network, mirror, and SSH-path proof.
- Public DNS sends guest DNS requests to the selected external resolver.
- The installer interface name must come from the live guest screen.

Recommendation:

- Use Cloudflare unfiltered DNS at `1.1.1.1` and `1.0.0.1` for this disposable lab.
- Keep encrypted DNS and local DNS service setup outside LAB-INSTALL-1.
- Treat the DNS choice and Ubuntu installation as separate owner approvals.

## LAB-INSTALL-1 and LAB-PROVISION-1B access review

### Facts

- The owner installed Ubuntu Server 24.04.4 LTS on the approved disposable VHDX.
- The installed guest boots without the ISO and uses static address `192.168.247.10`.
- The owner retained the `fadir-bootstrap` secret outside prompts, files, and logs.
- The `fadir-agent` account exists with a locked password.
- Its home has mode `750`, its `.ssh` directory has mode `700`, and `authorized_keys` has mode `600`.
- Windows and Ubuntu reported the same approved user-key fingerprint.
- Windows and Ubuntu reported the same ED25519 host-key fingerprint.
- The accepted host key moved to `C:\ProgramData\fadir-agent-control\lab_known_hosts`.
- Strict key-only SSH passed through the stable trust file with exit code `0`.
- The owner changed the order on 2026-09-03: prove command access first, then finish SSH hardening remotely.
- The agent account belongs only to group `fadir-agent`.
- `sudo -n true` failed with `sudo: a password is required` and exit code `1`.

### Limits

- This is local disposable-lab proof only.
- The guest still uses the installer SSH policy.
- Password authentication, root key login, terminal access, and forwarding remain enabled on the server.
- The agent account cannot make administrator changes.
- The approved temporary rule grants full root access. It is not a constrained sudo design.
- The temporary sudo rule is not installed.
- No host-driven restart, checkpoint recovery, PostgreSQL, hosted, public, or private proof exists.
- No product file, secret, private row, or owner email entered the lab.

### Uncertainty

- The failed control-program review still blocks a permanent password-free sudo boundary.
- Host-driven recovery remains unproved.

### Open work

- Let the owner validate and install the candidate with two VM console commands.
- Dispatch LAB-ADMIN-BOOTSTRAP-1 stage 2 after the owner reports both console results.
- Keep the temporary full sudo bootstrap separate from the permanent constrained sudo design.
- After administrator proof, dispatch a separate SSH hardening and temporary-rule removal assignment.
- Dispatch Quality and Security before the lab receives product files, secrets, or private data.

## LAB-ADMIN-BOOTSTRAP-1 stage 1 review

### Facts

- Strict key-only SSH returned `fadir-agent`, `fadir-control-lab-01`, and exit code `0` before and after the write.
- `sudo -n true` returned `sudo: a password is required` and exit code `1` before and after the write.
- The candidate and live sudoers paths were absent before the write.
- Stage 1 created only `/tmp/90-fadir-agent-bootstrap` through strict SSH standard input.
- The candidate has one line, one final LF byte, owner `fadir-agent:fadir-agent`, and mode `0600`.
- The candidate contains the exact approved full-sudo rule.
- Its SHA-256 value is `74ee3778abd56fb8b3c5c6068ec5b3730f94a63581e3afc4cd8fe2e9fc19311e`.
- Unprivileged `visudo -cf` returned `parsed OK` and exit code `0`.
- `/etc/sudoers.d/90-fadir-agent-bootstrap` remains absent.
- Protected repository metadata, Windows key metadata, trust metadata, and Git state stayed unchanged.

### Limits

- Stage 1 provides local disposable-lab proof only.
- Administrator access remains unavailable through SSH.
- No SSH policy, package, service, checkpoint, VM, PostgreSQL, hosted, public, or private-data change occurred.

### Uncertainty

- Root must validate the candidate again before installation.
- The permanent constrained sudo design still fails its prior Quality review.

### Open work

- Stage 2 must prove remote password-free root access and the installed file metadata.

## LAB-ADMIN-BOOTSTRAP-1 console installation review

### Facts

- Root `visudo -cf` returned `/tmp/90-fadir-agent-bootstrap: parsed OK`.
- The first install attempt used `/usr/sbin/install` and failed with `command not found`.
- The second install attempt used `/usr/bin/install` and returned to the prompt without an error message.
- The second install command used owner `root` and mode `0440`.
- The command omitted the approved explicit group argument `-g root`.
- The owner entered `echo $` before `echo $?`.
- The displayed zero is the exit code from `echo $`, not the install command.

### Limits

- The screenshot does not prove that the live file exists.
- The screenshot does not prove the live owner, group, mode, content, hash, or sudo behavior.
- No product file, private data, secret, SSH policy, package, service, or VM setting changed.

### Uncertainty

- The install command probably succeeded, but the screenshot does not prove this result.
- The live file group remains unproved because the command omitted `-g root`.

### Open work

- Preserve the console evidence with the stage 2 failure.
- Use a separate read-only diagnosis before any repair.

## LAB-ADMIN-BOOTSTRAP-1 stage 2 review

### Facts

- Strict SSH returned `fadir-agent`, `fadir-control-lab-01`, and exit code `0`.
- `sudo -n /usr/bin/true` returned exit code `0`.
- `sudo -n /usr/bin/id -u` returned `0` and exit code `0`.
- `/etc/sudoers.d/90-fadir-agent-bootstrap` does not exist.
- The specialist stopped at the first mismatch and made no repair.
- Repository, Windows key, trust, and protected metadata stayed unchanged.
- The final Git state matches the initial state.

### Limits

- Stage 2 did not inspect another sudo policy path.
- Stage 2 did not identify the active authorization source.
- Stage 2 provides local disposable-lab proof only.
- No SSH policy, package, service, VM setting, checkpoint, product, private-data, or secret change occurred.

### Uncertainty

- An unknown sudo policy source grants full password-free root access to `fadir-agent`.
- The console install command did not create the file at the approved destination.

### Open work

- Preserve the conclusive diagnosis and its unchanged-state proof.
- Apply only the separately approved two-path sudo repair.
- Keep product files, secrets, and private data outside the lab.

## LAB-SUDO-DIAG-1 review

### Facts

- The active authorization source is `/etc/sudoers.d/90=fadir-agent-bootstrap`.
- The file name contains ASCII byte `3d`, which is `=`.
- The file contains the exact approved full-sudo rule.
- Its owner is `root`, its group is `root`, and its mode is `0440`.
- Its size is 37 bytes, and its SHA-256 value matches the staged candidate.
- `/etc/sudoers` includes `/etc/sudoers.d` at line 57.
- `sudo -n -l` reports one effective `(root) NOPASSWD: ALL` grant.
- Global sudo syntax validation passed.
- The diagnosis used read-only commands and changed no state.
- Repository, Windows key, trust, and protected metadata stayed unchanged.

### Limits

- The rule grants full root access. It is not constrained sudo.
- The diagnosis provides local disposable-lab proof only.
- It provides no SSH hardening, recovery, PostgreSQL, hosted, public, or private-data proof.

### Uncertainty

- The evidence does not show how the equals sign entered the destination name.
- The permanent constrained sudo design still fails its prior Quality review.

### Open work

- Install the approved candidate at `/etc/sudoers.d/90-fadir-agent-bootstrap`.
- Validate the correct file before removal.
- Remove `/etc/sudoers.d/90=fadir-agent-bootstrap` only after every pre-removal gate passes.
- Preserve the staged candidate as the recovery source.
- Stop before SSH hardening or any unrelated change.

## LAB-SUDO-REPAIR-1 review

### Facts

- The correct hyphen path was absent before repair.
- The equals-sign file and staged candidate were exact before repair.
- The approved install command returned exit code `0`.
- The correct file matched the staged candidate byte for byte.
- File-specific and global sudo syntax validation passed while both files existed.
- Password-free sudo passed while both files existed.
- Removal of `/etc/sudoers.d/90=fadir-agent-bootstrap` returned exit code `0`.
- The equals-sign file was absent after removal.
- The correct hyphen file remained exact after removal.
- `/tmp/90-fadir-agent-bootstrap` was absent at the next check.
- The specialist stopped every guest command after that mismatch.
- Repository, Windows key, trust, and protected metadata stayed unchanged.

### Limits

- The final global sudo syntax, effective policy, sudo, root identity, and strict SSH checks did not run.
- The task provides local disposable-lab proof only.
- No SSH policy, package, service, VM setting, checkpoint, product, private-data, or secret change occurred.

### Uncertainty

- The evidence does not identify what removed the staged candidate.
- The correct live file passed exact checks, but final active authorization remains unproved.

### Open work

- Preserve the failure with the direct final diagnosis below.
- Keep candidate recreation and every other repair outside the completed diagnosis.

## LAB-SUDO-FINAL-DIAG-1 review

### Facts

- The owner approved the combined read-only diagnosis on 2026-09-03.
- The current task used Windows `ssh.exe` directly through the local shell.
- Strict SSH returned `fadir-agent`, `fadir-control-lab-01`, and exit code `0`.
- The correct live file is `/etc/sudoers.d/90-fadir-agent-bootstrap`.
- Its owner is `root`, its group is `root`, its mode is `0440`, and its size is 37 bytes.
- It contains one exact approved line and one final LF byte.
- Its SHA-256 value is `74ee3778abd56fb8b3c5c6068ec5b3730f94a63581e3afc4cd8fe2e9fc19311e`.
- The equals-sign file is absent.
- The staged candidate is absent.
- Global sudo syntax validation passed with exit code `0`.
- Effective policy reports one `(root) NOPASSWD: ALL` grant.
- `sudo -n /usr/bin/true` returned exit code `0`.
- `sudo -n /usr/bin/id -u` returned `0` and exit code `0`.
- Initial and final repository, protected root, key, trust, and Git evidence matched.

### Limits

- The diagnosis did not identify what removed the staged candidate.
- `/tmp` is transient and is not a durable recovery location.
- The active rule grants full password-free root access. It is not constrained sudo.
- This is local disposable-lab proof only.
- No SSH policy, package, service, VM setting, checkpoint, product, private-data, or secret change occurred.

### Uncertainty

- The candidate disappearance cause remains inconclusive.
- The permanent constrained sudo design still fails its prior Quality review.

### Open work

- The owner must accept or reject the absent transient candidate as a non-blocking limit.
- Keep the bootstrap console account as the current recovery path.
- Obtain a separate exact lease before SSH hardening.
- Keep product files, secrets, and private data outside the lab.

## Owner decisions

### Accepted decisions

- faðir will provide one hosted product.
- One PostgreSQL database will hold hosted data.
- Workspace and Portfolio keys will scope private rows.
- One User controls one Workspace.
- A Workspace can contain many Portfolios.
- Google is the primary Login Identity.
- An email magic link provides recovery.
- A Guest Workspace uses one opaque cookie and expires after 90 inactive days.
- Sign-in offers explicit Claim, Portfolio Transfer, or Portfolio Merge choices.
- Each Portfolio has one changeable Base Currency.
- Turkey is the first Tax Jurisdiction.
- The beta keeps direct Yahoo access under the owner's private written permit.
- The beta uses an Ubuntu Server LTS VM under Hyper-V.
- Cloudflare Tunnel provides public ingress.
- Runbook Gate 0 is approved as the control plan only.
- An agent-run Linux environment must have a proven command path from the Windows task shell.
- A Hyper-V console without that command path is not an acceptable agent work environment.
- A Hyper-V VM is acceptable after normal SSH access and host-driven recovery both pass proof.
- Official primary-source research must guide each new integration and its first test plan.
- Routine tests for an accepted integration do not need new research.
- Research must run again after a material version, environment, requirement, or documentation change.
- The owner approved a disposable Hyper-V Ubuntu lab strategy.
- The owner approved LAB-PREFLIGHT-1 as a read-only preflight only.
- The owner approved the LAB-PREFLIGHT-1 resource plan and provision direction on 2026-09-02.
- The elevated Codex CLI gate passed on 2026-09-02.
- The owner added only `C:\Hyper-V` to the LAB-PROVISION-1A-CONT host lease on 2026-09-02.
- The owner approved Ubuntu installation on the disposable lab VHDX on 2026-09-02.
- The owner approved Cloudflare DNS at `1.1.1.1` and `1.0.0.1` for the disposable lab on 2026-09-02.
- The owner approved a connect-first order on 2026-09-03: prove strict key-only SSH before the remaining guest hardening.
- The owner approved temporary full password-free sudo for `fadir-agent` on 2026-09-03.
- This approval applies only to the disposable lab and the exact rule `fadir-agent ALL=(root) NOPASSWD: ALL`.
- Product files, private data, and secrets must stay outside the lab until removal and Quality review.
- The owner approved LAB-SUDO-DIAG-1 as an exact read-only diagnosis on 2026-09-03.
- The owner approved LAB-SUDO-REPAIR-1 on 2026-09-03.
- The approval covers corrected installation and removal of `/etc/sudoers.d/90=fadir-agent-bootstrap` only.
- The owner approved LAB-SUDO-FINAL-DIAG-1 as a combined read-only diagnosis on 2026-09-03.
- The owner accepted the absent transient sudo candidate as a non-blocking lab limit on 2026-09-03.
- The owner directed the Senior Agent to return to product work on 2026-09-03.
- The owner authorized the Senior Agent to commit accepted agent work after review on 2026-09-03.
- Push, deployment, public changes, secrets, and destructive actions still need separate owner approval.
- The owner approved the DB-5D two-file synthetic migration core lease on 2026-09-03.
- DB-5D can use synthetic dependencies only. It cannot connect to SQLite or PostgreSQL.

### Decisions that remain open

- Approve each rollback or destructive cleanup action separately.
- Approve or reject an exact SSH hardening assignment.
- Approve any later change to the temporary full-sudo rule separately.
- Accept the disposable lab only after strict SSH and host recovery pass Quality review.
- Approve removal of the temporary full sudo bootstrap after the permanent control path passes review.
- Approve or revise Gate 1 after the repaired control design passes review.
- Select the external email service before identity implementation needs it.
- Approve any private data migration action and rollback plan.
- Select the production VM size, network rules, domain, tunnel settings, and service accounts.
- Select the encrypted off-site backup target and restore procedure.
- Approve every hosted or public proof window.

## Review template

### Facts

Record file changes, command results, and direct observations.

### Limits

Record proof boundaries and work outside the lease.

### Uncertainty

Record unresolved behavior or evidence gaps.

### Open work

Record the next safe action and each owner decision.
