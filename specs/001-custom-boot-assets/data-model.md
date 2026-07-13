# Data Model: Custom Boot Assets (SPIKE)

**Feature Branch**: `6688-custom-boot-assets`  
**Date**: 2025-07-18  
**Scope**: SPIKE — No usage tracking FK, no GC

---

## Entity Relationship Overview

```
┌─────────────────────────┐
│     BootResource        │  (identity: name + arch [+ kflavor for kernels])
│  rtype = UPLOADED (2)   │
│  name, architecture,    │
│  kflavor, bootloader_type│
└──────────┬──────────────┘
           │ 1:N
           ▼
┌─────────────────────────┐
│   BootResourceSet       │  (version: YYYYMMDD[.N])
│  version, label,        │
│  resource_id (FK)       │
└──────────┬──────────────┘
           │ 1:N
           ▼
┌─────────────────────────┐
│   BootResourceFile      │  (actual files: kernel, initrd, bootloader files)
│  filename, filetype,    │
│  sha256, size,          │
│  filename_on_disk       │
└──────────┬──────────────┘
           │ 1:N
           ▼
┌─────────────────────────┐
│ BootResourceFileSync    │  (per-region sync tracking)
│  file_id, region_id,    │
│  size (bytes synced)    │
└─────────────────────────┘
```

**Note**: No FK from Machine to BootResourceSet in this spike. Usage tracking is deferred to future work.

---

## Existing Tables (No Schema Changes Required)

### BootResourceTable

**Location**: `src/maasservicelayer/db/tables.py` (line 188)

| Column | Type | Description |
|--------|------|-------------|
| id | Integer (PK) | Auto-increment |
| rtype | Integer | `0=SYNCED`, `2=UPLOADED` |
| name | String | Free-text, typically `{os}/{series}` |
| architecture | String | `{arch}/{subarch}` (e.g., `amd64/generic`) |
| kflavor | String (nullable) | Kernel flavour (null for bootloaders) |
| bootloader_type | String (nullable) | Set for bootloaders, null for kernels |
| extra | JSONB (nullable) | Additional metadata |
| rolling | Boolean | Whether asset auto-updates |
| base_image | String (nullable) | Base image reference |
| alias | String (nullable) | Display alias |
| last_deployed | DateTime (nullable) | Last deployment timestamp |
| selection_id | Integer (FK, nullable) | FK to BootSourceSelection |

**Existing Constraints**:
- Unique: varies by query (name + architecture for lookups)

**Custom Boot Asset Usage**:
- Bootloaders: `rtype=2`, `name="{os}/{series}"`, `architecture="{arch}/{subarch}"`, `bootloader_type="custom"`, `kflavor=NULL`
- Kernels: `rtype=2`, `name="{os}/{series}"`, `architecture="{arch}/{subarch}"`, `kflavor="{flavour}"`, `bootloader_type=NULL`

### BootResourceSetTable

**Location**: `src/maasservicelayer/db/tables.py` (line 284)

| Column | Type | Description |
|--------|------|-------------|
| id | Integer (PK) | Auto-increment |
| version | String | `YYYYMMDD[.N]` format |
| label | String | Display label (e.g., "release") |
| resource_id | Integer (FK) | FK to BootResource |

**Constraint**: Unique `(resource_id, version)`

### BootResourceFileTable

**Location**: `src/maasservicelayer/db/tables.py` (line 213)

| Column | Type | Description |
|--------|------|-------------|
| id | Integer (PK) | Auto-increment |
| filename | String | Logical filename |
| filetype | String | `boot-kernel`, `boot-initrd`, `boot-dtb`, `bootloader` |
| sha256 | String | Content hash for integrity |
| size | BigInteger | File size in bytes |
| filename_on_disk | String (nullable) | Physical storage path |
| resource_set_id | Integer (FK) | FK to BootResourceSet |

**Constraint**: Unique `(resource_set_id, filename)`

### BootResourceFileSyncTable

**Location**: `src/maasservicelayer/db/tables.py` (line 254)

| Column | Type | Description |
|--------|------|-------------|
| id | Integer (PK) | Auto-increment |
| file_id | Integer (FK) | FK to BootResourceFile |
| region_id | Integer (FK) | FK to RegionController |
| size | BigInteger | Bytes synced (for progress) |

**Constraint**: Unique `(file_id, region_id)`

---

## New Schema Changes Required

### Migration: Add Unique Constraint for Custom Boot Asset Identity

**Purpose**: Enforce uniqueness for custom boot assets at the database level.

