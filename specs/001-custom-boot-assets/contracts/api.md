# API Contracts: Custom Boot Assets

**Feature Branch**: `6688-custom-boot-assets`  
**Date**: 2025-07-18  
**Updated**: 2025-07-18 — Simplified endpoint strategy (reuse existing list/get/delete)

---

## Endpoint Strategy

| Operation | Endpoint | Status |
|-----------|----------|--------|
| Upload bootloader | `POST /api/v3/boot_assets/bootloaders` | **NEW** |
| List bootloaders | `GET /api/v3/boot_assets/bootloaders` | **NEW** |
| Get bootloader by ID | `GET /api/v3/boot_assets/bootloaders/{id}` | **NEW** |
| Upload kernel (step 1) | `POST /api/v3/boot_assets/kernels` | **NEW** |
| Upload initrd (step 2) | `POST /api/v3/boot_assets/kernels/{resource_id}/initrd` | **NEW** |
| List kernels | `GET /api/v3/kernels` | **NEW** (`KernelsHandler`) |
| Get kernel by ID | `GET /api/v3/kernels/{id}` | **NEW** (`KernelsHandler`) |
| List all assets | `GET /api/v3/custom_images` | **EXISTING** — add `type` + `file_type` filter params |
| Get asset by ID | `GET /api/v3/custom_images/{id}` | **EXISTING** — no changes |
| Delete asset by ID | `DELETE /api/v3/custom_images/{id}` | **EXISTING** — no changes |
| Bulk delete assets | `DELETE /api/v3/custom_images` | **EXISTING** — no changes |
| Deploy with custom asset | `POST /api/2.0/machines/{system_id}/op-deploy` | **EXISTING** — add params |

**Rationale**: Upload endpoints live under `/boot_assets/bootloaders` and `/boot_assets/kernels` because bootloader tarball extraction and kernel pair validation differ from plain image uploads. Kernel upload is intentionally split into two sequential calls (kernel first, then initrd) to allow large files to be streamed independently; a kernel resource without an initrd is valid but marked incomplete. List and get endpoints for kernels are served by a dedicated `KernelsHandler` at `/api/v3/kernels` with typed response models. The existing `/custom_images` endpoints are retained for callers that need all uploaded assets in a single mixed-type call. All upload endpoints accept raw `application/octet-stream` bodies with metadata passed via custom `x-*` request headers.

**Per-version deletion**: NOT supported. Deletion at `BootResource` level only (all versions removed), consistent with custom images today.

---

## v3 API — New Upload Endpoints (FastAPI — `src/maasapiserver/`)

**Handler**: `CustomImagesHandler` in `src/maasapiserver/v3/api/public/handlers/boot_resources.py`

Upload endpoints stream raw `application/octet-stream` bodies. Metadata (name, architecture, sha256, etc.) is passed via custom `x-*` request headers. The handler streams the body to disk first, then calls the service method to create DB records.

### POST `/api/v3/boot_assets/bootloaders`

**User Story**: US1 — Upload Custom Bootloader Tarball

**Permission**: Admin (`CAN_EDIT_BOOT_ENTITIES`)

**Request**:
```
Content-Type: application/octet-stream (raw streaming body)

Headers (required):
  x-name:         string — e.g., "ubuntu/jammy"
  x-architecture: string — e.g., "amd64/generic"
  x-sha256:       string — SHA256 hash of the tarball body
  x-primary-file: string — filename of the EFI binary inside the tarball
                           used as DHCP option 67 value (e.g., "grubx64.efi")
  content-length: integer — total byte length of the tarball body

Body: raw tarball bytes (.tar.gz, .tar.xz, .tar.bz2)
```

**Validation** (handler delegates to service after streaming):
- `x-name` validated via `validate_boot_asset_name()` — rejects reserved OS names
- `x-architecture` validated via `validate_architecture()` — must match a known usable architecture
- SHA256 verified on-disk after streaming; mismatch raises 400

**Response** (201 Created):
```json
{
  "id": 42,
  "name": "ubuntu/jammy",
  "architecture": "amd64/generic",
  "bootloader_type": "custom",
  "version": "20250718",
  "files": [
    {"filename": "bootloader.tar.gz", "filetype": "bootloader-tarball", "size": 1048576, "sha256": "abc..."}
  ]
}
```

**Errors**:
- `400`: Missing required header, SHA256 mismatch, invalid name/architecture
- `403`: Insufficient permissions
- `409`: N/A (new version created on duplicate identity)

---

### POST `/api/v3/boot_assets/kernels`

**User Story**: US2 — Upload Custom Kernel (step 1 of 2)

**Permission**: Admin (`CAN_EDIT_BOOT_ENTITIES`)

**Request**:
```
Content-Type: application/octet-stream (raw streaming body)

Headers (required):
  x-name:         string — e.g., "ubuntu/noble"
  x-architecture: string — e.g., "arm64/generic"
  x-kflavor:      string — e.g., "generic", "lowlatency"
  x-sha256:       string — SHA256 hash of the kernel binary
  content-length: integer — total byte length of the kernel binary

Body: raw kernel binary bytes
```

**Note**: This endpoint uploads the kernel binary only. The initrd must be uploaded separately via `POST /boot_assets/kernels/{resource_id}/initrd`. A kernel resource without an initrd is considered incomplete; the `complete` field on `KernelResponse` reflects this.

**Response** (201 Created):
```json
{
  "id": 43,
  "name": "ubuntu/noble",
  "architecture": "arm64/generic",
  "kflavor": "generic",
  "version": "20250718",
  "files": [
    {"filename": "kernel", "filetype": "boot-kernel", "size": 12582912, "sha256": "abc..."}
  ]
}
```

**Errors**:
- `400`: Missing required header, SHA256 mismatch, invalid name/architecture
- `403`: Insufficient permissions

