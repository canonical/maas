# Feature Specification: [FEATURE NAME]

**Feature Branch**: `[###-feature-name]`  
**Created**: [DATE]  
**Status**: Draft  
**Input**: User description: "$ARGUMENTS"

## User Scenarios & Testing *(mandatory)*

<!--
  IMPORTANT: User stories should be PRIORITIZED as user journeys ordered by importance.
  Each user story/journey must be INDEPENDENTLY TESTABLE - meaning if you implement just ONE of them,
  you should still have a viable MVP (Minimum Viable Product) that delivers value.
  
  Assign priorities (P1, P2, P3, etc.) to each story, where P1 is the most critical.
  Think of each story as a standalone slice of functionality that can be:
  - Developed independently
  - Tested independently
  - Deployed independently
  - Demonstrated to users independently
-->

### User Story 1 - [Brief Title] (Priority: P1)

[Describe this user journey in plain language]

**Why this priority**: [Explain the value and why it has this priority level]

**Independent Test**: [Describe how this can be tested independently - e.g., "Can be fully tested by [specific action] and delivers [specific value]"]

**Acceptance Scenarios**:

1. **Given** [initial state], **When** [action], **Then** [expected outcome]
2. **Given** [initial state], **When** [action], **Then** [expected outcome]

---

### User Story 2 - [Brief Title] (Priority: P2)

[Describe this user journey in plain language]

**Why this priority**: [Explain the value and why it has this priority level]

**Independent Test**: [Describe how this can be tested independently]

**Acceptance Scenarios**:

1. **Given** [initial state], **When** [action], **Then** [expected outcome]

---

### User Story 3 - [Brief Title] (Priority: P3)

[Describe this user journey in plain language]

**Why this priority**: [Explain the value and why it has this priority level]

**Independent Test**: [Describe how this can be tested independently]

**Acceptance Scenarios**:

1. **Given** [initial state], **When** [action], **Then** [expected outcome]

---

## API Requirements *(if feature includes API endpoints)*

> For v3 API features: Describe REST endpoints, request/response models, and authorization.

### Endpoints

**Endpoint 1**: `[METHOD] /api/v3/[resource]`

- **Handler Class**: Extend `Handler` in `src/maasapiserver/handlers/[resource].py`
- **Pydantic Models**:
  - Request: `[Resource]CreateRequest` (use Pydantic builder pattern)
  - Response: `[Resource]Response` (Pydantic model)
- **Permissions**: `@check_permissions([Permission.X])`
- **Query Parameters**: `skip`, `limit`, `[filter_1]`, `[filter_2]`
- **Authentication**: Bearer token, sessionid cookie, or Macaroon

**Example**:
```python
class MachinesHandler(Handler):
    @handler(method="GET")
    @check_permissions([PermissionEnum.VIEW_MACHINES])
    async def list(self) -> MachineListResponse:
        """List all machines with optional filtering."""
```

**Endpoint 2**: `[METHOD] /api/v3/[resource]/[id]`

- **Handler Class**: [Same handler as above]
- **Pydantic Models**: Response model (detail view)

---

## Service Layer Requirements *(mandatory for v3 API)*

> Implement business logic in `src/maasservicelayer/services/`.

### Service Class

**Name**: `[Resource]Service`  
**Location**: `src/maasservicelayer/services/[resource].py`  
**Base Class**: `BaseService` or `ReadOnlyService`

**Responsibilities**:
- Orchestrate repository calls
- Implement business logic (validations, state transitions)
- Use builders for create/update operations
- Return Pydantic models (not ORM objects)

**Example**:
```python
class MachineService(BaseService):
    def __init__(self, context: Context, machine_repo: MachineRepository):
        self.context = context
        self.machine_repo = machine_repo

    async def create(self, builder: CreateMachineBuilder) -> Machine:
        # Validate builder
        # Check constraints
        # Call repository
        machine = await self.machine_repo.create(builder)
        return machine

    async def list(self, spec: QuerySpec) -> Paginated[Machine]:
        # Apply filters, sorting
        machines = await self.machine_repo.find(spec)
        return machines
```

### Builder Models

- **Location**: `src/maasservicelayer/builders/[resource].py`
- **Generated**: Via `make generate-builders` from domain models
- **Pattern**: All fields `UNSET` by default; only provided values set
- **Usage**: `CreateMachineBuilder`, `UpdateMachineBuilder`

