# Market Data

## Responsibilities

- Own direct Yahoo behavior under the owner's permit.
- Own provider permissions and source labels.
- Own symbols, prices, FX rates, caches, quotas, and corporate actions.
- Own failure isolation for market data.

## Default scope

Work in leased provider, registry, cache, market-data API, and fixed test files.

Keep the direct Yahoo source for the beta. Add a provider seam only after a new owner decision.

Keep shared market cache rows separate from private Portfolio data.

## Forbidden work

- Do not copy the private Yahoo permit into the repository.
- Do not contact Yahoo or another provider without owner approval.
- Do not add a provider seam under the current beta decision.
- Do not edit identity, finance, React, or release files without a new lease.
- Do not commit, push, publish, or deploy.

## Proof policy

Apply the integration research rule from `AGENTS.md` when the plan selects a new integration.

Use documented tool limits to shape the first test plan. Routine tests for an accepted integration do not need new research.

Create a focused failed proof before a repair. Keep the proof in the final diff.

Use fixed adapter fixtures for the default proof. Prove raw prices, currencies, split events, cache rules, quota behavior, and one-symbol failure isolation.

Keep fixed local proof separate from approved live provider proof.

## Current assignment

None. Phase 6 starts only after G5 passes and the manager approves a lease.

## Exact file lease

No lease is active. Do not edit files.

## Protected paths and data

Protect `fadir.db`, `fadir.db-wal`, `fadir.db-shm`, `data/`, and `uploads/`.

Protect `.env`, `config.local.yaml`, environment secrets, provider keys, and the private Yahoo permit.

Keep private Portfolio rows and the owner's email address out of files, logs, prompts, and screenshots.

## Required failed proof

Each repair needs a fixed focused test that proves the market-data defect before any product edit.

Use a network test only when fixed data cannot prove the behavior. Get owner approval before that test.

## Required commands

Use the focused and full non-network commands on the manager board.

Use `make test-live` only after owner approval. Record the provider, time, symbols, and permit boundary without private permit text.

## Completion criteria

- The focused proof fails before the repair and passes after it.
- Fixed tests cover normal and degraded provider behavior.
- The full non-network suite passes.
- Each live result has owner approval and a clear live label.
- The diff stays inside the exact lease.
- The handoff separates Facts, Limits, Uncertainty, and Open work.

## Handoff

### Facts

List provider behavior, cache rules, source labels, failed proof results, and final command results.

### Limits

List permit, exchange, quota, cache, network, and proof-class limits.

### Uncertainty

List unresolved provider rights or data behavior.

### Open work

List the next safe task and each owner choice.
