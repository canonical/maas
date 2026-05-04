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

### 1. Upload a Custom Bootloader

```bash
# Create a test bootloader tarball
mkdir -p /tmp/test-bootloader
echo "fake grub binary" > /tmp/test-bootloader/grubx64.efi
echo "fake shim binary" > /tmp/test-bootloader/shimx64.efi
tar -czf /tmp/test-bootloader.tar.gz -C /tmp/test-bootloader .

# Calculate SHA256
SHA256=$(sha256sum /tmp/test-bootloader.tar.gz | cut -d' ' -f1)

# Upload via v3 API (new endpoint)
curl -X POST http://localhost:5240/MAAS/api/v3/boot_assets/bootloaders \
  -H "Authorization: Bearer $TOKEN" \
  -F "name=ubuntu/jammy" \
  -F "architecture=amd64/generic" \
  -F "sha256=$SHA256" \
  -F "file=@/tmp/test-bootloader.tar.gz"
```

**Expected**: 201 response with asset details, version `YYYYMMDD`.

### 2. Upload a Custom Kernel Pair

```bash
# Create test kernel and initrd files
dd if=/dev/urandom of=/tmp/test-kernel bs=1M count=5
dd if=/dev/urandom of=/tmp/test-initrd bs=1M count=50

# Calculate SHA256s
KERNEL_SHA=$(sha256sum /tmp/test-kernel | cut -d' ' -f1)
INITRD_SHA=$(sha256sum /tmp/test-initrd | cut -d' ' -f1)

# Upload via v3 API (new endpoint)
curl -X POST http://localhost:5240/MAAS/api/v3/boot_assets/kernels \
  -H "Authorization: Bearer $TOKEN" \
  -F "name=ubuntu/noble" \
  -F "architecture=amd64/generic" \
  -F "kflavor=generic" \
  -F "kernel_sha256=$KERNEL_SHA" \
  -F "initrd_sha256=$INITRD_SHA" \
  -F "kernel=@/tmp/test-kernel" \
  -F "initrd=@/tmp/test-initrd"
```

**Expected**: 201 response with kernel pair details.

### 3. Verify Partial Upload Rejection

```bash
# Try uploading only a kernel (no initrd)
curl -X POST http://localhost:5240/MAAS/api/v3/boot_assets/kernels \
  -H "Authorization: Bearer $TOKEN" \
  -F "name=ubuntu/noble" \
  -F "architecture=amd64/generic" \
  -F "kflavor=generic" \
  -F "kernel_sha256=$KERNEL_SHA" \
  -F "kernel=@/tmp/test-kernel"
```

**Expected**: 400 response: "Both kernel and initrd files are required"

### 4. List and Filter Assets (Existing Endpoint)

```bash
# List all custom uploaded assets (existing behavior — includes bootloaders, kernels, images)
curl http://localhost:5240/MAAS/api/v3/custom_images \
  -H "Authorization: Bearer $TOKEN"

# Filter bootloaders only (new filter parameter)
curl "http://localhost:5240/MAAS/api/v3/custom_images?type=bootloader" \
  -H "Authorization: Bearer $TOKEN"

# Filter kernels only
curl "http://localhost:5240/MAAS/api/v3/custom_images?type=kernel" \
  -H "Authorization: Bearer $TOKEN"

# Filter plain images only (custom OS images, existing custom images)
curl "http://localhost:5240/MAAS/api/v3/custom_images?type=image" \
  -H "Authorization: Bearer $TOKEN"
```

### 5. Get Asset Details (Existing Endpoint)

```bash
# Get a specific asset by ID (works for bootloaders, kernels, or images)
curl http://localhost:5240/MAAS/api/v3/custom_images/42 \
  -H "Authorization: Bearer $TOKEN"
```

### 6. Deploy a Machine with Custom Boot Assets

```bash
# Deploy using custom bootloader and kernel (v2 API — extended with new params)
curl -X POST http://localhost:5240/MAAS/api/2.0/machines/$SYSTEM_ID/op-deploy \
  -d "distro_series=ubuntu/noble" \
  -d "custom_bootloader=ubuntu/jammy" \
  -d "custom_kernel=ubuntu/noble" \
  -d "custom_kernel_kflavor=generic" \
  -H "Authorization: oauth ..."
```

**Expected**: Machine deploys using the custom bootloader and kernel (latest versions).

### 7. Verify Version Resolution

```bash
# Upload a second version of the same bootloader
curl -X POST http://localhost:5240/MAAS/api/v3/boot_assets/bootloaders \
  -H "Authorization: Bearer $TOKEN" \
  -F "name=ubuntu/jammy" \
  -F "architecture=amd64/generic" \
  -F "sha256=$NEW_SHA256" \
  -F "file=@/tmp/test-bootloader-v2.tar.gz"

# List all — verify both versions visible via existing endpoint
curl "http://localhost:5240/MAAS/api/v3/custom_images?type=bootloader" \
  -H "Authorization: Bearer $TOKEN"
```

**Expected**: Asset listed; new deployments use the latest version.

### 8. Delete an Asset (Existing Endpoint)

```bash
# Delete an entire asset — all versions (existing delete endpoint)
curl -X DELETE http://localhost:5240/MAAS/api/v3/custom_images/42 \
  -H "Authorization: Bearer $TOKEN"
```

**Expected**: 204 No Content. All versions of the resource are removed.

**Note**: Per-version deletion is NOT supported. Deletion always removes the entire BootResource (all versions), consistent with custom images.

---

## Development Commands

```bash
# Run all tests
make test-py

# Run specific boot resource tests
python -m pytest tests/maasservicelayer/db/repositories/test_bootresources.py -v -k "custom_boot"
python -m pytest tests/maasservicelayer/services/test_bootresources.py -v -k "custom_boot"
python -m pytest tests/maasapiserver/v3/api/public/handlers/test_boot_resources.py -v

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
