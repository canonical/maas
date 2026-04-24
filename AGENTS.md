# AI Coding Agent Guidelines

Entry point for AI coding agents (GitHub Copilot, Cursor, Cline, etc.) working on the MAAS project. The canonical rules live in the `.github/` directory — read those files before proceeding.

## Canonical Instruction Files

Read these files before writing any code. They contain the authoritative rules for this codebase:

| File | Content |
|------|---------|
| `.github/copilot-instructions.md` | Core directives, interaction philosophy, code quality, security, subdirectory reference |
| `.github/instructions/python.instructions.md` | Python coding guidelines (style, imports, async, DB, testing, service layer patterns) |
| `.github/instructions/go.instructions.md` | Go coding guidelines (style, versions, testing, subdirectory specifics) |

## GitHub Copilot

The files above are applied automatically in Copilot Chat sessions. The following task prompts are also available:

| Prompt | Invoke with | Purpose |
|--------|-------------|---------|
| `.github/prompts/architect.prompt.md` | `/architect` | Architectural planning and design guidance |
| `.github/prompts/code-review.prompt.md` | `/code-review` | Branch code review against `master` |
| `.github/prompts/commit-message.prompt.md` | `/commit-message` | Write conventional commit messages |

## Conventional Commits

All commits and pull/merge requests must follow the [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) specification. Full specification with allowed types, scopes, and examples: `.github/prompts/commit-message.prompt.md`.

Quick reference:
- Format: `<type>[(scope)][!]: <description>`
- Ticket reference mandatory for `fix`: `Resolves LP:2066936` (Launchpad), `Resolves GH:123` (GitHub)
- Description: high-level summary only, 72 chars or less; no implementation detail lists
- Body: explain the *why*, not the *what*

## Collaboration Practices

- Follow the project's code review and pull request process
- Tag relevant team members for specialized reviews
- Reference related issues in commits and pull requests
- Link to relevant documentation when making architectural changes
- Ensure code is compatible with the project's current dependency versions

## Subdirectory-Specific Rules

### `src/maasserver`

**Purpose**: Legacy Django-based region controller server

- **Technology**: Python, Django, Twisted
- **Database**: Django ORM (legacy), transitioning to SQLAlchemy where possible
- **Key Patterns**:
    - Use `deferToDatabase` for database calls in async contexts
    - Follow Django model conventions for existing models
    - Maintain backward compatibility with existing APIs
    - Add new functionality to service layer when possible
- **Testing**: Use Django test fixtures and `testtools`. Run tests with `bin/test.region`
- **Notes**: This is legacy code; prefer adding new features to the v3 API when feasible

### `src/maasapiserver`

**Purpose**: FastAPI-based v3 REST API (Presentation Layer)

- **Technology**: Python, FastAPI, Pydantic
- **Architecture**: Part of the three-tier architecture (API layer)
- **Key Patterns**:
    - Extend `Handler` class for new endpoints
    - Use `@handler` decorator for endpoint methods
    - Define Pydantic models for requests/responses
    - Use `check_permissions` for authorization
    - Mock services in tests, not repositories
- **Testing**: Use `APICommonTests`, `mocked_api_client*` fixtures
- **Authentication**: Support Bearer tokens, Django sessionid, and Macaroons
- **Documentation**: Ensure OpenAPI spec stays accurate

### `src/maasservicelayer`

**Purpose**: Business logic layer for v3 API (Application Layer)

- **Technology**: Python, SQLAlchemy, Pydantic
- **Architecture**: Part of the three-tier architecture (Service + Repository layers)
- **Key Patterns**:
    - Repositories use SQLAlchemy Core (not ORM)
    - Services contain business logic
    - Use builders for create/update operations
    - Implement `ClauseFactory` for reusable filters
    - Use `QuerySpec` for query filtering
    - Extend `BaseRepository` or `ReadOnlyRepository`
    - Extend `BaseService` or `ReadOnlyService`
- **Testing**:
    - Test repositories with real database (`db_connection` fixture)
    - Test services with mocked repositories
    - Use `RepositoryCommonTests` and `ServiceCommonTests` base classes
- **Database**: Keep table definitions in `db/tables.py` synchronized
- **Migrations**: Use Alembic for schema migrations
- **Notes**: Read `src/maasservicelayer/README.md` for detailed architecture

### `src/maastemporalworker`

**Purpose**: Temporal workflow workers

- **Technology**: Python, Temporal
- **Key Patterns**:
    - Follow Temporal workflow and activity patterns
    - Ensure type hints for Pyright compliance
    - Use appropriate retry and timeout policies
