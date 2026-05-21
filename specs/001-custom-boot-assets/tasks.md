# Tasks: Custom Boot Assets (SPIKE)

**Input**: Design documents from `/specs/001-custom-boot-assets/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/  
**Branch**: `6688-custom-boot-assets`  
**Scope**: SPIKE — No usage tracking FK, no GC, unconditional deletion  
**Updated**: 2025-07-18 — Simplified scope: no new list/delete endpoints (reuse `/custom_images` with filter), only 2 new upload endpoints, no per-version deletion

**Organization**: Tasks grouped by implementation phase + user story, enabling parallel work

## Format & Conventions

- **[ID]**: Unique task identifier (T001, T002, T003...)
- **[P]**: Can run in parallel (independent tasks, different files)
- **[US#]**: Which user story the task serves
- **Exact paths**: File paths fully specified for implementation
- **No story label**: Setup/Foundational/Polish phase tasks

---

## Phase 1: Setup & Database Schema

**Purpose**: Database migration and partial unique indexes required by all user stories.

- [ ] T001 Add partial unique index definitions to `src/maasservicelayer/db/tables.py` for bootloader identity (`name + architecture WHERE rtype=2 AND bootloader_type IS NOT NULL`) and kernel identity (`name + architecture + kflavor WHERE rtype=2 AND bootloader_type IS NULL AND kflavor IS NOT NULL`)
- [ ] T002 Generate Alembic migration in `src/maasservicelayer/db/alembic/versions/` adding the two partial unique indexes (`UK_bootresource_bootloader_identity`, `UK_bootresource_kernel_identity`) and the lookup index `idx_bootresource_rtype_name_arch`
- [ ] T003 [P] Verify migration up/down reversibility with `alembic upgrade head && alembic downgrade -1 && alembic upgrade head`
- [x] T046 [P] Add `location /MAAS/a/v3/boot_assets { client_max_body_size 200G; proxy_pass http://apiserver; }` block to `src/maasserver/templates/http/regiond.nginx.conf.template` — permits large tarball and kernel/initrd uploads through nginx for both `/boot_assets/bootloaders` and `/boot_assets/kernels` via prefix matching (**done**)

---

## Phase 2: Foundational — Repository Layer

**Purpose**: Repository methods and clause factory extensions that all user stories depend on. Must complete before user story phases.

- [ ] T004 [P] Add `with_uploaded_type()` clause to `BootResourceClauseFactory` in `src/maasservicelayer/db/repositories/bootresources.py`
- [ ] T005 [P] Add `with_asset_type_bootloader()` clause to `BootResourceClauseFactory` in `src/maasservicelayer/db/repositories/bootresources.py`
- [ ] T006 [P] Add `with_asset_type_kernel()` clause to `BootResourceClauseFactory` in `src/maasservicelayer/db/repositories/bootresources.py`
- [ ] T007 [P] Add `with_asset_type_image()` clause to `BootResourceClauseFactory` in `src/maasservicelayer/db/repositories/bootresources.py`
- [ ] T008 [P] Add `with_kflavor(kflavor)` clause to `BootResourceClauseFactory` in `src/maasservicelayer/db/repositories/bootresources.py`
- [ ] T009 [P] Add `with_bootloader_identity(name, architecture)` clause to `BootResourceClauseFactory` in `src/maasservicelayer/db/repositories/bootresources.py`
- [ ] T010 [P] Add `with_kernel_identity(name, architecture, kflavor)` clause to `BootResourceClauseFactory` in `src/maasservicelayer/db/repositories/bootresources.py`
- [ ] T011 Implement `find_or_create_bootloader(name, architecture)` method on `BootResourcesRepository` in `src/maasservicelayer/db/repositories/bootresources.py`
- [ ] T012 Implement `find_or_create_kernel(name, architecture, kflavor)` method on `BootResourcesRepository` in `src/maasservicelayer/db/repositories/bootresources.py`
- [ ] T013 Implement `get_latest_version(resource_id)` method on `BootResourcesRepository` in `src/maasservicelayer/db/repositories/bootresources.py` (ORDER BY id DESC, LIMIT 1 on BootResourceSetTable)
- [ ] T014 Implement `get_bootloader_for_architecture(bootloader_name, architecture)` method on `BootResourcesRepository` in `src/maasservicelayer/db/repositories/bootresources.py`
- [ ] T015 Implement `get_bootloader_file_for_set(resource_set_id)` method on `BootResourcesRepository` in `src/maasservicelayer/db/repositories/bootresources.py` (JOIN BootResourceFile + BootResourceSet)

---

## Phase 3: User Story 1 — Upload Custom Bootloader Tarball (P1)

**Goal**: Infrastructure operator can upload a bootloader tarball via `POST /api/v3/boot_assets/bootloaders`, system extracts contents, creates versioned asset, and asset is visible via existing `/custom_images` endpoint.

**Independent Test**: Upload a bootloader tarball → verify 201 response with version → verify asset appears in `GET /custom_images?type=bootloader` → verify tarball extraction to isolated directory.

- [ ] T016 [P] [US1] Define `BootAssetFileInfo` and `BootAssetUploadResponse` Pydantic models in `src/maasapiserver/v3/api/public/models/responses/boot_resources.py`
- [ ] T017 [US1] Implement `upload_bootloader()` service method on `BootResourceService` in `src/maasservicelayer/services/bootresources.py` (validate arch format, find_or_create resource, generate version, stream tarball, verify SHA256, extract with path traversal checks, create BootResourceFile entries)
- [ ] T018 [US1] Add `upload_bootloader` handler method to `CustomImagesHandler` in `src/maasapiserver/v3/api/public/handlers/boot_resources.py` — route: `POST /boot_assets/bootloaders`, permission: `CAN_EDIT_BOOT_ENTITIES`, multipart/form-data (name, architecture, sha256, file)
- [ ] T019 [US1] Write repository tests for `find_or_create_bootloader()`, `get_latest_version()`, and `get_bootloader_file_for_set()` in `tests/maasservicelayer/db/repositories/test_bootresources.py` — cover: `find_or_create_bootloader()` identity uniqueness, `get_latest_version()` ordering, `get_bootloader_file_for_set()` with a valid set containing a file (verify JOIN correctness), set with no file, and set not found. Test class must inherit from `RepositoryCommonTests`.
- [ ] T020 [P] [US1] Write service unit tests for `upload_bootloader()` (mock repos) in `tests/maasservicelayer/services/test_bootresources.py` — cover: valid upload, SHA256 mismatch, path traversal rejection, duplicate identity versioning. Test class must inherit from `ServiceCommonTests`; use `mocked_api_client` fixture pattern consistent with existing service tests.
- [ ] T021 [P] [US1] Write API integration tests for `POST /boot_assets/bootloaders` in `tests/maasapiserver/v3/api/public/handlers/test_boot_resources.py` — cover: successful upload (201), invalid tarball (400), permission denied (403)

---

## Phase 4: User Story 2 — Upload Custom Kernel+Initrd Pair (P1)

**Goal**: Infrastructure operator can upload a kernel binary and initrd file as a paired asset via `POST /api/v3/boot_assets/kernels`. Partial uploads are rejected.

**Independent Test**: Upload kernel+initrd pair → verify 201 response → verify asset appears in `GET /custom_images?type=kernel`. Upload only kernel (no initrd) → verify 400 rejection.

- [ ] T022 [US2] Implement `upload_kernel_pair()` service method on `BootResourceService` in `src/maasservicelayer/services/bootresources.py` (validate both files present, validate arch format, find_or_create resource, generate version, stream+verify kernel SHA256, stream+verify initrd SHA256, create BootResourceFile entries with filetypes `boot-kernel` and `boot-initrd`)
- [ ] T023 [US2] Add `upload_kernel_pair` handler method to `CustomImagesHandler` in `src/maasapiserver/v3/api/public/handlers/boot_resources.py` — route: `POST /boot_assets/kernels`, permission: `CAN_EDIT_BOOT_ENTITIES`, multipart/form-data (name, architecture, kflavor, kernel_sha256, initrd_sha256, kernel, initrd)
- [ ] T024 [US2] Write repository tests for `find_or_create_kernel()` in `tests/maasservicelayer/db/repositories/test_bootresources.py`. Test class must inherit from `RepositoryCommonTests`.
- [ ] T025 [P] [US2] Write service unit tests for `upload_kernel_pair()` (mock repos) in `tests/maasservicelayer/services/test_bootresources.py` — cover: valid pair upload, missing initrd (400), missing kernel (400), SHA256 mismatch. Test class must inherit from `ServiceCommonTests`; use `mocked_api_client` fixture pattern consistent with existing service tests.
- [ ] T026 [P] [US2] Write API integration tests for `POST /boot_assets/kernels` in `tests/maasapiserver/v3/api/public/handlers/test_boot_resources.py` — cover: successful pair upload (201), partial upload rejection (400), permission denied (403)

---

## Phase 5: User Story 3 — Organize & Filter Assets by Type (P2)

**Goal**: Existing `/custom_images` list endpoint gains a `type` query parameter to filter by `bootloader`, `kernel`, or `image`. Assets carry correct metadata (name, architecture, kflavor).

**Independent Test**: Upload a bootloader, a kernel pair, and verify filtering: `?type=bootloader` shows only bootloaders, `?type=kernel` shows only kernels, `?type=image` excludes both, no filter shows all.

- [ ] T027 [US3] Add `type` (enum: `bootloader|kernel|image`), `name` (string), `architecture` (string), and `kflavor` (string) query filter parameters (all optional) to `list_custom_images` handler in `src/maasapiserver/v3/api/public/handlers/boot_resources.py` — build `QuerySpec` with appropriate clauses from `BootResourceClauseFactory` for each supplied filter
- [ ] T028 [P] [US3] Write API integration tests for filter parameters on `GET /custom_images` in `tests/maasapiserver/v3/api/public/handlers/test_boot_resources.py` — cover: each `type` value returns correct subset, `name` filter returns only matching name, `architecture` filter returns only matching architecture, `kflavor` filter returns only matching kflavor, combined filters narrow results correctly, no filter returns all, invalid `type` value returns 422

---

## Phase 6: User Story 4 — Explicit Asset Selection at Deploy Time (P2)

**Goal**: Users with deployment permissions can select custom boot assets via v2 deploy endpoint parameters. DHCP is updated for custom bootloaders.

**Independent Test**: Deploy a machine with `custom_bootloader=ubuntu/jammy` → verify bootloader resolves to latest version → verify DHCP config updated with per-host `filename` directive. Deploy without parameters → verify default Simplestreams asset used.

- [ ] T029 [US4] Implement `resolve_boot_asset_for_deployment(name, architecture, kflavor, asset_type)` service method on `BootResourceService` in `src/maasservicelayer/services/bootresources.py`
- [ ] T030 [US4] Implement `get_bootloader_path_for_machine(machine_id, bootloader_name, architecture)` service method on `BootResourceService` in `src/maasservicelayer/services/bootresources.py` (resolve latest version → compute Rack-relative serving path)
- [ ] T031 [US4] Implement `assign_bootloader_and_trigger_dhcp(machine_id, bootloader_name, architecture)` service method on `BootResourceService` in `src/maasservicelayer/services/bootresources.py` (resolve asset → trigger `ConfigureDHCPWorkflow`)
- [ ] T032 [US4] Add `custom_bootloader`, `custom_kernel`, `custom_kernel_kflavor` parameters to v2 deploy endpoint in `src/maasserver/api/machines.py` — resolve via service layer, trigger DHCP update if bootloader set; validate that the supplied `custom_bootloader` name/architecture matches the target machine's architecture and return HTTP 400 on mismatch
- [ ] T033 [US4] Add `bootloader_path` field to DHCP host declarations in `src/maasserver/dhcp.py` (`make_hosts_for_subnets()`) — include only when machine has custom bootloader assigned
- [ ] T034 [US4] Update DHCP template to render per-host `filename "{bootloader_path}";` directive when `bootloader_path` is present in host dict
- [ ] T035 [P] [US4] Write service unit tests for `resolve_boot_asset_for_deployment()` and `assign_bootloader_and_trigger_dhcp()` in `tests/maasservicelayer/services/test_bootresources.py` — cover: found resolution, not-found error, DHCP workflow trigger. Test class must inherit from `ServiceCommonTests`; use `mocked_api_client` fixture pattern consistent with existing service tests.
- [ ] T036 [P] [US4] Write tests for DHCP bootloader path override in `tests/maasserver/test_dhcp.py` — cover: host with custom bootloader has `filename` directive, host without does not
- [ ] T037 [P] [US4] Write integration tests for v2 deploy endpoint with custom asset params in `tests/maasserver/api/test_machines.py` — cover: valid deploy with custom bootloader, valid deploy with custom kernel, missing asset (400), no permissions (403), default fallback when no params, architecture mismatch between supplied `custom_bootloader` and target machine returns HTTP 400

---

## Phase 7: User Story 5 — Rack Controller Caching Proxy (P3)

**Goal**: Custom boot assets are served through the existing Rack Controller caching proxy. No new proxy mechanism needed — verify integration with existing infrastructure.

**Independent Test**: Request a custom asset from a Rack Controller → verify it fetches from Region on first access → verify cache hit on second access.

- [ ] T038 [US5] Verify custom boot assets (`rtype=UPLOADED`) are included in existing Temporal sync workflow scope in `src/maastemporalworker/workflow/bootresource.py` — add filter inclusion if needed
- [ ] T039 [US5] Write integration test verifying custom boot assets sync via existing `SYNC_ALL_LOCAL_BOOTRESOURCES_WORKFLOW_NAME` workflow in `tests/maastemporalworker/workflow/test_bootresource.py`
- [ ] T045 [P] [US5] Write integration test verifying Rack Controller cache hit/miss for custom boot assets in `tests/maastemporalworker/` or `tests/maasserver/` — first request must fetch from Region Controller (cache miss), subsequent requests must be served from local cache (cache hit); mock or use a real Rack Controller in test environment

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Final validation, lint, formatting, documentation updates.

- [ ] T040 [P] Run full lint and formatting pass: `make format-py && make lint-py && make lint-oapi` (the `make lint-oapi` step validates the generated OpenAPI spec against the schema; if T042 manual inspection is done separately, `make lint-oapi` must still be run as a scripted step)
- [ ] T041 [P] Run full test suite: `make test-py` — verify no regressions
- [ ] T042 [P] Verify OpenAPI spec generation includes new upload endpoints: check `openapi.yaml` reflects `/boot_assets/bootloaders` and `/boot_assets/kernels`
- [ ] T043 Update `specs/001-custom-boot-assets/quickstart.md` if any endpoint signatures changed during implementation
- [ ] T044 Research the current Simplestreams bootloader index format (`com.ubuntu.maas:candidate:1:bootloader-download.json`), draft a proposal for a new companion index file format that supports multiple bootloader entries per architecture (backward-compatible — existing single-bootloader-per-arch index must remain unchanged), and document the proposal as a spec deliverable in `specs/001-custom-boot-assets/` (addresses FR-7; see also External Dependencies table in spec.md)

---

## Dependency Graph

```
Phase 1 (DB Schema: T001-T003)
    │
    ▼
Phase 2 (Repository: T004-T015)
    │
    ├──────────────────────┬──────────────────────┐
    ▼                      ▼                      ▼
Phase 3 (US1: T016-T021) Phase 4 (US2: T022-T026) Phase 5 (US3: T027-T028)
    │                      │                      │
    └──────────────────────┴──────────────────────┘
                           │
                           ▼
                    Phase 6 (US4: T029-T037)
                           │
                           ▼
                    Phase 7 (US5: T038-T039, T045)
                           │
                           ▼
                    Phase 8 (Polish: T040-T044)
```

**Key dependencies**:
- T001-T003 → T004-T015: Repository methods depend on DB indexes existing
- T011-T015 → T017, T022: Upload services call repository find_or_create
- T016-T026 → T029-T037: Deploy-time selection depends on uploaded assets existing
- Phases 3, 4, 5 are **parallelizable** (independent user stories, different files)

---

## Parallel Execution Examples

### Maximum parallelism within Phase 2 (Repository):
T004, T005, T006, T007, T008, T009, T010 can all run in parallel (independent clause methods).

### Maximum parallelism across Phases 3-5 (User Stories):
- Worker A: Phase 3 (US1 — bootloader upload)
- Worker B: Phase 4 (US2 — kernel pair upload)
- Worker C: Phase 5 (US3 — type filter on list endpoint)

### Within Phase 6 (US4):
T035, T036, T037 (test tasks) can run in parallel after T029-T034 complete.

---

## Implementation Strategy

1. **MVP (Phase 1-3)**: Database schema + repository layer + bootloader upload endpoint. Delivers US1 independently testable.
2. **Core complete (add Phase 4-5)**: Kernel pair upload + type filter. All upload/listing functionality done.
3. **Deploy integration (Phase 6)**: v2 deploy endpoint + DHCP integration. Full deploy-time selection.
4. **Sync verification (Phase 7)**: Confirm existing Temporal workflow includes custom assets.
5. **Ship (Phase 8)**: Lint, test, documentation pass.

**Total tasks**: 46  
**Parallelizable tasks**: 24 (marked [P])  
**Critical path**: T001 → T002 → T011 → T017 → T018 → T029 → T032 → T040
