# Implementation Plan: Custom Boot Assets

**Branch**: `6688-custom-boot-assets` | **Date**: 2025-07-18 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `/specs/001-custom-boot-assets/spec.md`

**Note**: This plan reflects the simplified endpoint strategy: reuse existing v3 `/custom_images` endpoints for listing/get/delete; only add new upload endpoints for bootloader tarballs and kernel+initrd pairs.

## Summary

Implement custom bootloaders and kernel+initrd pairs as first-class boot assets within MAAS. Assets are uploaded via two new v3 API endpoints, reuse the existing `BootResource → BootResourceSet → BootResourceFile` storage model with versioning, and are distributed to Rack Controllers via the existing Temporal sync workflow. The existing `/custom_images` endpoints handle listing, retrieval, and deletion (with a new filter parameter for asset type). Deploy-time selection is via the v2 deploy endpoint with DHCP config update for custom bootloaders.

## Technical Context

**Language/Version**: Python 3.14  
**Primary Dependencies**: FastAPI, SQLAlchemy Core, Pydantic (v3 API) | Django, Twisted (legacy v2 deploy endpoint)  
**Database**: PostgreSQL via Alembic migrations  
**Testing**: pytest + asyncio (Python)  
**Target Component**: v3 API (maasapiserver + maasservicelayer) + Legacy (maasserver deploy endpoint + DHCP)  
**Architecture Pattern**: 3-tier (API → Service → Repository) for v3 API  
**Scale/Scope**: 2 new upload API endpoints, 1 filter parameter addition to existing endpoint, 2 service methods (upload), 3 new repository methods, 1 Alembic migration, 1 v2 deploy endpoint extension, DHCP template update

## Constitution Check

*Gate: Verify compliance before Phase 1 research.*

- ✅ Feature aligns with 3-tier v3 API architecture (new upload endpoints in v3; v2 exception for deploy endpoint documented in spec)
- ✅ Database changes planned as Alembic migrations (partial unique indexes for asset identity)
- ✅ Testing strategy covers repository + service + API tiers
- ✅ Conventional Commits scope assigned: `api`, `service`, `repo`, `db`, `legacy`
- ✅ Ruff formatting: 79 chars, double quotes
- ✅ No ORM in v3 API repositories (SQLAlchemy Core only)

---

## Project Structure

### Documentation (this feature)

```text
specs/001-custom-boot-assets/
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
src/
├── maasapiserver/v3/api/public/handlers/
│   └── boot_resources.py          # Extend CustomImagesHandler (add upload endpoints + filter param)
├── maasservicelayer/
│   ├── services/bootresources.py  # Add upload_bootloader, upload_kernel_pair, resolve methods
│   ├── db/
│   │   ├── repositories/bootresources.py  # Extend BootResourceClauseFactory + add query methods
│   │   ├── tables.py                      # Add partial unique index definitions
│   │   └── alembic/versions/             # Migration for unique constraints
│   └── models/boot_resources.py          # Domain models (if new Pydantic models needed)
├── maasserver/
│   ├── api/machines.py            # Add custom_bootloader/custom_kernel params to deploy
│   └── dhcp.py                    # Add bootloader_path to host declarations
└── tests/
    ├── maasservicelayer/
    │   ├── db/repositories/test_bootresources.py  # New clause/method tests
    │   └── services/test_bootresources.py         # Upload/resolve logic tests
    ├── maasapiserver/v3/api/public/handlers/
    │   └── test_boot_resources.py                 # Upload endpoint tests
    └── maasserver/
        └── test_dhcp.py                           # DHCP bootloader path tests
```

---

## Implementation Phases

> **Note**: Task IDs in this document are superseded by `tasks.md` (authoritative). Use `tasks.md` for all actionable task tracking, status updates, and dependency management.

### Phase 0: Research & Discovery

**Goal**: Answer open questions, finalize architecture decisions

**Deliverables**: `research.md` (complete)

**Key Decisions** (resolved):
1. ✅ Extend existing `BootResource` data model — no new tables
2. ✅ Use existing `get_next_version_name()` for YYYYMMDD[.N] versioning
3. ✅ Reuse existing `/custom_images` endpoints for list/get/delete — no new handlers for these
4. ✅ Add filter parameter (`type=bootloader|kernel|image`) to existing list endpoint
5. ✅ Deploy-time selection in v2 API (no v3 deploy endpoint exists)
6. ✅ DHCP option 67 per-host override via existing ConfigureDHCPWorkflow
7. ✅ Per-version deletion NOT supported — deletion at BootResource level only

---

### Phase 1: API Layer Design

**Goal**: Define new upload endpoints and filter parameter extension

**Deliverables**: `contracts/api.md`

**Tasks**: See `tasks.md` for actionable task tracking.

**Key Design Decisions (implemented)**:
- Upload endpoints use `application/octet-stream` + `x-*` request headers (not multipart/form-data); handler streams body to disk, then calls service
- Kernel upload split into two endpoints: `POST /boot_assets/kernels` (kernel binary) → `POST /boot_assets/kernels/{resource_id}/initrd` (append initrd)
- `x-primary-file` header on bootloader upload names the EFI binary for DHCP option 67
- `KernelsHandler` is a separate handler class serving `GET /kernels` and `GET /kernels/{id}`; `CustomImagesHandler` handles all upload endpoints and `GET /custom_images`
- Common streaming/sync helpers (`_stream_to_disk`, `_trigger_sync_workflow`, `_build_boot_asset_upload_response`) extracted as private handler methods

