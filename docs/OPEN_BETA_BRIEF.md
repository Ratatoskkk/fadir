# faðir Open Beta Brief

## Product goal

faðir is a hosted service for private investment portfolios. A person can use the full product as a Guest or as a User.

Sign-in protects recovery and long-term storage. It does not unlock product features.

The first beta serves individual users. It does not support teams or shared Portfolios.

## Product structure

One User controls one Workspace. One Workspace contains many Portfolios.

Each Portfolio has a unique name inside its Workspace. The first saved transaction creates `Ana Portföy` when no Portfolio exists.

Each Portfolio has one Base Currency. A currency change revalues views and does not rewrite source transactions.

The current private portfolio will move through a private administrator action. The action will target the owner's verified Google User.

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

1. Set up the Senior Agent and stable specialists.
2. Add Average Purchase Price as the first isolated product change.
3. Add PostgreSQL, migrations, and the User, Workspace, and Portfolio scopes.
4. Add Guest access, Google sign-in, Claim, Transfer, and Merge.
5. Add multiple Portfolios, Base Currency, Fee Currency, and the Tax Profile.
6. Prepare the market-data and cache behavior for public traffic.
7. Add security, privacy, deletion, export, and abuse proofs.
8. Create the Hyper-V VM and deploy the service through Cloudflare Tunnel.
9. Run local, browser, restart, release rollback, service reconstruction, and public acceptance checks.

## Work model

The Senior Agent coordinates the project and edits plan or agent instruction files only. It does not edit product code.

Six stable specialists own Product Experience, Identity and Data Integrity, Finance and Tax, Market Data, Platform and Release, and Quality and Security.

Each assignment uses an exact file lease. A specialist must show a focused failed proof before a repair.

Each handoff separates Facts, Limits, Uncertainty, and Open work. No agent can commit, push, or publish without owner approval.
