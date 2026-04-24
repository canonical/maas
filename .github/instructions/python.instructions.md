---
applyTo: "**/*.py"
---

## Subdirectory Context

See the subdirectory reference table in `copilot-instructions.md` for detailed constraints on: `maasserver`, `maasapiserver`, `maasservicelayer`, `maastemporalworker`, `provisioningserver`, `metadataserver`, `maascli`, `apiclient`, `maascommon`, `maastesting`. Different subdirectories have different async, database, and testing patterns.

## Style

- Max line length: 79 chars (see `pyproject.toml`)
- 4-space indentation, double quotes, Ruff formatter + linter
- Target Python 3.14+

## Imports

isort order:
1. Standard library
2. Third-party
3. MAAS first-party in this order: `apiclient`, `maasapiserver`, `maascli`, `maascommon`, `maasserver`, `maasservicelayer`, `maastesting`, `metadataserver`, `provisioningserver`

## Type hints

- Required on all function signatures
- New code in `maascommon`, `maasservicelayer`, `maasapiserver`, `maastemporalworker` must be Pyright-compliant
- Use Pydantic models for data validation

## Async

- Use `async`/`await` in async contexts
- v3 API: prefer async patterns
- Legacy Django: use `deferToDatabase` for DB calls in async contexts

## Database

- New code: SQLAlchemy Core (not ORM) in the service layer
- Legacy code: Django ORM where already established
- Always use parameterized queries; use transactions appropriately

## Linting

Run the narrowest target that covers your changes:

| Target | When to use |
|--------|-------------|
| `make lint-py` | General Python style and formatting (Ruff); use after any `.py` change |
| `make lint-py-imports` | After adding, removing, or reordering imports |
| `make lint-py-builders` | After modifying builder classes in `maasservicelayer` |
| `make lint-py-linefeeds` | If you touched line endings or file encoding |
| `make lint-oapi` | After changing any OpenAPI spec or `maasapiserver` handler that affects the spec |
| `make lint` | Full suite — run before submitting a PR or when unsure |

Prefer `make lint-py` for routine Python edits; add `make lint-py-imports` whenever import blocks change.

## Formatting

- Use `make format-py` to auto-format Python files after any edit
- Use `make format` only when multiple languages are affected

## Testing

- Use `make test-py` to run the Python test suite; use `make test` only when multiple languages are affected
- Use `pytest` for new code; follow existing patterns in the subdirectory
- Use appropriate fixtures (`db_connection`, `services_mock`, etc.)
- Mock external dependencies
- No trivial assertions; test meaningful behavior only

## Service layer patterns

- Use builders (Pydantic models) for create/update operations
- `ClauseFactory` for reusable query filters
- `QuerySpec` for repository filtering
- Three-tier architecture: repository → service → API
