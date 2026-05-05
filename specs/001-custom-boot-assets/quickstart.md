# Quickstart: Custom Boot Assets

**Feature Branch**: `6688-custom-boot-assets`  
**Date**: 2025-07-18  
**Updated**: 2025-07-18 — Simplified endpoint strategy (reuse existing `/custom_images` for list/get/delete)

---

## Prerequisites

1. Running MAAS development environment (`make run` or snap-based dev setup)
2. Admin user credentials
3. At least one Rack Controller connected
4. Sample bootloader tarball and kernel+initrd pair for testing

---

## Manual Testing Guide

> Note: The FastAPI v3 endpoints are served under `/MAAS/a/v3`.

```bash
# Obtain a Bearer token via the v3 login endpoint
TOKEN=$(curl -s -X POST http://localhost:5240/MAAS/a/v3/auth/login \
  -d "username=admin" \
  -d "password=admin" \
  | jq -r '.access_token')

export AUTH="Authorization: Bearer $TOKEN"
```

### 1. Upload a Custom Bootloader

```bash
# Create a test bootloader tarball
mkdir -p /tmp/test-bootloader
echo "fake grub binary" > /tmp/test-bootloader/grubx64.efi
echo "fake shim binary" > /tmp/test-bootloader/shimx64.efi
tar -czf /tmp/test-bootloader.tar.gz -C /tmp/test-bootloader .

# Calculate SHA256
SHA256=$(sha256sum /tmp/test-bootloader.tar.gz | cut -d' ' -f1)

# Upload via v3 API — metadata in headers, file as octet-stream body
curl -X POST http://localhost:5240/MAAS/a/v3/boot_assets/bootloaders \
  -H "$AUTH" \
  -H "x-name: custom/jammy" \
  -H "x-architecture: amd64/generic" \
  -H "x-sha256: $SHA256" \
  -H "x-primary-file: shimx64.efi" \
  -H "Content-Type: application/octet-stream" \
  --data-binary @/tmp/test-bootloader.tar.gz
```

**Expected**: 201 response with asset details, version `YYYYMMDD`.

### 2. Upload a Custom Kernel Pair

Kernel and initrd are uploaded as **two separate requests**. The first creates the
resource and uploads the kernel; the second attaches the initrd using the resource
ID returned from the first.

```bash
# Create test kernel and initrd files
dd if=/dev/urandom of=/tmp/test-kernel bs=1M count=2
dd if=/dev/urandom of=/tmp/test-initrd bs=1M count=100

# Calculate SHA256s
KERNEL_SHA=$(sha256sum /tmp/test-kernel | cut -d' ' -f1)
INITRD_SHA=$(sha256sum /tmp/test-initrd | cut -d' ' -f1)

# Step 1: Upload kernel — returns resource ID
RESOURCE_ID=$(
  curl -s -X POST http://localhost:5240/MAAS/a/v3/boot_assets/kernels \
    -H "$AUTH" \
    -H "x-name: custom/noble" \
    -H "x-architecture: amd64/generic" \
    -H "x-kflavor: generic" \
    -H "x-sha256: $KERNEL_SHA" \
    -H "Content-Type: application/octet-stream" \
    --data-binary @/tmp/test-kernel \
  | jq -r '.id'
)

# Step 2: Upload initrd — attaches to the resource created above
curl -X POST "http://localhost:5240/MAAS/a/v3/boot_assets/kernels/$RESOURCE_ID/initrd" \
  -H "$AUTH" \
  -H "x-sha256: $INITRD_SHA" \
  -H "Content-Type: application/octet-stream" \
  --data-binary @/tmp/test-initrd
```

**Expected**: Both requests return 201. After the initrd upload the resource set is
complete and the asset is ready for deployment.

### 3. Verify Partial Upload State

```bash
# A resource with only a kernel (no initrd yet) will be visible via the list
# endpoint but will not be selectable for deployment until the initrd is
# uploaded. The service enforces completeness at resolution time.
curl "http://localhost:5240/MAAS/a/v3/custom_images?type=kernel" \
  -H "$AUTH" | jq
```

### 4. List and Filter Assets (Existing Endpoint)

```bash
# List all custom uploaded assets (existing behavior — includes bootloaders, kernels, images)
curl http://localhost:5240/MAAS/a/v3/custom_images \
  -H "$AUTH" | jq

# Filter bootloaders only (new filter parameter)
curl "http://localhost:5240/MAAS/a/v3/custom_images?type=bootloader" \
  -H "$AUTH" | jq

# Filter kernels only
curl "http://localhost:5240/MAAS/a/v3/custom_images?type=kernel" \
  -H "$AUTH" | jq

# Filter plain images only (custom OS images, existing custom images)
curl "http://localhost:5240/MAAS/a/v3/custom_images?type=image" \
  -H "$AUTH" | jq
```

### 4b. List and Filter by Sub-Resource (Typed Endpoints)

