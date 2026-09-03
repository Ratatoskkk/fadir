# faðir agent index

Read [CONTEXT.md](CONTEXT.md) before product work. Read [docs/OPEN_BETA_BRIEF.md](docs/OPEN_BETA_BRIEF.md) before open beta work.

Use [plan/manager-open-beta.md](plan/manager-open-beta.md) as the only live work board. The board controls phases, assignments, leases, gates, and owner decisions.

Use the stable role briefs under [plan/specialists/](plan/specialists/). [plan/README.md](plan/README.md) lists all six roles.

Review `git status --short` before each lease. Treat all current changes as owner work.

When the plan selects a new integration, research current official primary documentation before design or testing.

Use the research to choose the best path for the current scenario. Record the source URL, retrieval date, version scope, and tool limits.

Use known tool limits to shape the first test plan. Routine tests for an accepted integration do not need new research.

Research again when the version, environment, requirements, or documented behavior changes.

Each assignment must have one exact file lease. Each specialist can have one active assignment at most.

Create a focused failed proof before a repair. Keep that proof through the repair.

Match each test to the risk. A visible interface change needs visible browser proof.

Keep local, hosted, and public proof separate. Local proof cannot prove a public pass.

Protect the private database, WAL files, uploads, secrets, local configuration, Portfolio rows, and the owner's email address.

Stop for an owner choice, a secret, a public change, or a destructive action. Get owner approval before a commit, push, deployment, or external service call.

Each review and handoff must separate Facts, Limits, Uncertainty, and Open work.
