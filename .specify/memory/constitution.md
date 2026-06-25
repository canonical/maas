# MAAS Project Constitution

**Version**: 1.0 | **Ratified**: 2025-04-20 | **Last Amended**: 2025-04-20

## Project Identity

**Name**: MAAS (Metal As A Service)  
**Purpose**: Infrastructure provisioning and management system for bare metal servers  
**Primary Languages**: Python (97%, FastAPI + SQLAlchemy), Go (3%, microcluster + microservices)  
**License**: GNU Affero General Public License v3  
**Repository**: https://launchpad.net/maas

**Architecture Pattern**: Monorepo with layered architecture for v3 API + legacy Django + Go microservices
- **v3 API**: 3-tier FastAPI (Presentation) → Service Layer (Business Logic) → Repository Layer (Data Access)
- **Legacy**: Django-based region controller (transitioning)
- **Microservices**: Go-based agent, Temporal workflow workers

## Core Principles

### I. Three-Tier v3 API Architecture (MANDATORY)

New features MUST follow the 3-tier architecture:

1. **API Layer** (`src/maasapiserver/`): FastAPI handlers, Pydantic models, authorization
2. **Service Layer** (`src/maasservicelayer/services/`): Business logic, builders, QuerySpec filters
3. **Repository Layer** (`src/maasservicelayer/db/repositories/`): SQLAlchemy Core queries, no ORM

Each tier has clear responsibilities:
- **API ↔ Service**: Service is mocked in API tests
- **Service ↔ Repository**: Repositories are mocked in service tests
- **Repository**: Real database connection in tests (via `db_connection` fixture)

### II. SQLAlchemy Core (Not ORM) For Repositories

Repositories MUST use SQLAlchemy Core (`sqlalchemy.sql`), NOT the ORM:

**WHY**: Full control over queries, explicit SQL, proper indexing, no N+1 problems.

**Requirements**:
- Define queries with `select()`, `insert()`, `update()`, `delete()` statements
- Use `ClauseFactory` for reusable filters (colocated with repository)
- Keep table definitions in `src/maasservicelayer/db/tables.py` and sync with actual DB
- Use `QuerySpec` for filtering (with/where/order_by clauses)
- Builders (`src/maasservicelayer/builders/`) map Pydantic models to table columns via `DomainDataMapper`

**Violation**: Using Django ORM or SQLAlchemy ORM in v3 API repositories → Code review rejection.

### III. Pydantic Builders for Create/Update

Services MUST use Pydantic builders (auto-generated via `make generate-builders`) for creating/updating entities:

**Structure**:
- Domain Model: Core business entity (Pydantic)
- Builder Model: All fields `UNSET` by default, accepts only provided values
- Data Mapper: Maps builder → database row (e.g., `DefaultDomainDataMapper`)

**Example**: `CreateUserBuilder` → repository.create(builder) → `DomainDataMapper` → INSERT

**Violation**: Direct INSERT with hardcoded dicts → Code review rejection.

### IV. Async/Await (v3 API), Twisted Deferred (Legacy)

**v3 API** (`maasapiserver`, `maasservicelayer`):
- All handlers MUST be `async`
- Use `pytest-asyncio` for testing async code
- Never block the event loop

**Legacy** (`maasserver`, `provisioningserver`):
- Twisted deferreds for async operations
- Use `deferToDatabase()` for DB access in async contexts
- Do NOT mix async/await with deferreds

**Temporal Workflows** (`maastemporalworker`):
- Follow Temporal SDK patterns
- Type hints for Pyright compliance
- Retry policies and timeouts configured

### V. Conventional Commits with Scopes (MANDATORY)