- **Testing**: Mock Temporal client in tests

### `src/provisioningserver`

**Purpose**: Rack controller provisioning services

- **Technology**: Python, Twisted
- **Key Patterns**:
    - Async operations using Twisted deferreds
    - Power driver implementations
    - TFTP and HTTP boot services
- **Notes**: Legacy async patterns; be careful with reactor usage

### `src/metadataserver`

**Purpose**: Cloud-init metadata service

- **Technology**: Python, Django
- **Key Patterns**:
    - Serve metadata to deploying machines
    - Handle commissioning and deployment scripts
- **Testing**: Follow Django testing patterns

### `src/maascli`

**Purpose**: Command-line interface

- **Technology**: Python
- **Key Patterns**:
    - CLI command implementations
    - User-facing error messages should be clear
    - Validate inputs early

### `src/apiclient`

**Purpose**: API client library

- **Technology**: Python
- **Key Patterns**:
    - HTTP client for MAAS API
    - Handle authentication and errors gracefully

### `src/maascommon`

**Purpose**: Common utilities shared across components

- **Technology**: Python
- **Key Patterns**:
    - Keep dependencies minimal
    - Well-tested utility functions
    - Ensure Pyright compliance
- **Notes**: Changes here affect multiple components

### `src/maastesting`

**Purpose**: Testing utilities and fixtures

- **Technology**: Python, pytest
- **Key Patterns**:
    - Reusable test fixtures
    - Database setup helpers
    - Pytest plugins
- **Notes**: Add reusable test utilities here

### `src/maasagent`

**Purpose**: Go-based MAAS agent using microcluster

- **Technology**: Go 1.24.4, microcluster, Temporal
- **Key Patterns**:
    - Microcluster-based architecture
    - DHCP and DNS services
    - Temporal workflow integration
    - Prometheus metrics
    - OpenTelemetry tracing
- **Testing**: Use Go testing with testify
- **Dependencies**: Check `go.mod` before adding dependencies

### `src/host-info`

**Purpose**: Collect host hardware information

- **Technology**: Go 1.18, LXD libraries
- **Key Patterns**:
    - Hardware detection and reporting
    - Minimal dependencies
- **Testing**: Standard Go tests
- **Notes**: Standalone utility; do not introduce new dependencies without good reason

### `src/perftests`

**Purpose**: Performance benchmarks

- **Technology**: Python
- **Notes**: Add performance tests for critical paths

### `src/tests`

**Purpose**: Integration and cross-component tests

- **Technology**: Python, pytest
- **Notes**: Tests that span multiple components

## Excluded Directories

Do not read or modify:

- `src/maas-offline-docs`: Documentation artifacts
- `src/maasui`: UI components (separate frontend codebase)

## Running Checks

### Formatting

Prefer the specialized format target that matches the files you changed.

| Target | When to use |
|--------|-------------|
| `make format` | Full format pass — when multiple categories are affected |
| `make format-py` | Any Python change |
| `make format-go` | Any Go change |

### Linting

Prefer the specialized lint target that matches the files you changed — it is faster and gives more focused output. Fall back to `make lint` when multiple categories are affected.

| Target | When to use |
|--------|-------------|
| `make lint` | Full lint pass — run before submitting a PR or when multiple categories are affected |
| `make lint-py` | Any Python change (runs Ruff linter + formatter check) |
| `make lint-py-imports` | After adding, removing, or reordering imports in Python files |
| `make lint-py-builders` | After modifying builder classes or Pydantic create/update models |
| `make lint-py-linefeeds` | If you suspect mixed or incorrect line endings in Python files |
| `make lint-go` | Any Go change |
| `make lint-go-fix` | Go change where you want auto-fix applied (runs `gofmt`/`golangci-lint --fix`) |
| `make lint-oapi` | After modifying any OpenAPI spec file (e.g. in `src/maasapiserver`) |
| `make lint-shell` | After modifying any shell script |

### Tests

Prefer the specialized test target that matches the files you changed.

| Target | When to use |
|--------|-------------|
| `make test` | Full test suite — run before submitting a PR or when multiple components are affected |
| `make test-py` | Any Python change |
| `make test-go` | Any Go change |

```bash
cd src/maasagent && make test    # Go agent tests (alternative)
cd src/host-info && go test ./...  # host-info tests
```

## Additional Resources

- Python configuration: `pyproject.toml`
- Go style guide: `go-style-guide.md`
- Go configuration: `src/maasagent/go.mod`, `src/host-info/go.mod`
- Service layer architecture: `src/maasservicelayer/README.md`
- Database migrations: `src/maasservicelayer/db/alembic/`
