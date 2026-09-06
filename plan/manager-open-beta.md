# faðir open beta manager board

Date: 2026-09-06

This is the only live work board. Historical records are in `plan/manager-open-beta-history.md`.
The Senior must name exact specialist files and resources before each specialist task.
Specialists read only the named paths. They do not read repository files by default.

## Current authority

The owner approved continued delivery, VM use, reviewed commits, and normal pushes.
The Senior coordinates and reviews. Specialists implement only under exact leases.
The owner selected `ratatosk.dev` and Google-only sign-in for the beta.
Email recovery and off-site backups are deferred. Do not claim lost-data recovery.
Restart, rollback, and service reconstruction proof remain required.
Protect private databases, WAL files, uploads, secrets, local configuration, Portfolio rows, and the owner's email.
Use synthetic resources for proof. Confirm destructive action on existing owner data or infrastructure.

Public DNS currently delegates to `mina.ns.cloudflare.com` and `sevki.ns.cloudflare.com`.
This proves delegation only. It does not prove Cloudflare account access, TLS, Tunnel, or a public faðir service.
The owner supplied Google Web client ID `133938753454-ivjems9e1a27jftdfrpkcckdbcfqgh1a.apps.googleusercontent.com`.
Keep it in deployment configuration. It does not prove a callback, authorized origin, or successful sign-in.

## Active assignments

| Role | Assignment | Repository lease | Operational lease | Status |
|---|---|---|---|---|
| Product Experience | None | Empty | Empty | Design accepted; wait for route contract |
| Identity and Data Integrity | ID-3A-CALC-SCOPE | `app/services/portfolio.py`, `tests/test_portfolio_service_scope.py` | `C:/Users/doguk/AppData/Local/Temp/fadir-id3a-scope-20260906/` | Active |
| Finance and Tax | None | Empty | Empty | MERGE-FIN-1 accepted |
| Market Data | None | Empty | Empty | Wait for Phase 6 |
| Platform and Release | None | Empty | Empty | BETA-SCOPE-1 accepted |
| Quality and Security | None | Empty | Empty | ID-2 final acceptance passed |

Each role has one active assignment at most. The Senior reviews the worktree before every lease.
The Senior reviews the diff, retained failed proof, final proof, and handoff before dependent work.

## Current accepted state

- `04bab50` published the seven-file Guest foundation.
- `476df16` published the five-file PostgreSQL runtime boundary.
- `4b681ae` published the current coordination records.
- Origin `main` was even with the local branch after the last push.
- ID-2 final proof: 18 focused passes, 365 offline passes, and 1 synthetic PostgreSQL pass.
- ID-2 retained the startup failure and verified no private query value escaped after repair.
- G2 is accepted. G3 is conditional on real PostgreSQL and private-scope proof.
- G4 is open. No HTTP, cookie, Google identity, User Session, Claim, Transfer, Merge, hosted, or public pass exists.
- Existing Starlette warning remains.

## Phase order and gates

1. Coordination baseline — G0
2. Average Purchase Price — G2
3. PostgreSQL and private data scopes — G3
4. Guest access and identity — G4
5. Multiple Portfolios, currencies, and Tax Profiles — G5
6. Public market-data behavior — G6
7. Security, privacy, export, deletion, and abuse controls — G7
8. Hyper-V VM and public release — G8
9. Full acceptance and recovery proof — G9

Dependencies: G2 precedes scope work. G3 precedes HTTP and identity work. G4 precedes public access.
G5 depends on User, Workspace, Portfolio, Base Currency, and Tax Profile scope.
G6 depends on provider permissions, cache boundaries, and scoped calculations.
G7 depends on identity and route isolation. G8 depends on hosted service and Tunnel proof.
G9 depends on all earlier gates plus restart, rollback, reconstruction, and acceptance evidence.

## ID-3A-CALC-SCOPE lease

Identity owns only `app/services/portfolio.py` and new `tests/test_portfolio_service_scope.py`.
Use the exact operational root above. Build synthetic proof from committed `2405850` plus only the two leased files.
Do not include the separate ID-2 candidate or canonical local configuration.
Use synthetic SQLite and stubbed providers. Install no package. Change no route, model, migration, provider, server, VM, or public resource.

Add an additive `PortfolioService.scoped(scope)` facade for inception, view, history, and intraday.
Require a valid PortfolioScope from the same Session. Query private Transactions by Portfolio before calculation.
Never assign filtered rows to `Instrument.transactions`. Preserve formulas and Average Purchase Price behavior.
Keep current local callers functional until their later cutover. Unscoped callers cannot qualify for public access.

Retain focused red proof for two Workspaces, two Portfolios, unowned rows, shared Instruments, and preloaded relationships.
Cover inception, view, history, intraday, same-Session rejection, inactive Instruments, empty Portfolios, and bounded ticker selection.
Verify a flush changes no source value or Portfolio association.
Run focused tests and the full offline suite with `-o addopts= -m "not live"`.
Retain source hashes, archive hashes, XML counts, failures, and cleanup evidence.

## Next assignments

After ID-3A acceptance, assign route selection and private CRUD under a new exact lease.
Then assign shared refresh and split application as separate leases.
Then assign User Identity, User Sessions, Google verification, Claim, Transfer, and Merge.
Product Experience receives a route contract before browser implementation.
Quality receives each final candidate with empty write leases and proof-only access.
Platform receives a separate operational lease for explicit PostgreSQL migrations, services, Tunnel, and release.

## Proof and handoff standard

Every repair keeps its first focused failure. Tests must match the risk.
Visible interface changes require desktop and 375-pixel browser proof.
Separate local, synthetic VM, hosted, private, and public proof.
Use only named synthetic schemas and verify their database, owner, marker, and OID before cleanup.
Never copy private configuration, databases, WAL files, uploads, secrets, or Portfolio rows into proof archives.

Every handoff contains only these sections:

### Facts

Current source observations, commands, evidence, and results.

### Limits

Unread sources, unrun tests, and proof classes outside the lease.

### Uncertainty

Unresolved behavior or evidence gaps.

### Open work

One safe next assignment, exact lease, and required owner value.

## Owner decisions

- Domain: `ratatosk.dev`.
- Nameservers: `mina.ns.cloudflare.com`, `sevki.ns.cloudflare.com`.
- Sign-in: Google only for beta.
- Email magic-link recovery: deferred.
- Off-site backups: deferred.
- No assumed identity mapping or private-data migration.
- No paid service without owner approval.
- No public deployment claim from local tests.

## Historical record

The prior board contains setup work, completed assignments, failed proofs, architecture traces, VM investigations, and earlier prompts.
It is retained in `plan/manager-open-beta-history.md` for evidence only.