**Quality Gates**:
- All endpoints have permission decorators (Admin for uploads)
- Pydantic models pass strict validation
- Tests use `mocked_api_client` fixtures
- nginx template (`src/maasserver/templates/http/regiond.nginx.conf.template`) includes `client_max_body_size 200G` for `location /MAAS/a/v3/boot_assets` (covers both `/bootloaders` and `/kernels` sub-paths via prefix matching)

**Duration**: ~2 days

---

### Phase 2: Service Layer Implementation

**Goal**: Implement upload business logic and deploy-time resolution

**Deliverables**: `contracts/services.md`

**Tasks**: See `tasks.md` for actionable task tracking.

**Key Design Decisions (implemented)**:
- `BootResourceFilesService` added as a constructor dependency of `BootResourceService` (required for upload methods to create `BootResourceFile` records)
- Upload logic fully moved to service layer: `upload_custom_image`, `upload_bootloader`, `upload_kernel`, `upload_kernel_initrd` are all service methods
- Handler is responsible only for streaming bytes to disk and triggering sync; service creates all DB records
- `validate_boot_asset_name()` and `validate_architecture()` extracted as module-level async functions in `requests/boot_resources.py` and shared between `BootResourceCreateRequest` and new upload handlers
- Bootloader DHCP path uses `__` as separator: `bootloaders/{name_with__}/{arch_with__}/{version}/{primary_file}`

**Quality Gates**:
- Services use existing builders
- >80% test coverage for business logic
- No database calls in services (use repositories)
- Async/await patterns throughout

**Duration**: ~3 days

---

### Phase 3: Repository Layer & Queries

**Goal**: Extend existing repository with clause factory methods and new queries

**Deliverables**: `contracts/repos.md`

**Tasks**: See `tasks.md` for actionable task tracking.

**Quality Gates**:
- All queries use SQLAlchemy Core (no ORM)
- Repositories return Pydantic models
- `QuerySpec` used for all filtering
- Repository tests inherit from `RepositoryCommonTests`

**Duration**: ~2 days

---

### Phase 4: Database Schema & Migrations

**Goal**: Add partial unique indexes for asset identity enforcement

**Deliverables**: `data-model.md`, Alembic migration

**Tasks**: See `tasks.md` for actionable task tracking.

**Quality Gates**:
- Migration is reversible
- Constraints named per convention
- Indexes on filter columns

**Duration**: ~1 day

---

### Phase 5: v2 Deploy Endpoint & DHCP Integration

**Goal**: Implement deploy-time asset selection and DHCP bootloader path override

**Tasks**: See `tasks.md` for actionable task tracking.

**Quality Gates**:
- v2 API backward compatible (new params are optional)
- DHCP update triggered before machine power-on
- Template renders correct filename for custom bootloader

**Duration**: ~2 days

---

### Phase 6: Integration Testing & Functional Tests

**Goal**: Test full stack, cross-module flows

**Deliverables**: `quickstart.md`, functional tests

**Tasks**: See `tasks.md` for actionable task tracking.

**Quality Gates**:
- All user stories tested end-to-end
- >80% overall code coverage
- All acceptance criteria from spec.md verified

**Duration**: ~2 days

---

## Testing Strategy

### Tier 1: Repository Tests (Unit — Real DB)
- Use `db_connection` fixture
- Test new clause factory methods and find_or_create logic
- Base class: `RepositoryCommonTests`

### Tier 2: Service Tests (Unit — Mocked Repos)
- Mock repositories
- Test upload logic (SHA256 validation, tarball extraction, pair enforcement)
- Test resolution logic (latest version, architecture matching)

### Tier 3: API Tests (Integration — Mocked Services)
- Mock services
- Test upload endpoints (multipart, chunked)
- Test filter parameter on existing list endpoint
- Test permission checks

### Tier 4: Functional Tests (End-to-End)
- Full stack through upload → list → deploy → DHCP

---

## Dependencies & Risks

### Key Design Decision: Reuse Existing Endpoints

The existing `CustomImagesHandler` in `src/maasapiserver/v3/api/public/handlers/boot_resources.py` already provides:
- `list_custom_images`: Lists all `rtype=UPLOADED` resources (includes bootloaders, kernels, and images)
- `get_custom_image_by_id`: Get a specific uploaded resource by ID
- `delete_custom_image_by_id`: Delete a specific uploaded resource (all versions)
- `bulk_delete_custom_images`: Bulk delete uploaded resources

These endpoints work unchanged for custom boot assets because bootloaders and kernel pairs share `rtype=UPLOADED`. The only addition needed is a **filter parameter** (`type=bootloader|kernel|image`) on the list endpoint to allow callers to retrieve only one category.

**Per-version deletion is NOT supported** — consistent with how custom images work today. Deletion removes the entire `BootResource` and all its versions.

### Risks

1. **Legacy v2 compatibility**: Deploy endpoint changes must not break existing clients
   - Mitigation: New params are optional; default behavior unchanged
2. **DHCP timing race**: Machine might PXE before DHCP config propagates
   - Mitigation: Temporal workflow fires before power-on; natural timing margin
3. **Large file uploads (initrd ~500MB)**: Must handle chunked streaming
   - Mitigation: Reuse existing `CustomImagesHandler` chunking pattern

---

## Success Criteria

- ✅ Bootloader tarball upload creates versioned asset (viewable via existing list endpoint)
- ✅ Kernel+initrd pair upload enforces completeness
- ✅ Filter parameter on list endpoint correctly discriminates asset types
- ✅ Existing delete endpoints work unchanged for custom boot assets
- ✅ Deploy-time selection resolves to latest version
- ✅ DHCP option 67 set per-host for custom bootloader
- ✅ >80% code coverage
- ✅ All tests pass (`make test` succeeds)
- ✅ Linting passes (`make lint` succeeds)
