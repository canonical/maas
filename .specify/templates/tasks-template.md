---
description: "Task list template for MAAS feature implementation (v3 API + Python + Go)"
---

# Tasks: [FEATURE NAME]

**Input**: Design documents from `/specs/[###-feature-name]/`  
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Organization**: Tasks grouped by implementation phase + user story, enabling parallel work

## Format & Conventions

- **[ID]**: Unique task identifier (T001, T100, T200, etc.)
- **[P]**: Can run in parallel (independent tasks, different files)
- **[Phase]**: Which implementation phase (API, Service, Repo, DB, Integration)
- **[Story]**: Which user story (US1, US2, US3)
- **Exact paths**: File paths fully specified for implementation

---

## Phase 1: Setup & Configuration

**Purpose**: Project initialization, shared infrastructure

### T001 [P] Create API handler structure

**Phase**: API | **Story**: US1-3 | **Parallel**: All API tasks

- Create `src/maasapiserver/handlers/[resource].py`
- Define handler class extending `Handler`
- Add docstrings for OpenAPI spec generation
- Ensure `@check_permissions([PermissionEnum.X])` on all endpoints

**Files Created**:
- `src/maasapiserver/handlers/[resource].py` (handler stub)
- `src/maasapiserver/handlers/test_[resource].py` (test stub)

**Command**: `make format-py && make lint-py`

---

### T002 [P] Define Pydantic request/response models

**Phase**: API | **Story**: US1-3 | **Parallel**: All models

- Create request models: `[Resource]CreateRequest`, `[Resource]UpdateRequest`
- Create response models: `[Resource]Response`, `[Resource]ListResponse`
- Add Pydantic validators (length, format, allowed values)
- Use `Field(description="...")` for OpenAPI documentation

**Files**:
- `src/maasapiserver/models/[resource].py` (if shared models)
- Or inline in `src/maasapiserver/handlers/[resource].py` (if handler-specific)

**Command**: `make format-py && make lint-py`

---

### T003 [P] Create service layer interface

**Phase**: Service | **Story**: US1-3 | **Parallel**: All services

- Create `src/maasservicelayer/services/[resource].py`
- Define `[Resource]Service` class extending `BaseService` or `ReadOnlyService`
- Add method signatures (async def)
- Add docstrings for each method

**Files**:
- `src/maasservicelayer/services/[resource].py` (service stub)
- `src/tests/maasservicelayer/services/test_[resource].py` (test stub)

**Command**: `make format-py && make lint-py`

---

### T004 [P] Create repository structure

**Phase**: Repo | **Story**: US1-3 | **Parallel**: All repositories

- Create `src/maasservicelayer/db/repositories/[resource].py`
- Define `[Resource]Repository` class extending `BaseRepository`
- Add method signatures (async def)
- Define `[Resource]ClauseFactory` for filters

**Files**:
- `src/maasservicelayer/db/repositories/[resource].py` (repo stub)
- `src/tests/maasservicelayer/db/repositories/test_[resource].py` (test stub)

**Command**: `make format-py && make lint-py`

---

### T005 [P] Generate builder models

**Phase**: Service | **Story**: US1-3

- Run `make generate-builders` to auto-generate from domain models
- Verify builders in `src/maasservicelayer/builders/[resource].py`
- All fields should default to `UNSET`

**Command**: `make generate-builders && make format-py`

---

## Phase 2: API Layer Implementation

### T100 [P] Implement GET endpoint (list)

**Phase**: API | **Story**: US1 | **Parallel**: Independent per resource

**Endpoint**: `GET /api/v3/[resource]`

**Handler Method**:
```python
@handler(method="GET")
@check_permissions([PermissionEnum.VIEW_[RESOURCE]])
async def list(self) -> [Resource]ListResponse:
```

**Implementation**:
1. Extract query parameters: `skip`, `limit`, filters
2. Build `QuerySpec` for service layer
3. Call `self.context.service.[resource_service].list(spec)`
4. Return `[Resource]ListResponse` with data + pagination info

**Files Modified**:
- `src/maasapiserver/handlers/[resource].py` (add method)

**Testing**:
- [ ] T100a: Write test for successful list
- [ ] T100b: Write test for list with filters
- [ ] T100c: Write test for list with pagination
- [ ] T100d: Write test for permission denied (403)

**Commands**:
```bash
make format-py
make lint-py
make test-py -k "test_list_[resource]"
```

---

### T101 [P] Implement GET endpoint (detail)

**Phase**: API | **Story**: US1 | **Parallel**: Independent per resource

**Endpoint**: `GET /api/v3/[resource]/{id}`

