# faðir open beta manager board

Date: 2026-09-07

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
| Identity and Data Integrity | None | Empty | Empty | Session candidate frozen for final review |
| Finance and Tax | None | Empty | Empty | MERGE-FIN-1 accepted |
| Market Data | SHARED-REFRESH-1 queued | Empty | Empty | Wait for the serial dispatch slot |
| Platform and Release | None | Empty | Empty | Strict SSH verified after owner started VM |
| Quality and Security | None | Empty | Empty | SESSION-1-FINAL passed |

Each role has one active assignment at most. The Senior reviews the worktree before every lease.
Run only one specialist task at a time. Queue every later task, including independent work.
Resume retained evidence after an interruption. Use focused and affected tests during repair; reserve the full suite for final lease acceptance.
The Senior reviews the diff, retained failed proof, final proof, and handoff before dependent work.

## Current accepted state

- `04bab50` published the seven-file Guest foundation.
- `476df16` published the five-file PostgreSQL runtime boundary.
- `4b681ae` published the current coordination records.
- `a390862` published the two-file scoped calculation service after independent acceptance and 370 isolated offline passes.
- `c131047` records the accepted seven-file internal User Session foundation; Quality returned PASS and verified archive/source bytes and retained schema metadata.
- Origin `main` was even with the local branch after the last push.
- ID-2 final proof: 18 focused passes, 365 offline passes, and 1 synthetic PostgreSQL pass.
- ID-2 retained the startup failure and verified no private query value escaped after repair.
- G2 is accepted. G3 is conditional on real PostgreSQL and private-scope proof.
- G4 is open. Internal User Sessions passed synthetic proof. No HTTP, cookie, Google identity, Claim, Transfer, Merge, hosted, or public pass exists.
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

## ID-3A acceptance

Facts: Commit `a390862` published the two-file scoped calculation service after Quality returned PASS.
The Senior matched both source hashes and compared archived files with committed `476df16` plus the two candidates.
Retained red proof: five absent-method failures. Final focused proof: five passes. Final isolated combined proof: 370 passes.
Evidence root: `C:/Users/doguk/AppData/Local/Temp/fadir-id3a-scope-20260906/`.
Final XML: `isolated-full-r5.xml`. Archive: `id3a-scope-candidate-r5.tar`, 85 entries.
Archive SHA-256: `9ebcf92962595396e1fa3d77bef7cf030b4fa00db0df9e04e90781f7dbbe66f8`.
Both write leases are released. Preserve every earlier archive, failure, and final proof.
Limits: The earlier canonical test run is not accepted isolated proof and may have read canonical configuration.
R5 copied three unneeded committed scripts outside the named paths: bootstrap, tray, and symbol verification.
Their source matched the commit, with newline-only tray differences. This scope error supplies no proof for those scripts.
Uncertainty: PostgreSQL request isolation, concurrent writes, HTTP, browser, and public behavior remain unproved.
Open work: Inspect the exact archive file list before the next extraction or test. Connect request identity and route scope.

## Next assignments

### SHARED-REFRESH-1

Queued after a confirmed usage-limit interruption. Its write leases are inactive until the Senior dispatches it again.
This Phase 4 prerequisite separates shared provider cache writes from private split application.
The Senior checked `app/providers/price_service.py` is clean and the new test and proof root are absent.
Write only `app/providers/price_service.py` and new `tests/test_shared_refresh.py`.
Read only those two paths plus `app/models.py`, `app/config.py`, `app/providers/yf_client.py`, `app/providers/base.py`,
`app/providers/market_hours.py`, `tests/test_splits.py`, `tests/test_providers.py`, and `tests/conftest.py`.
The code skill and relevant knowledge leaves are permitted. Use the supplied excerpt, not the board or history.
Add an explicit shared-only refresh entry point with the existing provider inputs and report shape.
It may update PriceCache and CorporateAction. It must never read Transaction relationships or mutate private rows.
Force may refresh provider data and split metadata; it must never apply splits to Transactions through this entry point.
Preserve the existing local refresh behavior until its later route/background cutover. Keep its formulas and split tests unchanged.
Require a clean caller Session before shared refresh. Reject pending ORM writes before provider calls or flushes.
Do not commit, roll back, or close the caller Session. No separate connection, model, migration, route, or split-reconciler change belongs here.
Retain focused red proof for forced refresh with shared Instruments and multiple private Portfolios, cold relationships, and pending caller writes.
Prove SQL has no private-row query or write, shared data updates, caller rollback works, and existing local split behavior remains.
Use only `C:/Users/doguk/AppData/Local/Temp/fadir-shared-refresh-20260906/`, after an absence check.
Build isolated source from committed `a390862` plus only the two candidates, with the same exact public archive paths specified for SESSION-1.
Inspect the file list before extraction/tests. Use committed public configuration, existing Windows packages, synthetic SQLite, and stubbed providers.
Run focused and full offline proof with explicit `-o addopts= -m "not live"`, fresh XML/basetemp, scoped temporary files, and no bytecode/cache writes.
Keep all archives and failures. No VM, live provider, package, private-data, public, commit, or push action is authorized.
Return concise Facts, Limits, Uncertainty, and Open work with hashes and proof paths/counts.