```sql
-- Bootloader identity: name + architecture (where bootloader_type IS NOT NULL and rtype=2)
CREATE UNIQUE INDEX UK_bootresource_bootloader_identity
ON maas_bootresource(name, architecture)
WHERE rtype = 2 AND bootloader_type IS NOT NULL;

-- Kernel identity: name + architecture + kflavor (where bootloader_type IS NULL and rtype=2)
CREATE UNIQUE INDEX UK_bootresource_kernel_identity
ON maas_bootresource(name, architecture, kflavor)
WHERE rtype = 2 AND bootloader_type IS NULL AND kflavor IS NOT NULL;
```

**Note**: These are partial unique indexes that only apply to uploaded (custom) resources. Synced resources from Simplestreams have their own identity management.

**Deferred (future work)**: Migration to add `boot_resource_set_id` FK to `maasserver_node` for version usage tracking.

---

## Entity Validation Rules

### Bootloader Asset

| Field | Rule |
|-------|------|
| name | Required, non-empty, max 255 chars |
| architecture | Required, format `{arch}/{subarch}`, validated against known architectures |
| bootloader_type | Required, set to `"custom"` for user-uploaded bootloaders |
| kflavor | Must be NULL |
| rtype | Must be `2` (UPLOADED) |

### Kernel Asset

| Field | Rule |
|-------|------|
| name | Required, non-empty, max 255 chars |
| architecture | Required, format `{arch}/{subarch}`, validated against known architectures |
| kflavor | Required, non-empty (e.g., `generic`, `lowlatency`, `hwe`) |
| bootloader_type | Must be NULL |
| rtype | Must be `2` (UPLOADED) |

### Upload Validation (Kernel Pair)

| Check | Error |
|-------|-------|
| Kernel file missing | "Both kernel and initrd files are required" |
| Initrd file missing | "Both kernel and initrd files are required" |
| SHA256 mismatch | "File integrity check failed: SHA256 does not match" |
| Tarball path traversal | "Invalid tarball: path traversal detected" |

---

## State Transitions

### Boot Asset Version Lifecycle (Spike)

```
UPLOADING → COMPLETE → SUPERSEDED
                ↓
              (latest — used for new deployments)
```

- **UPLOADING**: File upload in progress (tracked via BootResourceFileSync size < total)
- **COMPLETE**: All files synced to at least one region
- **SUPERSEDED**: A newer version exists for the same identity (retained indefinitely in spike)

**Deferred (future work)**: IN_USE state (requires usage tracking FK), GARBAGE_COLLECTED state (requires GC workflow).

---

## DHCP Configuration Data Flow (FR-12)

### Per-Host Boot Filename Override

When a machine has a custom bootloader assigned at deploy time, the DHCP host declaration for that machine's MAC address must include an explicit `filename` directive pointing to the custom bootloader path.

**Data resolution at DHCP config generation time**:

```
Machine (maasserver_node)
  │── deploy parameters (custom_bootloader name) ──→ resolve latest BootResourceSet
  │                                                      │── resource_id (FK) ──→ BootResource (bootloader_type != NULL)
  │                                                      └── BootResourceFile (filename_on_disk = storage path)
  │── boot_interface_id (FK) ──→ Interface
  │                                └── mac_address (used for DHCP host match)
  └── StaticIPAddress (via Interface)
       └── ip (used for DHCP host fixed-address)
```

**Note**: In this spike, the bootloader resolution happens dynamically at deploy/DHCP-config time by resolving the latest version of the named bootloader for the machine's architecture. There is no FK on the node table recording which version was deployed.

**Host dictionary enhancement** (produced by `make_hosts_for_subnets()`):

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `host` | String | Machine hostname | Host declaration name |
| `mac` | String | Interface.mac_address | Hardware ethernet match |
| `ip` | String | StaticIPAddress.ip | Fixed address |
| `bootloader_path` | String (optional) | BootResourceFile.filename | Per-host boot filename override (DHCP option 67) |

**DHCP template rendering**: When `bootloader_path` is present in the host dict, the template emits `filename "{bootloader_path}";` inside the host block. This overrides the subnet-level conditional bootloader for that specific machine.

---

## Indexes Required

| Index | Columns | Purpose |
|-------|---------|---------|
| `idx_bootresource_rtype_name_arch` | `(rtype, name, architecture)` | Fast lookup for asset listing/filtering |
| `idx_bootresource_uploaded_bootloader` | `(name, architecture) WHERE rtype=2 AND bootloader_type IS NOT NULL` | Bootloader identity uniqueness |
| `idx_bootresource_uploaded_kernel` | `(name, architecture, kflavor) WHERE rtype=2 AND bootloader_type IS NULL` | Kernel identity uniqueness |
| `idx_bootresourceset_resource_version` | `(resource_id, version)` | Already exists (unique constraint) |
