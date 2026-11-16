# Conventions Steering

> Full authoritative rules live in `/project/AGENTS.md`. This file is a quick-reference pointer, not a duplicate.

## Code Style

- Python: 79-char lines, 4-space indent, double quotes, Ruff format/lint. See AGENTS.md § Python Guidelines.
- Go: `gofmt`/`go fmt`, table-driven tests. See AGENTS.md § Go Guidelines.
- Prefer clear naming over comments; comments explain *why*, not *what*.

## Architecture Patterns

- Three-tier v3 API: repository (SQLAlchemy Core) → service → API handler.
- Legacy Django: `deferToDatabase` for DB calls in async contexts.
- See AGENTS.md § Subdirectory-Specific Rules for per-directory patterns (`maasserver`, `maasapiserver`, `maasservicelayer`, etc.).

## Testing Rules

- New code: `pytest`. Legacy: Django/`testtools` fixtures.
- Repositories tested against real DB (`db_connection`); services tested with mocked repositories.
- No trivial/obvious assertions.

## Workflow Rules

- Commits/PRs: Conventional Commits (see AGENTS.md for types/scopes/examples).
- `fix` commits require a ticket reference (Launchpad/GitHub/Jira).
- Excluded from AI agent work: `src/maas-offline-docs`, `src/maasui`.