---

## Repository Layer Requirements *(mandatory for v3 API)*

> Implement data access in `src/maasservicelayer/db/repositories/`.

### Repository Class

**Name**: `[Resource]Repository`  
**Location**: `src/maasservicelayer/db/repositories/[resource].py`  
**Base Class**: `ReadOnlyRepository` or `BaseRepository`

**Requirements**:
- Use SQLAlchemy Core (NOT ORM): `select()`, `insert()`, `update()`, `delete()`
- Define queries explicitly; no lazy loading
- Return Pydantic models (via `RowToModel`)
- Support `QuerySpec` for filtering

**Example**:
```python
class MachineRepository(BaseRepository):
    async def find(self, spec: QuerySpec = None) -> List[Machine]:
        query = select(machines_table)
        if spec:
            for clause in spec.where_clauses:
                query = query.where(clause.condition)
        rows = await self.execute(query)
        return [RowToModel.row_to_model(row, Machine) for row in rows]

    async def create(self, builder: CreateMachineBuilder) -> Machine:
        mapper = DefaultDomainDataMapper(builder)
        values = mapper.map_to_create_dict()
        query = insert(machines_table).values(**values)
        result = await self.execute(query)
        return await self.get(result.inserted_primary_key[0])
```

### Clause Factories

**Location**: Same file as repository (e.g., `_machines.py`)  
**Pattern**: `with_<column>` methods for reusable filters

**Example**:
```python
class MachineClauseFactory:
    @staticmethod
    def with_name(name: str) -> Clause:
        return Clause(
            condition=eq(machines_table.c.name, name),
            joins=[]
        )

    @staticmethod
    def with_status(status: MachineStatus) -> Clause:
        return Clause(
            condition=eq(machines_table.c.status, status.value),
            joins=[]
        )
```

### Database Changes

- **Table Definition**: Add/modify in `src/maasservicelayer/db/tables.py`
- **Migration**: Create with `alembic revision --autogenerate -m "message"`
- **Migration Location**: `src/maasservicelayer/db/alembic/versions/`
- **Reversibility**: Down migration MUST work (tested)

---

## Database Schema *(if schema changes required)*

> Describe tables, columns, constraints, and relationships.

### New Tables

| Table | Columns | Constraints | Indexes |
|-------|---------|-------------|---------|
| `[table_name]` | `id` (PK), `name` (UK), `created_at`, ... | FK to `[parent]`, CHECK (`status` IN ...) | `idx_[table]_[column]` on status, created_at |

### Migrations

- **Script**: `src/maasservicelayer/db/alembic/versions/[timestamp]_[description].py`
- **Testing**: Migration tested on schema before/after
- **Rollback**: Down migration reverses all changes

---

## Legacy Django Code *(if touching maasserver)*

> For changes in `src/maasserver/`, describe Django model interaction and backward compatibility.

### Django ORM Integration

- **Model**: `src/maasserver/models/[model].py`
- **Adapter**: Access via `src/maasserver/sqlalchemy.py` to bridge v3 API service layer
- **Pattern**: Use `deferToDatabase()` for async DB calls
- **Goal**: Prefer adding features to v3 API; Django is transitioning

### Backward Compatibility

- **v2 API Endpoints**: Still supported; delegate to v3 service layer when possible
- **Database**: Single shared database (postgres)
- **No Breaking Changes**: Existing clients must continue working

---

## Go Microservices *(if adding Go code)*

> For `src/maasagent/` or other Go modules.

### Architecture

- **Module**: `src/maasagent/`
- **Framework**: microcluster, Temporal SDK
- **Version**: Go 1.24.4+
- **Testing**: testify assertions, standard `testing` package

### Key Patterns

