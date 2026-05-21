# Service Contracts: Custom Boot Assets

**Feature Branch**: `6688-custom-boot-assets`  
**Date**: 2025-07-18  
**Updated**: 2025-07-18 — Simplified endpoint strategy (removed list_assets, get_asset_detail, delete_asset, delete_version)

---

## Extended Service: `BootResourceService`

**Location**: `src/maasservicelayer/services/bootresources.py`  
**Base Class**: `Service` (existing)  
**Existing Dependencies**: `BootResourcesRepository`, `BootResourceSetsService`  
**Additional Dependencies**: `BootResourceFilesService` (added in this feature — upload logic moved to service layer)

**Rationale**: The existing `BootResourceService` already manages the same tables (BootResource → BootResourceSet → BootResourceFile), has `get_next_version_name()` for YYYYMMDD[.N] versioning, cascade deletion hooks (`pre_delete_hook`, `pre_delete_many_hook`), and custom image-scoped methods (`get_custom_image_status_by_id`, `list_custom_images_status`). Adding custom boot asset upload methods follows this established pattern. File streaming and sync triggering remain in the handler layer; the service receives the `filename_on_disk` after streaming is complete.

**Note**: List, get-by-ID, delete, and bulk-delete operations use the existing service methods (already called by `CustomImagesHandler`). No new service methods are needed for these operations.

---

### Existing Methods (Reused Without Modification)

| Method | Purpose | Called By |
|--------|---------|-----------|
| `get_next_version_name(boot_resource_id)` | Generate YYYYMMDD[.N] version for new uploads | Upload methods |
| `pre_delete_hook(resource_id)` | Cascade delete sets → files → physical files | Existing delete endpoint |
| `pre_delete_many_hook(resource_ids)` | Cascade delete for bulk operations | Existing bulk delete endpoint |
| `list_custom_images_status()` | List all rtype=UPLOADED resources | Existing list endpoint |
| `get_custom_image_status_by_id()` | Get specific uploaded resource | Existing get endpoint |

---

### Method: `upload_custom_image`

**Purpose**: Create DB records for an uploaded custom image. File must already be streamed to disk by the handler before calling this method.

```python
async def upload_custom_image(
    self,
    name: str,
    architecture: str,
    sha256: str,
    filetype: BootResourceFileType,
    filename: str,
    filename_on_disk: str,
    size: int,
    base_image: str,
    extra: dict[str, object],
) -> tuple[BootResource, BootResourceFile]:
```

**Logic**:
1. Find or create `BootResource` with `(name, architecture, rtype=UPLOADED)`
2. Generate next version via `get_next_version_name()`
3. Create `BootResourceSet`
4. Create `BootResourceFile` using the pre-written `filename_on_disk`
5. Return `(boot_resource, resource_file)`

---

### Method: `upload_bootloader`

**Purpose**: Create DB records for a custom bootloader tarball. File must already be streamed to disk by the handler.

```python
async def upload_bootloader(
    self,
    name: str,
    architecture: str,
    sha256: str,
    primary_file: str,
    filename_on_disk: str,
    size: int,
) -> tuple[BootResource, str]:
```

**Parameters**:
- `primary_file`: filename of the EFI binary inside the tarball (used as DHCP option 67 value, stored in `BootResourceFile.extra["primary_file"]`)

**Logic**:
1. Call `repository.find_or_create_bootloader(name, architecture)` — creates `BootResource` with `bootloader_type="custom"` if not found
2. Generate next version via `get_next_version_name()`
3. Create `BootResourceSet`
4. Create `BootResourceFile` with `filetype=BOOTLOADER_TARBALL`, `filename="bootloader.tar.gz"`, `extra={"primary_file": primary_file}`
5. Return `(boot_resource, version)`

**Errors**:
- `BadRequestException`: Missing required header, SHA256 mismatch

---

### Method: `upload_kernel`

**Purpose**: Create DB records for a kernel binary (step 1 of 2). File must already be streamed to disk.

```python
async def upload_kernel(
    self,
    name: str,
    architecture: str,
    kflavor: str,
    sha256: str,
    filename_on_disk: str,
    size: int,
) -> tuple[BootResource, str]:
```

**Logic**:
1. Call `repository.find_or_create_kernel(name, architecture, kflavor)` — creates `BootResource` with `kflavor` set and `bootloader_type=NULL`
2. Generate next version via `get_next_version_name()`
3. Create `BootResourceSet`
4. Create `BootResourceFile` with `filetype=BOOT_KERNEL`, `filename="kernel"`
5. Return `(boot_resource, version)`

**Errors**:
- `BadRequestException`: SHA256 mismatch

---

### Method: `upload_kernel_initrd`

