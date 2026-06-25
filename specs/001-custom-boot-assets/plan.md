# Implementation Plan: Custom Boot Assets

**Branch**: `6688-custom-boot-assets` | **Date**: 2025-07-21 | **Spec**: `specs/001-custom-boot-assets/spec.md`

**Input**: Feature specification from `specs/001-custom-boot-assets/spec.md`

**Implementation status**: The core implementation was completed in commit `952bf7491b` (`feat(api,service,repo,db): implement custom boot assets`). This plan documents what **remains to be done** based on the reviewed spec and contracts (updated in commits `aa2f65bfe2` and `5772f20b06`).

---

## Summary

Custom bootloaders and kernels as first-class boot assets within MAAS — uploaded by admins via v3 API, versioned using the existing `BootResource → BootResourceSet → BootResourceFile` model, synchronized across regions via the existing Temporal workflow, cached by Rack Controllers via the existing proxy infrastructure, and selectable at machine deploy time via the v2 API. DHCP is updated per-host when a custom bootloader is assigned. Garbage collection and version-usage tracking are deferred to a future iteration (spike scope).

**Research**: `specs/001-custom-boot-assets/research.md`
**Data model**: `specs/001-custom-boot-assets/data-model.md`
**API contracts**: `specs/001-custom-boot-assets/contracts/api.md`, `contracts/services.md`

---

## Technical Context

**Language/Version**: Python 3.14 (v3 API + service layer), Django/Twisted (legacy v2 layer)

**Primary Dependencies**: FastAPI (v3 API), SQLAlchemy Core (repositories), Pydantic (models), Temporal (workflow integration), Django (v2 deploy endpoint)

**Storage**: PostgreSQL — existing `maasbootresource`, `maasbootresourceset`, `maasbootresourcefile`, `maasbootresourcefilesync` tables; two new partial unique indexes added in Alembic migration `0022_add_unique_constraints_for_custom_boot_assets`

**Testing**: pytest + pytest-asyncio; repository tests use real DB (`db_connection` fixture); service tests mock repositories; API tests mock services

**Target Platform**: Linux server (MAAS region controller)

**Project Type**: Web service feature addition — new upload endpoints, extended list/filter endpoints, DHCP config enhancement, v2 deploy param extension

**Performance Goals**: Uploads stream at network speed (no buffering beyond chunk size = 4 MB); DHCP config regeneration time unchanged (incremental OMAPI update path)

**Constraints**: Initrd files up to several hundred MB; nginx must allow 200 GB body size at `/MAAS/a/v3/boot_assets` (already set); line length 79 chars, double quotes, Pyright strict

**Scale/Scope**: SPIKE — foundational implementation only; GC and usage-tracking deferred

---

## Constitution Check

*Verified against `constitution.md`. Status: PASS.*

| Gate | Status | Notes |
|------|--------|-------|
| 3-tier v3 architecture (API → Service → Repository) | ✅ PASS | All new endpoints follow FastAPI handler → `BootResourceService` → `BootResourcesRepository` pattern |
| SQLAlchemy Core (no ORM) in repositories | ✅ PASS | All repository methods use `select()`, `insert()`, `update()` with `ClauseFactory` |
| Pydantic builders for create/update | ✅ PASS | `CreateBootResourceBuilder`, `CreateBootResourceSetBuilder`, `CreateBootResourceFileBuilder` reused |
| Async/await in v3 API | ✅ PASS | All handlers are `async def` |
| Twisted deferreds in legacy (v2 deploy endpoint) | ✅ PASS | `machines.py` uses existing Django/Twisted patterns |
| Alembic migration for schema changes | ✅ PASS | Migration `0022` adds two partial unique indexes |
| Testing pyramid (repo + service + API tests) | ✅ PASS | All three tiers have test files; remaining gaps noted in work items below |
| Conventional commits with scopes | ✅ PASS | Required for all remaining commits |
| Boundary rules (API imports only service layer) | ✅ PASS | No cross-boundary imports added |

