# Research: Custom Boot Assets

**Feature Branch**: `6688-custom-boot-assets`  
**Date**: 2025-07-18  

---

## R1: Existing Boot Resource Data Model

**Decision**: Extend the existing `BootResource → BootResourceSet → BootResourceFile` three-tier storage model.

**Rationale**: The existing model already supports:
- `BootResource`: identity (name + architecture + rtype + kflavor + bootloader_type)
- `BootResourceSet`: versioning per resource (version string: `YYYYMMDD[.N]`)
- `BootResourceFile`: individual files per version (kernel, initrd, bootloader tarball contents)
- `BootResourceFileSync`: per-region sync tracking

Custom boot assets are logically the same as existing uploaded resources (`BootResourceType.UPLOADED = 2`). The existing table structure and unique constraints can accommodate the new feature with minimal schema changes.

**Alternatives considered**:
- New dedicated tables for custom boot assets → Rejected: duplicates existing infrastructure, breaks Temporal sync workflow compatibility
- Flat single-table approach → Rejected: loses versioning and file association

---

## R2: Versioning Convention

**Decision**: Use the existing `get_next_version_name()` pattern: `YYYYMMDD` with `.N` suffix for multiple uploads on the same day.

**Rationale**: Already implemented in `src/maasservicelayer/services/bootresources.py` (lines 138-168). The spec explicitly states "follows the same versioning convention as custom images." No new versioning logic needed.

**Implementation**: Call `get_next_version_name(boot_resource_id)` when creating a new `BootResourceSet` for an upload.

---

## R3: Asset Type Discrimination

**Decision**: Use the existing `rtype` field (value `UPLOADED = 2`) combined with `bootloader_type` field and file types to distinguish bootloader assets from kernel assets.

**Rationale**: 
- Bootloader assets: `bootloader_type` is set (non-null), files contain extracted tarball contents
- Kernel assets: `bootloader_type` is null, files contain `boot-kernel` and `boot-initrd` file types
- The `kflavor` field already exists on `BootResourceTable` and is used for kernel flavour discrimination

**Key insight**: The existing `BootResourceTable` already has `kflavor` and `bootloader_type` columns. The composite identity keys map naturally:
- Bootloader identity: `name + architecture` (kflavor is null)
- Kernel identity: `name + architecture + kflavor`

---

## R4: API Layer Strategy

**Decision**: 
- New **upload** endpoints only → v3 API (FastAPI, added to `CustomImagesHandler`)
- Listing, get-by-ID, delete, bulk-delete → **reuse existing** v3 `/custom_images` endpoints (no new handlers)
- Filter parameter (`type=bootloader|kernel|image`) added to existing list endpoint
- Deploy-time asset selection → v2 API (Django, `src/maasserver/api/machines.py`)
- Per-version deletion → NOT supported (deletion at BootResource level only, same as custom images)

**Rationale**: The existing `CustomImagesHandler` already filters by `rtype=UPLOADED`, which naturally includes all custom boot assets (bootloaders, kernels, and images). Creating separate list/get/delete endpoints would duplicate existing functionality. Only the upload endpoints need to be new because bootloader tarball extraction and kernel+initrd pair enforcement have distinct processing logic.

**Alternatives considered**:
- Separate `/boot_assets` list/delete endpoints → Rejected: duplicates existing `/custom_images` which already covers the same resources
- All in v3 API → Rejected: deploy endpoint has no v3 equivalent yet
- All in v2 API → Rejected: violates constitution (new features must use v3)
- Per-version deletion endpoint → Rejected: not consistent with custom images pattern; deletion is at resource level only

---

## R5: Temporal Workflow Integration

**Decision**: Extend existing Temporal boot resource sync workflow to include custom boot assets. GC extension is deferred.

**Rationale**: The existing workflow (`src/maastemporalworker/workflow/bootresource.py`) already handles:
- `SYNC_BOOTRESOURCES_WORKFLOW_NAME`: master sync orchestration
- `SYNC_ALL_LOCAL_BOOTRESOURCES_WORKFLOW_NAME`: local cache sync
- `DELETE_BOOTRESOURCE_WORKFLOW_NAME`: cleanup/deletion

Custom boot assets with `rtype=UPLOADED` should be included in the local sync workflow for Rack distribution. The existing `DELETE_BOOTRESOURCE_WORKFLOW_NAME` can be used for unconditional deletion when an admin requests it.

**Deferred**: Extending the GC activity to check machine references before deleting old versions is out of scope for this spike.

**Key files**:
- `src/maastemporalworker/workflow/bootresource.py`
- `src/maascommon/workflows/` (workflow name constants)

---

