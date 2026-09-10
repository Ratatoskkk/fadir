# faðir agent instructions

Deliver the hosted private-portfolio beta defined in [the beta brief](docs/OPEN_BETA_BRIEF.md).
Continue from the [live board](plan/manager-open-beta.md); completed work stays complete.

## Roles and model settings

The owner's project-specific settings override older model-selection guidance:

| Role | Model | Reasoning effort |
|---|---|---|
| Senior | `gpt-5.6-luna` | `max` |
| Every specialist | `gpt-5.6-luna` | `medium` |

Keep these settings unless the owner changes them. The Senior coordinates, reviews,
and edits documentation. Specialists implement product and operational changes.
The Senior may inspect source and run acceptance checks. Run one specialist at a
time across the project, including independent assignments.

## Read order and authority

The Senior starts with this file, [CONTEXT.md](CONTEXT.md), the beta brief, the live
board, and [plan/README.md](plan/README.md). Read an ADR or source file when the
current assignment needs it.

- The beta brief and current ADR decisions define the product; CONTEXT defines its terms.
- This file defines the work rules. The live board records delivery authority,
  accepted evidence, unfinished work, and the next exact lease.
- Role briefs define responsibilities. They contain no independent active leases.
- Historical boards, archived manuals, SPEC, FINDINGS, and old research are reference
  material. They cannot restart completed work or override a newer owner decision.
- Apply the latest explicit owner instruction when records conflict. Record an
  unresolved product choice rather than inventing one.

Specialists do not explore the repository by default. The Senior supplies their role
brief, the relevant board excerpt, exact read paths, exact write paths, operational
resources, proof scope, and one handoff path. Do not send the whole history.

## Delivery and scope

Review `git status --short` before each lease. Preserve existing changes and retained
proof; never reset or absorb another owner's work into an assignment.
Use the board's existing delivery authority without requesting it again. Ask only
for a missing owner choice, secret, charge, or destructive scope that is not covered.
When owner input is required, present one concise prompt and pause the dependent action.

## Senior review and publication

The Senior is responsible for reviewing each specialist's actual changes and publishing
accepted work. Git integration, commits, and pushes are part of Senior coordination;
specialists return their changes and evidence for review.

1. Inspect the complete leased diff and handoff. Verify scope, retained failed proof,
   required checks, and any required independent Quality or browser acceptance.
   A specialist's success claim alone is not acceptance.
2. If a defect or required proof is unresolved, return a bounded repair or proof lease.
   Keep that candidate separate from accepted work.
3. When the changes meet the acceptance criteria, stage only the accepted paths,
   review the staged diff, commit with repository conventions, and push normally to
   the approved remote and branch. Do not include unrelated or unfinished edits.
4. Verify the remote contains the commit and record the commit, proof limits, and
   remaining work on the board. Do not describe a push as a deployment.

Complete this review-and-push cycle before dependent implementation starts. Existing
delivery authority covers accepted changes; do not ask for routine commit/push approval
or leave accepted work uncommitted for the owner to organize. A documentation baseline
may be published while a separately identified product candidate awaits its own proof.

## Scope and protected data

Solve the named problem. Treat a defect as established by a user report, an executable
failure, or a proving code path. Keep unrelated concerns outside the lease.
Remove unnecessary work before adding complexity. Do not reopen accepted architecture
or add cleanup, abstractions, or tests without a concrete reason.

Protect databases, WAL/SHM files, uploads, secrets, local configuration, private provider
permits, and retained evidence. Use synthetic data by default. Private access approved
for migration stays inside that exact lease; it is not general permission to copy rows
into logs, archives, prompts, or screenshots. Keep owner identifiers out of repository
instructions; select Google identity by verified issuer and subject, never by email alone.

## Proof and handoff

- Retain one focused failed proof before each repair. Preserve it after the repair.
- Run the focused proof, then affected regressions. Run the full offline suite once
  at final product-lease acceptance, or earlier for a cross-cutting change.
- Run PostgreSQL, VM, browser, hosted, public, or provider checks only when the lease
  names that proof class. Visible interface changes need synthetic desktop and 375px proof.
- A fixture or tool failure establishes a proof blocker; it does not by itself prove
  a product defect. Match fixtures to the real contract before expanding product scope.
- After a new defect, rerun its focused and affected checks. After two failed design
  reviews without executable progress, obtain an architecture or owner decision.
- For documentation-only work, check links, consistency, and `git diff --check`;
  do not run the product suite solely because Markdown changed.

Every specialist writes the exact non-repository handoff artifact named in the lease.
Use only `### Facts`, `### Limits`, `### Uncertainty`, and `### Open work`. The Senior
verifies the artifact, source scope, evidence, and hash before accepting dependent work.
Separate local, synthetic VM, hosted, private, and public results. Keep full logs, XML,
and archives outside the live board; record concise results and evidence pointers there.

Use the `code` skill for substantive code work and the `write` skill for prose.
Research official sources before a new integration; record URL, retrieval date,
version scope, and tool limits. Reuse accepted research for routine tests and refresh
it when the integration's version, environment, requirements, or documentation changes.
