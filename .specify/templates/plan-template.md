# Implementation Plan: [FEATURE]

**Branch**: `[###-feature-name]` | **Date**: [DATE] | **Spec**: [link to spec.md]  
**Input**: Feature specification from `/specs/[###-feature-name]/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. Output includes research.md, data-model.md, quickstart.md, and contracts/ for each user story.

## Summary

[Extract from feature spec: primary requirement + technical approach from research]

## Technical Context

**Language/Version**: Python 3.14 (or Go 1.24.4 if Go module)  
**Primary Dependencies**: FastAPI, SQLAlchemy Core, Pydantic (v3 API) | Django, Twisted (legacy)  
**Database**: PostgreSQL via Alembic migrations  
**Testing**: pytest + asyncio (Python), testify (Go)  
**Target Component**: v3 API (maasapiserver + maasservicelayer) | Legacy (maasserver) | Go (maasagent)  
**Architecture Pattern**: 3-tier (API → Service → Repository) for v3 API  
**Scale/Scope**: [e.g., affects 3 API endpoints, 2 services, 1 repository]

## Constitution Check

*Gate: Verify compliance before Phase 1 research.*

- ✅ Feature aligns with 3-tier v3 API architecture (or legacy/Go exception documented)
- ✅ Database changes planned as Alembic migrations
- ✅ Testing strategy covers repository + service + API tiers (or exception documented)
- ✅ Conventional Commits scope assigned (see `scopes.md`)
- ✅ Ruff formatting: 79 chars, double quotes
- ✅ No ORM in v3 API repositories (SQLAlchemy Core only)

---

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature-name]/
├── spec.md              # User stories and requirements (input)
├── plan.md              # This file (output of /speckit.plan)
├── research.md          # Phase 0: Research & decisions (output of /speckit.plan)
├── data-model.md        # Phase 1: Entity models & relationships (output of /speckit.plan)
├── quickstart.md        # Phase 1: Getting started guide (output of /speckit.plan)
├── contracts/
│   ├── api.md           # REST endpoints per user story (output of /speckit.plan)
│   ├── services.md      # Service interfaces & builders (output of /speckit.plan)
│   └── repos.md         # Repository queries & filters (output of /speckit.plan)
└── tasks.md             # Phase 2: Actionable task list (output of /speckit.tasks)
```

### Source Code (repository root)

```text
# v3 API Architecture (Primary Pattern)
src/
├── maasapiserver/
│   └── handlers/[resource].py       # FastAPI handlers + Pydantic models
├── maasservicelayer/
│   ├── services/[resource].py       # Business logic services
│   ├── builders/[resource].py       # Pydantic builders (auto-generated)
│   ├── db/
│   │   ├── repositories/[resource].py  # SQLAlchemy Core repositories
│   │   ├── tables.py                # All table definitions
│   │   └── alembic/versions/        # Migrations
│   └── models/[resource].py         # Domain Pydantic models
└── tests/
    ├── maasservicelayer/
    │   ├── db/repositories/test_[resource].py    # Repo unit tests
    │   └── services/test_[resource].py           # Service unit tests
    ├── maasapiserver/
    │   └── handlers/test_[resource].py           # API integration tests
    └── functional/test_[feature].py              # End-to-end tests
```

---

## Implementation Phases

### Phase 0: Research & Discovery

**Goal**: Answer open questions, finalize architecture decisions

**Deliverables** (from `/speckit.plan`):
- `research.md`: API design decisions, schema considerations, legacy compatibility
- Answers to all open questions from spec.md
- Identified dependencies (new packages, module interactions)

**Key Decisions**:
1. Does this feature touch legacy Django code? → Compatibility strategy
2. Requires database schema changes? → Alembic migration plan
3. Multi-module feature? → Service layer architecture across modules
4. Go component needed? → microcluster or Temporal integration

**Go/No-Go**: Any blockers → Escalate before Phase 1

---

### Phase 1: API Layer Design

**Goal**: Define REST endpoints, request/response contracts, handlers

**Deliverables** (from `/speckit.plan`):
- `contracts/api.md`: Endpoints, HTTP methods, status codes, error handling
- Pydantic request/response models defined (in `src/maasapiserver/`)
- Handler stubs with permission decorators

**Tasks** (from `/speckit.tasks`):
- [ ] T001: Create handler class in `src/maasapiserver/handlers/[resource].py`
- [ ] T002: Define Pydantic models for requests/responses
- [ ] T003: Add permission checks via `@check_permissions()`
- [ ] T004: Write handler docstrings for OpenAPI spec
- [ ] T005: Add API integration tests (mock services)

