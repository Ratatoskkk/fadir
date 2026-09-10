# faðir open beta manager board

Updated: 2026-09-10. This is the only live work board.

## Goal and next action

Finish the hosted private-portfolio beta in [the product brief](../docs/OPEN_BETA_BRIEF.md).
The immediate user outcome is a browser that stays signed in after refresh and shows
the owner's original portfolio under the verified Google User.

**Hydration is accepted locally and published as `b22875e38a7174d823212bb291dcd78151e781bd`.**
The earlier VM deployment and hosted public edge proof are accepted. The newer session-auth
serialization repair is now deployed with its rollback copy and sanitized public
static/health proof. The protected dry run, committed-candidate recovery, and live
database migration are accepted within their guards. The owner refresh still shows a
request rejection, and the narrow diagnostic established a real `/api/portfolio` 500 in
the trusted window. The backend root cause is repaired and deployed as `71eacca`, with
its rollback copy preserved; the sanitized portfolio probe is still authorization-blocked.
The new owner-browser refresh still shows `Bağlantı hatası: request rejected`. The
separately leased r3 service correlation returned no allowlisted records for the exact
trusted window, so it could not attribute a route or status. The next action is a
bounded local source proof and smallest repair of the User-session request boundary;
the owner red browser proof, source, candidate, serving data, and rollback remain
preserved.
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
- `PRIVATE-MIGRATION-LIVE-1` was the bounded live-migration lease. It used only the
  protected VM migration channel and its fresh proof directory. Its target was the
  existing serving PostgreSQL `public` context, preserving the verified Google User,
  Workspace, Login Identity, and User Sessions; service configuration was unchanged.
- `PRIVATE-MIGRATION-LIVE-1` completed with `COMMIT` in the serving `public` context.
  Protected ownership, reconciliation, value fidelity, isolation, source preservation,
  and post-checks passed for `Ana Portföy`/TRY. The lease inserted 1,164 shared rows and
  17 private rows, stopped/started `fadir.service` once, and verified loopback and
  hosted health 200. Its hosted owner proof is blocked: refresh displayed the portfolio
  selector but the private portfolio request returned 401. See
  `C:/Users/doguk/AppData/Local/Temp/fadir-private-migration-20260910/private-migration-live-r1/handoff.md`.
- `GOOGLE-SESSION-AUTH-SERIALIZATION-1` completed and was published as
  `a270f4072d86b2c72b3e9560f4e40402ec6bb6d8`, changing only `frontend/src/api.js`.
  The FIFO queue covers every session-dependent operation, including Google start;
  only health and Guest bootstrap bypass it. The accepted local build, deterministic
  recovery/serialization harness, and synthetic 1440x900/375x812 browser proof pass.
  See `C:/Users/doguk/AppData/Local/Temp/fadir-private-migration-20260910/session-auth-serialization-r1/handoff.md`
  (SHA-256 `6F958254877AB59F59353538037FEEF8885452DBEDF5D657ADCBEA36739455F4`).
- `GOOGLE-SESSION-AUTH-SERIALIZATION-DEPLOY-1` stopped before VM mutation because the
  approved SSH identity and matching strict known-hosts entry were unavailable in the
  current session. The published build/archive passed local verification; restart count
  is zero and the retained hosted 401 remains red until this exact build is deployed.
  Handoff: `C:/Users/doguk/AppData/Local/Temp/fadir-private-migration-20260910/session-auth-serialization-deploy-r1/handoff.md`
  (SHA-256 `0C0EFAF4FF64750BC420C706C42054C6EE339B64B89C4005C87F6480933199B2`).
- A fresh strict read-only SSH preflight now succeeds with the approved control paths
  `C:/ProgramData/fadir-agent-control/lab_ed25519` and
  `C:/ProgramData/fadir-agent-control/lab_known_hosts`, while bypassing a stale local
  SSH-agent pipe. It proves the expected hostname, active `fadir.service`, and the
  port-8000 listener without changing the VM. The r1 stop evidence remains preserved;
  the deployment retry uses a fresh r2 proof root.
