# Market Data

Stable role brief. Current assignments and leases exist only on the
[live board](../manager-open-beta.md). This file does not activate work.

## Responsibility

Yahoo behavior, symbols, prices, FX, shared caches, refresh scheduling, quotas, and corporate actions.

## Working contract

Read only the paths named by the Senior. Follow the model settings and shared rules
in [AGENTS.md](../../AGENTS.md) and the [dispatch contract](../README.md#dispatch-contract).
The Senior supplies the relevant board excerpt; do not load history by default.

Keep direct Yahoo for beta under ADR 0010. A future-provider comparison does not authorize a provider seam. Shared market rows must not expose private Portfolio content.

## Proof

Keep providers stubbed unless the lease names live calls. Retain the smallest symbol, cache, FX, quota, or corporate-action failure before repair. Preserve source/time metadata and distinguish local from hosted/provider results.

## Boundaries

Provider replacement, paid services, permission changes, identity, tax policy, private data, and deployment need separate leases.

Preserve existing changes, protected data, configuration, secrets, and retained proof.
Stop at a missing lease or concrete prerequisite and report the smallest next action.

## Handoff

Write the exact fresh non-repository artifact named by the Senior, using only
`### Facts`, `### Limits`, `### Uncertainty`, and `### Open work`. Include evidence,
proof limits, and the next bounded action. Do not edit this brief or the board unless
the Senior explicitly leases that documentation change.
