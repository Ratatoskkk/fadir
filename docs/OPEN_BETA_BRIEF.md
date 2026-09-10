# faðir Open Beta Brief

Current product decisions, reconciled on 2026-09-10. This is the product contract from
the original design interview plus later owner decisions. It describes the target;
the [live board](../plan/manager-open-beta.md) records what is implemented and accepted.

## Product goal

faðir is a hosted service for private investment portfolios. A person can use the full product as a Guest or as a User.

Sign-in protects recovery and long-term storage. It does not unlock product features.

The first beta serves individual users. It does not support teams or shared Portfolios.

## Product structure

One User controls one Workspace. One Workspace contains many Portfolios.

Each Portfolio has a unique name inside its Workspace. The first saved transaction creates `Ana Portföy` when no Portfolio exists.

Each Portfolio has one Base Currency. A currency change revalues views and does not rewrite source transactions.

The original private SQLite portfolio will move through a protected administrator migration into the owner's existing verified Google User Workspace. The owner selected `Ana Portföy`, TRY Base Currency, and mapping every legacy Transaction and Snapshot to it. See the [migration runbook](PRIVATE_MIGRATION_RUNBOOK.md).

## Guest use

A Guest Workspace uses an opaque browser cookie. It has no recovery key or device identifier.

The service deletes Guest data after 90 days without access. A quiet notice explains this rule after the first save.

The sign-in flow asks how to handle Guest data. It supports Claim, Portfolio Transfer, and Portfolio Merge.

A Merge moves Guest transactions into a selected User Portfolio. The target keeps its Base Currency.

The User must choose to keep or skip possible duplicate transactions. The service does not combine rows without confirmation.

If the User rejects a Merge, the service keeps the Guest Portfolio as a separate Portfolio. It asks for a new name after a name conflict.

## Identity

Google is the only sign-in method in the beta. Email magic-link recovery is deferred.

The beta does not use an email sender service or an email sign-in flow. Google identity uses the provider issuer and subject as the durable key.

A User Session expires after 30 days without activity. The User can view and revoke active sessions.

## Portfolio calculations

The detailed table will show Average Purchase Price for every Stock Group. It will use the weighted cost of all purchases.

The calculation includes purchase fees and excludes sales. A fully sold Stock Group keeps its lifetime purchase average.

A fee can have its own Fee Currency. The service converts it on the transaction date.

## Tax

The first public release keeps the Turkey Tax Estimate. The estimate uses TRY, even when a Portfolio uses another Base Currency.

One Tax Profile belongs to one User, Tax Jurisdiction, and tax year. All User Portfolios can contribute to one estimate.

The Turkey beta proof needs an official source, a visible tax year, fixed tests, and a tax-advice disclaimer.

The team will add another country only after Turkey passes public beta acceptance.

## Market data

The beta will keep the current Yahoo source under the owner's written permit. The permit stays outside the repository.

The team will defer a provider seam. The market-data report records Marketstack, Twelve Data, EODHD, and other options.

## Hosted service

The hosted service will use one PostgreSQL database. Workspace and Portfolio keys will scope each private row.

Shared market data can use global cache rows. Private Portfolio data cannot enter Operator tools or normal logs.

The beta will run on an Ubuntu Server LTS VM under Hyper-V. Cloudflare Tunnel will provide public access for `ratatosk.dev`.

The owner will keep the host computer on. A later full product can move to a separate server computer.

The beta will not use off-site backups. It has no one-hour data-loss target and no four-hour restore guarantee.

Release readiness still requires proof of service restart, release rollback, and service reconstruction. These proofs do not recover lost Portfolio data.

## Public controls

The service will use Cloudflare controls, server rate limits, size limits, and Guest quotas. Turnstile will appear only after abuse.

The footer will contain quiet privacy, terms, tax, data-source, and Guest retention notices.

Operator views can show health, counts, quotas, and failures. They cannot show transaction values or Portfolio values.

## User data rights

A User can export each Portfolio as CSV and JSON. A User can delete a Portfolio or the full User record.

Deletion revokes active sessions at once. If the beta retains encrypted backups, deleted data can remain in them for no more than 30 days.

## Delivery order

This is the dependency order, not a restart checklist. Resume the live board checkpoint.

1. Maintain the existing Senior and specialist coordination baseline.
2. Preserve the accepted Average Purchase Price contract and proof.
3. Add PostgreSQL, migrations, and the User, Workspace, and Portfolio scopes.
4. Add Guest access, Google sign-in, Claim, Transfer, and Merge.
5. Add multiple Portfolios, Base Currency, Fee Currency, and the Tax Profile.
6. Prepare the market-data and cache behavior for public traffic.
7. Add security, privacy, deletion, export, and abuse proofs.
8. Create the Hyper-V VM and deploy the service through Cloudflare Tunnel.
9. Run local, browser, restart, release rollback, service reconstruction, and public acceptance checks.

## Work model

The Senior uses Luna Max (`gpt-5.6-luna`, `max`) and coordinates, reviews, and maintains
documentation. Specialists use Luna Medium (`gpt-5.6-luna`, `medium`) and implement
product and operational work, one specialist at a time.

The Senior checks each specialist's actual changes and required evidence. When they
meet the acceptance criteria, the Senior commits and pushes the accepted paths under
existing delivery authority. Incomplete candidates receive a bounded follow-up before
publication. This responsibility is part of coordination and does not authorize the
Senior to implement product changes.

The six stable roles and exact dispatch format are in [plan/README.md](../plan/README.md).
[AGENTS.md](../AGENTS.md) owns the shared proof and handoff policy. The live board owns
current leases and delivery authority, including existing reviewed commit/push and
release approval. Do not reimpose the original setup-only approval pause.

## Settled decisions

| Decision | Record |
|---|---|
| Hosted-only product; local development/recovery remains | [ADR 0001](adr/0001-hosted-service-only.md) |
| One hosted PostgreSQL database with private scopes | [ADR 0002](adr/0002-postgresql-for-hosted-data.md) |
| Owner-managed VM; off-site backups deferred | [ADR 0003](adr/0003-owner-managed-vm-for-open-beta.md) |
| Google-only beta; email recovery deferred | [ADR 0004](adr/0004-google-primary-with-email-magic-link.md) |
| Cloudflare Tunnel and quiet abuse controls | [ADR 0005](adr/0005-cloudflare-tunnel-for-public-ingress.md) |
| Base Currency per Portfolio | [ADR 0006](adr/0006-base-currency-per-portfolio.md) |
| Operator tools exclude Portfolio content | [ADR 0007](adr/0007-keep-portfolio-data-out-of-operator-tools.md) |
| Turkey first; Tax Profiles at User level | [ADR 0008](adr/0008-turkey-first-with-tax-jurisdiction-adapters.md) |
| Cookie-only Guests and explicit transitions | [ADR 0009](adr/0009-cookie-only-guest-workspaces.md) |
| Direct Yahoo for beta; provider seam deferred | [ADR 0010](adr/0010-keep-yahoo-direct-for-beta.md) |

Do not add teams, shared Portfolios, email recovery, another tax jurisdiction, a stack
rewrite, off-site backups, or a speculative provider seam to the beta without a new
owner decision. Missing acceptance evidence does not change the product contract.
