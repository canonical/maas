# MAAS Agent Governance

**Version**: 1.0 | **Created**: 2025-04-20

## Overview

This document defines AI agent boundaries, responsibilities, and communication protocols for the MAAS monorepo. It reflects the project's 3-tier v3 API architecture + legacy Django + Go microservices.

**Key Principle**: Each agent owns specific modules and communicates through well-defined interfaces (APIs, service layer, message queues).

---

## Agent Boundaries

### 1. API Agent (`src/maasapiserver/`)

**Responsibility**: FastAPI handlers, request/response models, HTTP concerns

**Scope**:
- `src/maasapiserver/handlers/` — FastAPI handler classes
- `src/maasapiserver/models/` — Request/response Pydantic models
- `src/maasapiserver/permissions.py` — Permission decorators
- `src/maasapiserver/middleware.py` — HTTP middleware
- `src/tests/maasapiserver/` — API integration tests

**Owns**: REST endpoints, OpenAPI spec, authentication, authorization checks

**Imports From**: 
- `maasservicelayer.services.*` (call services, NOT repositories)
- `maascommon.*` (utilities)
- Standard library + FastAPI

**Must NOT Import**:
- Django ORM
- Repository classes directly
- Database layer

**Tests**: Use `mocked_api_client` fixtures, mock services, inherit `APICommonTests`

**Build Command**: `make test-py -k "test_.*handler"`

**Linting**: `make lint-py` (Ruff 79 char, double quotes)

---

### 2. Service Agent (`src/maasservicelayer/services/` + `src/maasservicelayer/builders/`)

**Responsibility**: Business logic, builders, service coordination

**Scope**:
- `src/maasservicelayer/services/` — Service classes
- `src/maasservicelayer/builders/` — Pydantic builders (auto-generated)
- `src/maasservicelayer/models/` — Domain Pydantic models
- `src/tests/maasservicelayer/services/` — Service unit tests

**Owns**: Business logic, builders, service layer

**Imports From**:
- Repository layer (colocated in maasservicelayer)
- `maascommon.*`
- Pydantic, SQLAlchemy models
- Standard library

**Must NOT Import**:
- Django ORM
- FastAPI (if needed, route to API Agent)
- External APIs directly (if needed, abstract to adapters)

**Tests**: Mock repositories, use `db_connection` fixture for fixtures, inherit `ServiceCommonTests`

**Build Command**: `make test-py -k "test_.*service"`

---

### 3. Repository Agent (`src/maasservicelayer/db/repositories/` + `src/maasservicelayer/db/tables.py`)

**Responsibility**: SQLAlchemy Core queries, data access, query filters

**Scope**:
- `src/maasservicelayer/db/repositories/` — Repository classes
- `src/maasservicelayer/db/tables.py` — Table definitions
- `src/maasservicelayer/db/alembic/` — Migrations
- `src/tests/maasservicelayer/db/repositories/` — Repository unit tests

**Owns**: Data access, queries, migrations

**Imports From**:
- SQLAlchemy Core (`sqlalchemy.sql`)
- Pydantic models (for `RowToModel`)
- Standard library

**Must NOT Import**:
- Django ORM
- Services or handlers
- Application logic

**Tests**: Real database via `db_connection` fixture, inherit `RepositoryCommonTests`

**Build Command**: `make test-py -k "test_.*repository"`

**Migrations**:
- Generate: `alembic revision --autogenerate -m "description"`
- Review: Verify up/down reversibility
- Test: `alembic upgrade head && alembic downgrade -1 && alembic upgrade head`

---

### 4. Legacy Agent (`src/maasserver/`)

**Responsibility**: Django region controller (TRANSITIONING to v3 API)

**Scope**:
- `src/maasserver/` — Django models, views, managers
- `src/maasserver/sqlalchemy.py` — Adapter to bridge v3 API
- `src/tests/maasserver/` — Legacy tests
- `src/metadataserver/` — Cloud-init metadata service (also Django)