**Handler Method**:
```python
@handler(method="GET", path="/{id}")
@check_permissions([PermissionEnum.VIEW_[RESOURCE]])
async def get(self, id: str) -> [Resource]Response:
```

**Implementation**:
1. Validate ID (format, exists)
2. Call `self.context.service.[resource_service].get(id)`
3. Return `[Resource]Response`
4. Handle 404 if not found

**Files Modified**:
- `src/maasapiserver/handlers/[resource].py` (add method)

**Testing**:
- [ ] T101a: Write test for successful get
- [ ] T101b: Write test for invalid ID (400)
- [ ] T101c: Write test for not found (404)
- [ ] T101d: Write test for permission denied (403)

**Commands**:
```bash
make format-py
make test-py -k "test_get_[resource]"
```

---

### T102 [P] Implement POST endpoint (create)

**Phase**: API | **Story**: US1 | **Parallel**: Independent per resource

**Endpoint**: `POST /api/v3/[resource]`

**Handler Method**:
```python
@handler(method="POST")
@check_permissions([PermissionEnum.CREATE_[RESOURCE]])
async def create(self, request: [Resource]CreateRequest) -> [Resource]Response:
```

**Implementation**:
1. Validate request via Pydantic (automatic)
2. Build `Create[Resource]Builder` from request
3. Call `self.context.service.[resource_service].create(builder)`
4. Return `[Resource]Response` with 201 status

**Files Modified**:
- `src/maasapiserver/handlers/[resource].py` (add method)

**Testing**:
- [ ] T102a: Write test for successful create
- [ ] T102b: Write test for invalid input (400)
- [ ] T102c: Write test for duplicate/constraint violation (409)
- [ ] T102d: Write test for permission denied (403)

**Commands**:
```bash
make test-py -k "test_create_[resource]"
```

---

### T103 [P] Implement PUT/PATCH endpoint (update)

**Phase**: API | **Story**: US2 | **Parallel**: Independent per resource

**Endpoint**: `PUT /api/v3/[resource]/{id}` or `PATCH`

**Handler Method**:
```python
@handler(method="PUT", path="/{id}")
@check_permissions([PermissionEnum.UPDATE_[RESOURCE]])
async def update(self, id: str, request: [Resource]UpdateRequest) -> [Resource]Response:
```

**Implementation**:
1. Validate request
2. Build `Update[Resource]Builder` from request
3. Call `self.context.service.[resource_service].update(id, builder)`
4. Return updated `[Resource]Response`

**Files Modified**:
- `src/maasapiserver/handlers/[resource].py` (add method)

**Testing**:
- [ ] T103a: Write test for successful update
- [ ] T103b: Write test for invalid input (400)
- [ ] T103c: Write test for not found (404)
- [ ] T103d: Write test for permission denied (403)

**Commands**:
```bash
make test-py -k "test_update_[resource]"
```

---

### T104 [P] Implement DELETE endpoint

**Phase**: API | **Story**: US3 | **Parallel**: Independent per resource

**Endpoint**: `DELETE /api/v3/[resource]/{id}`

**Handler Method**:
```python
@handler(method="DELETE", path="/{id}")
@check_permissions([PermissionEnum.DELETE_[RESOURCE]])
async def delete(self, id: str) -> None:
```

**Implementation**:
1. Call `self.context.service.[resource_service].delete(id)`
2. Return 204 No Content
3. Handle 404 if not found

**Files Modified**:
- `src/maasapiserver/handlers/[resource].py` (add method)

**Testing**:
- [ ] T104a: Write test for successful delete (204)
- [ ] T104b: Write test for not found (404)
- [ ] T104c: Write test for permission denied (403)

**Commands**:
```bash
make test-py -k "test_delete_[resource]"
```

---

## Phase 3: Service Layer Implementation

### T200 [P] Implement service list method

**Phase**: Service | **Story**: US1 | **Parallel**: Independent per service

**Method Signature**:
```python
async def list(self, spec: QuerySpec = None) -> Paginated[[Resource]]:
```

**Implementation**:
1. Validate `spec` (filters, pagination)
2. Call `self.repository.find(spec)`
3. Return `Paginated[Model]` with data + total count

**Files Modified**:
- `src/maasservicelayer/services/[resource].py` (implement list)

**Testing** (mock repository):
- [ ] T200a: Test list with no filters
- [ ] T200b: Test list with filters applied
- [ ] T200c: Test list pagination
- [ ] T200d: Test list with invalid spec

**Commands**:
```bash
make test-py -k "test_list" -k "[service_name]"
```

