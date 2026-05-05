# Service Contracts: Custom Boot Assets

**Feature Branch**: `6688-custom-boot-assets`  
**Date**: 2025-07-18  
**Updated**: 2025-07-18 — Simplified endpoint strategy (removed list_assets, get_asset_detail, delete_asset, delete_version)

---

## Extended Service: `BootResourceService`

**Location**: `src/maasservicelayer/services/bootresources.py`  
**Base Class**: `Service` (existing)  
**Existing Dependencies**: `BootResourcesRepository`, `BootResourceSetsService`  
**Additional Dependencies**: (none — uses existing repository dependencies)

**Rationale**: The existing `BootResourceService` already manages the same tables (BootResource → BootResourceSet → BootResourceFile), has `get_next_version_name()` for YYYYMMDD[.N] versioning, cascade deletion hooks (`pre_delete_hook`, `pre_delete_many_hook`), and custom image-scoped methods (`get_custom_image_status_by_id`, `list_custom_images_status`). Adding custom boot asset upload methods follows this established pattern.

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

### Method: `upload_bootloader`

**Purpose**: Upload a bootloader tarball, extract contents, create/version the asset.

```python
async def upload_bootloader(
    self,
    name: str,
    architecture: str,
    sha256: str,
    file_content: AsyncIterator[bytes],
) -> BootResource:
```

**Logic**:
1. Validate architecture format (`{arch}/{subarch}`)
2. Find or create `BootResource` with `(name, architecture, rtype=UPLOADED, bootloader_type="custom")`
3. Generate next version name via `get_next_version_name(resource.id)`
4. Create `BootResourceSet` with the new version
5. Stream tarball to temporary storage, verify SHA256
6. Extract tarball to isolated directory (validate: no path traversal, no symlinks)
7. Create `BootResourceFile` entries for each extracted file
8. Return the `BootResource` with version info

**Errors**:
- `BadRequestException`: Invalid architecture format, SHA256 mismatch, invalid tarball

---

### Method: `upload_kernel_pair`

**Purpose**: Upload a kernel + initrd pair as a complete asset.

```python
async def upload_kernel_pair(
    self,
    name: str,
    architecture: str,
    kflavor: str,
    kernel_sha256: str,
    initrd_sha256: str,
    kernel_content: AsyncIterator[bytes],
    initrd_content: AsyncIterator[bytes],
) -> BootResource:
```

**Logic**:
1. Validate both files are provided (reject partial uploads)
2. Validate architecture format
3. Find or create `BootResource` with `(name, architecture, kflavor, rtype=UPLOADED, bootloader_type=NULL)`
4. Generate next version name
5. Create `BootResourceSet`
6. Stream kernel to storage, verify SHA256
7. Stream initrd to storage, verify SHA256
8. Create `BootResourceFile` entries (filetype: `boot-kernel`, `boot-initrd`)
9. Return the `BootResource` with version info

**Errors**:
- `BadRequestException`: Missing kernel/initrd, SHA256 mismatch, invalid architecture

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
3. Fetch latest `BootResourceSet` for the resource
4. Fetch `BootResourceFile` entries for the set with filetype `bootloader`
5. Compute the Rack-relative serving path for the primary bootloader file
6. Return the path string (e.g., `bootloaders/{resource_id}/{version}/{filename}`)

**Returns**: `None` if no matching custom bootloader found, otherwise the relative path for DHCP option 67.

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
