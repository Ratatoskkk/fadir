# faðir agent index

Specialists must not read repository files by default.
The Senior must name each file or path that a specialist may read.
The Senior must provide only the relevant board excerpt and named source paths.
The Senior must not send the historical board or unrelated documents by default.
This rule applies before specialist analysis, implementation, testing, and handoff.

Before product work, the Senior reads [CONTEXT.md](CONTEXT.md) or names it in a specialist lease.
Before beta work, the Senior reads [the beta brief](docs/OPEN_BETA_BRIEF.md) and relevant ADRs or names them in a lease.

Use [the manager board](plan/manager-open-beta.md) as the only live work board.
The Senior reads its current authority, work rules, protected state, and exact lease before each assignment.
Historical records preserve evidence. They do not activate a lease.

Use [the specialist index](plan/README.md) for the six stable role briefs.
Use Luna with High effort for specialist tasks: `gpt-5.6-luna`, `high`.

Review `git status --short` before each lease. Preserve current changes as owner work.
Require a focused failed proof before a repair. Preserve that proof through the repair.
Require visible browser proof for each visible interface change.
Separate Facts, Limits, Uncertainty, and Open work in each review and handoff.
Keep local, synthetic VM, hosted, private, and public proof separate.
Keep proof summaries in the live board. Store full XML, archives, and logs outside prompt context.
Use the four handoff sections only. Keep each section concise and evidence-based.

Research current official sources before design or tests for a new integration.
Record each source URL, retrieval date, version scope, and tool limit.
Repeat research after a material version, environment, requirement, or documentation change.
Routine tests for an accepted integration can use its accepted research.

Protect private databases, WAL files, uploads, secrets, local configuration, Portfolio rows, and the owner's email address.
The owner approved continued delivery, VM use, and reviewed commits and pushes.
Use the board's current delivery authority and exact leases for each action.
The Senior coordinates and reviews. Specialists implement product and operational changes.
Ask for missing owner values and protect private data throughout delivery.

Use the relevant code or write skill for substantive work.

## Test policy

- Before each repair, retain one focused failed proof that demonstrates the defect.
- After repair, run the focused proof, then only the targeted regressions for the affected risk.
- Run the full offline suite once at final lease acceptance, or earlier only when the change is cross-cutting.
- Run PostgreSQL, VM, browser, hosted, and public checks only when the active lease requires that proof class.
- When a new defect appears, add one focused regression and rerun the affected set; do not restart the entire cycle.
- After two failed design reviews without executable progress, stop expanding tests and require an architecture or owner decision.

## Elonmusk rule

1. Do not optimize something that should not exist.
2. Cut as much as you can before you break the project.
3. Only fix and clean up what is left after you cut as much as you can.

## Specialist dispatch

- The Senior prompts specialists one at a time. Queue later assignments and do not run specialist chats concurrently.
- Before dispatch, size the lease and prompt for the available token budget. Prefer a smaller resumable lease with a checkpoint over a task likely to be cut off mid-repair.
- Preserve the failed proof and current handoff when a token limit or other interruption occurs; resume from that evidence instead of restarting or overlapping the assignment.