---

### T201 [P] Implement service get method

**Phase**: Service | **Story**: US1 | **Parallel**: Independent per service

**Method Signature**:
```python
async def get(self, id: str) -> [Resource]:
```

**Implementation**:
1. Validate ID
2. Call `self.repository.get(id)`
3. Raise `NotFound` if not exists
4. Return `[Resource]` model

**Files Modified**:
- `src/maasservicelayer/services/[resource].py` (implement get)

**Testing** (mock repository):
- [ ] T201a: Test get existing resource
- [ ] T201b: Test get non-existent resource (raises NotFound)
- [ ] T201c: Test get with invalid ID format

**Commands**:
```bash
make test-py -k "test_get" -k "[service_name]"
```

---

### T202 [P] Implement service create method with builders

**Phase**: Service | **Story**: US1 | **Parallel**: Independent per service

**Method Signature**:
```python
async def create(self, builder: Create[Resource]Builder) -> [Resource]:
```

**Implementation**:
1. Validate builder (call any custom validators)
2. Check business logic constraints (e.g., unique name)
3. Call `self.repository.create(builder)`
4. Return created `[Resource]` model

**Files Modified**:
- `src/maasservicelayer/services/[resource].py` (implement create)

**Testing** (mock repository):
- [ ] T202a: Test create with valid builder
- [ ] T202b: Test create with validation error
- [ ] T202c: Test create with constraint violation (e.g., duplicate)
- [ ] T202d: Test builder → repository mapping

**Commands**:
```bash
make test-py -k "test_create" -k "[service_name]"
```

---

### T203 [P] Implement service update method

**Phase**: Service | **Story**: US2 | **Parallel**: Independent per service

**Method Signature**:
```python
async def update(self, id: str, builder: Update[Resource]Builder) -> [Resource]:
```

**Implementation**:
1. Get existing resource
2. Validate builder changes
3. Call `self.repository.update(id, builder)`
4. Return updated `[Resource]` model

**Files Modified**:
- `src/maasservicelayer/services/[resource].py` (implement update)

**Testing** (mock repository):
- [ ] T203a: Test update existing resource
- [ ] T203b: Test update non-existent resource
- [ ] T203c: Test update with validation error

**Commands**:
```bash
make test-py -k "test_update" -k "[service_name]"
```

---

### T204 [P] Implement service delete method

**Phase**: Service | **Story**: US3 | **Parallel**: Independent per service

**Method Signature**:
```python
async def delete(self, id: str) -> None:
```

**Implementation**:
1. Get existing resource (or skip check for soft-delete)
2. Call `self.repository.delete(id)`
3. Return None (or return deleted resource if needed)

**Files Modified**:
- `src/maasservicelayer/services/[resource].py` (implement delete)

**Testing** (mock repository):
- [ ] T204a: Test delete existing resource
- [ ] T204b: Test delete non-existent resource

**Commands**:
```bash
make test-py -k "test_delete" -k "[service_name]"
```

---

## Phase 4: Repository Layer Implementation

### T300 [P] Add table definition

**Phase**: DB | **Story**: US1 | **Parallel**: Independent per entity

**File Modified**: `src/maasservicelayer/db/tables.py`

**Implementation**:
1. Define `[resource]_table = Table("[resource]", metadata, ...)`
2. Add columns with appropriate types (Integer, String, DateTime, etc.)
3. Add primary key: `Column("id", Integer, primary_key=True)`
4. Add constraints: `ForeignKey`, `UniqueConstraint`, `CheckConstraint`
5. Add indexes on filter columns (status, created_at, etc.)

**Constraints Naming**:
- Foreign key: `FK_[table]_[foreign_column]`
- Unique: `UK_[table]_[column]`
- Check: `CK_[table]_[name]`
- Index: `idx_[table]_[column]`

**Commands**:
```bash
make format-py
make lint-py
```

---

### T301 [P] Generate Alembic migration

**Phase**: DB | **Story**: US1 | **Parallel**: All migrations together

**Implementation**:
1. Run: `cd src/maasservicelayer && alembic revision --autogenerate -m "[description]"`
2. Review generated migration in `db/alembic/versions/[timestamp]_[description].py`
3. Verify `upgrade()` and `downgrade()` functions
4. Add explicit constraints if needed (if autogenerate missed them)

**File Created**: `src/maasservicelayer/db/alembic/versions/[timestamp]_[description].py`

**Commands**:
```bash
cd src/maasservicelayer
alembic revision --autogenerate -m "Add [resource] table"
make format-py  # Format the migration
make lint-py
```

---

