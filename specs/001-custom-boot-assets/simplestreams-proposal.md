# Simplestreams Multi-Bootloader Index Format Proposal

**Feature**: Custom Boot Assets (FR-7)  
**Date**: 2025-07-23  
**Status**: DRAFT — for review by Simplestreams team and MAAS Site Manager team  
**Author**: MAAS team  

---

## 1. Background and Motivation

MAAS currently downloads bootloaders from a Simplestreams mirror using the
index file identified by:

```
content_id: com.ubuntu.maas:stable:1:bootloader-download
```

This index expresses **one canonical bootloader per `(arch, bootloader-type)`
pair**. A product key has the form:

```
com.ubuntu.maas.stable:1:{os}:{bootloader-type}:{arch}
```

For example:

```
com.ubuntu.maas.stable:1:grub-efi-signed:uefi:amd64
com.ubuntu.maas.stable:1:grub-ieee1275:open-firmware:ppc64el
com.ubuntu.maas.stable:1:pxelinux:pxe:amd64
```

Each product carries one or more versioned file sets (e.g. `grub2-signed`,
`shim-signed`). At sync time, MAAS stores these as `BootResource` records
with `rtype=SYNCED`.

**Limitation**: The current format cannot express multiple vendor-specific
bootloaders for the same `(arch, bootloader-type)` combination. As custom
boot assets become a supported feature (operators uploading their own
bootloaders via the v3 API), the Simplestreams mirror should be able to
distribute *additional* vendor/OEM bootloaders alongside the default one,
without replacing or modifying the existing index structure.

---

## 2. Current Format Description

### 2.1 Index entry (in `streams/v1/index.json`)

```json
{
  "com.ubuntu.maas:stable:1:bootloader-download": {
    "path": "streams/v1/com.ubuntu.maas:stable:1:bootloader-download.sjson",
    "updated": "Thu, 24 Jul 2025 09:01:42 +0000",
    "datatype": "image-ids",
    "format": "products:1.0",
    "products": [
      "com.ubuntu.maas.stable:1:grub-efi-signed:uefi:amd64",
      "com.ubuntu.maas.stable:1:grub-efi:uefi:arm64",
      "com.ubuntu.maas.stable:1:grub-ieee1275:open-firmware:ppc64el",
      "com.ubuntu.maas.stable:1:pxelinux:pxe:amd64"
    ]
  }
}
```

### 2.2 Product file structure

```json
{
  "content_id": "com.ubuntu.maas:stable:1:bootloader-download",
  "datatype": "image-ids",
  "format": "products:1.0",
  "updated": "Thu, 24 Jul 2025 09:01:42 +0000",
  "products": {
    "com.ubuntu.maas.stable:1:grub-efi-signed:uefi:amd64": {
      "arch": "amd64",
      "arches": "amd64",
      "bootloader-type": "uefi",
      "label": "stable",
      "os": "grub-efi-signed",
      "versions": {
        "20231004.0": {
          "items": {
            "grub2-signed": {
              "ftype": "archive.tar.xz",
              "path": "bootloaders/uefi/amd64/20231004.0/grub2-signed.tar.xz",
              "sha256": "5897d6ffc...",
              "size": 1228336,
              "src_package": "grub2-signed",
              "src_release": "jammy",
              "src_version": "1.187.6+2.06-2ubuntu14.4"
            },
            "shim-signed": {
              "ftype": "archive.tar.xz",
              "path": "bootloaders/uefi/amd64/20231004.0/shim-signed.tar.xz",
              "sha256": "4467e0cc7...",
              "size": 321940,
              "src_package": "shim-signed",
              "src_release": "jammy",
              "src_version": "1.51.3+15.7-0ubuntu1"
            }
          }
        }
      }
    }
  }
}
```

### 2.3 Key constraints of the current format

| Constraint | Detail |
|-----------|--------|
| **One product per `(arch, bootloader-type)`** | Product key encodes `os:bootloader-type:arch` — a second `uefi/amd64` product with a different `os` replaces the first at sync time |
| **Named file items** | Each file within a version set is keyed by a fixed name (`grub2-signed`, `shim-signed`, `grub2`, `syslinux`) |
| **No `name` field** | MAAS derives the `BootResource.name` from the product `os` field and the bootloader-type (`{os}/{bootloader-type}`) |
| **No `primary_file` field** | MAAS cannot determine which EFI binary to use for DHCP `option filename` from Simplestreams metadata alone |

---

## 3. Proposed New Companion Index Format

### 3.1 Design principles

1. **Additive, not destructive**: The existing `com.ubuntu.maas:stable:1:bootloader-download` index is **unchanged**. The new index is a companion published alongside it.
2. **Multiple bootloaders per arch**: The product key includes a `name` slug that disambiguates products with the same `(arch, bootloader-type)`.
3. **Single-tarball delivery**: Each version delivers a single tarball (`.tar.gz` or `.tar.xz`) that the MAAS upload endpoint already knows how to handle — extract with path-traversal checks, infer file list.
4. **Explicit `primary_file`**: The tarball's EFI entry-point filename is declared explicitly so MAAS can populate DHCP `option filename` without guessing.
5. **`name` field maps to `BootResource.name`**: The product `name` slug is the MAAS asset name (e.g. `custom/jammy`), enabling MAAS to upsert the resource predictably.
6. **`content_id` version bump**: The new index uses `com.ubuntu.maas:candidate:2:bootloader-download` to signal that consumers of this index must be MAAS ≥ 3.6 (which understands the new fields).