---

## Project Structure

### Documentation (this feature)

```text
specs/001-custom-boot-assets/
├── plan.md              # This file
├── research.md          # R1–R13: design decisions (complete)
├── data-model.md        # Entity model and schema notes (complete)
├── quickstart.md        # Endpoint quick reference (complete, may need updates)
├── contracts/
│   ├── api.md           # API endpoint contracts (reviewed 2025-07-21)
│   ├── services.md      # Service method contracts (reviewed 2025-07-21)
│   └── repos.md         # Repository method contracts (complete)
└── tasks.md             # Task list (updated alongside this plan)
```

### Source Code (affected files)

```text
src/
├── maasapiserver/v3/api/public/
│   ├── handlers/boot_resources.py         # Upload + list/get handlers
│   └── models/
│       ├── requests/boot_resources.py     # Request models
│       └── responses/boot_resources.py    # ← INCOMPLETE: needs discriminated union
│
├── maasservicelayer/
│   ├── services/bootresources.py          # Upload, resolve, DHCP path methods
│   ├── db/repositories/bootresources.py   # find_or_create, get_latest_version, etc.
│   ├── db/tables.py                       # Table definitions (no changes needed)
│   └── db/alembic/versions/
│       └── 0022_add_unique_constraints_for_custom_boot_assets.py
│
├── maasserver/
│   ├── api/machines.py                    # v2 deploy endpoint (custom_bootloader/kernel params)
│   ├── dhcp.py                            # make_hosts_for_subnets (bootloader_path in host dict)
│   └── templates/dhcp/dhcpd.conf.template # ← INCOMPLETE: filename directive missing
│
└── maastemporalworker/workflow/bootresource.py  # UPLOADED assets included in sync

tests/
├── maasapiserver/v3/api/public/handlers/test_boot_resources.py
├── maasapiserver/v3/api/public/models/requests/test_boot_resources.py
├── maasservicelayer/db/repositories/test_bootresources.py
├── maasservicelayer/services/test_bootresources.py
├── maasserver/api/tests/test_machine.py
├── maasserver/tests/test_dhcp.py
└── maastemporalworker/workflow/test_bootresource.py
```

---

## Implementation State Assessment

### ✅ COMPLETE — Core implementation done

| Area | What's done |
|------|------------|
| **DB schema** | Migration `0022`: two partial unique indexes for bootloader/kernel identity |
| **nginx config** | `client_max_body_size 200G` at `/MAAS/a/v3/boot_assets` |
| **Repository clauses** | `with_uploaded_type`, `with_asset_type_bootloader`, `with_asset_type_kernel`, `with_asset_type_image`, `with_kflavor`, `with_bootloader_identity`, `with_kernel_identity`, `with_name`, `with_architecture` |
| **Repository methods** | `find_or_create_bootloader`, `find_or_create_kernel`, `get_latest_version`, `get_bootloader_file_for_set` |
| **Upload endpoints** | `POST /api/v3/boot_assets/bootloaders` (tarball, streaming, SHA256, tarball extraction) |
| **Upload endpoints** | `POST /api/v3/boot_assets/kernels` (kernel binary, step 1 of 2) |
| **Upload endpoints** | `POST /api/v3/boot_assets/kernels/{resource_id}/initrd` (initrd, step 2 of 2) |
| **`BootAssetUploadResponse`** | Upload response model with `id`, `name`, `architecture`, `version`, `kflavor`, `bootloader_type`, `files` |
| **Upload service methods** | `upload_bootloader`, `upload_kernel`, `upload_kernel_initrd` on `BootResourceService` |
| **Deploy-time resolution** | `resolve_boot_asset_for_deployment`, `get_bootloader_path_for_machine` on `BootResourceService` |
| **Bootloader list/get** | `GET /api/v3/bootloaders` and `GET /api/v3/bootloaders/{id}` in `BootloadersHandler` |
| **Kernel list/get** | `GET /api/v3/kernels` (with `name`, `architecture`, `kflavor` filter params) and `GET /api/v3/kernels/{id}` in `KernelsHandler` |
| **Custom images `type` filter** | `GET /api/v3/custom_images?type=bootloader\|kernel\|image` working |
| **v2 deploy params** | `custom_bootloader`, `custom_kernel`, `custom_kernel_kflavor` on `POST /api/2.0/machines/{id}/op-deploy` |
| **DHCP host dict** | `make_hosts_for_subnets()` appends `bootloader_path` to host entry when machine has `custom_bootloader` node metadata |
| **Temporal workflow** | `UPLOADED` assets included in `SYNC_ALL_LOCAL_BOOTRESOURCES_WORKFLOW_NAME` scope |
| **Tests** | Baseline tests for all above at API, service, and repository tiers |