**Owns**: Existing Django code, backward compatibility

**Imports From**:
- Django ORM
- `deferToDatabase()` for async DB access
- Service layer via adapter (for new features)

**Strategy for New Features**:
1. Prefer implementing in v3 API (maasapiserver + maasservicelayer)
2. Expose via adapter (`src/maasserver/sqlalchemy.py`) if Django needs to call it
3. Gradually deprecate Django code as v3 API matures

**Tests**: Django test fixtures, `testtools`, `deferToDatabase` patterns

**Build Command**: `make test-py -k "test_.*maasserver" or bin/test.region`

**Constraint**: v3 API must NOT import from maasserver (one-way dependency only: Legacy → v3 API via adapter)

---

### 5. Go Agent (`src/maasagent/` + `src/host-info/`)

**Responsibility**: Go microservices, microcluster, Temporal integration

**Scope**:
- `src/maasagent/` — Microcluster-based agent, DHCP, DNS, Temporal workflows
- `src/host-info/` — Hardware information collection
- `src/maasagent/go.mod` — Go dependencies

**Owns**: Go code, microservices, Temporal workflows

**Imports From**:
- microcluster SDK
- Temporal SDK
- Standard Go libraries

**Communicates With**: Python services via REST APIs or Temporal message queue

**Tests**: `go test ./...`, testify assertions

**Build Command**: `make test-go` or `cd src/maasagent && make test`

**Constraint**: No Python imports (separate runtime). Communication is async (APIs, Temporal workflows, message queues).

---

### 6. Workflow Agent (`src/maastemporalworker/`)

**Responsibility**: Temporal workflow definitions, activities, orchestration

**Scope**:
- `src/maastemporalworker/` — Temporal activities and workflows
- `src/maastemporalworker/workflows/` — Workflow definitions
- `src/maastemporalworker/activities/` — Activity definitions

**Owns**: Workflow logic, async orchestration

**Imports From**:
- `maasservicelayer.services.*` (call services for data operations)
- Temporal SDK
- Standard library

**Communicates With**: Go agent via Temporal workflows (not direct Python calls)

**Tests**: Mock Temporal client, use `db_connection` for service layer access

**Build Command**: `make test-py -k "test_.*temporal"`

---

## Inter-Agent Communication

### Request Flow: Web Request

```
User Request (HTTP)
      ↓
[API Agent] — FastAPI handler
      ↓ (call service method)
[Service Agent] — Business logic
      ↓ (call repository method)
[Repository Agent] — SQLAlchemy query
      ↓
Database (PostgreSQL)
```

**Key**: Each layer mocks the layer below in tests. Mocking strategy:
- **API tests**: Mock services
- **Service tests**: Mock repositories
- **Repository tests**: Real database

---

### Request Flow: Long-Running Workflow

```
API Request to start workflow
      ↓
[Service Agent] — Creates workflow record
      ↓ (queues Temporal workflow)
Temporal Server
      ↓
[Workflow Agent] — Orchestrates async steps
      ↓ (calls services for data ops)
[Service Agent] — Reads/writes data
      ↓ (calls repositories)
[Repository Agent] — Database queries
      ↓
Database (PostgreSQL)
```

---

### Cross-Language: Go Agent to v3 API

```
Go Agent (microcluster)
      ↓ (HTTP request)
[API Agent] — FastAPI endpoint
      ↓
[Service Agent] — Business logic
      ↓
Database
```

**Communication**: REST API calls only (no shared Python code in Go runtime)

---

### Legacy Code: Django to v3 API

```
[Legacy Agent] — Django code
      ↓ (via adapter)
[Service Layer] — Synchronous wrapper
      ↓
[Repository Agent] — Database queries
```

**Adapter**: `src/maasserver/sqlalchemy.py` bridges sync Django → async v3 API service layer

---

## Code Boundaries (Module Dependency Rules)