### 3.2 New `content_id`

```
com.ubuntu.maas:candidate:2:bootloader-download
```

The `candidate` channel indicates this is initially published on the candidate
stream; graduation to `stable` follows after MAAS and Site Manager validation.

### 3.3 Product key format

```
com.ubuntu.maas.candidate:2:{name_slug}:{bootloader-type}:{arch}
```

Where `name_slug` is the MAAS asset name with `/` replaced by `.`
(e.g. `custom/jammy` → `custom.jammy`).

### 3.4 New product fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | ✅ | MAAS asset name, e.g. `custom/jammy`. Maps directly to `BootResource.name`. |
| `arch` | ✅ | Target architecture (e.g. `amd64`). |
| `arches` | ✅ | Comma-separated arches string (e.g. `amd64`). |
| `bootloader-type` | ✅ | MAAS bootloader type: `uefi`, `open-firmware`, `pxe`. |
| `label` | ✅ | Stream label: `stable`, `candidate`. |
| `os` | ✅ | OS/vendor identifier (e.g. `grub-efi-signed`, `custom-vendor`). |
| `primary_file` | ✅ | Filename inside the tarball to use for DHCP `option filename` (e.g. `shimx64.efi`). |
| `description` | — | Human-readable description of this bootloader. |

### 3.5 Version file structure

Each version contains a **single** tarball item keyed `bootloader-tarball`:

| Field | Required | Description |
|-------|----------|-------------|
| `ftype` | ✅ | File type, e.g. `archive.tar.gz` or `archive.tar.xz`. |
| `path` | ✅ | Mirror-relative path to the tarball. |
| `sha256` | ✅ | SHA-256 hex digest of the tarball. |
| `size` | ✅ | Tarball size in bytes. |

---

## 4. Example JSON

### 4.1 Index entry addition (in `streams/v1/index.json`)

```json
{
  "com.ubuntu.maas:candidate:2:bootloader-download": {
    "path": "streams/v1/com.ubuntu.maas:candidate:2:bootloader-download.sjson",
    "updated": "Thu, 24 Jul 2025 09:01:42 +0000",
    "datatype": "image-ids",
    "format": "products:1.0",
    "products": [
      "com.ubuntu.maas.candidate:2:custom.jammy:uefi:amd64",
      "com.ubuntu.maas.candidate:2:vendor-shim.oem1:uefi:amd64",
      "com.ubuntu.maas.candidate:2:grub-open-firmware.r2:open-firmware:ppc64el"
    ]
  }
}
```

### 4.2 Product file (`com.ubuntu.maas:candidate:2:bootloader-download.sjson`)

```json
{
  "content_id": "com.ubuntu.maas:candidate:2:bootloader-download",
  "datatype": "image-ids",
  "format": "products:1.0",
  "updated": "Thu, 24 Jul 2025 09:01:42 +0000",
  "products": {
    "com.ubuntu.maas.candidate:2:custom.jammy:uefi:amd64": {
      "name": "custom/jammy",
      "arch": "amd64",
      "arches": "amd64",
      "bootloader-type": "uefi",
      "label": "candidate",
      "os": "grub-efi-signed",
      "primary_file": "shimx64.efi",
      "description": "Custom Jammy UEFI bootloader with OEM shim",
      "versions": {
        "20250723.0": {
          "items": {
            "bootloader-tarball": {
              "ftype": "archive.tar.gz",
              "path": "bootloaders/uefi/amd64/custom-jammy/20250723.0/bootloader.tar.gz",
              "sha256": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
              "size": 2457600
            }
          }
        },
        "20250801.0": {
          "items": {
            "bootloader-tarball": {
              "ftype": "archive.tar.gz",
              "path": "bootloaders/uefi/amd64/custom-jammy/20250801.0/bootloader.tar.gz",
              "sha256": "b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3",
              "size": 2461696
            }
          }
        }
      }
    },
    "com.ubuntu.maas.candidate:2:vendor-shim.oem1:uefi:amd64": {
      "name": "vendor-shim/oem1",
      "arch": "amd64",
      "arches": "amd64",
      "bootloader-type": "uefi",
      "label": "candidate",
      "os": "oem-shim",
      "primary_file": "shimx64-oem1.efi",
      "description": "OEM1 vendor-signed UEFI shim for specialised hardware",
      "versions": {
        "20250701.0": {
          "items": {
            "bootloader-tarball": {
              "ftype": "archive.tar.xz",
              "path": "bootloaders/uefi/amd64/vendor-shim-oem1/20250701.0/bootloader.tar.xz",
              "sha256": "c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4",
              "size": 1835008
            }
          }
        }
      }
    },
    "com.ubuntu.maas.candidate:2:grub-open-firmware.r2:open-firmware:ppc64el": {
      "name": "grub-open-firmware/r2",
      "arch": "ppc64el",
      "arches": "ppc64el,ppc64",
      "bootloader-type": "open-firmware",
      "label": "candidate",
      "os": "grub-ieee1275",
      "primary_file": "grub.elf",
      "description": "Updated GRUB for POWER9 r2 firmware variants",
      "versions": {
        "20250715.0": {
          "items": {
            "bootloader-tarball": {
              "ftype": "archive.tar.xz",
              "path": "bootloaders/open-firmware/ppc64el/grub-r2/20250715.0/bootloader.tar.xz",
              "sha256": "d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5",
              "size": 524288
            }
          }
        }
      }
    }
  }
}
```

