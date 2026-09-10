# faðir open beta manager board

Updated: 2026-09-10. This is the only live work board.

## Goal and next action

Finish the hosted private-portfolio beta in [the product brief](../docs/OPEN_BETA_BRIEF.md).
The immediate user outcome is a browser that stays signed in after refresh and shows
the owner's original portfolio under the verified Google User.

**Resume the unfinished browser proof for `GOOGLE-SESSION-HYDRATION-1` first.**
Its two frontend files are already implemented and uncommitted. The subsequent private
migration is approved in principle but has not passed its dry run. Do not restart APP,
identity architecture, credential rotation, or the completed Transfer repair.

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
work. This publication excludes the unfinished frontend candidate and changes no deployment.

## Current checkpoint

### Facts

- Documentation baseline published as `e785b7e779a07f9666040add586b5ecbe64bc3f7`
  on 2026-09-10 and verified on `origin/main`. Its 21 Markdown files passed 129 local
  link/anchor checks, staged scope review, and `git diff --check`; all 158 tracked
  non-Markdown files remained unchanged. The frontend candidate was excluded.
- Product source baseline: `0bb35e9a6778c66e83499b474929bc4416b47fe5`
  (`fix: complete Google portfolio transfer`). Local `main` matched freshly fetched
  `origin/main` before the documentation publication. Documentation-only commits may
  follow this product baseline; verify current local/remote commit IDs before dispatch.
- The existing uncommitted product work is exactly `frontend/src/api.js` and
  `frontend/src/components/GoogleIdentityPanel.jsx`. Both still match the hydration
  handoff hashes below. The pre-cleanup board is archived; old role assignments are
  superseded by this checkpoint.
- The hydration implementation checks `GET /api/user/sessions` on mount: 200 shows
  signed-in state, 401 returns to Google sign-in after guarded recovery, and other
  failures show a neutral retry state. Its retained handoff reports source checks
  and a successful frontend build.
- The r2 component harness exists. Its handoff claims no browser pass. The prior Senior
  task ended at a usage limit after harness startup failures and opening a browser tab.
- The earlier Transfer repair was published as `0bb35e9`. Retained Quality, focused
  PostgreSQL, and final offline evidence report PASS; the final offline suite had
  512 passes. The deployment handoff records the route delta, one restart, and
  loopback/public health 200. Those results predate the hydration candidate.
- A later owner-visible Transfer succeeded. The retained read-only state handoff records
  one identity/User/Workspace chain, active User Sessions, consumed login, revoked
  Guest access, and zero Portfolios. Credential rotation has a successful retained
  handoff and is not unfinished work.

### Limits

This documentation work checks links, consistency, Git scope, and candidate hashes;
its approved publication contains Markdown only. It runs no product test, browser,
provider, VM, private database, or deployment action. Earlier runtime results are
retained evidence, not fresh runtime verification. No hydration browser, independent
Quality, publication, or deployment acceptance exists. No private migration or full
beta acceptance exists.

### Uncertainty

The r1 full-App synthetic fixture crashed before rendering the panel. The prior Senior
classified it as a harness limitation, not an established App defect. The r2 harness
has no observed desktop/375px result. Its startup commands and current port ownership
need checking before reuse. The persisted Transfer timestamps were internally correlated
but were not tied to an authoritative screenshot time window.

### Open work

Review the frozen hydration candidate, complete synthetic visible proof, then obtain
Quality acceptance. The Senior commits and pushes the accepted delta, then assigns
deployment under an exact operational lease using existing delivery authority.
Verify owner refresh behavior before resuming the protected private dry run and
conditional migration.

## Resumable assignment

Status: **checkpoint retained; no specialist was dispatched by this documentation task**.
The old implementation lease is frozen pending proof. All other roles have no active lease.

The next Senior may activate `GOOGLE-SESSION-HYDRATION-BROWSER-3` for Product Experience
after verifying the checkpoint and worktree:

