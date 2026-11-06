# faðir agent instructions

faðir is the hosted private-portfolio beta defined in [the beta brief](docs/OPEN_BETA_BRIEF.md).

- The beta brief and the current [ADR](docs/adr/) decisions define the product. [CONTEXT.md](CONTEXT.md) defines its terms.
- Historical boards, archived manuals, SPEC, FINDINGS and old research are reference material only.
- When records conflict, the latest explicit owner instruction wins. If a product choice is unresolved, record it rather than inventing one.
- Select a Google identity by verified issuer and subject, never by email alone.
- Keep databases, WAL/SHM files, uploads, secrets and local configuration out of the repository, logs and prompts. Use synthetic data in tests.
