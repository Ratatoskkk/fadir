# faðir open beta manager board

Updated: 2026-09-10. This is the only live work board.

## Goal and next action

Finish the hosted private-portfolio beta in [the product brief](../docs/OPEN_BETA_BRIEF.md).
The immediate user outcome is a browser that stays signed in after refresh and shows
the owner's original portfolio under the verified Google User.

**Hydration is accepted locally and published as `b22875e38a7174d823212bb291dcd78151e781bd`.**
The VM deployment and hosted public edge proof are now accepted. The protected dry run
and committed-candidate recovery are also accepted within their guards. The next action
is a separately leased live migration into the existing serving `public` context for
the approved `Ana Portföy`/TRY mapping; the source, candidate, and existing serving
state remain preserved until the live lease's pre-commit gate passes.
Do not restart APP, identity architecture, credential rotation, or the completed
Transfer repair.

## Current authority

- Senior: `gpt-5.6-luna` / `max`. Specialists: `gpt-5.6-luna` / `medium`.
  Use the [shared work rules](../AGENTS.md) and [dispatch contract](README.md#dispatch-contract).
- The owner approved continued delivery through product completion, VM and public
  release, recovery proof, reviewed commits, and normal pushes to the existing origin.
  The Senior reviews; specialists implement under exact leases, one at a time.
- The owner explicitly assigned review and publication to the Senior: inspect each
  specialist's changes and required proof, then commit and push accepted paths to
  `origin/main`. Return unfinished work for repair/proof. Verify the remote commit
  and update the board before dependent implementation; no routine approval pause.
- Existing VM use, needed dependency installation in the VM, and Cloudflare MCP use
  are approved. Bound each operational change to its named resources and proof.
- `ratatosk.dev` is the approved domain. Google-only sign-in, deferred email recovery,
  deferred off-site backups, and direct Yahoo under the private permit remain settled.
- Private row inspection, a protected WAL-consistent snapshot, a private dry run, and
  conditional live migration after all validations were approved. The owner selected
  `Ana Portföy`, TRY Base Currency, and all legacy Transactions and Snapshots mapped
  to that Portfolio. The [migration runbook](../docs/PRIVATE_MIGRATION_RUNBOOK.md) separates
  those approvals from the technical preconditions still to be proved.
- Do not ask for those approvals again. Obtain only a missing concrete owner value or
  a new charge/destructive scope. No source deletion or destructive cleanup is authorized.
  Secrets and private values stay out of ordinary artifacts.

Authority includes the owner's 2026-09-10 instruction to publish the documentation
cleanup and make the Senior responsible for reviewing and pushing accepted specialist
work. The hydration publication changes no deployment; deployment remains a separate
Platform lease.

## Current checkpoint

### Facts

- Documentation baseline is published through `4d7e1f6` (`docs: record published
  coordination baseline`) and verified on `origin/main`; the earlier 21-file Markdown
  cleanup remains recorded in `e785b7e`.
- Hydration publication `b22875e38a7174d823212bb291dcd78151e781bd` is present on local
  `main` and `origin/main` with exactly `frontend/src/api.js` and
  `frontend/src/components/GoogleIdentityPanel.jsx`. The published files match the
  frozen hashes below.
- The hydration implementation checks `GET /api/user/sessions` on mount: 200 shows
  signed-in state, 401 returns to Google sign-in after guarded recovery, and other
  failures show a neutral retry state. Its retained handoff reports source checks
  and a successful frontend build. Fresh r3 evidence and independent Quality review
  accepted the component at 1440x900 and 375x812; see the evidence pointers below.
- The retained r1 red proof and r2 harness failure remain intact. r2 was not repaired in
  place; r3 used a separate plain-JavaScript harness that imported the real source.
- Platform deployment attempt `GOOGLE-SESSION-HYDRATION-DEPLOY-1` stopped before
  mutation: local build/archive and VM preflight passed, but the approved remote rollback
  parent was absent. The service remains unchanged with restart count zero. See the
  retained stop handoff at `C:/Users/doguk/AppData/Local/Temp/fadir-private-migration-20260910/session-hydration-deploy-r1/handoff.md`.
- Deployment follow-up `GOOGLE-SESSION-HYDRATION-DEPLOY-2` replaced the frontend bundle
  from the published manifest, preserved the nine-file rollback copy, restarted
  `fadir.service` exactly once, and verified loopback health 200. Both sanitized public
  probes returned HTTP 530. A read-only Cloudflare check shows tunnel
  `production-web-linux` (`d4e1cc1b-a37a-4ca6-9684-ffb91601bcc0`) is `down` with no
  connections; its saved route still points `ratatosk.dev` to `http://localhost:8000`.
  See `C:/Users/doguk/AppData/Local/Temp/fadir-private-migration-20260910/session-hydration-deploy-r2/handoff.md`.
- Tunnel repair `GOOGLE-SESSION-HYDRATION-TUNNEL-1` stopped read-only. The existing
  `cloudflared.service` is enabled but auto-restarting with `ExecMainStatus=255` because
  `/etc/cloudflared/token` is absent/empty. No connector restart, secret/config repair,
  Cloudflare write, DNS/Tunnel change, or application restart occurred. See
  `C:/Users/doguk/AppData/Local/Temp/fadir-private-migration-20260910/session-hydration-tunnel-r1/handoff.md`.
- A fresh read-only VM recheck after the Tunnel-1 handoff found the same protected
  precondition: the token remains absent/empty, `cloudflared.service` remains enabled
  in `activating/auto-restart` with `ExecMainStatus=255` and `NRestarts=4788`, while
  `fadir.service` remains active on `127.0.0.1:8000`. No repair or restart occurred.
- Tunnel repair `GOOGLE-SESSION-HYDRATION-TUNNEL-2` passed. The owner-provisioned
  token was present as root:root mode 600 without exposing its value. Exactly one
  existing `cloudflared.service` restart left it active/enabled with `ExecMainStatus=0`;
  the named tunnel had four healthy connections and its remote-managed configuration
  was unchanged. Loopback health, public `/api/health`, `/`, and both referenced
  hashed assets returned 200 and matched the deployed bundle. See
  `C:/Users/doguk/AppData/Local/Temp/fadir-private-migration-20260910/session-hydration-tunnel-r2/handoff.md`.
- `PRIVATE-MIGRATION-DRYRUN-1` stopped before target creation. The fresh SQLite
  snapshot/restore proof passed and the protected service context had exactly one
  eligible Google issuer/subject -> User -> Workspace chain with no Portfolio, but a
  fresh owner/provider issuer+subject comparison was unavailable. No target, schema,
  migration, cleanup, freeze, or serving-state change occurred. See
  `C:/Users/doguk/AppData/Local/Temp/fadir-private-migration-20260910/private-migration-r1/handoff.md`.
- A fresh owner-authenticated hosted browser state is now visible: the panel reports
  `Google User` session active with User Workspace access, while the portfolio remains
  empty as expected before migration. No cookies, identity values, or private rows
  were emitted. This enables a new protected identity/session binding lease; it is not
  itself migration or portfolio acceptance.
- `PRIVATE-MIGRATION-DRYRUN-2` proved `owner_identity_match=true` in protected
  execution and passed fresh source snapshot/restore parity, but stopped with a
  sanitized isolated-target setup failure before complete validation. No PASS is
  claimed; candidate target state is unknown and must be verified before retry or
  cleanup. No serving or public state changed. See
  `C:/Users/doguk/AppData/Local/Temp/fadir-private-migration-20260910/private-migration-r2/handoff.md`.
- `PRIVATE-MIGRATION-TARGET-VERIFY-1` found exactly one task-owned candidate with
  valid database/owner/marker/OID guards, the accepted-or-superset table set, the
  accepted Alembic head, and root/shared/private row-presence categories. No active
  transaction or per-schema commit/rollback evidence was available, so the candidate
  remains UNKNOWN and is preserved. The read-only protected database/service
  mutation count was zero. See
  `C:/Users/doguk/AppData/Local/Temp/fadir-private-migration-20260910/private-migration-target-verify-r1/handoff.md`.
- `PRIVATE-MIGRATION-TARGET-VALIDATE-1` re-guarded the same candidate and proved
  complete content: accepted schema/constraints/indexes/FKs, exact approved
  identity/User/Workspace/Portfolio binding, source-to-candidate row/key/value
  reconciliation, typed value fidelity, private ownership, shared separation,
  target isolation, and source/snapshot preservation. The protected mutation count
  was zero. PostgreSQL still exposed no independent commit/rollback evidence, so
  this is COMPLETE-CONTENT-BUT-OUTCOME-UNKNOWN, not migration acceptance. See
  `C:/Users/doguk/AppData/Local/Temp/fadir-private-migration-20260910/private-migration-target-validate-r1/handoff.md`.
- `PRIVATE-MIGRATION-OUTCOME-AUDIT-1` re-guarded the candidate and searched the
  bounded PostgreSQL log/journal/audit surfaces. Statement/audit logging, durable
  audit tables, and candidate-matching log records were unavailable or absent;
  explicit COMMIT/ROLLBACK evidence was not found. Protected database/server/SQLite/
  repository/public mutation count was zero, so the candidate remains UNKNOWN and
  isolated. See
  `C:/Users/doguk/AppData/Local/Temp/fadir-private-migration-20260910/private-migration-outcome-audit-r1/handoff.md`.
- The owner has now authorized a bounded recovery: preserve and isolate the existing
  candidate/source; correlate candidate-row `xmin` values to this attempt; query
  PostgreSQL 16 `pg_xact_status(xid8)` with the correct full transaction ID; repair
  the rehearsal script's invalid unused access and PASS gates; and use a fresh
  isolated target only if the historical outcome remains unrecoverable. No candidate
  or source reinsertion, cleanup, or serving change is authorized by this instruction.
- `PRIVATE-MIGRATION-XID-RECOVERY-1` correlated all five migration-table row groups
  to one full transaction ID and `pg_xact_status(full_xid::xid8)` returned `committed`.
  Candidate/source/database mutation count was zero; no fresh target was created. A
  fresh repaired copy removed the invalid unused `target.transaction` access, records
  `database_outcome` before later checks, and gates PASS on an explicit validation map.
  Its idempotent-rerun and failure/rollback checks were not run against the preserved
  candidate, so the lease verdict is BLOCKED_VALIDATION, not migration PASS. See
  `C:/Users/doguk/AppData/Local/Temp/fadir-private-migration-20260910/private-migration-xid-recovery-r1/handoff.md`.
- `PRIVATE-MIGRATION-COMMITTED-CHECKS-1` completed the two remaining guarded behavior
  checks without successful reinsertion. The duplicate rerun returned
  `ROLLED_BACK/TARGET_CONSTRAINT_CONFLICT`; the invalid-portfolio path returned
  `ROLLED_BACK/INVALID_PORTFOLIO_ID`; pre/post content, row-key, and row-count
  fingerprints matched, with `successful_reinsert_count=0` and
  `candidate_mutation_count=0`. The bounded validation outcome is PASS while the
  candidate remains isolated. See
  `C:/Users/doguk/AppData/Local/Temp/fadir-private-migration-20260910/private-migration-committed-check-r1/handoff.md`.
- `PRIVATE-MIGRATION-LIVE-1` is now the active bounded lease. It may write only through
  the protected VM migration channel and its fresh proof directory. The intended target
  is the existing serving PostgreSQL `public` context, preserving the existing verified
  Google User, Workspace, Login Identity, and User Sessions. The service remains on its
  current configuration; a short writer freeze and one bounded service stop/start are
  permitted only after the lease proves the writer set and rollback boundary.
- The earlier Transfer repair was published as `0bb35e9`. Retained Quality, focused
  PostgreSQL, and final offline evidence report PASS; the final offline suite had
  512 passes. The deployment handoff records the route delta, one restart, and
  loopback/public health 200. Those results predate the hydration candidate.
- A later owner-visible Transfer succeeded. The retained read-only state handoff records
  one identity/User/Workspace chain, active User Sessions, consumed login, revoked
  Guest access, and zero Portfolios. Credential rotation has a successful retained
  handoff and is not unfinished work.

### Limits

Hydration acceptance is component-level local synthetic browser proof only. It has no
persisted PNG paths; the r3 manifest, DOM observations, request log, and inline browser
captures are retained. The current host's focused backend session-route test could not
collect because system Python lacks `sqlalchemy`; no backend pass is inferred. No
full-App, authenticated User journey, migration, or full beta acceptance exists. The
current owner browser shows the User state but has not yet shown migrated private data.
The VM bundle, loopback service, tunnel, and public static/health reachability are
accepted; no authenticated or private-data acceptance is inferred.

### Uncertainty

The r1 full-App synthetic fixture still crashes before rendering the panel; this remains
a harness limitation, not an established App defect. The r3 signed-out mobile state
needed one extra observation before settling. The candidate's transaction outcome,
content reconciliation, idempotent rerun, and failure/rollback behavior are now
confirmed within the recorded guards. The candidate is still not a serving target;
live writer/freeze, cutover, rollback-window, and hosted owner checks remain separate.
The persisted Transfer timestamps were internally correlated but were not tied to an
authoritative screenshot time window.

### Open work

The recovery proof is complete. `PRIVATE-MIGRATION-LIVE-1` is the separate live lease;
keep the committed candidate isolated and stop before mutation if its fresh guards,
writer/freeze control, source freshness, or serving-scope decision cannot be proved.

## Resumable assignment

Status: **hydration accepted; VM deployment and public edge passed; DRYRUN-2 candidate is COMMITTED and its bounded content/behavior validation is PASS; `PRIVATE-MIGRATION-LIVE-1` is active**.
One Identity and Data Integrity specialist is active under the live lease.
The Product Experience browser, Quality, deployment, Tunnel, DRYRUN-1, and DRYRUN-2
leases are closed.

The active live-migration lease is:

| Field | Exact scope |
|---|---|
| Outcome | Revalidate the verified Google identity/User/Workspace binding, fresh WAL-consistent source snapshot, all relevant writers, candidate/source/serving guards, and every runbook validation; then migrate into the existing serving `public` context and prove hosted owner access after refresh |
| Repository writes | Empty; no product, migration-core, service-config, or frontend change is leased |
| Evidence reads | `C:/Users/doguk/AppData/Local/Temp/fadir-private-migration-20260910/private-migration-committed-check-r1/handoff.md`, `protected-committed-check-output.txt`, `private-migration-xid-recovery-r1/handoff.md`, `protected-xid-status-output.txt`, `private-migration-target-validate-r1/handoff.md`, `docs/PRIVATE_MIGRATION_RUNBOOK.md`, and the live service context |
| Operational writes/resources | Approved VM `fadir-control-lab-01`; protected `/home/fadir-agent/fadir-tests/venv/bin/python`; protected source/snapshot channels; serving PostgreSQL `public`; fresh absent `C:/Users/doguk/AppData/Local/Temp/fadir-private-migration-20260910/private-migration-live-r1/`; temporary `fadir.service` writer freeze and one bounded restart only after pre-commit checks; no Cloudflare, DNS, provider, source deletion, candidate cleanup, or public configuration write |
| Handoff | `C:/Users/doguk/AppData/Local/Temp/fadir-private-migration-20260910/private-migration-live-r1/handoff.md` |
| Proof | Before any target write, record sanitized identity/source freshness, writer/freeze, database/owner/search-path, candidate preservation, target and rollback boundary. Within one guarded transaction validate schema, identity, ownership, shared/private separation, reconciliation, value fidelity, isolation, failure behavior, and source preservation; commit only when all pass. After commit, restart/release the service and prove health plus authorized owner portfolio access after refresh. |
| Stop | Any identity ambiguity, source/WAL mismatch, concurrent writer, guard mismatch, validation failure, unknown outcome, missing pre-commit rollback boundary, need for product/configuration changes, unexpected service effect, or any request to retry, reverse-copy, delete, clean up, expose the candidate, or alter Cloudflare/public/provider state |

Do not start an owner-browser sign-in or change the product during this dry run. Private
source and target inspection is permitted only through the protected channels named
above; no identity, issuer, subject, email, holdings, transaction values, or secrets may
enter ordinary artifacts. If the protected target context is not uniquely selectable,
stop with the smallest next action. Any adapter repair, live cutover, service
configuration change, browser acceptance, or public proof requires a separate lease.

Proof root: `C:/Users/doguk/AppData/Local/Temp/fadir-private-migration-20260909/`.
Paths in the evidence row are relative to this proof root.

| Frozen file | SHA-256 |
|---|---|
| `frontend/src/api.js` | `D72B7038A066D920A3FA9CEBE157129E6F435851C146C0E9A9CCE666231BFADC` |
| `frontend/src/components/GoogleIdentityPanel.jsx` | `FADE560CA442CCB5A867FCAB06C3A1608CE18B1D17EE8D4B6BB28F1E71C524F2` |

## Delivery sequence and acceptance gates

The original phase order remains the dependency map. These are bounded recorded
results, not a fresh release certification. Do not repeat a completed gate without
changed source, failed evidence, or a newly established risk.

| Gate | Recorded state | Remaining outcome |
|---|---|---|
| G0 Coordination | Baseline exists; current instructions reconciled | Keep this checkpoint current |
| G2 Average Purchase Price | Accepted locally in earlier history | Retain the accepted lifetime purchase-average rule |
| G3 PostgreSQL and private scope | Conditional synthetic acceptance; later request scope and route work published | Complete the owner's private dry run/migration and its acceptance |
| G4 Guest and identity | Guest, Google transitions, Merge, session controls, and hydration candidate published; component hydration PASS | Accept hosted User refresh and finish Guest/User browser and session journeys |
| G5 Portfolios, currencies, tax | Portfolio selection, Fee Currency, Tax Profile backend/UI published | Finish full user journeys and close the missing independent Tax Profile review artifact |
| G6 Market data | Shared refresh route/worker published; direct Yahoo decision retained | Establish hosted cache, refresh, quota, source/time, and permitted public-use acceptance |
| G7 Security and data rights | Scoped routes, exports and deletion delivered; no-cookie denial matrix recorded | Finish authenticated isolation, data-rights UI, notices, abuse controls, and the recorded missing public security headers |
| G8 VM and public service | VM/Tunnel service, HTTPS health, bounded Guest denial and Google start observed | Accept the deployed user journeys and exact final release state |
| G9 Final acceptance and recovery | Earlier bounded VM rollback/reconstruction proof exists | Final browser/product/release acceptance; carry its version and data-recovery limits forward |

G9 needs the remaining G3–G8 outcomes. A public health 200, no-cookie 401, or local
suite pass cannot close an authenticated journey. Off-site backup and lost-Portfolio
recovery guarantees remain outside this beta.

After deployment and owner refresh acceptance, queue these outcomes one at a time:

1. Complete the protected migration into the verified Google User's `Ana Portföy`/TRY
   and prove that the original portfolio is accessible after refresh.
2. Reconcile and close the remaining G4–G7 product and security acceptance items against
   the beta brief. Check Guest product parity, including tax behavior; do not silently
   redefine full Guest use around the currently implemented User-only Tax Profile panel.
3. Complete G8/G9 on the accepted release, with browser, restart, rollback, and service
   reconstruction evidence appropriate to the actual change.

## Evidence pointers

Under the private-migration proof root above, read only the files needed by the lease:

- Hydration: `session-hydration-r1/handoff.md`, `session-hydration-r2/handoff.md`,
  `session-hydration-r3/manifest.md`, `session-hydration-r3/observations.log`, and
  `C:/Users/doguk/AppData/Local/Temp/fadir-private-migration-20260910/session-hydration-quality-r1/handoff.md`;
  published as `b22875e` and verified on `origin/main`.
- Transfer: `transfer-reject-quality-r3/handoff.md`, `transfer-reject-final-r1/handoff.md`,
  `transfer-reject-publish-r1/handoff.md`, `transfer-reject-deploy-r1/handoff.md`.
- Persisted transition: `post-transfer-state-r1/handoff.md`; credential rotation:
  `credential-rotation-r1/handoff.md`.
- Stopped private dry runs: `dryrun-r1/handoff.md` and `dryrun-r2/handoff.md`.
  These older handoffs contain superseded approval requests; use current authority above.

Older accepted evidence and its limits:

- [G2 acceptance](manager-open-beta-history.md#g2-acceptance).
- [Conditional G3 acceptance](manager-open-beta-history.md#g3-acceptance-and-g3-record).
- [Tax Profile bounded Senior review](archive/manager-open-beta-2026-09-10.md#g5-tax-profile-1-senior-review-r1-acceptance).
- [Bounded VM rollback and reconstruction](archive/manager-open-beta-2026-09-10.md#vm-rollback-reconstruction-1-acceptance).
- [No-cookie private-route denial](archive/manager-open-beta-2026-09-10.md#g8-public-unauthenticated-private-gate-1-acceptance).
- [Session deployment and missing security headers](archive/manager-open-beta-2026-09-10.md#user-session-controls-1-deploy2-acceptance).

Keep old failed proofs and raw artifacts intact. Record only concise accepted summaries
here; move closed chronology into [history](README.md#historical-reference).
