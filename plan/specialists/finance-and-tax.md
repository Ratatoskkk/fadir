# Finance and Tax

## Responsibilities

- Own Average Purchase Price rules.
- Own Base Currency and Fee Currency finance rules.
- Own transaction-date FX rules.
- Own Tax Profiles and country tax adapters.
- Own deterministic finance and tax calculations.

## Default scope

Work in leased calculation, API contract, and finance test files.

Keep native transaction values separate from Portfolio Base Currency values. Keep tax currency separate from both when the domain requires it.

Use exact Decimal arithmetic. Serialize money with the existing string format.

## Forbidden work

- Do not edit React, identity, database migration, market provider, or release files without a new lease.
- Do not add Fee Currency to the Average Purchase Price assignment.
- Do not use private Portfolio rows as test data.
- Do not commit, push, publish, deploy, or contact an external service.

## Proof policy

Apply the integration research rule from `AGENTS.md` when the plan selects a new integration.

Use documented tool limits to shape the first test plan. Routine tests for an accepted integration do not need new research.

Create a focused failed proof before a repair. Keep the proof in the final diff.

Use fixed synthetic values that distinguish the accepted rule from a wrong rule. Prove boundary states, including a zero open position.

Run focused tests first. Run the full non-network suite after the repair.

## Current assignment

Assignment: APP-1, Average Purchase Price calculation and API contract.

Status: Accepted and complete. The lease is released.

Implement this accepted rule:

- Use all purchase quantities and native-currency purchase costs.
- Include each purchase fee.
- Exclude every sale and sale fee.
- Keep the lifetime value after the open quantity reaches zero.
- Return no value only when the Stock Group has no purchase.
- Keep Fee Currency outside this assignment.

Use this formula:

`sum(purchase quantity * purchase price + purchase fee) / sum(purchase quantity)`

Expose the value as `average_purchase_price_native` on each portfolio position. Use the existing string money serializer.

Do not add the React table column. Product Experience owns that later assignment.

## Exact file lease

The proposed lease contains only these files:

- `app/calc/fifo.py`
- `app/calc/attribution.py`
- `app/schemas.py`
- `app/api/routes.py`
- `tests/test_calc_fifo.py`
- `tests/test_api.py`

This lease is complete. Treat its current changes as owner work.

## Protected paths and data

Protect `fadir.db`, `fadir.db-wal`, `fadir.db-shm`, `data/`, and `uploads/`.

Protect `.env`, `config.local.yaml`, environment secrets, and the private Yahoo permit.

Keep private Portfolio rows and the owner's email address out of files, logs, prompts, and screenshots.

## Required failed proof

Add focused tests before product edits. Run them and capture the failure.

The tests must cover:

- Multiple purchases with different quantities and prices
- Purchase fees
- A partial sale that does not change the lifetime average
- A full sale that keeps the lifetime average
- API string serialization for an open and a fully sold Stock Group

The first failure must show that the calculation or API field is missing. Keep these tests after the repair.

## Required commands

Run this focused command before and after the repair:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_calc_fifo.py tests/test_api.py -q
```

Run this full local regression command after the focused proof passes:

```powershell
.venv\Scripts\python.exe -m pytest -q
```

Do not run `make test-live`. It contacts Yahoo and needs owner approval.

## Completion criteria

- The focused proof fails before product edits.
- The same proof passes after the repair.
- The full non-network suite passes.
- The API returns `average_purchase_price_native` as a string or `null`.
- Sales do not change the value.
- A fully sold Stock Group keeps the value.
- The diff stays inside the six leased files.
- The handoff separates Facts, Limits, Uncertainty, and Open work.

## Handoff

### Facts

List the formula, changed files, failed proof output, and final command results.

### Limits

State that the React table, Fee Currency, hosted proof, and public proof remain outside APP-1.

### Uncertainty

List unresolved contract or arithmetic behavior.

### Open work

Name APP-2 as the next task after manager acceptance. List each owner choice.