---

## 5. Backward Compatibility

| Concern | Resolution |
|---------|-----------|
| **Existing `com.ubuntu.maas:stable:1:bootloader-download` index** | Completely unchanged. MAAS continues to sync default bootloaders from it exactly as before. |
| **MAAS versions < 3.6** | Older MAAS ignores `content_id` values it doesn't recognise. Because the new index uses a different `content_id`, older MAAS will skip it silently. |
| **MAAS Site Manager** | Must be updated to surface the new `candidate:2` stream in its mirror policy UI so operators can opt in. |
| **Simplestreams mirror infrastructure** | The new `.sjson` file is added alongside the existing one. No path conflicts. |
| **`BootResource` upsert** | MAAS `find_or_create_bootloader(name, architecture)` upserts on `(name, architecture, rtype=SYNCED)`. The `name` field from the product becomes `BootResource.name`, distinct from existing Simplestreams-synced names like `grub-efi-signed/uefi`. |
| **Two canonical bootloaders for same arch+type** | Both the old `grub-efi-signed/uefi` (from `:1:`) and any new `custom/jammy` (from `:2:`) can coexist in the DB. At deploy time the operator explicitly selects which one via `custom_bootloader=custom/jammy`; the default remains the Simplestreams canonical one. |

---

## 6. MAAS Implementation Notes

When MAAS processes a product from the `:2:bootloader-download` index, it:

1. Reads `product["name"]` as the `BootResource.name` (e.g. `custom/jammy`).
2. Reads `product["primary_file"]` and stores it in `BootResourceFile.extra["primary_file"]`.
3. Uses `find_or_create_bootloader(name=product["name"], architecture=product["arch"])` — same repository method used for admin-uploaded bootloaders.
4. Downloads the single `bootloader-tarball` item, verifies SHA-256, extracts with path-traversal checks.
5. Creates a `BootResourceSet` (version = version key, label = `product["label"]`) and one `BootResourceFile` entry per extracted file.
6. The asset is then selectable via `custom_bootloader=custom/jammy` at deploy time.

No new repository or service methods are required beyond what was implemented
for admin uploads (FR-1 through FR-6).

---

## 7. Migration Path

### Phase 1 — MAAS 3.6 (current sprint)

- [x] v3 API upload endpoints allow admin-uploaded custom bootloaders
- [x] `find_or_create_bootloader` handles both admin-uploaded (`rtype=UPLOADED`) and future Simplestreams-synced (`rtype=SYNCED`) assets via the same identity key `(name, architecture)`
- [ ] **Simplestreams client**: extend `BootloaderProduct` to accept `name` and `primary_file` optional fields (no breaking change — existing products omit them)
- [ ] **Image sync service**: when processing a `:2:bootloader-download` product, use `product.name` as `BootResource.name` instead of deriving it from `os` + `bootloader-type`

### Phase 2 — Simplestreams team

- [ ] Design and publish the `:2:bootloader-download` index to the candidate mirror
- [ ] Confirm `.sjson` path conventions and signing requirements with the MAAS images team
- [ ] Add 1–3 example multi-bootloader products (e.g. a second UEFI shim for `amd64`) for MAAS to test against

### Phase 3 — MAAS Site Manager

- [ ] Expose the new `candidate:2` stream in the boot source selection UI
- [ ] Allow operators to opt in to individual products (by `name` slug) rather than all-or-nothing per `bootloader-type`
- [ ] Display `primary_file` and `description` in the boot asset inventory view

### Phase 4 — Graduation

- [ ] After successful MAAS + Site Manager validation, graduate the new index from `candidate` to `stable` channel
- [ ] Update MAAS default boot source URL to include the `stable:2` index

---

## 8. Open Questions

| ID | Question | Owner |
|----|----------|-------|
| Q1 | Should the product key `name_slug` use `.` as separator or `-`? Both avoid `/` in JSON keys. | Simplestreams team |
| Q2 | Should `primary_file` be a full path within the tarball (e.g. `EFI/ubuntu/shimx64.efi`) or just the basename (`shimx64.efi`)? MAAS current upload code stores only the basename. | MAAS team |
| Q3 | Is the `.sjson` (signed JSON) format required for the new index, or can it be plain `.json` on the candidate stream? | Simplestreams/security team |
| Q4 | How should MAAS handle a product in `:2:` that has the same `(name, arch)` as an admin-uploaded asset? Prefer Simplestreams (overwrite) or prefer admin upload (skip)? | MAAS product team |