---

### ❌ REMAINING WORK — Gaps vs reviewed contracts

The following items were identified by comparing the reviewed `contracts/api.md` and `contracts/services.md` against the actual implementation:

---

#### Gap 1 — Response model discriminated union (API layer)

**Files**: `src/maasapiserver/v3/api/public/models/responses/boot_resources.py`

**Problem**: The reviewed contract specifies a `BootAssetResponse` discriminated union keyed on `type` (`"bootloader"` | `"kernel"` | `"image"`). The current `BootloaderResponse` and `KernelResponse` models are missing:
- `type: Literal["bootloader"]` / `type: Literal["kernel"]` / `type: Literal["image"]` discriminator field
- `versions: list[str]` — all version strings for this asset identity, newest first
- `latest_version: str` — the most recent version string
- `created_at: datetime`, `updated_at: datetime`
- `primary_file: str` on bootloader responses (EFI binary filename for DHCP option 67)
- `complete: bool` on kernel responses (True when latest version has both `boot-kernel` and `boot-initrd`)
- `files: list[BootAssetFileInfo]` on bootloader responses

The current `GET /api/v3/custom_images` and `GET /api/v3/custom_images/{id}` return the old `ImageResponse` (from `boot_images_common.py`) which has no type discriminator, no `versions`, no `complete`, and no `primary_file`.

**Required changes**:
1. Add `BootloaderAssetResponse(type="bootloader", primary_file, files, versions, latest_version, created_at, updated_at)` to `responses/boot_resources.py`
2. Add `KernelAssetResponse(type="kernel", complete, files, versions, latest_version, created_at, updated_at)` to `responses/boot_resources.py`
3. Add `ImageAssetResponse(type="image", versions, latest_version, created_at, updated_at)` to `responses/boot_resources.py`
4. Expose `BootAssetResponse = Annotated[BootloaderAssetResponse | KernelAssetResponse | ImageAssetResponse, Field(discriminator="type")]`
5. Update `BootloadersHandler.list_bootloaders` → return `BootloaderAssetResponse` (or a list wrapper)
6. Update `BootloadersHandler.get_bootloader` → return `BootloaderAssetResponse`
7. Update `KernelsHandler.list_kernels` → return `KernelAssetResponse` (or a list wrapper)
8. Update `KernelsHandler.get_kernel` → return `KernelAssetResponse`
9. Update `CustomImagesHandler.list_custom_images` → return paginated `BootAssetResponse` (discriminated union per item)
10. Update `CustomImagesHandler.get_custom_image_by_id` → return `BootAssetResponse`

**Service/repository support needed**: To populate `versions`, `latest_version`, `complete`, and `primary_file`, the service layer must return version lists and file metadata alongside `BootResource`. This likely requires:
- A new service method or enriched return type that fetches associated `BootResourceSet` versions and `BootResourceFile` entries for a given resource
- `complete` is `True` when the latest `BootResourceSet` has both `boot-kernel` and `boot-initrd` file entries
- `primary_file` is read from `BootResourceFile.extra["primary_file"]` on the bootloader file
- `versions` is the list of `BootResourceSet.version` strings ordered by `id` DESC