### SESSION-1

Final checkpoint report: 3 repaired live cases passed (11 deselected), PostgreSQL migration proof passed 1 (14 deselected), final isolated offline suite passed 383 (85 deselected, one warning). Remote XMLs are `current-source-r6/live-issue-collision.xml`, `live-migrations.xml`, and `final-full-offline.xml` under the existing guest proof root. The nine unchanged earlier live passes remain applicable. Four failed schemas remain intentionally preserved; no new failed schema was reported. Senior matched all seven current source hashes. Quality now reviews the seven candidate paths, accepted Guest service/runtime dependencies, and exact retained host/guest proof roots; no test rerun or mutation. HTTP, browser, Google, private, hosted, and public acceptance remain absent.

SESSION-1B produced the actual before-repair clock baseline: two expected PostgreSQL failures, with both schemas retained.
The corrected candidate passed nine live cases and failed two fixture cases. No migration suite or full offline suite ran.
The failures are a separate-connection read of an uncommitted row and a noncanonical fixed token before the intended unique collision.
SESSION-1B-FIX writes only `tests/test_postgresql_user_sessions.py`; all product files and other tests remain frozen.
Resumed on Luna High after a confirmed usage-limit stop. The fixture edits survived; continue their remaining proof without restarting implementation.
Facts: Resume retained the repaired test candidate but strict SSH to `192.168.247.10` timed out twice. Archive SHA-256 `122c3fa77946e45c7a52c60b6fb3e1212a2581175b2ed1bbd3ab2c9f2c184159`; PostgreSQL test SHA-256 `904cb3ca0805374cdf66a275db7bbec186cdbed43113e034954e654b3fadbd36`.
Limits: No new live, migration, or full offline result. Identity leases released while Platform checks reachability.
Uncertainty: The existing VM may have stopped or changed address; no cause established.
Resolved: The owner confirmed the VM was off and started it. Platform then verified strict SSH exit 0 at `192.168.247.10`, hostname `fadir-control-lab-01`, uptime one minute. Hyper-V metadata still requires permissions, but SSH is available. Platform leases are released; Identity resumes the retained proof archive with its prior exact scope.
Open work: VM-REACHABILITY-1 reads only host Hyper-V state, its VM network adapter addresses, host network routes/neighbors, and the existing SSH trust host identifiers. Probe only the identified lab VM with the existing key and strict trust. No VM start, settings, trust, service, database, package, or file mutation. Return the verified address/identity or concrete blocking fact before repair.
Inspect the issued row through its caller connection and prove a second connection cannot see it before commit.
Use a canonical secret in the collision fixture. Cover public-identifier and secret-digest collisions without printing either secret.
Retain the existing failures. Run only the repaired live cases first, then the named migration tests and one final isolated offline suite.
Use the existing host/guest roots, exact archive inputs, strict SSH, timeouts, and schema controls. Stop on any new unexpected failure.
The nine unaffected live passes remain valid because the product source is frozen. Do not restart their test cycle without a new defect.
Retained expected-red schemas: `session1_fee5c638e63944f3afd27a4b985f7b5a` (OID 43752), `session1_6a586314a0884b689c8aff00e04df2a8` (OID 43918).
Retained fixture-failure schemas: `session1_fe0fef40192e4b8b8f0d53fe93f1cfbd` (OID 44084), `session1_1dee1fc330ca4d0db301ca5349e70c20` (OID 45412).
Preserve these schemas and their XML markers. Their retention is intentional; do not claim zero remaining schemas.