- `GOOGLE-SESSION-AUTH-SERIALIZATION-DEPLOY-2` passed. The published `a270f40` bundle
  was transferred and verified, the prior frontend directory remains at the approved
  remote `dist.previous` rollback path, and exactly one `fadir.service` restart left
  the service active with `NRestarts=0` and listener `127.0.0.1:8000`. Loopback and
  public health/shell/hashed shell assets returned 200. Handoff:
  `C:/Users/doguk/AppData/Local/Temp/fadir-private-migration-20260910/session-auth-serialization-deploy-r2/handoff.md`
  (SHA-256 `0C9F01C09487603B7E7D6D9429C438CE643F6B91AFE5125F8DC4C485451CCCB7`).
  The public shell includes Cloudflare Insights injection; its application asset
  references and hashed JS/CSS match the published manifest. No authenticated owner
  acceptance is inferred.
- The first post-deployment owner-tab refresh loaded the published JS/CSS but still
  visibly rendered `Bağlantı hatası: request rejected` with `Ana Portföy · TRY` selected.
  The owner-browser lease stopped before acceptance; no cookie, identity, private row,
  response body, or provider action was captured.
- `GOOGLE-SESSION-AUTH-SERIALIZATION-OWNER-DIAGNOSTIC-1` correlated real allowlisted
  VM traffic but was blocked by an untrusted wide journal window: `/api/portfolio`
  included 401 and 500 responses, while history and transactions were mixed 200/401;
  no session/recovery tuples were retained. Handoff:
  `C:/Users/doguk/AppData/Local/Temp/fadir-private-migration-20260910/session-auth-serialization-owner-diagnostic-r1/handoff.md`
  (SHA-256 `A1E3FF4C1BC7E3B015C88E9CAD6987C762470D68A8FD07AAC43718CA94C5C410`).
- `GOOGLE-SESSION-AUTH-SERIALIZATION-OWNER-DIAGNOSTIC-2` correlated the trusted
  owner-refresh window with sanitized endpoint tuples. It recorded `/api/portfolios` 200,
  `/api/portfolio` 500, `/api/portfolio/history` 200, `/api/transactions` 200, and
  `/api/instruments` 200, with no session/recovery tuple. Attribution to an individual
  refresh remains limited because the available records lack per-request timestamps or
  correlation IDs, but the `/api/portfolio` 500 is a real established backend failure in
  the bounded window. Handoff:
  `C:/Users/doguk/AppData/Local/Temp/fadir-private-migration-20260910/session-auth-serialization-owner-diagnostic-r2/handoff.md`
  (SHA-256 `CC69D4F6B3B8BB6E1C3AF3691C5488CF4792F881E9DC76C0700B238B688656B7`).
- `GOOGLE-SESSION-AUTH-SERIALIZATION-PORTFOLIO-500-REPAIR-1` proved the source trigger
  with synthetic SQLite data: a migrated-style transaction with a foreign fee and no fee
  FX rate raised `ValueError` while building the current lot book, which the request
  transaction boundary sanitized to HTTP 500. `PortfolioService.build_view` now isolates
  that malformed position as `ok=false` and continues rendering the portfolio; authority,
  session, route, response-schema, and frontend contracts are unchanged. Focused,
  affected, and full offline suites passed. The accepted source/test commit is `71eacca`.
  Handoff:
  `C:/Users/doguk/AppData/Local/Temp/fadir-private-migration-20260910/session-auth-serialization-portfolio-500-repair-r1/handoff.md`
  (SHA-256 `29B374876A0EADCF0C65723F0E9C038B48FF180CCBFD388B808122521BFE2D52`).
- `GOOGLE-SESSION-AUTH-SERIALIZATION-PORTFOLIO-500-DEPLOY-1` deployed the accepted
  backend file to `/opt/fadir/app/services/portfolio.py` with the exact source hash and
  preserved its rollback copy. Exactly one `fadir.service` restart left the service
  active/enabled with `NRestarts=0`; sanitized loopback health returned 200. The local
  portfolio probe returned 401 and is authorization-blocked, so no authenticated route or
  browser acceptance is claimed. Handoff:
  `C:/Users/doguk/AppData/Local/Temp/fadir-private-migration-20260910/session-auth-serialization-portfolio-500-deploy-r1/handoff.md`
  (SHA-256 `61AAAF2EB49B4301C281F57E614C6C9F7B2D37BD4FB84479525F9FD91CF4D7F5`).