**Purpose**: Append an initrd file to an existing kernel resource's latest version (step 2 of 2). File must already be streamed to disk.

```python
async def upload_kernel_initrd(
    self,
    resource_id: int,
    sha256: str,
    filename_on_disk: str,
    size: int,
) -> tuple[BootResource, str]:
```

**Logic**:
1. Fetch `BootResource` by `resource_id` — raise `NotFoundException` if not found
2. Fetch all `BootResourceSet` entries for the resource; pick the latest by `id` (highest)
3. Create `BootResourceFile` with `filetype=BOOT_INITRD`, `filename="initrd"`, attached to that set
4. Return `(boot_resource, version)`

**Errors**:
- `NotFoundException`: `resource_id` not found, or resource has no sets

---

### Method: `resolve_boot_asset_for_deployment`

**Purpose**: Resolve the latest version of a custom boot asset for a machine deployment.

```python
async def resolve_boot_asset_for_deployment(
    self,
    name: str,
    architecture: str,
    kflavor: str | None = None,
    asset_type: Literal["bootloader", "kernel"] = "bootloader",
) -> BootResourceSet:
```

**Logic**:
1. Find `BootResource` matching identity:
   - Bootloader: `(name, architecture, rtype=UPLOADED, bootloader_type IS NOT NULL)`
   - Kernel: `(name, architecture, kflavor, rtype=UPLOADED, bootloader_type IS NULL)`
2. Find latest `BootResourceSet` for the resource (ordered by version DESC)
3. Return the set (caller uses for deployment)

**Errors**:
- `NotFoundException`: No matching asset found for the given parameters

---

### Method: `get_bootloader_path_for_machine`

**Purpose**: Resolve the DHCP boot filename path for a machine with a custom bootloader assigned. Used by DHCP configuration generation to set per-host `filename` directive.

```python
async def get_bootloader_path_for_machine(
    self,
    machine_id: int,
    bootloader_name: str,
    architecture: str,
) -> str | None:
```

**Logic**:
1. Find `BootResource` matching `(name=bootloader_name, architecture, rtype=UPLOADED, bootloader_type IS NOT NULL)`
2. If not found → return `None` (no custom bootloader)
3. Fetch latest `BootResourceSet` for the resource via `repository.get_latest_version()`
4. Fetch `BootResourceFile` for the set via `repository.get_bootloader_file_for_set()`
5. Read `primary_file` from `BootResourceFile.extra["primary_file"]`; log warning and return `None` if absent
6. Compute Rack-relative path: `bootloaders/{safe_name}/{safe_arch}/{version}/{primary_file}` where slashes in `name` and `architecture` are replaced with `__` (e.g. `ubuntu/jammy` → `ubuntu__jammy`)

**Returns**: `None` if no matching custom bootloader found or `primary_file` is unset, otherwise the relative path string for DHCP option 67.

---

### Method: `assign_bootloader_and_trigger_dhcp`

**Purpose**: Resolve a custom bootloader for a machine and trigger DHCP configuration update on the serving Rack Controller. Called by the v2 deploy endpoint when `custom_bootloader` parameter is provided.

```python
async def assign_bootloader_and_trigger_dhcp(
    self,
    machine_id: int,
    bootloader_name: str,
    architecture: str,
) -> BootResourceSet:
```

**Logic**:
1. Call `resolve_boot_asset_for_deployment(name, architecture, asset_type="bootloader")`
2. Fetch machine's static IP address IDs (from boot interface)
3. Call `configure_dhcp_on_agents(static_ip_addr_ids=[...])` to trigger the existing `ConfigureDHCPWorkflow` Temporal workflow
4. Return the resolved `BootResourceSet`

**Errors**:
- `NotFoundException`: No matching custom bootloader found
- `BadRequestException`: Machine has no boot interface or no static IP assigned

**Side Effects**:
- Triggers `ConfigureDHCPWorkflow` Temporal workflow → updates DHCP config on serving Rack Controller

---

## Builder Models

### `CreateBootResourceBuilder`

Already exists. Used when creating a new `BootResource` entry for a first-time upload.

### `CreateBootResourceSetBuilder`

Already exists. Used to create a new version (`BootResourceSet`) for each upload.

### `CreateBootResourceFileBuilder`

Already exists. Used to register individual files within a version.

---

## Domain Models (Pydantic) — New

### `BootAssetUploadResponse`

Used only for upload endpoint responses (201 Created). Listing and retrieval use the `BootAssetResponse` discriminated union defined in the API contracts.

```python
class BootAssetUploadResponse(BaseModel):
    id: int
    name: str
    architecture: str
    bootloader_type: str | None
    kflavor: str | None
    version: str
    files: list[BootAssetFileInfo]  # shared with BootAssetResponse variants
    created_at: datetime
```