---

#### Gap 2 — Bootloader list/get endpoint path

**Files**: `src/maasapiserver/v3/api/public/handlers/boot_resources.py`, handler registration in `handlers/__init__.py`

**Problem**: The reviewed contract specifies bootloader list and get endpoints at:
- `GET /api/v3/boot_assets/bootloaders`
- `GET /api/v3/boot_assets/bootloaders/{id}`

But `BootloadersHandler` currently exposes them at:
- `GET /api/v3/bootloaders`
- `GET /api/v3/bootloaders/{id}`

This is a path mismatch. The upload endpoint (`POST /api/v3/boot_assets/bootloaders`) is correctly placed on `CustomImagesHandler` — the list/get endpoints should be co-located under the same prefix or explicitly noted as a contract deviation.

**Required change**: Either move the `BootloadersHandler` paths from `/bootloaders` to `/boot_assets/bootloaders` (and `/boot_assets/bootloaders/{id}`), or update `contracts/api.md` to document the implemented path as the accepted design. If the paths are moved, update the nginx config if needed and update `quickstart.md`.

---

#### Gap 3 — `GET /custom_images` missing filter params

**File**: `src/maasapiserver/v3/api/public/handlers/boot_resources.py` (`list_custom_images` method)

**Problem**: The reviewed contract adds `name`, `architecture`, and `kflavor` query filter parameters to `GET /api/v3/custom_images`. Only `type` was added in the implementation. The spec (FR-11, US3) requires assets to be filterable by name, architecture, and kflavor via the list endpoint.

**Required change**: Add `name: str | None`, `architecture: str | None`, and `kflavor: str | None` query parameters to `list_custom_images`; build corresponding `QuerySpec` clauses using existing `BootResourceClauseFactory.with_name()`, `with_architecture()`, `with_kflavor()` and include them in the filter.

---

#### Gap 4 — DHCP template: per-host `filename` directive missing

**File**: `src/maasserver/templates/dhcp/dhcpd.conf.template`

**Problem**: `make_hosts_for_subnets()` in `dhcp.py` correctly adds `bootloader_path` to host dictionaries when a machine has a custom bootloader assigned. However, the host block in `dhcpd.conf.template` (lines 170–192) does not render a `filename` directive when `bootloader_path` is present. The DHCP server therefore never receives the per-host boot filename override, making the feature non-functional end-to-end.

**Required change**: In the `{{for host in hosts}}` block of the template, add:
```
{{if "bootloader_path" in host and host['bootloader_path']}}
filename "{{host['bootloader_path']}}";
{{endif}}
```
immediately after `fixed-address {{host['ip']}};`.

---

#### Gap 5 — `assign_bootloader_and_trigger_dhcp` service method

**File**: `src/maasservicelayer/services/bootresources.py`

**Problem**: The reviewed `contracts/services.md` specifies an `assign_bootloader_and_trigger_dhcp(machine_id, bootloader_name, architecture)` service method that: (1) calls `resolve_boot_asset_for_deployment`, (2) fetches machine static IP address IDs, and (3) calls `configure_dhcp_on_agents(static_ip_addr_ids=[...])`. In the current implementation, steps 2 and 3 are performed directly in the v2 Django deploy endpoint (`machines.py`) rather than in the service layer.

**Decision required**: Either:
- **Option A (conform to contract)**: Implement the method in `BootResourceService`; move DHCP trigger logic from `machines.py` into the service. This requires careful handling of Django/SQLAlchemy boundary (the service layer must not import Django models).
- **Option B (accept deviation)**: Document in `contracts/services.md` that DHCP triggering remains in `machines.py` for the Django boundary reason; remove `assign_bootloader_and_trigger_dhcp` from the service contract. This is acceptable since the v2 endpoint already correctly triggers DHCP and the service layer cannot call Django DHCP functions without a boundary violation.