SESSION-1A-CLOCK completed. The Senior reviewed the small source delta: both bulk methods validate one time against selected row timestamps.
The helper-only local clock test does not demonstrate the original service-method defect; its two failures are not accepted behavioral red proof.
SESSION-1B-PROOF removes only that duplicate helper test from `tests/test_user_sessions.py`. All product files and other tests stay frozen.
Use the same named manual reads and exact public archive inputs. Both named host and guest proof roots are now active for synthetic proof.
Build a fresh before-repair source using the retained r2 service bytes and current named PostgreSQL clock tests.
Run only the two clock cases against this retained service and keep their expected failures as behavioral baseline evidence.
Then run the named User Session and migration PostgreSQL tests against the current corrected candidate.
Use strict SSH, the existing guest environment, `fadir_test`, exact schema prefixes, timeouts, and ownership checks from the contract below.
Retain expected-failure schemas and report their exact identifiers. Clean only successful new test schemas with verified ownership.
Run the full isolated offline suite once after the current candidate passes the live tests. Stop on an unexpected failure and retain it.
No other repair, package, service, private-data, or public action is authorized. Return concise four-section evidence for final review.

SESSION-1A-REVIEW returned NOT READY for one source-proved clock defect.
`revoke_all` can write revocation before stored creation or access times. `list_active` also omits row-aware time checks.
The Senior checked current hashes and assigns SESSION-1A-CLOCK to Identity with exactly three write paths:
`app/services/user_sessions.py`, `tests/test_user_sessions.py`, and `tests/test_postgresql_user_sessions.py`.
Keep the other four session candidate files frozen. Use only the existing host proof root; no VM or full-suite run.
Retain a focused failure for backward time through list and bulk revoke. Validate the operation's time against its selected rows before returning or writing.
Prove no target timestamp changes and no caller transaction loss on rejection. Add the matching planned PostgreSQL case without running it yet.
Run only focused affected tests and create a fresh checked archive. Preserve all earlier proof and use the same archive/read allowlists.
Return the repair diff, focused result, hashes, and a concise four-section handoff. The Senior will review this bounded delta before VM proof.
The earlier broad VM approval remains valid. No new owner approval is required for the named synthetic PostgreSQL proof.

SESSION-1A checkpoint completed. Both write leases are released and all seven candidate files are frozen.
Facts: The retained absent-model/service proof has seven failures. Isolated affected proof passed 49 tests with no skips or failures.
The Senior matched all seven candidate hashes and parsed `isolated-affected-r2.xml` in the exact host proof root.
Candidate archive SHA-256: `4fe2dd349d574f2c91f2c418e91e1b723dc851c2731b3879ddbba2dae0b8bc83`.
Limits: No full offline, real PostgreSQL, VM, HTTP, or public acceptance exists for this session candidate.
Uncertainty: Transaction ownership, race behavior, and migration execution still need the later PostgreSQL proof.
Open work: SESSION-1A-REVIEW reads only the seven candidate paths, `app/services/guest_access.py`, `app/db.py`, and the exact host proof root.
Quality receives the contract excerpt. It may inspect Git status/diff and compare archive bytes with committed `a390862` plus those seven files.
Review the planned live tests and success-only cleanup before activation. Run no test, repair, VM probe, or new artifact.
Return READY or NOT READY for the next proof checkpoint, with concise Facts, Limits, Uncertainty, and Open work.

Both specialist tasks stopped at a confirmed usage limit. SESSION-1A resumes first under the new serial dispatch rule.
Checkpoint scope: finish the session source and retained focused offline tests, then stop with a concise handoff.
Use only the existing host proof root. Do not start live PostgreSQL, the VM, or the full offline suite in this checkpoint.
Remove inherited `FADIR_*` values in the test subprocess, then set only the synthetic configuration and path values it needs.
Print no environment values. Keep PostgreSQL opt-in values exclusive to the later live command.
Retain the seven-test absent-model/service failure and every partial file. No restart or repeated broad proof is required.
The later PostgreSQL proof remains required for final acceptance and keeps its reserved resource contract below.
Request identity needs revocable User Sessions before the final route and Google cutover.
The Senior verified three existing files have no diff and four new paths are absent.
Write exactly `app/models.py`, `app/services/user_sessions.py`, `migrations/versions/0005_user_sessions.py`,
`tests/test_user_sessions.py`, `tests/test_postgresql_user_sessions.py`, `tests/test_migrations.py`, and `tests/test_postgresql_migrations.py`.
Manual read scope is those seven paths plus `app/services/guest_access.py`, `app/db.py`, `app/config.py`,
`migrations/env.py`, `migrations/versions/`, `tests/test_guest_access.py`, `tests/test_postgresql_guest_access.py`,
`tests/conftest.py`, `pytest.ini`, and `requirements-migrate.txt`. The code skill and relevant knowledge leaves are permitted.
The Senior supplies this excerpt; read no board history or unrelated source.