**Quality Gates**:
- All endpoints have permission decorators
- Pydantic models pass strict validation
- OpenAPI spec generated correctly (`make lint-oapi`)
- Tests use `mocked_api_client` fixtures

**Duration**: ~1-2 days per user story

---

### Phase 2: Service Layer Implementation

**Goal**: Implement business logic, transactions, validations

**Deliverables** (from `/speckit.plan`):
- `contracts/services.md`: Service methods, signatures, error cases
- Service class in `src/maasservicelayer/services/[resource].py`
- Builder models auto-generated in `src/maasservicelayer/builders/[resource].py`

**Tasks** (from `/speckit.tasks`):
- [ ] T100: Create service class with interface definitions
- [ ] T101: Implement create/update methods with builders
- [ ] T102: Implement business logic (validations, state checks)
- [ ] T103: Write service unit tests (mock repositories)
- [ ] T104: Verify async/await patterns

**Quality Gates**:
- All services inherit from `BaseService` or `ReadOnlyService`
- Builders use `UNSET` pattern for optional fields
- >80% test coverage for business logic
- No database calls (services use repositories)

**Duration**: ~2-3 days per user story

---

### Phase 3: Repository Layer & Queries

**Goal**: Implement SQLAlchemy Core data access, query filters

**Deliverables** (from `/speckit.plan`):
- `contracts/repos.md`: Repository methods, QuerySpec filters, ClauseFactory patterns
- Repository class in `src/maasservicelayer/db/repositories/[resource].py`
- ClauseFactory for reusable filters (colocated)

**Tasks** (from `/speckit.tasks`):
- [ ] T200: Create repository class extending `BaseRepository`
- [ ] T201: Implement SQLAlchemy Core queries (select, insert, update, delete)
- [ ] T202: Define ClauseFactory methods for filtering
- [ ] T203: Write repository unit tests (real database `db_connection` fixture)
- [ ] T204: Test query performance and indexes

**Quality Gates**:
- All queries use SQLAlchemy Core (no ORM)
- Repositories return Pydantic models (via `RowToModel`)
- `QuerySpec` used for all filtering
- >80% test coverage for data access
- Repository tests inherit from `RepositoryCommonTests`

**Duration**: ~2-3 days per entity

---

### Phase 4: Database Schema & Migrations

**Goal**: Define tables, create Alembic migrations, test schema changes

**Deliverables** (from `/speckit.plan`):
- `data-model.md`: Entity relationships, columns, constraints, indexes
- Table definitions in `src/maasservicelayer/db/tables.py`
- Alembic migration in `src/maasservicelayer/db/alembic/versions/`

**Tasks** (from `/speckit.tasks`):
- [ ] T300: Add table definitions to `db/tables.py`
- [ ] T301: Generate migration: `alembic revision --autogenerate -m "message"`
- [ ] T302: Review generated migration, add constraints as needed
- [ ] T303: Test migration up/down on test database
- [ ] T304: Verify table definitions stay in sync

**Quality Gates**:
- Migration is immutable (no edits after merge)
- Down migration works (reversible)
- All constraints named per convention: `FK_*`, `UK_*`, `idx_*`
- Indexes on filter columns (status, created_at, etc.)
- Schema matches table definitions exactly

**Duration**: ~1-2 days

---

### Phase 5: Integration Testing & Functional Tests

**Goal**: Test full stack (API → Service → Repo → DB), cross-module flows

**Deliverables** (from `/speckit.plan`):
- `quickstart.md`: How to manually test the feature end-to-end
- Functional tests in `src/tests/functional/test_[feature].py`

**Tasks** (from `/speckit.tasks`):
- [ ] T400: Create functional test class
- [ ] T401: Test user story 1 end-to-end
- [ ] T402: Test user story 2 end-to-end
- [ ] T403: Test error cases and edge cases
- [ ] T404: Test with real database (migration run, cleanup)

**Quality Gates**:
- All user stories tested end-to-end
- >80% overall code coverage
- No flaky tests (tests pass consistently)
- All acceptance criteria from spec.md verified

**Duration**: ~1-2 days

---

## Testing Strategy

### Tier 1: Repository Tests (Unit — Real DB)

**Command**: `make test-py -k "test_.*repository"`

- Use `db_connection` fixture (real PostgreSQL)
- Base class: `RepositoryCommonTests` or `ReadOnlyRepositoryCommonTests`
- Focus: Query correctness, filtering, edge cases
- No mocking (use real DB)

**Example**:
```python
class TestMachineRepository(RepositoryCommonTests):
    async def test_find_with_status_filter(self, db_connection):
        repo = MachineRepository(db_connection)
        machines = await repo.find(spec=QuerySpec(
            where_clauses=[MachineClauseFactory.with_status(MachineStatus.READY)]
        ))
        assert all(m.status == MachineStatus.READY for m in machines)
```