These endpoints return concrete typed responses — `BootloaderResponse` for
`/bootloaders` and `KernelResponse` for `/kernels` — with no discriminator
field needed. Use them when you want only one asset type; use `/custom_images`
when you need all asset types in a single call.

```bash
# List bootloaders only — returns BootloaderResponse items, no ?type= needed
curl http://localhost:5240/MAAS/a/v3/bootloaders \
  -H "$AUTH" | jq

# Get a specific bootloader by ID
curl http://localhost:5240/MAAS/a/v3/bootloaders/42 \
  -H "$AUTH" | jq

# List kernels — supports ?name=, ?architecture=, ?kflavor= filters
curl "http://localhost:5240/MAAS/a/v3/kernels?kflavor=generic" \
  -H "$AUTH" | jq

# Get a specific kernel by ID
curl http://localhost:5240/MAAS/a/v3/kernels/43 \
  -H "$AUTH" | jq
```

### 5. Get Asset Details (Existing Endpoint)

```bash
# Get a specific asset by ID (works for bootloaders, kernels, or images)
curl http://localhost:5240/MAAS/a/v3/custom_images/42 \
  -H "$AUTH" | jq
```

### 6. Deploy a Machine with Custom Boot Assets

```bash
# Deploy using custom bootloader and kernel (v2 API — extended with new params)
curl -X POST http://localhost:5240/MAAS/api/2.0/machines/$SYSTEM_ID/op-deploy \
  -d "distro_series=custom/noble" \
  -d "custom_bootloader=custom/jammy" \
  -d "custom_kernel=custom/noble" \
  -d "custom_kernel_kflavor=generic" \
  -H "Authorization: oauth ..."
```

**Expected**: Machine deploys using the custom bootloader and kernel (latest versions).

### 7. Verify Version Resolution

```bash
# Upload a second version of the same bootloader
SHA256_V2=$(sha256sum /tmp/test-bootloader-v2.tar.gz | cut -d' ' -f1)
curl -X POST http://localhost:5240/MAAS/a/v3/boot_assets/bootloaders \
  -H "$AUTH" \
  -H "x-name: custom/jammy" \
  -H "x-architecture: amd64/generic" \
  -H "x-sha256: $SHA256_V2" \
  -H "x-primary-file: shimx64.efi" \
  -H "Content-Type: application/octet-stream" \
  --data-binary @/tmp/test-bootloader-v2.tar.gz

# List all — verify both versions visible via existing endpoint
curl "http://localhost:5240/MAAS/a/v3/custom_images?type=bootloader" \
  -H "$AUTH" | jq
```

**Expected**: Asset listed; new deployments use the latest version.

### 8. Delete an Asset (Existing Endpoint)

```bash
# Delete an entire asset — all versions (existing delete endpoint)
curl -X DELETE http://localhost:5240/MAAS/a/v3/custom_images/42 \
  -H "$AUTH"
```

**Expected**: 204 No Content. All versions of the resource are removed.

**Note**: Per-version deletion is NOT supported. Deletion always removes the entire BootResource (all versions), consistent with custom images.

---

## Development Commands

```bash
# Run all tests
make test-py

# Run specific boot resource tests
python -m pytest src/tests/maasservicelayer/db/repositories/test_bootresources.py -v -k "custom_boot"
python -m pytest src/tests/maasservicelayer/services/test_bootresources.py -v -k "custom_boot"
python -m pytest src/tests/maasapiserver/v3/api/public/handlers/test_boot_resources.py -v
python -m pytest src/tests/maastemporalworker/workflow/test_bootresource.py -v -k "custom_boot_assets or sync_all_local"

# Generate builders after model changes
make generate-builders

# Create database migration
cd src/maasservicelayer && alembic revision --autogenerate -m "add unique constraints for custom boot assets"

# Lint
make lint-py
make format-py
```

---

## Key Files to Modify/Create

| Action | File |
|--------|------|
| Modify | `src/maasapiserver/v3/api/public/handlers/boot_resources.py` (add upload handlers + type filter to CustomImagesHandler) |
| Modify | `src/maasservicelayer/services/bootresources.py` (add upload + resolve methods) |
| Modify | `src/maasservicelayer/db/repositories/bootresources.py` (extend BootResourceClauseFactory + add query methods) |
| Modify | `src/maasservicelayer/db/tables.py` (add partial unique index definitions) |
| Create | `src/maasservicelayer/db/alembic/versions/XXXX_add_unique_constraints_for_custom_boot_assets.py` |
| Modify | `src/maasserver/api/machines.py` (add deploy params) |
| Modify | `src/maasserver/dhcp.py` (bootloader path in host declarations) |
| Modify | `tests/maasservicelayer/db/repositories/test_bootresources.py` (add custom boot asset tests) |
| Modify | `tests/maasservicelayer/services/test_bootresources.py` (add custom boot asset tests) |
| Modify | `tests/maasapiserver/v3/api/public/handlers/test_boot_resources.py` (add upload + filter tests) |