All commits MUST follow [Conventional Commits](https://www.conventionalcommits.org/):

**Format**: `<type>[(scope)][!]: <description>`

**Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`, `ci`

**Scopes** (see `scopes.md` for full list):
- `api`: maasapiserver changes
- `service`: maasservicelayer service layer
- `repo`: maasservicelayer repositories & filters
- `db`: Database changes (migrations, table definitions)
- `agent`: maasagent (Go) changes
- `worker`: maastemporalworker
- `legacy`: maasserver (Django)
- `provisioning`: provisioningserver
- `metadata`: metadataserver
- `cli`: maascli
- `common`: maascommon
- `testing`: maastesting

**Ticket Reference** (mandatory for `fix`):
- Launchpad: `Resolves LP:2066936`
- GitHub: `Resolves GH:123`

**Examples**:
```
feat(api): add device list filtering by architecture

feat(service): implement machine allocation logic

fix(repo)!: change ip_addresses table schema
Resolves LP:2066936

test(api): add test coverage for IPAM endpoints
```

**Violation**: Commit without scope, missing ticket → CI rejects PR.

### VI. Code Quality & Linting (ENFORCED)

**Python** (Ruff + formatter):
- Line length: **79 characters** (not 88, not 100)
- Quotes: **Double quotes** only (`"string"`, not `'string'`)
- Import order: `isort` compatible
- Type hints: Pyright strict mode (Python 3.14)

**Command**: `make lint-py`, `make format-py`

**Go** (golangci-lint + gofmt):
- Version: Go 1.24.4+
- Format: `gofmt` compliance
- Lint: golangci-lint rules in `.golangci.yaml`

**Command**: `make lint-go`, `make lint-go-fix`

**Enforcement**: Pre-commit hooks, CI pipeline blocks merges.

### VII. Database Migrations with Alembic (MANDATORY for Schema Changes)

**Workflow**:
1. Add/modify table definition in `src/maasservicelayer/db/tables.py`
2. Run `alembic revision --autogenerate -m "description"`
3. Review generated migration in `src/maasservicelayer/db/alembic/versions/`
4. Test migration: `make test` runs migrations on test DB
5. Commit migration with scope: `feat(db): add role-based access control columns`

**Requirements**:
- Table definitions MUST stay in sync with actual DB
- Migrations are immutable (no editing after merge)
- Reversibility: Down migrations MUST work (tested)
- Named constraints: `FK_<table>_<column>`, `UK_<table>_<column>`

**Violation**: Schema change without migration → Breaks test DB setup.

### VIII. Testing Pyramid (MANDATORY)

**Repository Tests** (Unit — Real DB):
- Use `db_connection` fixture
- Inherit from `ReadOnlyRepositoryCommonTests` or `RepositoryCommonTests`
- Test queries in isolation
- Example: `tests/maasservicelayer/db/repositories/test_machines.py`

**Service Tests** (Unit — Mocked Repos):
- Mock repositories
- Inherit from `ServiceCommonTests`
- Focus on business logic
- Example: `tests/maasservicelayer/services/test_machine_service.py`

**API Tests** (Integration):
- Use `APICommonTests`, `mocked_api_client` fixtures
- Mock services, not repositories
- Test handlers, permissions, responses
- Example: `tests/maasapiserver/test_machines.py`

**Functional Tests** (End-to-End):
- Test full flow: API → Service → Repository → DB
- Use `db_connection` with clean state
- Example: `src/tests/functional/test_machine_provisioning.py`

**Command**: `make test-py`, `make test-go`

### IX. Three-Module Governance (Via AGENTS.md)

Monorepo is divided into 3 primary zones with clear agent boundaries:

1. **API Zone** (`src/maasapiserver/`): FastAPI handlers, Pydantic models
2. **Service Zone** (`src/maasservicelayer/{services,db}/`): Business logic, repositories, migrations
3. **Legacy Zone** (`src/maasserver/`): Django region controller (transitioning)

Plus auxiliary modules:
- **Go Services**: `src/maasagent/` (microcluster), `src/host-info/`
- **Workers**: `src/maastemporalworker/`
- **Utilities**: `src/maascommon/`, `src/maastesting/`, `src/maascli/`

See `AGENTS.md` for agent boundaries and inter-module communication.

### X. Backward Compatibility for Legacy Code

**For `maasserver` (Django)**:
- Use adapter in `src/maasserver/sqlalchemy.py` to access v3 API service layer
- Use `deferToDatabase()` for async DB access
- Prefer adding new features to v3 API
- Goal: Eventual deprecation of Django ORM

**For dependency management**:
- Both Django and FastAPI must coexist (production requirement)
- Service layer bridges both architectures
- migrations are centralized in `maasservicelayer/db/alembic/`

## Code Boundaries & Module Structure

### Primary Modules (MAAS Core)

| Module | Purpose | Technology | Dependencies | Owner |
|--------|---------|-----------|--------------|-------|
| `src/maasapiserver` | v3 REST API (Presentation) | FastAPI, Pydantic | maasservicelayer | API Agent |
| `src/maasservicelayer` | Service layer + repositories (App+Data) | SQLAlchemy Core, Pydantic | postgres | Service Agent |
| `src/maasserver` | Legacy region controller | Django, Twisted | postgres | Legacy Agent |
| `src/maasagent` | Go microservices (microcluster) | Go 1.24.4, microcluster, Temporal | — | Go Agent |
| `src/maastemporalworker` | Temporal workflows | Python, Temporal SDK | maasservicelayer | Workflow Agent |

### Supporting Modules

| Module | Purpose | Technology | Dependencies |
|--------|---------|-----------|--------------|
| `src/provisioningserver` | Rack controller (Twisted) | Twisted, Power drivers | — |
| `src/metadataserver` | Cloud-init metadata service | Django | — |
| `src/maascli` | Command-line interface | Python, Click | maasservicelayer |
| `src/apiclient` | HTTP API client library | Python, HTTPX | — |
| `src/maascommon` | Shared utilities | Python | — |
| `src/maastesting` | Test fixtures & utilities | pytest | — |
| `src/host-info` | Hardware information collection | Go 1.18 | — |

### Boundary Rules

1. **API Zone**: Can only import from maasservicelayer (services) and common
2. **Service Zone**: Can import from maasservicelayer and common; NO Django imports
3. **Legacy Zone**: Can import from maasservicelayer (adapter) and common; gradual transition
4. **Go Zone**: Communicates via APIs or Temporal workflows; isolated from Python
5. **Common Zone**: Minimal dependencies, reused by all zones

**Violation**: API importing maasserver models → Code review rejection.

## Quality Gates

### Pre-Commit (Developer Responsibility)

- `make format-py` or `make format-go` (auto-fix formatting)
- Run tests locally: `make test-py` or `make test-go`

### CI/CD (Automated)

1. **Linting**: `make lint` (Ruff + golangci-lint)
2. **Type Checking**: Pyright for Python, `go vet` for Go
3. **Tests**: `make test-py && make test-go`
4. **Coverage**: Python >80%, Go >70% (configurable per module)
5. **Conventional Commits**: Scope validation, ticket references for fixes
6. **OpenAPI**: Spec consistency check (`make lint-oapi`)

### Code Review (Team Responsibility)

1. Verify architecture adherence (3-tier for v3 API)
2. Check for Conventional Commits compliance
3. Verify test coverage (repository + service + API tiers)
4. Migration review (schema changes, reversibility)
5. Performance: Query analysis, index strategy
6. Legacy code: Prefer service layer for new features

## Governance

### Amendment Process

1. Propose amendment with justification (PR + discussion)
2. Requires 2+ maintainer approvals
3. Document in git commit: `docs(constitution): <change>`
4. Update version: `<major>.<minor>.<patch>`

### Violations

- **Formatting/Linting**: Automatically blocked by CI
- **Unconventional commits**: PR cannot merge until fixed
- **Architecture boundary violations**: Code review rejection
- **Missing tests**: PR blocked, requires >80% coverage
- **Migration without reversibility**: Code review rejection

### Enforcement Tools

- **Pre-commit**: `.pre-commit-config.yaml` runs linting locally
- **CI**: `.github/workflows/` runs all checks
- **Makefile**: `make lint`, `make test`, `make format` targets
- **Copilot**: `.github/copilot-instructions.md` + `constitution.md` guide AI agents
- **Alembic**: DB schema validation before migrations

## Next Steps

1. **For new features**: Follow this constitution + read `AGENTS.md` + read `scopes.md`
2. **For legacy features**: See `.github/instructions/python.instructions.md` section on `maasserver`
3. **For Go features**: See `.github/instructions/go.instructions.md` + `AGENTS.md`
4. **For AI agents**: Copilot/Cursor will load this file automatically via `.github/copilot-instructions.md`

---

**Last Review**: 2025-04-20  
**Maintainers**: MAAS Core Team  
**Questions**: Refer to `.github/copilot-instructions.md` for detailed subdirectory rules