### Tier 2: Service Tests (Unit — Mocked Repos)

**Command**: `make test-py -k "test_.*service"`

- Mock repositories
- Base class: `ServiceCommonTests`
- Focus: Business logic, validations, state transitions
- Fast (no DB)

**Example**:
```python
class TestMachineService(ServiceCommonTests):
    async def test_create_sets_initial_status(self, context, mock_machine_repo):
        service = MachineService(context, mock_machine_repo)
        builder = CreateMachineBuilder(name="machine-1")
        machine = await service.create(builder)
        assert machine.status == MachineStatus.NEW
```

### Tier 3: API Tests (Integration — Mocked Services)

**Command**: `make test-py -k "test_.*handler" or test_.*api"`

- Mock services
- Base class: `APICommonTests`
- Fixtures: `mocked_api_client`, `mocked_service`
- Focus: Handler logic, permissions, HTTP responses

**Example**:
```python
class TestMachinesHandler(APICommonTests):
    async def test_list_returns_200(self, mocked_api_client):
        client = mocked_api_client()
        response = await client.get("/api/v3/machines")
        assert response.status_code == 200
```

### Tier 4: Functional Tests (End-to-End)

**Command**: `make test-py -k "test_.*functional"`

- Full stack (API → Service → Repo → DB)
- Use `db_connection` fixture for setup/teardown
- Test user stories end-to-end

**Example**:
```python
class TestMachineProvisioning:
    async def test_create_and_provision_machine(self, db_connection):
        # 1. Call API to create machine
        # 2. Verify it appears in database
        # 3. Provision and verify state change
        # 4. Verify events logged
```

### Go Tests

**Command**: `cd src/maasagent && make test` or `go test ./...`

- Use testify assertions
- Standard Go testing patterns
- Mock external services (Temporal, APIs)

---

## Build & Deploy

### Local Development

```bash
# Format
make format-py                    # Auto-fix Python
make format-go                    # Auto-fix Go

# Lint
make lint-py                      # Ruff + Pyright
make lint-go                      # golangci-lint

# Test
make test-py                      # All Python tests
make test-go                      # All Go tests
make test                         # Full suite

# Build
make build-py                     # Package Python
make build-go                     # Build Go binaries
```

### CI/CD Pipeline (GitHub Actions)

```yaml
# .github/workflows/ runs automatically on PR
- Linting (Ruff + golangci-lint)
- Type checking (Pyright + go vet)
- Tests (pytest + go test)
- Code coverage (>80% for Python)
- OpenAPI spec validation
- Conventional Commits validation
```

### Deployment Steps

1. **Feature branch**: Create `[###-feature-name]` branch
2. **Implement**: Follow phases 0-5 above
3. **PR review**: Code review against constitution
4. **CI passes**: All tests, linting, coverage gates pass
5. **Merge**: Squash or rebase per team policy
6. **Release**: Feature included in next MAAS release

---

## Dependencies & Risks

### Internal Dependencies

- **maasservicelayer**: v3 API features depend on service layer
- **Database**: All features require PostgreSQL + migrations
- **Alembic**: Schema changes require migration scripts

### External Dependencies

- **FastAPI**: v0.x+ (if API feature)
- **SQLAlchemy**: Core only (if repository feature)
- **Pydantic**: v2.x (all features)
- **pytest**: v9+ (all tests)

### Known Risks

1. **Legacy compatibility**: v2 API changes must not break existing clients
   - Mitigation: Test with v2 API client
   - Rollback plan: Feature flag to disable new functionality
2. **Database migration failures**: Production DB changes must be reversible
   - Mitigation: Test migration up/down on staging
   - Rollback plan: Have down migration ready
3. **Performance regression**: New queries must have appropriate indexes
   - Mitigation: Analyze query plans before merge
   - Rollback plan: Add indexes post-deployment if needed

---

## Success Criteria

- ✅ All user stories (P1, P2, P3) implemented and tested
- ✅ >80% code coverage (Python)
- ✅ All tests pass (`make test` succeeds)
- ✅ Linting passes (`make lint` succeeds)
- ✅ OpenAPI spec updated and valid
- ✅ Database migrations tested (up/down)
- ✅ Conventional Commits followed
- ✅ Constitution compliance verified
- ✅ Performance benchmarks met (if applicable)
- ✅ Documentation complete (`quickstart.md`, `contracts/`)

---

**Next Step**: Run `/speckit.tasks` to generate actionable task list per user story.
