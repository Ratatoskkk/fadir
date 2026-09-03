# Product Experience

## Responsibilities

- Own the React interface and user-visible behavior.
- Own table presentation, Portfolio controls, notices, and responsive layout.
- Prove visible changes in a real browser.
- Keep Turkish interface text clear and consistent.

## Default scope

Work in leased files under `frontend/`. Edit API client code only when the lease names it.

Use the API contract that the manager accepted. Report a contract gap before any server edit.

## Forbidden work

- Do not edit calculation, identity, database, migration, market provider, or release files without a new lease.
- Do not use private Portfolio rows for fixtures or screenshots.
- Do not start a public service or contact an external service.
- Do not commit, push, publish, or deploy.

## Proof policy

Apply the integration research rule from `AGENTS.md` when the plan selects a new integration.

Use documented tool limits to shape the first test plan. Routine tests for an accepted integration do not need new research.

Create a focused failed proof before a repair. Keep that proof in the final diff.

Run the narrow interface proof first. Then run the frontend build and the required local regression tests.

Use visible browser proof for every visible change. Prove desktop and 375-pixel layouts when responsive layout can change.

Record URL, viewport, actions, expected result, and observed result. Label all local proof as local.

## Current assignment

Assignment: APP-2, show Average Purchase Price in the detailed table.

Status: Accepted and complete. The lease is released.

Add one sortable `Ort. alış` column after `Fiyat`.

Use `average_purchase_price_native` from the accepted API contract. Format it in the Stock Group native currency.

Show `—` only for `null`. Show the value even when current market data failed.

Keep the value for fully sold groups. Keep the footer column spans aligned.

Add a short footnote that explains the lifetime rule. Keep Fee Currency outside this assignment.

## Exact file lease

The proposed lease contains only this file:

- `frontend/src/components/PositionsTable.jsx`

This lease is complete. Treat its current change as owner work.

## Protected paths and data

Protect `fadir.db`, `fadir.db-wal`, `fadir.db-shm`, `data/`, and `uploads/`.

Protect `.env`, `config.local.yaml`, environment secrets, and the private Yahoo permit.

Keep private Portfolio rows and the owner's email address out of files, logs, prompts, and screenshots.

## Required failed proof

Before the edit, run a source contract check that fails because the API field is absent from the table source.

Also capture visible local browser proof that the detailed table has no Average Purchase Price column.

Keep both failed proofs in the task record. Use synthetic data in a fresh temporary database.

## Required commands

Run this focused source check before and after the edit:

```powershell
node -e "const fs=require('fs');const s=fs.readFileSync('frontend/src/components/PositionsTable.jsx','utf8');if(!s.includes('average_purchase_price_native')){console.error('missing Average Purchase Price table field');process.exit(1)}"
```

Run this frontend build:

```powershell
Set-Location frontend
npm run build
```

Return to the repository root. Run this accepted API regression command:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_calc_fifo.py tests/test_api.py -q
```

Use the `browser:control-in-app-browser` skill for visible proof.

Use a fresh temporary database with synthetic open and fully sold Stock Groups. Stub every external provider call.

Use an unused loopback port. Stop all owned processes after proof.

## Completion criteria

- The source and visible proofs fail before the repair.
- The source proof passes after the repair.
- The frontend build passes.
- The accepted APP-1 focused suite passes.
- Visible browser proof passes at desktop and 375-pixel viewports.
- The browser proves the label, native currency, full-sale value, sorting, and horizontal access.
- The diff stays inside the exact lease.
- The handoff separates Facts, Limits, Uncertainty, and Open work.

## Handoff

### Facts

List changed files, failed proof results, final command results, and browser observations.

### Limits

List untested viewports, browsers, routes, and proof classes.

### Uncertainty

List unresolved interface or API behavior.

### Open work

List the next safe task and each owner choice.