## R6: Rack Controller Caching

**Decision**: Leverage existing Rack caching proxy infrastructure without new proxy mechanisms.

**Rationale**: The Rack Controller already serves boot resources via TFTP/HTTP (`src/provisioningserver/boot/`). Boot methods (PXE, iPXE, GRUB) already resolve boot files from local cache. The existing `BootResourceFileSync` table tracks which files exist on which region, and the Temporal sync workflow distributes files to Racks.

Custom assets stored as `BootResourceFile` entries will be automatically picked up by the existing distribution pipeline.

---

## R7: Garbage Collection Strategy

**Decision**: Deferred to future work. Old versions are retained indefinitely in this spike.

**Rationale**: The spike focuses on the foundational upload/sync/deploy/DHCP flow. GC requires:
1. A `boot_resource_set_id` FK on the node table to track which version machines are using
2. Extension of cleanup activities to check machine references before deletion
3. Policy decisions about retention (keep N versions, time-based, etc.)

These complexities add significant scope without being required for the core functionality to work. The existing cleanup activity (`CLEANUP_BOOT_RESOURCE_SETS_FOR_SELECTION_ACTIVITY_NAME`) will NOT be extended to cover custom assets in this spike.

**Future work**: Add usage tracking FK, implement reference-aware GC, define retention policy.

---

## R8: Tarball Extraction Strategy

**Decision**: Extract bootloader tarballs to isolated directories under the boot resource storage path, with each extraction identified by the `BootResourceFile.filename_on_disk` convention.

**Rationale**: The existing `BootResourceFile` model already uses `filename_on_disk` for storage location. For tarballs:
1. Accept tarball upload (validated: `.tar.gz`, `.tar.xz`, `.tar.bz2`)
2. Extract to a unique directory (e.g., `bootloaders/{resource_id}/{set_id}/`)
3. Create `BootResourceFile` entries for each extracted file

**Security**: Validate tarball contents (no path traversal, no symlinks outside extraction root, reasonable file count/size limits).

---

## R9: Simplestreams New Index Format

**Decision**: Design a new companion index file alongside the existing `com.ubuntu.maas:candidate:1:bootloader-download.json`.

**Rationale**: Per the spec, the existing index is immutable for backward compatibility. The new index needs:
- Support for multiple bootloader entries per architecture
- Same Simplestreams v1 format conventions
- Fallback: if new index absent, use existing single-bootloader index

**Status**: This is a deliverable (proposal document) rather than immediate implementation. The upload/management path (FR-1 through FR-6) does not depend on this.

---

## R10: Deploy-Time Asset Selection Parameters

**Decision**: Add `custom_bootloader` and `custom_kernel` parameters to the v2 deploy endpoint.

**Rationale**: The existing deploy endpoint (`src/maasserver/api/machines.py`, line 726) already accepts `distro_series` and `hwe_kernel`. New parameters:
- `custom_bootloader`: name of custom bootloader asset (architecture auto-matched to machine)
- `custom_kernel`: name of custom kernel asset (architecture + kflavor matched)

Both parameters are optional. If not provided, the system uses official Ubuntu assets from Simplestreams (existing default behavior).

---

## R11: Permission Model

**Decision**: 
- Upload/delete/manage: Admin permission (existing `AdminPermission` check)
- Deploy-time selection: `NodePermission.edit` (existing deploy permission)
- Listing: `NodePermission.view` (any authenticated user)

**Rationale**: Maps directly to existing MAAS permission model. The v3 API handlers already use `@check_permissions()` decorators. The v2 deploy endpoint already checks `NodePermission.edit`.

---

## R12: Upload Size and Chunking

**Decision**: Use existing chunked upload pattern from `CustomImagesHandler` (4MB chunks, SHA256 validation).

**Rationale**: The existing custom image upload in `src/maasapiserver/v3/api/public/handlers/boot_resources.py` already handles:
- Chunked streaming (CHUNK_SIZE = 4 * 1024 * 1024)
- SHA256 hash verification
- Large file support

Initrd files (hundreds of MB) require this chunked approach. No new upload mechanism needed.

---

## R13: DHCP Configuration Update for Custom Bootloader Delivery

**Decision**: Trigger the existing `ConfigureDHCPWorkflow` Temporal workflow when a machine is assigned a custom bootloader at deploy time, passing the machine's static IP address IDs so the DHCP host declaration is regenerated with the correct boot filename.

**Rationale**: The existing DHCP configuration pipeline already supports per-host `filename` directives (DHCP option 67) via the template at `src/maasserver/templates/dhcp/dhcpd.conf.template`. Currently, boot filenames are set globally per subnet via `compose_conditional_bootloader()` which matches on architecture octets. For custom bootloaders, a per-host override is needed in the host declaration block (matched by MAC address).