- `GOOGLE-SESSION-AUTH-SERIALIZATION-OWNER-BROWSER-2` refreshed the current owner tab
  exactly once after backend deployment. The trusted window was
  `2026-09-10T19:48:13.161Z`–`2026-09-10T19:48:13.696Z`; after settling, the visible
  selector showed `Ana Portföy · TRY` and the page showed `Bağlantı hatası: request
  rejected`. No private values or browser credentials were captured, and no owner
  acceptance is claimed. Handoff:
  `C:/Users/doguk/AppData/Local/Temp/fadir-private-migration-20260910/session-auth-serialization-owner-browser-r2/handoff.md`
  (SHA-256 `A111599C56F2FE98DF1DD9B2B963BA356FD704638FB4E483051E348370460ED3`).
- `GOOGLE-SESSION-AUTH-SERIALIZATION-OWNER-DIAGNOSTIC-3` was read-only and returned no
  allowlisted service records for the exact trusted browser window or its small
  clock-safe margin. It retained no raw log lines and proved the hostname, active/
  enabled service, MainPID `66511`, `NRestarts=0`, and listener unchanged before and
  after. Verdict: `CORRELATED-BUT-BLOCKED`; it does not establish a User-session 401,
  renewal, `/api/portfolio` status, another portfolio route, or service behavior.
  Handoff:
  `C:/Users/doguk/AppData/Local/Temp/fadir-private-migration-20260910/session-auth-serialization-owner-diagnostic-r3/handoff.md`
  (SHA-256 `04572B10358DD437C7F7FCD6A96132DD3A142748867FD9FF9BF4F87C44EAF85C`).
- `GOOGLE-SESSION-AUTH-SERIALIZATION-SESSION-401-REPAIR-1` accepted the smallest
  frontend repair and published it as `600289e`. The local synthetic fetch boundary
  proved that `POST /api/guest/bootstrap`, although authority-independent at the
  route, still participates in the browser session boundary and was incorrectly
  outside the FIFO; it could overlap User-session renewal and trigger PostgreSQL
  `NOWAIT` contention. Only `GET /api/health` now bypasses the queue. The focused
  synthetic recovery/concurrency proof passed with `maxPrivate=1`; `node --check`,
  `git diff --check`, and `npm run build` (844 modules) passed. Handoff:
  `C:/Users/doguk/AppData/Local/Temp/fadir-private-migration-20260910/session-auth-serialization-session-401-repair-r1/handoff.md`
  (SHA-256 `6ED4D1BA36A1D311E21AE6120094CE978D26051D497FE3E96A7FA39160D68E1E`).
  The accepted source hash is
  `9860B1E150AA7D52E6C8A64456C0A36A75BED20D0D477A19549FD546B5F7929E`.
- `GOOGLE-SESSION-AUTH-SERIALIZATION-SESSION-401-DEPLOY-1` passed. The accepted
  `600289e` bundle matched its source/archive manifest, replaced only
  `/opt/fadir/frontend/dist`, and preserved the prior bundle at the lease-owned
  rollback path. Exactly one `fadir.service` restart left the service active/enabled,
  `ExecMainStatus=0`, `NRestarts=0`, and listening on `127.0.0.1:8000`. Sanitized
  loopback/public health, shell, and all three hashed assets returned 200; no
  authenticated route or browser acceptance is inferred. Handoff:
  `C:/Users/doguk/AppData/Local/Temp/fadir-private-migration-20260910/session-auth-serialization-session-401-deploy-r1/handoff.md`
  (SHA-256 `A8221BFA3345548BA313A344C9646DD97C45209BC7008F74C90BE7FEB6C855E6`).
- `GOOGLE-SESSION-AUTH-SERIALIZATION-OWNER-BROWSER-3` stopped before proof because
  its browser inventory at `2026-09-10T20:17:48.7698289Z` contained no open tabs; the
  required existing authorized owner tab was unavailable in that browser context.
  No refresh, navigation, UI state, request tuple, credential action, or mutation
  occurred. Verdict: `BLOCKED`. Handoff:
  `C:/Users/doguk/AppData/Local/Temp/fadir-private-migration-20260910/session-auth-serialization-owner-browser-r3/handoff.md`
  (SHA-256 `20BD62F770A1B3ED94665A9374CEEF8BE93D14C712D0A89595E770C6C388A11F`).