Add User Session persistence and internal issue, authenticate, list, revoke-one, and revoke-all operations.
Issue only for an existing User with its Workspace. Create no User, Workspace, Login Identity, Google flow, or HTTP endpoint.
Use a random opaque session token, store only its 32-byte digest, and expose a separate opaque public session identifier.
Store aware creation, last-access, and revocation times. Expire after exactly 30 days without successful authenticated access.
List only the caller User's active sessions with public identifier and dates. Never expose token digests or private fields.
Return User and Workspace authority only within the caller-owned PostgreSQL root transaction.
Follow the accepted Guest rules for supported psycopg transactions, parameter hiding, pending security-state rejection, trusted time, and stable errors.
Use consistent User, Workspace, then User Session lock order and fresh post-lock checks. Preserve unrelated caller state and transaction ownership.
Make cross-User revocation indistinguishable from an unknown session. Repeated own-session revocation is a bounded no-op.
Do not refresh inactive clocks on failed authentication or session list/revoke targets. The authenticated current session can renew normally.
No operation reads Portfolio contents. Use no email, browser fingerprint, user agent, or device identifier.

Retain focused failed proof before implementation. Test expiry boundary, rotation/collision safety, revocation, ownership, rollback, clock failure, and secret-safe errors.
Use real PostgreSQL for locking, same-User concurrency, revocation races, caller-state preservation, and migration proof.
Proof roots: `C:/Users/doguk/AppData/Local/Temp/fadir-user-sessions-20260906/` and `/home/fadir-agent/fadir-tests/user-sessions-20260906/`.
Verify both roots are absent before creation. Preserve every existing resource.
Build proof source from committed `a390862` plus only the seven leased files.
Archive-only read scope: committed `app/`, `tests/`, `migrations/`, `alembic.ini`, `requirements*.txt`, `pytest.ini`, `config.yaml`,
`scripts/make_golden.py`, and `examples/seed_transactions.example.csv`. Inspect exact entries before extraction or tests.
Use the existing Windows environment and guest environment. Install no package. Force configuration to the extracted public file.
Run focused tests with `-o addopts= -m "not live"`, fresh XML and basetemp, and no bytecode or pytest cache writes.
Run the full offline suite once at final lease acceptance. Earlier broad runs require a cross-cutting change or a specific new failure.
Use existing strict SSH to `fadir-agent@192.168.247.10`; key `C:/ProgramData/fadir-agent-control/lab_ed25519`, trust `C:/ProgramData/fadir-agent-control/lab_known_hosts`.
Use the key only for authentication. Preserve key and trust contents and permissions.
Live tests use only the existing synthetic `fadir_test` database through `postgresql+psycopg:///fadir_test` and the established explicit opt-in variables.
Select only the new session PostgreSQL test and PostgreSQL migration tests. Bound the command to 300 seconds, SQL waits, and worker joins.
Create only new `session1_<32hex>` or migration-test `db6a_<32hex>` schemas. Confirm database, name, owner, marker, and OID before success-only cleanup.
Retain failed or unconfirmed schemas and all archives/XML. Change no role, package, service, database configuration, private data, or public resource.
Return only concise Facts, Limits, Uncertainty, and Open work with source hashes and proof summaries. The Senior owns review and publication.

GOOGLE-CONTRACT defines the Google sign-in boundary before implementation.
Quality may read only `app/models.py`, `app/services/guest_access.py`, and `docs/adr/0004-google-primary-with-email-magic-link.md`.
The Senior supplies the relevant beta excerpt and official Google source URLs. Both write leases are empty.
Recommend one flow, server verification rules, browser binding, replay controls, User Session lifecycle, and minimal stored identity fields.
Use issuer and subject, never email matching. Preserve explicit Guest Claim, Transfer, and Merge choices.
Specify concrete required owner configuration without requesting secrets in chat. Do not claim Google account or public proof.
Return concise Facts, Limits, Uncertainty, and Open work, with source URLs, retrieval date, version scope, and research limits.
The first report recommends a redirect POST but leaves its transaction-cookie policy unresolved.
Quality must resolve that browser boundary before acceptance. Compare GIS popup with a same-origin credential POST.
Specify nonce storage and expiry, one-use consumption, CSRF, cookie policy, issuer normalization, key-cache failures, and exact owner configuration.
Keep the same source and documentation read scope. This refinement permits no implementation or account action.

