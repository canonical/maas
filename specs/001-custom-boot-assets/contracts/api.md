# API Contracts: Custom Boot Assets

**Feature Branch**: `6688-custom-boot-assets`  
**Date**: 2025-07-18  
**Updated**: 2025-07-18 — Simplified endpoint strategy (reuse existing list/get/delete)

---

## Endpoint Strategy

| Operation | Endpoint | Status |
|-----------|----------|--------|
| Upload bootloader | `POST /api/v3/boot_assets/bootloaders` | **NEW** |
| Upload kernel pair | `POST /api/v3/boot_assets/kernels` | **NEW** |
| List assets | `GET /api/v3/custom_images` | **EXISTING** — add `type` filter param |
| Get asset by ID | `GET /api/v3/custom_images/{id}` | **EXISTING** — no changes |
| Delete asset by ID | `DELETE /api/v3/custom_images/{id}` | **EXISTING** — no changes |
| Bulk delete assets | `DELETE /api/v3/custom_images` | **EXISTING** — no changes |
| Deploy with custom asset | `POST /api/2.0/machines/{system_id}/op-deploy` | **EXISTING** — add params |

**Rationale**: The existing `CustomImagesHandler` already filters by `rtype=UPLOADED`, which includes all custom boot assets (bootloaders, kernels, and images). No separate list/get/delete endpoints are needed. Only new **upload** endpoints are required because bootloader tarball extraction and kernel pair validation differ from custom image uploads.

**Per-version deletion**: NOT supported. Deletion at `BootResource` level only (all versions removed), consistent with custom images today.

---

## v3 API — New Upload Endpoints (FastAPI — `src/maasapiserver/`)

**Handler**: `CustomImagesHandler` in `src/maasapiserver/v3/api/public/handlers/boot_resources.py`

### POST `/api/v3/boot_assets/bootloaders`

**User Story**: US1 — Upload Custom Bootloader Tarball

**Permission**: Admin (`CAN_EDIT_BOOT_ENTITIES`)

**Request**:
```
Content-Type: multipart/form-data (streaming/chunked)

Fields:
  name: string (required) — e.g., "ubuntu/jammy"
  architecture: string (required) — e.g., "amd64/generic"  
  sha256: string (required) — SHA256 hash of the tarball
  file: binary (required) — tarball file (.tar.gz, .tar.xz, .tar.bz2)
```

**Response** (201 Created):
```json
{
  "id": 42,
  "name": "ubuntu/jammy",
  "architecture": "amd64/generic",
  "bootloader_type": "custom",
  "version": "20250718",
  "files": [
    {"filename": "grubx64.efi", "size": 1048576, "sha256": "abc..."},
    {"filename": "shimx64.efi", "size": 524288, "sha256": "def..."}
  ],
  "created_at": "2025-07-18T12:00:00Z"
}
```

**Errors**:
- `400`: Invalid tarball format, path traversal detected, SHA256 mismatch
- `403`: Insufficient permissions
- `409`: N/A (new version created on duplicate identity)

---

### POST `/api/v3/boot_assets/kernels`

**User Story**: US2 — Upload Custom Kernel and Initrd Pair

**Permission**: Admin (`CAN_EDIT_BOOT_ENTITIES`)

**Request**:
```
Content-Type: multipart/form-data (streaming/chunked)

Fields:
  name: string (required) — e.g., "ubuntu/noble"
  architecture: string (required) — e.g., "arm64/generic"
  kflavor: string (required) — e.g., "generic", "lowlatency"
  kernel_sha256: string (required) — SHA256 of kernel binary
  initrd_sha256: string (required) — SHA256 of initrd file
  kernel: binary (required) — kernel binary file
  initrd: binary (required) — initrd file
```

**Response** (201 Created):
```json
{
  "id": 43,
  "name": "ubuntu/noble",
  "architecture": "arm64/generic",
  "kflavor": "generic",
  "version": "20250718",
  "files": [
    {"filename": "boot-kernel", "filetype": "boot-kernel", "size": 12582912, "sha256": "abc..."},
    {"filename": "boot-initrd", "filetype": "boot-initrd", "size": 268435456, "sha256": "def..."}
  ],
  "created_at": "2025-07-18T12:00:00Z"
}
```

**Errors**:
- `400`: Missing kernel or initrd ("Both kernel and initrd files are required"), SHA256 mismatch
- `403`: Insufficient permissions

---

## v3 API — Filter Parameter Addition to Existing Endpoint

### GET `/api/v3/custom_images` (Extended)

**User Story**: US3 — Organize and Filter Assets by Type

**Existing handler**: `list_custom_images` in `CustomImagesHandler`

**New Query Parameter**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `type` | enum (optional) | Filter by asset type: `bootloader`, `kernel`, or `image`. If omitted, returns all uploaded resources (existing behavior). |

**Filter logic**:
- `type=bootloader` → `WHERE bootloader_type IS NOT NULL`
- `type=kernel` → `WHERE bootloader_type IS NULL AND kflavor IS NOT NULL`
- `type=image` → `WHERE bootloader_type IS NULL AND kflavor IS NULL`
- No `type` param → all `rtype=UPLOADED` resources (current behavior, unchanged)

**Response**: Unchanged format from existing endpoint (returns `ImageResponse` list with pagination).

**Note**: Additional filters (`name`, `architecture`, `kflavor`) may also be added as query parameters following the same pattern, but `type` is the primary discriminator needed.

---

## v3 API — Existing Endpoints (No Changes Required)

The following endpoints in `CustomImagesHandler` already work for custom boot assets with zero modifications:

### GET `/api/v3/custom_images/{id}`
Returns details of any `rtype=UPLOADED` resource by ID (includes bootloaders, kernels, images).

### DELETE `/api/v3/custom_images/{id}`
Deletes a resource and all its versions (cascade via `pre_delete_hook`). Deletion is unconditional (no in-use protection in this spike).

### DELETE `/api/v3/custom_images` (bulk)
Bulk delete uploaded resources by ID list. Same cascade behavior.

---

## v2 API Endpoint (Django — `src/maasserver/api/machines.py`)

### POST `/api/2.0/machines/{system_id}/op-deploy` (Extended)

**User Story**: US4 — Explicit Asset Selection

**New Parameters** (added to existing deploy endpoint):

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `custom_bootloader` | string | No | Name of custom bootloader asset (e.g., "ubuntu/jammy"). Architecture auto-matched to machine. |
| `custom_kernel` | string | No | Name of custom kernel asset (e.g., "ubuntu/noble"). Architecture auto-matched to machine. |
| `custom_kernel_kflavor` | string | No | Kernel flavour for custom kernel selection (default: "generic"). Required if `custom_kernel` is set. |

**Behavior**:
- If `custom_bootloader` is provided: resolve to latest version of bootloader matching `(name=custom_bootloader, architecture=machine.architecture)`
- If `custom_kernel` is provided: resolve to latest version of kernel matching `(name=custom_kernel, architecture=machine.architecture, kflavor=custom_kernel_kflavor)`
- If neither provided: use official Ubuntu boot asset from Simplestreams (existing behavior, unchanged)
- Trigger DHCP config update if custom bootloader resolved

**Note (spike scope)**: The resolved `BootResourceSet.id` is NOT recorded on the machine (no usage tracking FK). Resolution is dynamic.

**Errors**:
- `400`: Custom asset not found for given name/architecture combination
- `403`: User lacks deployment permissions (`NodePermission.edit`)

---

## Error Response Format

All v3 API errors follow the standard MAAS error format:

```json
{
  "kind": "Error",
  "code": 400,
  "message": "Both kernel and initrd files are required"
}
```