| Field | Exact scope |
|---|---|
| Outcome | Visible refresh/session states at desktop and 375px without a false Google prompt or private session data |
| Repository writes | Empty; keep the two implementation files frozen |
| Repository reads | `AGENTS.md`, `plan/README.md`, `plan/specialists/product-experience.md`, `frontend/src/api.js`, `frontend/src/components/GoogleIdentityPanel.jsx`, `frontend/src/styles.css`, `frontend/package.json`, `frontend/vite.config.js`, `app/api/routes.py`, `app/schemas.py`, `tests/test_user_session_routes.py` |
| Evidence reads | Under the proof root below: `session-hydration-r1/handoff.md`, `session-hydration-r1/source-red-proof.txt`, `session-hydration-r1/source-red.png`, `session-hydration-r1/browser-proof.md`, `session-hydration-r2/handoff.md`, `session-hydration-r2/manifest.md`, `session-hydration-r2/server.js`, `session-hydration-r2/harness.html`, `session-hydration-r2/harness-entry.jsx` |
| Operational writes | New absent `C:/Users/doguk/AppData/Local/Temp/fadir-private-migration-20260909/session-hydration-r3/`; local synthetic harness and owned process logs/screenshots only |
| Handoff | `C:/Users/doguk/AppData/Local/Temp/fadir-private-migration-20260909/session-hydration-r3/handoff.md` |
| Proof | Inspect the existing harness and port ownership; run it with synthetic 200, 401/recovery, and 503 responses; inspect initial checking, signed-in, signed-out, retry, no login flash, no callback loop, and no private fields at both widths |
| Completion | Four-section handoff with actual visible evidence and owned-process cleanup; a component pass stays separate from full-App and hosted acceptance |
| Stop | Source hash drift, an unexpected real API/provider request, an unavailable browser surface, or a new defect requiring repository writes |

Do not start Google sign-in or access the owner database for this proof. Do not patch
`App.jsx` because an incomplete fixture crashed. If the specialist lacks a browser
surface, it can prepare a reproducible harness for Senior acceptance; it cannot claim
the missing browser result. If new evidence requires a rebuild or source repair, the
Senior revises the lease before execution.

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
| G4 Guest and identity | Guest, Google transitions, Merge, and session controls published; owner Transfer observed | Accept hydration and finish Guest/User browser and session journeys |
| G5 Portfolios, currencies, tax | Portfolio selection, Fee Currency, Tax Profile backend/UI published | Finish full user journeys and close the missing independent Tax Profile review artifact |
| G6 Market data | Shared refresh route/worker published; direct Yahoo decision retained | Establish hosted cache, refresh, quota, source/time, and permitted public-use acceptance |
| G7 Security and data rights | Scoped routes, exports and deletion delivered; no-cookie denial matrix recorded | Finish authenticated isolation, data-rights UI, notices, abuse controls, and the recorded missing public security headers |
| G8 VM and public service | VM/Tunnel service, HTTPS health, bounded Guest denial and Google start observed | Accept the deployed user journeys and exact final release state |
| G9 Final acceptance and recovery | Earlier bounded VM rollback/reconstruction proof exists | Final browser/product/release acceptance; carry its version and data-recovery limits forward |

G9 needs the remaining G3–G8 outcomes. A public health 200, no-cookie 401, or local
suite pass cannot close an authenticated journey. Off-site backup and lost-Portfolio
recovery guarantees remain outside this beta.

After hydration acceptance, queue these outcomes one at a time:

1. Complete the protected migration into the verified Google User's `Ana Portföy`/TRY
   and prove that the original portfolio is accessible after refresh.
2. Reconcile and close the remaining G4–G7 product and security acceptance items against
   the beta brief. Check Guest product parity, including tax behavior; do not silently
   redefine full Guest use around the currently implemented User-only Tax Profile panel.
3. Complete G8/G9 on the accepted release, with browser, restart, rollback, and service
   reconstruction evidence appropriate to the actual change.

## Evidence pointers

Under the private-migration proof root above, read only the files needed by the lease:

- Hydration: `session-hydration-r1/handoff.md` and `session-hydration-r2/handoff.md`.
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