**Key Mechanism**:
1. **Deploy-time trigger**: When the v2 deploy endpoint resolves a custom bootloader (`custom_bootloader` parameter), call `configure_dhcp_on_agents()` with the machine's `static_ip_addr_ids` to trigger a DHCP config update on the relevant Rack Controller.
2. **Host declaration enhancement**: The `make_hosts_for_subnets()` function in `src/maasserver/dhcp.py:322` builds host declarations with MAC + fixed IP. This must be extended to include a per-host `filename` directive when the machine has a custom bootloader assigned.
3. **Temporal workflow**: The existing `ConfigureDHCPWorkflow` → `ConfigureDHCPForAgentWorkflow` pipeline handles both full reload (via file) and partial update (via OMAPI). For custom bootloader changes, passing `static_ip_addr_ids` triggers the OMAPI-based partial update path for the affected host.

**Note (spike scope)**: Without a `boot_resource_set_id` FK on the node table, the DHCP config generation resolves the bootloader by looking up the machine's custom bootloader name (stored as deploy metadata) and resolving the latest version dynamically.

**Key Files**:
- `src/maasserver/dhcp.py`: `make_hosts_for_subnets()` — add `filename` to host dict when custom bootloader assigned
- `src/maasserver/templates/dhcp/dhcpd.conf.template` lines 170-192: host declaration template — add conditional `filename` directive
- `src/maastemporalworker/workflow/dhcp.py`: `DHCPConfigActivity._get_dhcp_host_reservations()` — include boot filename in host reservation data
- `src/maasserver/dhcpd/config.py`: `get_config_v4()` / `get_config_v6()` — ensure per-host filename overrides subnet-level bootloader

**Alternatives considered**:
- DHCP snippets approach (user creates DHCP snippet per machine) → Rejected: manual, error-prone, not automatable
- New dedicated DHCP workflow for bootloader updates → Rejected: existing `ConfigureDHCPWorkflow` already handles host-level updates via OMAPI
- Modify `compose_conditional_bootloader()` to be machine-aware → Rejected: that function generates subnet-level config; per-host overrides belong in host declarations

---

## R14: DHCP Host Declaration Boot Filename Override

**Decision**: Add an optional `bootloader_path` field to the host dictionary produced by `make_hosts_for_subnets()`. When present, the DHCP template renders a `filename` directive inside the host block, overriding the subnet-level conditional bootloader for that specific MAC address.

**Rationale**: ISC DHCP and the MAAS internal DHCP server both support per-host `filename` directives. A `filename` in a `host {}` block takes precedence over subnet-level `filename` directives, which is the standard mechanism for per-machine boot filename delivery.

**Template change** (dhcpd.conf.template host block):
```
host {{host['host']}}-{{host['mac'].replace(":", "-")}} {
    hardware ethernet {{host['mac']}};
    fixed-address {{host['ip']}};
    {{if host.get('bootloader_path')}}
    filename "{{host['bootloader_path']}}";
    {{endif}}
}
```

**Data flow**:
1. Machine deploy metadata contains custom bootloader name → resolve latest `BootResourceSet` → lookup `BootResourceFile` entries → compute path
2. `make_hosts_for_subnets()` queries machine's custom bootloader assignment (via deploy metadata)
3. If custom bootloader found → set `host['bootloader_path']` to the file path served by the Rack
4. Rack Controller serves the file from its local cache (FR-6) at that path

---

## R15: DHCP Update Timing and Consistency

**Decision**: DHCP configuration update must complete before the machine's PXE boot is initiated. The deploy action sequence is: assign bootloader → update DHCP → power on machine.

**Rationale**: If the machine powers on before DHCP is updated, it will receive the default bootloader. The Temporal workflow already has a timeout of 5 minutes for DHCP config application. The deploy endpoint must await DHCP workflow completion (or at minimum, workflow acceptance) before issuing the power-on command.

**Implementation approach**:
- The existing deploy flow in `src/maasserver/node_action.py` calls `self.node.start()` which powers on the machine
- Before `start()`, ensure `configure_dhcp_on_agents()` has been called with the machine's static IP IDs
- The Temporal workflow is fire-and-forget from the Region's perspective (async), but the DHCP update propagates to the Rack before the machine's BIOS completes POST (typically seconds for DHCP vs minutes for machine boot), providing natural timing safety
- For additional safety, the deploy transition could await workflow completion via Temporal's query interface, but this adds complexity and latency — recommend starting with the natural timing guarantee and adding explicit await only if real-world races are observed