### API Agent
- ✅ Can import: maasservicelayer.services, maascommon, FastAPI, Pydantic
- ❌ Cannot import: maasserver, repositories, Django ORM

### Service Agent
- ✅ Can import: repositories (colocated), maascommon, Pydantic, SQLAlchemy models
- ❌ Cannot import: maasserver, FastAPI, Django ORM, external APIs (without abstraction)

### Repository Agent
- ✅ Can import: SQLAlchemy Core, Pydantic models, maascommon
- ❌ Cannot import: Services, handlers, maasserver, Django

### Legacy Agent
- ✅ Can import: maasservicelayer.services (via adapter), Django
- ✅ Can import: SQLAlchemy (via adapter)
- ❌ Cannot be imported by: API or Service agents (one-way dependency)

### Go Agent
- ✅ Can import: microcluster, Temporal, testify
- ❌ Cannot import: Python modules

### Workflow Agent
- ✅ Can import: maasservicelayer.services, Temporal SDK
- ❌ Cannot import: FastAPI, Django, microcluster

---

## Code Review Checklist (Per Agent)

### For API Agent PRs
- [ ] All endpoints have `@check_permissions()` decorator
- [ ] Pydantic models validate input (length, format, allowed values)
- [ ] Handlers mock services (not repositories)
- [ ] Tests use `mocked_api_client` fixtures
- [ ] OpenAPI spec is accurate (`make lint-oapi` passes)
- [ ] No direct repository imports

### For Service Agent PRs
- [ ] Services mock repositories in tests
- [ ] Builders use `UNSET` pattern
- [ ] Business logic is testable (pure functions where possible)
- [ ] Services use `async def` (no blocking calls)
- [ ] Tests inherit `ServiceCommonTests`

### For Repository Agent PRs
- [ ] Uses SQLAlchemy Core (not ORM)
- [ ] Queries are explicit (not lazy-loaded)
- [ ] Repositories return Pydantic models
- [ ] ClauseFactory defined for reusable filters
- [ ] Tests use `db_connection` fixture
- [ ] Tests inherit `RepositoryCommonTests`
- [ ] Migration tested (up/down reversible)

### For Legacy Agent PRs
- [ ] No new Django models added if feature can go to v3 API
- [ ] `deferToDatabase()` used for async DB access
- [ ] Via adapter if calling v3 API service layer
- [ ] Backward compatibility maintained

### For Go Agent PRs
- [ ] `go fmt` compliant
- [ ] `golangci-lint` passes
- [ ] Tests use testify assertions
- [ ] No Python imports

### For Workflow Agent PRs
- [ ] Temporal SDK patterns followed
- [ ] Type hints present (Pyright compliance)
- [ ] Services mocked in tests
- [ ] Retry policies configured

---

## Adding New Modules

**When to add a new agent boundary**:

1. New programming language (new runtime, e.g., Rust, Kotlin)
2. New major subsystem (not just utilities)
3. Clear separation of concerns (can be developed independently)
4. Explicit communication protocol (API, message queue, or function call)

**Steps**:

1. Update `AGENTS.md` (this file) with new agent
2. Document module path and responsibility
3. Define imports/exports
4. Define how it communicates with existing agents
5. Add code review checklist

---

## Conflict Resolution

**When two agents want to claim a module**:

1. First agent to merge owns the module
2. Other agent refactors their code to use the first agent's API
3. Update AGENTS.md to reflect ownership
4. Document any future code moves in the commit message

**When responsibilities overlap** (e.g., Service Agent needs repository test utilities):

1. Move shared code to `maastesting` (neutral module)
2. Both agents can import from `maastesting`
3. Update `AGENTS.md` to document shared ownership

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-04-20 | Initial bootstrap: API, Service, Repository, Legacy, Go, Workflow agents |

---

**Maintainers**: MAAS Core Team  
**Questions**: Refer to `.github/copilot-instructions.md`