- The retained 401 is a real hosted defect: the browser starts concurrent private requests while
  `user_sessions.authenticate` renews one User Session under PostgreSQL `NOWAIT`, so
  lock contention can become a sanitized 401. The repair stays at the browser request
  boundary; no backend authority or lock behavior changed.
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
current owner browser shows the User state and portfolio selector but has not yet shown
migrated private data; the live lease recorded a reproducible private-request 401. The
deployed bundle, loopback service, tunnel, and public static/health reachability are
accepted. No authenticated or private-data acceptance is inferred.

### Uncertainty

The r1 full-App synthetic fixture still crashes before rendering the panel; this remains
a harness limitation, not an established App defect. The r3 signed-out mobile state
needed one extra observation before settling. The candidate's transaction outcome,
content reconciliation, idempotent rerun, and failure/rollback behavior are confirmed
within the recorded guards. The candidate remains isolated evidence; hosted
owner/browser acceptance remains separate.
The persisted Transfer timestamps were internally correlated but were not tied to an
authoritative screenshot time window.

### Open work

The recovery and live migration proofs are complete within their recorded limits. The
browser repair and backend 500 repair are deployed with their rollback copies; public
static/health and sanitized loopback health are accepted. The authenticated portfolio
probe remains authorization-blocked, so preserve the committed serving data, rollback
copies, and live browser rejection proof until the separate owner-browser proof passes.
The r3 timestamped service correlation is closed as unavailable evidence. The source
repair and bounded frontend deployment are accepted with rollback and sanitized
static/health proof. Retain all diagnostic handoffs, both repair/deployment handoffs,
the blocked browser r3 handoff, and the owner red baseline before attempting another
browser proof. Reissue the owner-browser acceptance only after the existing authorized
tab is available; no database, authority, or service mutation is allowed under it.

## Resumable assignment

Status: **hydration accepted; VM deployment/public edge passed for the earlier hydration bundle; DRYRUN-2 candidate is COMMITTED; live migration committed and passed protected validation; browser repair published and deployed as `a270f40`; hosted owner proof is pending under a separate browser lease; `GOOGLE-SESSION-AUTH-SERIALIZATION-DEPLOY-1` stopped before mutation and `GOOGLE-SESSION-AUTH-SERIALIZATION-DEPLOY-2` is accepted; owner diagnostics r1/r2/r3 are closed; backend 500 repair is published and deployed as `71eacca`; owner-browser r2/r3 stopped before acceptance; session-401 repair is published as `600289e` and deployed with rollback; owner-browser r4 is the active acceptance lease**.
The Platform and Release specialist closed the session-401 deployment after Senior review; the owner-browser and diagnostic leases stopped before acceptance, the backend repair and bounded VM deployments are accepted, the session-401 source/deployment are accepted, and owner-browser r4 is now the sole active delivery path.
The Product Experience browser, Quality, Tunnel, DRYRUN-1, and DRYRUN-2 leases are
closed; the earlier deployment lease, backend repair lease, backend deployment lease,
owner-browser r2/r3, diagnostic r3, session-401 source repair, and session-401
deployment leases are closed, and owner-browser r4 is active.

The completed deployment retry lease was:

| Field | Exact scope |
|---|---|
| Outcome | Deploy exactly the published `a270f4072d86b2c72b3e9560f4e40402ec6bb6d8` frontend build, preserve a rollback copy, restart `fadir.service` once, and prove loopback plus public static/health reachability |
| Repository writes | Empty; use the published commit and exact local build only |
| Evidence reads | `C:/Users/doguk/AppData/Local/Temp/fadir-private-migration-20260910/session-auth-serialization-r1/handoff.md`, `frontend/src/api.js`, the local Vite manifest/hashes, retained deployment/tunnel r1/r2 handoffs, and `plan/manager-open-beta.md` |
| Operational writes/resources | Approved VM `fadir-control-lab-01`; fresh absent `C:/Users/doguk/AppData/Local/Temp/fadir-private-migration-20260910/session-auth-serialization-deploy-r2/`; approved writable `/home/fadir-agent/fadir-tests/fadir-private-migration-20260910/`; strict key `C:/ProgramData/fadir-agent-control/lab_ed25519`, known hosts `C:/ProgramData/fadir-agent-control/lab_known_hosts`, and `IdentityAgent=none`; preserve the prior `/opt/fadir/frontend/dist` under a fresh lease-owned `dist.previous`; one `fadir.service` restart; no database/WAL/source/candidate/configuration/Tunnel/DNS/Cloudflare/provider write and no tunnel restart |
| Handoff | `C:/Users/doguk/AppData/Local/Temp/fadir-private-migration-20260910/session-auth-serialization-deploy-r2/handoff.md` |
| Proof | Build/archive from the published commit; verify transfer bytes and manifest before replacement; verify rollback copy; replace only the frontend bundle; restart once; after readiness poll prove service state/listener, loopback `/api/health`, public `/api/health`, `/`, and every hashed asset referenced by the shell. Keep the old public 401 proof and do not claim authenticated owner acceptance. |
| Stop | Source/build/archive mismatch, missing rollback path, failed service/readiness/health/static probe, unknown replacement state, any database or service-config change, tunnel/DNS/public API write, extra restart, or any request to remove the rollback copy or alter private data |

