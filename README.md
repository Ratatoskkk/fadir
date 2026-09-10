# faðir

faðir tracks private investment portfolios and separates a holding's price return
from the effect of exchange rates. The interface is Turkish; code and documentation
are English. The name is Old Norse for *father*; filenames use `fadir`.

The product target is a **hosted open beta** for individuals. One User controls one
Workspace with multiple Portfolios. Guests can use the product before signing in;
sign-in provides recovery and persistent identity. Each Portfolio has a Base Currency.

## Start here

| Need | Read |
|---|---|
| Product goal and settled beta choices | [Open Beta Brief](docs/OPEN_BETA_BRIEF.md) |
| Domain terms | [CONTEXT.md](CONTEXT.md) |
| Agent rules and model settings | [AGENTS.md](AGENTS.md) |
| Current progress, authority, next lease | [Manager board](plan/manager-open-beta.md) |
| Specialist roles and handoffs | [Coordination index](plan/README.md) |
| Prompt for the next Senior | [Senior continuation prompt](docs/SENIOR_AGENT_SETUP_PROMPT.md) |
| Original portfolio migration | [Private Migration Runbook](docs/PRIVATE_MIGRATION_RUNBOOK.md) |

The board records remaining acceptance work. A reachable service is not a completed
beta. Local runs remain development and recovery tools, not a separate local-only
product promise.

## Product and stack

- Python/FastAPI and SQLAlchemy on the backend; React, Vite, and Recharts on the frontend.
- One PostgreSQL database for hosted data, with Workspace and Portfolio ownership
  boundaries. SQLite remains available for local development and the legacy source.
- Google-only sign-in for beta, with explicit Claim, Portfolio Transfer, and Portfolio
  Merge. Email recovery is deferred.
- Cookie-only Guest Workspaces expire after 90 days without access. User Sessions
  expire after 30 days without activity and support revocation.
- An owner-managed Ubuntu Server LTS VM under Hyper-V, reached through Cloudflare
  Tunnel at `ratatosk.dev`.
- Direct Yahoo market data under the owner's written beta permit. The permit stays
  outside the repository; a provider replacement is deferred.

The [ADRs](docs/adr/0001-hosted-service-only.md) record the individual decisions.
The beta brief links each current decision and distinguishes the target from progress.

## Financial contracts

Transactions retain their native-currency values. FX is separately sourced and stored
with its date and provider. Base Currency changes revalue views without rewriting
transactions. Use Decimal for financial calculation and preserve API money strings.

Average Purchase Price is the quantity-weighted native cost of all purchases in a
Stock Group, including purchase fees and excluding sales. Fully sold groups keep
that lifetime purchase average; it is distinct from remaining FIFO cost.

The return decomposition preserves both price and FX effects:

```text
total_return = local_return × fx_return
PnL in TRY = price_effect_try + fx_effect_try
```

Portfolio tax results require their stated year, jurisdiction, source, inputs, and
calculation limits. The published User Tax Profile path covers realized FIFO disposals
across that User's Portfolios in TRY. It does not establish a complete tax return or an
unsold-position policy. The legacy liquidation projection is a separate calculation.
Do not treat old config defaults or historical tax notes as current tax guidance.

## Local development

Use Python 3.11+ and Node/npm for the frontend. The existing dependency lists are
[requirements-dev.txt](requirements-dev.txt), [requirements-migrate.txt](requirements-migrate.txt),
and [frontend/package.json](frontend/package.json).

Work in an isolated development/proof checkout with synthetic data. The owner's
canonical checkout contains protected local state. Setting `FADIR_DB_PATH` alone does
not isolate a run when `FADIR_DATABASE_URL` is present; the URL takes precedence.
`app/config.py` can also read local `config.yaml`. Do not copy that file into proof archives.

In a configured development checkout, the [Makefile](Makefile) provides:

| Command | Effect |
|---|---|
| `make install` | Create the virtual environment and install Python/Node dependencies |
| `make build` | Build the frontend |
| `make run` | Build and serve on `127.0.0.1:8000` |
| `make dev` | Run the API with reload and the Vite frontend |
| `make test` | Run pytest with live tests excluded |
| `make test-live` | Run tests marked live; requires a named network/provider lease for agents |

On Windows without make, use the existing environment for the specific task:

```powershell
.\.venv\Scripts\python.exe -m pytest -m "not live"
npm --prefix frontend run build
```

These commands are reference entry points. Agent proof runs use the exact isolated
root and commands in the lease. A documentation edit does not require product tests.

`start.cmd` and `fadir-tray.vbs` remain local launcher helpers. Bootstrap, demo, verify,
and reset targets can write the configured database or contact providers; they are
not synthetic acceptance commands. Use the private migration runbook to move the
owner's original portfolio, rather than importing it again through a default bootstrap.

## Configuration and migrations

| Setting | Purpose |
|---|---|
| `FADIR_DATABASE_URL` | Explicit SQLAlchemy database URL; takes precedence over the SQLite path |
| `FADIR_DB_PATH` | Local SQLite path when no database URL is configured |
| `FADIR_GOOGLE_WEB_CLIENT_ID` | Google Web client ID; `FADIR_GOOGLE_CLIENT_ID` is also accepted |
| `FADIR_TCMB_API_KEY` | TCMB provider secret when that provider is configured |

Keep secrets in protected configuration. Alembic uses `FADIR_DATABASE_URL`; hosted
migrations and deployment belong to a named operational lease. Preserve a consistent
SQLite snapshot: copying `fadir.db` alone does not capture active WAL state.

## Testing and acceptance

[pytest.ini](pytest.ini) excludes tests marked `live` by default. Test counts belong
to dated evidence, not this README. Tests cover calculation, ownership, request/session
boundaries, transitions, privacy, and migration behavior.

Follow the [proof policy](AGENTS.md#proof-and-handoff): focused failure before repair,
focused and affected checks afterward, one final offline suite for a product lease,
and only the additional proof classes the lease requires. Frontend changes require
synthetic desktop and 375px browser evidence. A browser harness must honor the API
contract; fixture failures alone do not establish product defects.

The current board keeps local, synthetic VM, hosted, private, and public acceptance
separate. Off-site backups and lost-Portfolio recovery guarantees are deferred; restart,
release rollback, and service reconstruction still require appropriate proof.

## Repository map

| Path | Purpose |
|---|---|
| `app/calc/` | Financial calculations |
| `app/api/` | Routes, request authority, and transactions |
| `app/services/` | Ownership, sessions, transitions, finance, and data workflows |
| `app/providers/` | Prices, FX, and provider boundaries |
| `migrations/` | Alembic schema history |
| `frontend/` | React interface |
| `tests/` | Offline and explicitly guarded live proof |
| `examples/` | Synthetic import examples |
| `docs/` | Product decisions and focused reference documents |
| `plan/` | Live coordination and stable roles |

## Historical reference

- [Original local SPEC](docs/SPEC.md) preserves calculation/API section references
  used in source. Its local-only scope and agent decomposition are superseded.
- [FINDINGS](docs/FINDINGS.md) preserves earlier implementation observations.
- [Market-data comparison](docs/MARKET_DATA_OPTIONS.md) is dated fallback research;
  refresh it before any provider decision.
- [Local v1 manual](docs/archive/local-v1-readme.md) preserves the old chart/design
  explanation, launcher detail, and measurements. It is not current operational guidance.
- [Coordination history](plan/README.md#historical-reference) preserves previous leases
  and proof records. Read it only to answer a named historical question.

## Licence

MIT. See [LICENSE](LICENSE). Provider permission and tax-calculation limits are separate
from the source-code licence.