---

### POST `/api/v3/boot_assets/kernels/{resource_id}/initrd`

**User Story**: US2 — Upload Custom Initrd (step 2 of 2)

**Permission**: Admin (`CAN_EDIT_BOOT_ENTITIES`)

**Request**:
```
Content-Type: application/octet-stream (raw streaming body)

Path params:
  resource_id: int — ID of the kernel BootResource created by step 1

Headers (required):
  x-sha256:       string — SHA256 hash of the initrd file
  content-length: integer — total byte length of the initrd file

Body: raw initrd bytes
```

**Note**: The initrd is appended to the **latest** `BootResourceSet` of the given kernel resource. After this call the kernel set is complete (`complete=true`).

**Response** (201 Created):
```json
{
  "id": 43,
  "name": "ubuntu/noble",
  "architecture": "arm64/generic",
  "kflavor": "generic",
  "version": "20250718",
  "files": [
    {"filename": "kernel",  "filetype": "boot-kernel",  "size": 12582912,  "sha256": "abc..."},
    {"filename": "initrd",  "filetype": "boot-initrd",  "size": 268435456, "sha256": "def..."}
  ]
}
```

**Errors**:
- `400`: Missing `x-sha256` header, SHA256 mismatch
- `403`: Insufficient permissions
- `404`: `resource_id` not found or has no resource set

---

## v3 API — New List/Get Endpoints

### Handler: `KernelsHandler`

**Location**: `src/maasapiserver/v3/api/public/handlers/boot_resources.py`

Kernel list and get endpoints are served by a dedicated `KernelsHandler` class (separate from `CustomImagesHandler`), mounted at `/api/v3/kernels`.

### GET `/api/v3/kernels`

**Permission**: Authenticated user (`CAN_VIEW_BOOT_ENTITIES`)

**Query Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | string (optional) | Filter by asset name (e.g. `myos/jammy`) |
| `architecture` | string (optional) | Filter by architecture (e.g. `amd64/generic`) |
| `kflavor` | string (optional) | Filter by kernel flavour (e.g. `generic`, `lowlatency`) |

**Response** (200 OK): Paginated list of `KernelResponse`.

**Errors**:
- `403`: Insufficient permissions

---

### GET `/api/v3/kernels/{kernel_id}`

**Permission**: Authenticated user (`CAN_VIEW_BOOT_ENTITIES`)

**Response** (200 OK): Single `KernelResponse`.

**Errors**:
- `403`: Insufficient permissions
- `404`: Asset not found or not a kernel

---

## v3 API — Filter Parameter Addition to Existing Endpoint

### GET `/api/v3/custom_images` (Extended)

**User Story**: US3 — Organize and Filter Assets by Type

**Existing handler**: `list_custom_images` in `CustomImagesHandler`

**New Query Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `type` | enum (optional) | Filter by asset type: `bootloader`, `kernel`, or `image`. If omitted, returns all uploaded resources (existing behavior). |
| `name` | string (optional) | Filter by asset name (e.g. `ubuntu/jammy`). |
| `architecture` | string (optional) | Filter by architecture (e.g. `amd64/generic`). |
| `kflavor` | string (optional) | Filter by kernel flavour (e.g. `generic`, `lowlatency`). Only meaningful when `type=kernel`; ignored for other types. |

**Filter logic**:
- `type=bootloader` → `WHERE bootloader_type IS NOT NULL`
- `type=kernel` → `WHERE bootloader_type IS NULL AND kflavor IS NOT NULL`
- `type=image` → `WHERE bootloader_type IS NULL AND kflavor IS NULL`
- No `type` param → all `rtype=UPLOADED` resources (current behavior, unchanged)

**Response**: Paginated list of `BootAssetResponse` (discriminated union — see **Response Models** section below). Each item includes a `type` field that identifies its concrete variant.

**Note**: All filter parameters are combinable; each supplied parameter further narrows the result set.

---

## v3 API — Response Models

All list and single-item get responses return a `BootAssetResponse` discriminated union, keyed on the `type` field.

```python
class BootAssetFileInfo(BaseModel):
    filename: str
    filetype: str | None
    size: int
    sha256: str

class _BootAssetBase(BaseModel):
    id: int
    name: str
    architecture: str
    versions: list[str]      # YYYYMMDD[.N], newest first
    latest_version: str
    created_at: datetime
    updated_at: datetime

class BootloaderAssetResponse(_BootAssetBase):
    type: Literal["bootloader"]
    bootloader_type: str     # e.g. "custom"
    primary_file: str        # primary EFI binary filename inside the tarball
    files: list[BootAssetFileInfo]

class KernelAssetResponse(_BootAssetBase):
    type: Literal["kernel"]
    kflavor: str
    complete: bool           # True when latest version has both kernel and initrd
    files: list[BootAssetFileInfo]

class ImageAssetResponse(_BootAssetBase):
    type: Literal["image"]

BootAssetResponse = Annotated[
    BootloaderAssetResponse | KernelAssetResponse | ImageAssetResponse,
    Field(discriminator="type"),
]
```

`type` is derived server-side from the stored columns:
- `bootloader_type IS NOT NULL` -> `"bootloader"`
- `kflavor IS NOT NULL` -> `"kernel"`
- otherwise -> `"image"`

`complete` for kernels is `True` when the latest version's `BootResourceSet` contains both a `boot-kernel` and a `boot-initrd` file.

---

## v3 API — Existing Endpoints (Updated)

The following endpoints in `CustomImagesHandler` are updated to return `BootAssetResponse` instead of the legacy `ImageResponse`:

### GET `/api/v3/custom_images/{id}`
Returns a single `BootAssetResponse` for any `rtype=UPLOADED` resource by ID.

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