### T302 [P] Test migration up/down

**Phase**: DB | **Story**: US1 | **Parallel**: All migrations

**Implementation**:
1. Run migration forward: `alembic upgrade head`
2. Verify schema matches table definition
3. Run migration backward: `alembic downgrade -1`
4. Verify tables/columns removed
5. Run forward again to verify idempotent

**Commands**:
```bash
cd src/maasservicelayer
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

---

### T303 [P] Implement repository find method

**Phase**: Repo | **Story**: US1 | **Parallel**: Independent per repository

**Method Signature**:
```python
async def find(self, spec: QuerySpec = None) -> List[[Resource]]:
```

**Implementation**:
1. Build `select()` query from table
2. Apply `spec.where_clauses` filters (if provided)
3. Apply sorting from `spec.order_by`
4. Apply pagination (skip/limit)
5. Execute query via `self.execute(query)`
6. Map rows to Pydantic models via `RowToModel`

**Example**:
```python
async def find(self, spec: QuerySpec = None) -> List[Machine]:
    query = select(machines_table)
    if spec:
        for clause in spec.where_clauses:
            query = query.where(clause.condition)
        for join in clause.joins:
            query = query.join(join)
    rows = await self.execute(query)
    return [RowToModel.row_to_model(row, Machine) for row in rows]
```

**Files Modified**:
- `src/maasservicelayer/db/repositories/[resource].py` (implement find)

**Testing** (real DB via `db_connection` fixture):
- [ ] T303a: Test find with no filters
- [ ] T303b: Test find with single filter
- [ ] T303c: Test find with multiple filters
- [ ] T303d: Test find with sorting
- [ ] T303e: Test find with pagination

**Commands**:
```bash
make test-py -k "test_find" -k "[repository_name]"
```

---

### T304 [P] Implement repository get method

**Phase**: Repo | **Story**: US1 | **Parallel**: Independent per repository

**Method Signature**:
```python
async def get(self, id: str) -> [Resource]:
```

**Implementation**:
1. Build query: `select(table).where(table.c.id == id)`
2. Execute and fetch one row
3. Raise `NotFound` if no result
4. Map row to Pydantic model

**Files Modified**:
- `src/maasservicelayer/db/repositories/[resource].py` (implement get)

**Testing** (real DB):
- [ ] T304a: Test get existing resource
- [ ] T304b: Test get non-existent resource (raises NotFound)

**Commands**:
```bash
make test-py -k "test_get" -k "[repository_name]"
```

---

### T305 [P] Implement repository create method

**Phase**: Repo | **Story**: US1 | **Parallel**: Independent per repository

**Method Signature**:
```python
async def create(self, builder: Create[Resource]Builder) -> [Resource]:
```

**Implementation**:
1. Map builder to table columns via `DomainDataMapper`
2. Build `insert()` query
3. Execute and get inserted ID
4. Fetch and return created resource

**Files Modified**:
- `src/maasservicelayer/db/repositories/[resource].py` (implement create)

**Testing** (real DB):
- [ ] T305a: Test create with all fields
- [ ] T305b: Test create with partial fields (others default)
- [ ] T305c: Test create returns new resource
- [ ] T305d: Test created_at timestamp set

**Commands**:
```bash
make test-py -k "test_create" -k "[repository_name]"
```

---

### T306 [P] Implement repository update method

**Phase**: Repo | **Story**: US2 | **Parallel**: Independent per repository

**Method Signature**:
```python
async def update(self, id: str, builder: Update[Resource]Builder) -> [Resource]:
```

**Implementation**:
1. Map builder (only non-UNSET fields) to table columns
2. Build `update()` query with WHERE id clause
3. Execute
4. Fetch and return updated resource

**Files Modified**:
- `src/maasservicelayer/db/repositories/[resource].py` (implement update)

**Testing** (real DB):
- [ ] T306a: Test update single field
- [ ] T306b: Test update multiple fields
- [ ] T306c: Test updated_at timestamp changed
- [ ] T306d: Test update non-existent raises error

**Commands**:
```bash
make test-py -k "test_update" -k "[repository_name]"
```

---

### T307 [P] Implement repository delete method

**Phase**: Repo | **Story**: US3 | **Parallel**: Independent per repository

**Method Signature**:
```python
async def delete(self, id: str) -> None:
```

**Implementation**:
1. Build `delete()` query with WHERE id clause
2. Execute
3. Raise `NotFound` if no rows deleted (optional)

**Files Modified**:
- `src/maasservicelayer/db/repositories/[resource].py` (implement delete)

**Testing** (real DB):
- [ ] T307a: Test delete existing resource
- [ ] T307b: Test delete non-existent resource
- [ ] T307c: Test resource actually removed from DB

**Commands**:
```bash
make test-py -k "test_delete" -k "[repository_name]"
```

---

### T308 [P] Implement ClauseFactory filters

**Phase**: Repo | **Story**: US1 | **Parallel**: Independent per repository

**File Modified**: `src/maasservicelayer/db/repositories/[resource].py` (add factory class)

**Implementation** (colocated in same file):
```python
class [Resource]ClauseFactory:
    @staticmethod
    def with_name(name: str) -> Clause:
        return Clause(
            condition=eq([resource]_table.c.name, name),
            joins=[]
        )
    
    @staticmethod
    def with_status(status: str) -> Clause:
        return Clause(
            condition=eq([resource]_table.c.status, status.value),
            joins=[]
        )