Google contract review: accept GIS JavaScript popup and a same-origin credential POST as the implementation direction.
Use authorized origin `https://ratatosk.dev`. This flow needs no Google redirect URI or client secret.
Use a ten-minute, browser-bound login transaction, nonce, CSRF checks, exact audience, signature, expiry, and canonical issuer plus subject.
Consume verification once. Store no raw Google credential. Omit email unless a later explicit product need requires it.
Use hashed opaque User Session tokens, 30-day inactivity, successful-access renewal, and revocation.
Keep network verification outside database locks, with bounded timeout and public-key cache expiry. Fail closed if verification is unavailable.
Senior correction: do not create an empty Workspace that defeats the accepted new-User Claim flow.
Resolve the verified identity first. Finalize new User and Workspace creation with the explicit Guest choice in one transaction.
An incomplete sign-in transaction grants no User or private-data authority. Existing Users keep their Workspace and explicit Transfer/Merge choices.
Limits: This is a contract, not Google, session, or browser proof. Package version and concrete implementation tests remain required.
Official sources retrieved 2026-09-06: `https://developers.google.com/identity/gsi/web/guides/verify-google-id-token`,
`https://developers.google.com/identity/gsi/web/guides/display-button`, `https://developers.google.com/identity/gsi/web/reference/js-reference`,
and `https://google-auth.readthedocs.io/en/latest/reference/google.oauth2.id_token.html`.
Version scope: current Web GIS documentation and the reported google-auth 2.38.0 reference; no installed version or account UI was verified.

SPLIT-SCOPE-DESIGN resolves the corporate-action boundary needed before scoped public routes.
Market Data may read only `app/providers/price_service.py`, `app/services/portfolio.py`, `app/models.py`,
`app/services/portfolio_scope.py`, `tests/test_splits.py`, and `docs/SPEC.md` section 5.
The Senior supplies the beta requirements in the prompt. Both write leases are empty; run no test or provider call.
Trace the shared applied flag, late transactions, retries, partial failure, and concurrent Portfolio work.
Propose one precise split-application contract that preserves stored-cost invariance and keeps shared refresh out of private rows.
Identify any model or migration need and sequential exact leases. Treat unproved behavior as uncertainty.
Return only a concise Facts, Limits, Uncertainty, and Open work handoff. Full implementation waits for review.
Report complete: a unique Transaction/action application record can cover independent Portfolios and late historical rows.
The shared applied flag cannot prove which legacy rows received a split. Do not guess that mapping or rewrite private values.
The Senior will preserve the private migration gate. New synthetic data can prove the new contract without an owner-data decision.

Complete the internal User Session foundation, then assign request identity, route selection, and private CRUD under a new exact lease.
Then assign shared refresh and split application as separate leases.
Then complete Google verification, Claim, Transfer, and Merge with the accepted session and scope boundaries.
Product Experience receives a route contract before browser implementation.
Quality receives each final candidate with empty write leases and proof-only access.
Platform receives a separate operational lease for explicit PostgreSQL migrations, services, Tunnel, and release.

## Proof and handoff standard

Every repair keeps its first focused failure. Tests must match the risk.
Visible interface changes require desktop and 375-pixel browser proof.
Separate local, synthetic VM, hosted, private, and public proof.
Use only named synthetic schemas and verify their database, owner, marker, and OID before cleanup.
Never copy private configuration, databases, WAL files, uploads, secrets, or Portfolio rows into proof archives.

Test policy: retain one focused red proof before each repair; run the focused proof and targeted regressions after repair; run the full offline suite once at final lease acceptance or sooner only for a cross-cutting change. Run PostgreSQL, VM, browser, hosted, and public checks only when the lease requires them. A new defect adds one focused regression and an affected-set rerun. After two failed design reviews without executable progress, stop expanding tests and require an architecture or owner decision.

Apply the global Elonmusk rule: do not optimize something that should not exist; cut as much as possible before breaking the project; then fix and clean up only what remains.

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