**Recommendation**: Option B — the Django boundary makes Option A impractical. Update `contracts/services.md` to reflect this.

---

#### Gap 6 — Test coverage for remaining gaps

Tests must be added or updated to cover all items in Gaps 1–4:

| Test file | Required additions |
|-----------|-------------------|
| `tests/maasapiserver/v3/api/public/handlers/test_boot_resources.py` | Tests for new response fields (`type`, `versions`, `complete`, `primary_file`) on list/get responses; tests for `name`, `architecture`, `kflavor` filter params on `GET /custom_images` |
| `tests/maasserver/tests/test_dhcp.py` | Test that host dict with `bootloader_path` renders `filename` directive in template; test that host without `bootloader_path` does not |
| `tests/maasapiserver/v3/api/public/models/requests/test_boot_resources.py` | Tests for any new filter request models |

---

#### Gap 7 — Simplestreams index format proposal (FR-7)

**File**: to be created as `specs/001-custom-boot-assets/simplestreams-proposal.md`

**Problem**: FR-7 requires a proposal document for a new Simplestreams index file format supporting multiple bootloaders per architecture. This is a design deliverable (not code), tracked as T044. It is not blocking FR-1 through FR-6 but is required before the Simplestreams team and MAAS Site Manager team can act.

**Required change**: Research the existing `com.ubuntu.maas:candidate:1:bootloader-download.json` format, draft a new companion index format that extends it with multiple bootloader entries per architecture (backward-compatible — existing index must remain unchanged), and commit it as a spec deliverable.

---

## Remaining Work — Prioritized

| Priority | Gap | Effort | Blocks |
|----------|-----|--------|--------|
| P1 | Gap 4: DHCP template `filename` directive | Small (template + 1 test) | DHCP bootloader delivery (FR-12, US1 SC9) |
| P1 | Gap 3: `GET /custom_images` name/arch/kflavor filters | Small (handler + tests) | US3 filtering (FR-11) |
| P2 | Gap 1: Response model discriminated union | Medium (models + service enrichment + handler wiring + tests) | Full API contract compliance |
| P2 | Gap 2: Bootloader endpoint path decision | Small (move paths or update contract) | API contract accuracy |
| P2 | Gap 5: `assign_bootloader_and_trigger_dhcp` decision | Minimal (accept Option B + update contract doc) | Contract accuracy |
| P3 | Gap 6: Test coverage for gaps 1–4 | Medium (test additions) | Quality gate |
| P3 | Gap 7: Simplestreams index proposal | Medium (research + doc writing) | FR-7 deliverable |

---

## Constitution Check — Post-Design

*Re-evaluated after reviewing implementation.*

All constitution gates remain PASS. Notable observations:

- **SQLAlchemy Core**: Repository methods added in implementation use raw `select()` / `insert()` — compliant.
- **Builders**: `CreateBootResourceBuilder` etc. reused — compliant.
- **Legacy boundary**: DHCP trigger stays in `machines.py` (Django) to avoid importing Django models in the service layer — this is the correct boundary behaviour, not a violation.
- **Async**: All v3 handlers are `async def` — compliant.
- **Gap 1 (response models)**: Adding `versions` and `complete` fields requires the service/repository to eagerly fetch version and file metadata. The repository must use additional joins or separate queries — this is acceptable as long as it uses SQLAlchemy Core and does not introduce N+1 problems (use `IN` or a single JOIN).

---

## Complexity Tracking

No constitution violations requiring justification. All deviations are within spec scope:

| Decision | Justification |
|----------|--------------|
| DHCP trigger in Django layer, not service | Django models (`NodeMetadata`, `configure_dhcp_on_agents`) cannot be imported in `maasservicelayer` without violating the service zone boundary rule |
| Bootloader list/get at `/bootloaders` not `/boot_assets/bootloaders` | Implementation preceded contract review; both paths are logically correct — resolution is a path rename or contract update, not an architecture issue |