The stopped owner-browser lease was `GOOGLE-SESSION-AUTH-SERIALIZATION-OWNER-BROWSER-1`:

| Field | Exact scope |
|---|---|
| Outcome | Refresh the existing authorized owner browser against the deployed `a270f40` bundle; prove Google User session hydration, `Ana Portföy · TRY` selection, successful private portfolio/related requests, no request-rejected surface, and no cross-Workspace disclosure |
| Repository writes | Empty; use the current Codex in-app browser tab only |
| Evidence writes | Fresh absent `C:/Users/doguk/AppData/Local/Temp/fadir-private-migration-20260910/session-auth-serialization-owner-browser-r1/`; sanitized observations and request status/method/path tuples only; no cookies, identity values, email, session identifiers, holdings, transactions, or response bodies |
| Browser proof | Current `https://ratatosk.dev/` owner tab; refresh after deployment, capture desktop state, then verify the required mobile-width state without changing account or provider data |
| Stop | Missing owner state, any identity/Workspace ambiguity, private request 401/403/error, cross-Workspace or empty unexpected result, browser/provider prompt requiring owner action, leaked private value, or any source/VM/database/configuration mutation |

The owner-browser and diagnostic r1/r2 leases stopped before acceptance. The completed
backend repair lease was `GOOGLE-SESSION-AUTH-SERIALIZATION-PORTFOLIO-500-REPAIR-1`:

| Field | Exact scope |
|---|---|
| Outcome | Trace the established `/api/portfolio` 500 from route through service/schema using synthetic fixtures; implement the smallest backend repair and prove the migrated-data contract without exposing private values |
| Repository writes | Backend source and focused regression tests only; no frontend, migration, identity, authority, service, or infrastructure changes |
| Evidence writes | Fresh absent `C:/Users/doguk/AppData/Local/Temp/fadir-private-migration-20260910/session-auth-serialization-portfolio-500-repair-r1/`; exact non-repository handoff with facts, limits, uncertainty, open work, test commands/results, and changed-path hashes |
| Read paths | `app/api/routes.py`, `app/api/request_transaction.py`, `app/services/portfolio.py`, `app/calc/`, response schemas, focused API/service tests, and the two retained diagnostic handoffs |
| Proof | Preserve the hosted 500/401 red baseline; reproduce the failure or proving seam with synthetic data, run the focused regression and affected offline tests, and run the full offline suite once at final product-lease acceptance. Do not inspect, log, or copy private rows. |
| Stop | No reproducible or code-proven trigger after bounded trace, response-contract ambiguity requiring owner choice, any private-data access, any authority/session/migration/service/configuration change, or any failed proof without retaining its output |

The completed backend deployment lease was `GOOGLE-SESSION-AUTH-SERIALIZATION-PORTFOLIO-500-DEPLOY-1`:

| Field | Exact scope |
|---|---|
| Outcome | Deploy the published backend commit `71eacca` containing the accepted portfolio 500 repair; prove service health and the repaired route, then preserve a rollback path |
| Repository writes | Empty; use the published commit and its exact backend source only |
| Evidence writes | Fresh absent `C:/Users/doguk/AppData/Local/Temp/fadir-private-migration-20260910/session-auth-serialization-portfolio-500-deploy-r1/`; sanitized service/route statuses, hashes, restart count, and exact handoff only |
| Operational resources | Approved `fadir-control-lab-01`; strict SSH with `C:/ProgramData/fadir-agent-control/lab_ed25519`, `C:/ProgramData/fadir-agent-control/lab_known_hosts`, and `IdentityAgent=none`; approved remote proof root; preserve the current backend under a fresh rollback path; no database, WAL, migration, identity, Tunnel, DNS, Cloudflare, provider, or frontend write |
| Proof | Verify source/archive bytes and manifest before replacement; prove rollback copy; replace only the backend application files required by `71eacca`; restart `fadir.service` exactly once; verify active/enabled/listener, loopback health, and sanitized `/api/portfolio` status with the existing owner red baseline retained. Do not claim authenticated browser acceptance. |
| Stop | Source/archive mismatch, missing rollback path, failed readiness/health/route probe, unknown replacement state, extra restart, any database or service-config change, private response/body/row exposure, or any Tunnel/DNS/Cloudflare/provider action |

The stopped owner-browser lease was `GOOGLE-SESSION-AUTH-SERIALIZATION-OWNER-BROWSER-2`:

| Field | Exact scope |
|---|---|
| Outcome | Refresh the current authorized owner browser against the deployed `a270f40` frontend and `71eacca` backend; prove Google User hydration, `Ana Portföy · TRY` selection, successful authenticated portfolio/related requests, no request-rejected surface, no cross-Workspace disclosure, and required desktop/375px states |
| Repository writes | Empty; use the current Codex in-app browser tab only |
| Evidence writes | Fresh absent `C:/Users/doguk/AppData/Local/Temp/fadir-private-migration-20260910/session-auth-serialization-owner-browser-r2/`; sanitized UI observations and method/path/status tuples only; no cookies, identity values, email, session identifiers, holdings, transactions, response bodies, or private values |
| Browser proof | Current `https://ratatosk.dev/` owner tab; one trusted refresh after deployment, then desktop and 375px browser observations without changing account or provider data |
| Stop | Missing owner state, identity/Workspace ambiguity, private request 401/403/error, cross-Workspace or empty unexpected result, provider prompt requiring owner action, leaked private value, or any source/VM/database/configuration mutation |

The completed diagnostic lease was `GOOGLE-SESSION-AUTH-SERIALIZATION-OWNER-DIAGNOSTIC-3`:

| Field | Exact scope |
|---|---|
| Outcome | Correlate only the trusted owner-browser r2 refresh window with sanitized VM service/access records, retaining UTC timestamp, method/path/status/count tuples for the allowlisted session and portfolio endpoints; identify whether the remaining rejection is the User-session 401 path or another route failure |
| Repository writes | Empty |
| Operational resources | Approved `fadir-control-lab-01`; strict SSH using the recorded key/known-hosts pair with `IdentityAgent=none`; fresh absent `C:/Users/doguk/AppData/Local/Temp/fadir-private-migration-20260910/session-auth-serialization-owner-diagnostic-r3/` and matching remote proof root; no restart or mutation |
| Trusted window | `2026-09-10T19:48:13.161Z`–`2026-09-10T19:48:13.696Z`, current owner tab only; do not refresh the browser again |
| Allowlist | `GET /api/user/sessions`, `POST /api/auth/recover-user-cookie`, `GET /api/portfolios`, `GET /api/portfolio`, `GET /api/portfolio/history`, `GET /api/transactions`, `GET /api/instruments`; strip query strings and retain only method/path/status/timestamp/count evidence |
| Handoff | `C:/Users/doguk/AppData/Local/Temp/fadir-private-migration-20260910/session-auth-serialization-owner-diagnostic-r3/handoff.md` |
| Stop | Missing trusted window, raw/private log content, cookies, response bodies, identity values, DB/private-row queries, service/config/Tunnel/DNS changes, restart, or ambiguous/unavailable correlation |

The completed source lease was `GOOGLE-SESSION-AUTH-SERIALIZATION-SESSION-401-REPAIR-1`:

| Field | Exact scope |
|---|---|
| Role and outcome | Product Experience; reproduce the owner-visible session/request rejection with a local synthetic fetch boundary, trace the exact concurrent request sequence, and implement the smallest frontend repair that prevents same-browser User-session renewal contention while preserving the existing recovery contract |
| Current checkpoint | Published `600289e` serializes session-dependent calls and Guest bootstrap in one tab, but the hosted owner refresh has not yet been re-proven. Diagnostic r3 returned no allowlisted VM records, so no route/status attribution is accepted. Preserve owner-browser r2 and all diagnostic handoffs as red evidence. |
| Read paths | `frontend/src/api.js`, `frontend/src/App.jsx`, `frontend/src/components/GoogleIdentityPanel.jsx`, `frontend/package.json`, the published session-serialization handoff, owner-browser r2 handoff, diagnostic r3 handoff, and the relevant API/session route contracts only |
| Repository writes | `frontend/src/api.js` and focused frontend regression harness/tests only; no backend, migration, identity, authority, service, or infrastructure files |
| Operational writes/resources | Empty; fresh absent `C:/Users/doguk/AppData/Local/Temp/fadir-private-migration-20260910/session-auth-serialization-session-401-repair-r1/` handoff only |
| Proof | Preserve the current red baseline; use synthetic responses and no private values to prove the initial User-session check, dashboard requests, 401 recovery/retry behavior, and concurrent same-browser calls do not produce an avoidable rejection. Run the focused harness, `npm run build`, and any affected offline checks. Keep desktop/375px browser acceptance and VM deployment for separate leases. |
| Excluded/stop | No browser refresh, hosted/public request, VM/SSH/service restart, database/WAL/private-row query, authority/lock change, cookie/identity/provider action, or raw/private log capture; stop if the source contract cannot prove a minimal repair or if a product/authority choice is required |
| Handoff | `C:/Users/doguk/AppData/Local/Temp/fadir-private-migration-20260910/session-auth-serialization-session-401-repair-r1/handoff.md` |
| Model | `gpt-5.6-luna`; reasoning effort: `medium` |

The completed deployment lease was `GOOGLE-SESSION-AUTH-SERIALIZATION-SESSION-401-DEPLOY-1`:

| Field | Exact scope |
|---|---|
| Role and outcome | Platform and Release; build exactly the accepted `600289e` frontend, preserve the currently served bundle under a fresh rollback path, replace only `/opt/fadir/frontend/dist`, restart `fadir.service` exactly once, and prove service/static/health reachability |
| Current checkpoint | Source repair `600289e` is reviewed, published, and locally proven. It serializes `/api/guest/bootstrap` with User-session and dashboard requests; only `/api/health` bypasses the FIFO. Retain owner-browser r2 and diagnostic r3 as red/blocked evidence. No authenticated owner acceptance is inferred. |
| Read paths | `frontend/src/api.js`, `frontend/package.json`, the accepted source handoff, the deployed frontend r2 handoff, `plan/manager-open-beta.md`, and the published commit manifest only |
| Repository writes | Empty; use published `600289e` and its exact local Vite build/archive only |
| Operational writes/resources | Approved VM `fadir-control-lab-01`; fresh absent `C:/Users/doguk/AppData/Local/Temp/fadir-private-migration-20260910/session-auth-serialization-session-401-deploy-r1/`; approved writable `/home/fadir-agent/fadir-tests/fadir-private-migration-20260910/`; strict key `C:/ProgramData/fadir-agent-control/lab_ed25519`, known hosts `C:/ProgramData/fadir-agent-control/lab_known_hosts`, and `IdentityAgent=none`; preserve the current frontend bundle under a fresh lease-owned remote rollback path; one `fadir.service` restart |
| Proof | Build/archive from `600289e`; verify transfer bytes, manifest, and source hash before replacement; verify the rollback copy; replace only the frontend bundle; restart exactly once; prove active/enabled/listener, `NRestarts=0`, loopback `/api/health`, public `/api/health`, `/`, and every hashed asset referenced by the shell. Do not claim authenticated route or browser acceptance. |
| Excluded/stop | No database/WAL/migration/private-row/identity/authority/session-state change, no service configuration/Tunnel/DNS/Cloudflare/provider write, no extra restart, no browser refresh, no rollback deletion, no source change, and stop on any source/archive mismatch, missing rollback, failed readiness/static/health proof, or unknown replacement state |
| Handoff | `C:/Users/doguk/AppData/Local/Temp/fadir-private-migration-20260910/session-auth-serialization-session-401-deploy-r1/handoff.md` |
| Model | `gpt-5.6-luna`; reasoning effort: `medium` |

The completed blocked lease was `GOOGLE-SESSION-AUTH-SERIALIZATION-OWNER-BROWSER-3`:

| Field | Exact scope |
|---|---|
| Role and outcome | Product Experience; use the existing authorized `https://ratatosk.dev/` owner tab after the accepted `600289e` deployment, perform exactly one trusted refresh, and prove Google User hydration, `Ana Portföy · TRY` selection, successful private portfolio/related requests, no request-rejected surface, and required desktop/375px visible states |
| Current checkpoint | Owner-browser r2 remains the red baseline: one refresh after the prior deployment visibly settled on `Ana Portföy · TRY` with `Bağlantı hatası: request rejected`. Diagnostic r3 is blocked/unavailable. The source repair `600289e` and deployment are accepted with rollback and sanitized static/health proof; no authenticated acceptance is inferred. |
| Repository writes | Empty; do not edit source or board |
| Evidence writes | Fresh absent `C:/Users/doguk/AppData/Local/Temp/fadir-private-migration-20260910/session-auth-serialization-owner-browser-r3/`; sanitized UI observations and method/path/status/count tuples only; no cookies, identity values, email, session identifiers, holdings, transactions, response bodies, or private values |
| Browser proof | Current Codex in-app browser tab at `https://ratatosk.dev/`; exactly one refresh after deployment; capture settled desktop state and then the required 375px viewport without changing account or provider data. Use synthetic/visible evidence only and keep browser proof separate from source/VM proof. |
| Excluded/stop | Missing owner state, identity/Workspace ambiguity, any private request 401/403/error, cross-Workspace or empty unexpected result, provider prompt requiring owner action, leaked private value, extra refresh, raw/private response/log/cookie capture, or any source/VM/database/configuration mutation |
| Handoff | `C:/Users/doguk/AppData/Local/Temp/fadir-private-migration-20260910/session-auth-serialization-owner-browser-r3/handoff.md` |
| Model | `gpt-5.6-luna`; reasoning effort: `medium` |

The next exact lease is `GOOGLE-SESSION-AUTH-SERIALIZATION-OWNER-BROWSER-4`:

| Field | Exact scope |
|---|---|
| Role and outcome | Senior/Product Experience; use the existing authorized `https://ratatosk.dev/` owner tab once it is visible in this task's browser context, perform exactly one trusted refresh, and prove Google User hydration, `Ana Portföy · TRY` selection, successful private portfolio/related requests, no request-rejected surface, and required desktop/375px visible states |
| Current checkpoint | Owner-browser r3 was blocked before any action because the delegated browser context had no open tabs. No refresh/navigation/UI/request proof exists for r3. Owner-browser r2 remains the red baseline. The source repair `600289e` and deployment are accepted with rollback and sanitized static/health proof; no authenticated acceptance is inferred. |
| Repository writes | Empty; do not edit source or board |
| Evidence writes | Fresh absent `C:/Users/doguk/AppData/Local/Temp/fadir-private-migration-20260910/session-auth-serialization-owner-browser-r4/`; sanitized UI observations and method/path/status/count tuples only; no cookies, identity values, email, session identifiers, holdings, transactions, response bodies, or private values |
| Browser proof | Current Codex in-app browser tab at `https://ratatosk.dev/`; verify the authorized tab exists before acting; exactly one refresh after deployment; capture settled desktop state and then the required 375px viewport without changing account or provider data. Keep browser evidence distinct from synthetic/source/VM evidence. |
| Excluded/stop | Missing authorized owner tab, identity/Workspace ambiguity, any private request 401/403/error, cross-Workspace or empty unexpected result, provider prompt requiring owner action, leaked private value, extra refresh/navigation, raw/private response/log/cookie capture, or any source/VM/database/configuration mutation |
| Handoff | `C:/Users/doguk/AppData/Local/Temp/fadir-private-migration-20260910/session-auth-serialization-owner-browser-r4/handoff.md` |
| Model | `gpt-5.6-luna`; reasoning effort: `medium` |

Do not perform any follow-up mutation under the completed diagnostic, source, or
deployment leases; owner-browser r4 is the only active assignment.
Keep the live browser rejection proof and migration evidence intact; no identity, issuer,
subject, email, holdings, transaction values, cookies, or secrets may enter ordinary
artifacts. Any backend authority change, service configuration change, or public proof
outside the exact diagnostic scope above requires a separate
lease.

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