- **Error Handling**: Explicit error returns; use sentinel errors
- **Context**: Pass context through all async operations
- **Type Hints**: Required for clarity (Go's implicit typing is fine, but use interfaces)
- **Temporal Integration**: Activities and workflows defined with proper retry policies

### Build & Test

```bash
cd src/maasagent
make test    # or: go test ./...
make lint    # or: golangci-lint run
```

---

## Testing Strategy

### Repository Tests

- **Location**: `src/tests/maasservicelayer/db/repositories/test_[resource].py`
- **Pattern**: Real database (`db_connection` fixture)
- **Base Class**: `RepositoryCommonTests` or `ReadOnlyRepositoryCommonTests`
- **Focus**: Query correctness, filtering, edge cases

**Example**:
```python
class TestMachineRepository(RepositoryCommonTests):
    async def test_find_by_status(self, db_connection):
        repo = MachineRepository(db_connection)
        machines = await repo.find(spec=QuerySpec(
            where_clauses=[MachineClauseFactory.with_status(MachineStatus.READY)]
        ))
        assert len(machines) == 2
```

### Service Tests

- **Location**: `src/tests/maasservicelayer/services/test_[resource].py`
- **Pattern**: Mocked repositories
- **Base Class**: `ServiceCommonTests`
- **Focus**: Business logic, validation, state transitions

**Example**:
```python
class TestMachineService(ServiceCommonTests):
    async def test_create_validates_name(self, context, mock_repo):
        service = MachineService(context, mock_repo)
        builder = CreateMachineBuilder(name="")
        with pytest.raises(ValidationError):
            await service.create(builder)
```

### API Tests

- **Location**: `src/tests/maasapiserver/handlers/test_[resource].py`
- **Pattern**: `APICommonTests`, `mocked_api_client` fixtures
- **Focus**: Handlers, permissions, HTTP status codes, response format

**Example**:
```python
class TestMachinesHandler(APICommonTests):
    async def test_list_machines(self, mocked_api_client):
        client = mocked_api_client()
        response = await client.get("/api/v3/machines?status=ready")
        assert response.status_code == 200
        assert len(response.json()["data"]) == 2
```

### Functional Tests

- **Location**: `src/tests/functional/test_[feature].py`
- **Pattern**: Full stack (API → Service → Repository → DB)
- **Focus**: End-to-end workflows, cross-module integration

---

## Configuration & Dependencies

### Python Dependencies

- **FastAPI**: v0.x (for v3 API)
- **SQLAlchemy**: Core only (no ORM)
- **Pydantic**: v2.x
- **pytest**: v9+ (with asyncio, mock, xdist)
- **Alembic**: For migrations
- **Ruff**: Line length 79, double quotes

### Go Dependencies

- **Go Version**: 1.24.4+
- **microcluster**: For agent architecture
- **Temporal**: For workflow orchestration
- **testify**: For test assertions
- Check `go.mod` before adding new dependencies

### Database

- **Engine**: PostgreSQL
- **Migrations**: Alembic (Python)
- **Schema Sync**: `src/maasservicelayer/db/tables.py` MUST match DB

---

## Deployment & Rollout

> Describe rollout plan, feature flags, gradual adoption, etc.

### Rollout Phases

1. **Phase 1**: Internal testing on staging
2. **Phase 2**: Gradual rollout to early adopters (10% of instances)
3. **Phase 3**: Full rollout with monitoring

### Feature Flags

- **Environment Variable**: `FEATURE_[NAME]_ENABLED` (set in `.github/workflows/`)
- **Graceful Degradation**: Feature disabled → Legacy behavior active
- **No Breaking Changes**: v2 API still works during rollout

---

## Performance & Observability

### Performance Requirements

- **API Response Time**: <500ms p95 for list endpoints
- **Query Performance**: All queries use appropriate indexes
- **Database Connections**: Connection pooling configured
- **Memory**: No memory leaks in long-running services

### Monitoring

- **Structured Logging**: Include request ID, user, timestamp
- **Metrics**: Response time, error rate, throughput
- **Traces**: OpenTelemetry integration for cross-service tracing
- **Alerts**: Critical errors trigger alerts

---

## Security & Compliance

### Authorization

- **API Endpoints**: All require `@check_permissions([PermissionEnum.X])`
- **Services**: Validate user context before data access
- **Repositories**: No permission checks (service layer responsibility)

### Input Validation

- **Pydantic Models**: Define all validators (length, format, allowed values)
- **Range Checks**: Validate numeric inputs (min/max)
- **CSRF/CORS**: FastAPI middleware configured

### Secrets Management

- **Database Credentials**: Via environment variables, not hardcoded
- **API Keys**: Use Macaroons or Bearer tokens (not passwords in API)

---

## Open Questions *(as discovered during research)*

> Document any ambiguities or decisions needed from stakeholders.

- [ ] Question 1: [...]
- [ ] Question 2: [...]

---

**Next Step**: Implement per `plan.md` → Run `/speckit.plan` to generate detailed design.