```

**Testing**:
- [ ] T308a: Test each clause factory compiles correctly
- [ ] T308b: Test clauses combine with AND/OR
- [ ] T308c: Test clause negation

**Commands**:
```bash
make test-py -k "test_clause_factory"
```

---

## Phase 5: Integration & Functional Tests

### T400 [P] Write end-to-end test for User Story 1

**Phase**: Integration | **Story**: US1

**File Created**: `src/tests/functional/test_[feature]_us1.py`

**Implementation**:
1. Set up test database with fixtures
2. Call API endpoint (full stack)
3. Verify response status + data
4. Verify data in database
5. Clean up (transaction rollback or DELETE)

**Example**:
```python
async def test_create_and_list_machines(self, db_connection):
    # Call API to create machine
    response = await client.post("/api/v3/machines", json={"name": "m1"})
    assert response.status_code == 201
    
    # List machines
    response = await client.get("/api/v3/machines")
    assert len(response.json()["data"]) == 1
    
    # Verify in DB
    repo = MachineRepository(db_connection)
    machines = await repo.find()
    assert machines[0].name == "m1"
```

**Testing**:
- [ ] T400a: Test full flow (API → Service → Repo → DB)
- [ ] T400b: Test acceptance criteria met
- [ ] T400c: Test error handling in full stack

**Commands**:
```bash
make test-py -k "test_.*us1" -k "functional"
```

---

### T401 [P] Write end-to-end test for User Story 2

**Phase**: Integration | **Story**: US2

**File Created/Modified**: `src/tests/functional/test_[feature]_us2.py`

**Similar to T400**: Test US2 acceptance criteria end-to-end

**Commands**:
```bash
make test-py -k "test_.*us2" -k "functional"
```

---

### T402 [P] Write end-to-end test for User Story 3

**Phase**: Integration | **Story**: US3

**Similar to T400**: Test US3 acceptance criteria end-to-end

**Commands**:
```bash
make test-py -k "test_.*us3" -k "functional"
```

---

## Phase 6: Quality & Documentation

### T500 Verify test coverage >80%

**Implementation**:
1. Run: `make test-py --cov=src/maasservicelayer --cov=src/maasapiserver`
2. Verify coverage >80% for modified files
3. Add tests for uncovered branches if needed

**Commands**:
```bash
make test-py --cov src/maasservicelayer --cov src/maasapiserver --cov-report=term-missing
```

---

### T501 Verify linting passes

**Implementation**:
1. Run: `make lint-py`
2. Fix any issues (Ruff formatting, type hints)
3. Run: `make format-py` if auto-fixable

**Commands**:
```bash
make lint-py
make format-py
make lint-py  # Verify fixed
```

---

### T502 Verify OpenAPI spec

**Implementation**:
1. Run: `make lint-oapi`
2. Verify endpoints documented in OpenAPI schema
3. Verify request/response models in spec

**Commands**:
```bash
make lint-oapi
```

---

### T503 Create/update documentation

**Implementation**:
1. Add `quickstart.md` to spec directory (how to use feature)
2. Update API docs (if customer-facing)
3. Update architecture docs if significant changes

**Files**:
- `specs/[###-feature-name]/quickstart.md`
- `src/maasservicelayer/README.md` (if architectural changes)

---

## Summary

**Total Tasks**: ~60 tasks across 6 phases  
**Estimated Duration**: ~4-6 weeks depending on feature complexity  
**Parallel Tasks**: ~15-20 tasks can run simultaneously (different handlers/services/repos)  
**Blocking Tasks**: T001, T002, T003, T004, T005 (setup must complete first)

---

**Next Step**: Developers claim tasks, create feature branches (`[###-task-id]`), and implement per task description.
