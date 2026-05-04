# Feature Specification: Custom Boot Assets

**Feature Branch**: `6688-custom-boot-assets`  
**Created**: 2025-07-17  
**Status**: Clarified  
**Scope**: **SPIKE** — Exploratory/foundational implementation. Version usage tracking and garbage collection are deferred to a future iteration.  
**Input**: User description: "Custom bootloaders and kernels as first-class boot assets within MAAS, synchronized via Simplestreams, distributed as tarballs with isolated extraction, Rack Controller caching proxy, kernel+initrd pairs, OS/arch namespacing, deployment permission-based selection, and user-managed Secure Boot signing."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Upload Custom Bootloader Tarball (Priority: P1)

An infrastructure operator uploads a custom bootloader tarball to MAAS. The system extracts the tarball contents into a unique, isolated directory and makes the bootloader available for selection during machine deployment. The bootloader is synchronized across all Region Controllers via the existing Temporal boot asset sync workflow and cached by Rack Controllers. When a machine is assigned this bootloader, the DHCP configuration on the serving Rack Controller is updated to deliver the correct bootloader file to that machine (matched by MAC address via DHCP option 67).

**Why this priority**: Bootloader distribution is the foundational capability that enables all other custom boot asset features. Without it, no custom boot workflow is possible.

**Independent Test**: Can be fully tested by uploading a bootloader tarball and verifying it appears when querying the existing `/custom_images` endpoint (filtered by type=bootloader), is extracted to an isolated directory, and is accessible from a Rack Controller.

**Acceptance Scenarios**:

1. **Given** a valid bootloader tarball, **When** the operator uploads it via the MAAS interface, **Then** the tarball is extracted into a uniquely-named isolated directory and becomes available for deployment selection.
2. **Given** an uploaded bootloader, **When** a Rack Controller needs to serve it to a machine, **Then** the Rack Controller fetches the asset from the Region Controller if not already cached locally.
3. **Given** an uploaded bootloader, **When** another Region Controller synchronizes, **Then** the bootloader appears in that region's available bootloaders via the existing Temporal boot asset sync workflow.
4. **Given** a bootloader with the same name and architecture already exists, **When** a new upload is made matching these properties, **Then** a new version of the asset is created (following the same versioning convention as custom images). Previous versions are retained indefinitely (garbage collection is deferred to future work). Note: bootloader identity is `name + architecture` only; `kflavor` does not apply to bootloaders.
5. **Given** multiple versions of a bootloader exist, **When** a new deployment references this bootloader, **Then** the system always uses the latest version.

---

### User Story 2 - Upload Custom Kernel and Initrd Pair (Priority: P1)

An infrastructure operator uploads a custom kernel binary along with its associated initrd file as a complete asset pair. Both files are required together; MAAS rejects incomplete uploads. The kernel pair supports both ephemeral (in-memory) environments and final disk-based deployments.

**Why this priority**: Kernel management is equally critical to bootloader management. Machines cannot boot custom operating systems without both a kernel and initrd.

**Independent Test**: Can be fully tested by uploading a kernel+initrd pair and verifying both files are stored, associated with each other, and can be used for commissioning (ephemeral) and deployment (disk).

**Acceptance Scenarios**:

1. **Given** a kernel binary and its matching initrd file, **When** the operator uploads them, **Then** both are stored as an associated pair and made available for selection.
2. **Given** only a kernel binary without an initrd, **When** the operator attempts to upload, **Then** the system rejects the upload with a clear error indicating both files are required.
3. **Given** a valid kernel+initrd pair, **When** a machine is commissioned (ephemeral boot), **Then** the custom kernel and initrd are used for the ephemeral environment.
4. **Given** a valid kernel+initrd pair, **When** a machine is deployed to disk, **Then** MAAS serves the custom kernel and initrd to the deployment environment; Curtin (out of scope) is responsible for writing them to the target disk.

---

### User Story 3 - Organize Assets by Name and Properties (Priority: P2)

Assets (bootloaders and kernel pairs) are identified by a name that typically follows the `{os}/{series}` format (e.g., `ubuntu/jammy`, `ubuntu/noble`). Each asset carries the following properties as metadata on the boot asset record:
- **architecture** — a single field storing `{arch}/{subarch}` (e.g., `amd64/generic`, `arm64/generic`, `arm64/xgene-uboot`). The default subarch is `generic`.
- **kflavor** *(kernel assets only)* — the kernel flavour (e.g., `generic`, `lowlatency`, `hwe`). This property applies only to kernel boot assets (kernel+initrd pairs); bootloader assets do not carry a `kflavor`.

These properties are metadata on the boot asset record, not part of the name/identity. The uniqueness constraint differs by asset type:
- **Bootloader assets**: uniquely identified by `name + architecture`.
- **Kernel assets**: uniquely identified by `name + architecture + kflavor`.

**Why this priority**: Namespace organization is essential for multi-OS, multi-architecture environments, but the upload and serving mechanisms must exist first.

**Independent Test**: Can be tested by uploading assets for different OS/series and architecture/kflavor combinations and verifying they are correctly stored with their properties and retrievable independently.

**Acceptance Scenarios**:

1. **Given** a kernel pair uploaded with name `ubuntu/jammy`, architecture `amd64/generic`, and kflavor `generic`, **When** another kernel pair is uploaded with name `ubuntu/jammy`, architecture `arm64/generic`, and kflavor `generic`, **Then** both exist independently as distinct asset records distinguished by their architecture property.
2. **Given** assets with various properties, **When** listing available assets via the existing `/custom_images` endpoint, **Then** assets are filterable by type (bootloader, kernel, image), name, architecture, and kflavor using query parameters.
3. **Given** a machine with a known architecture, **When** selecting boot assets for deployment, **Then** only assets matching the machine's architecture are presented.

---

### User Story 4 - Explicit Asset Selection or Default to Official (Priority: P2)

A user with deployment permissions can explicitly select a specific custom boot asset by its name and matching architecture/kflavor properties for a deployment. The architecture field uses the `{arch}/{subarch}` format (e.g., `amd64/generic`). If no custom asset is selected, the system always uses the official Ubuntu boot asset synced from Simplestreams. There is no automatic selection or heuristic among custom assets. When a custom bootloader is selected, MAAS updates the DHCP configuration on the Rack Controller to deliver the correct bootloader to the target machine (matched by MAC address).

**Why this priority**: Asset selection provides operational flexibility but depends on assets being properly uploaded and namespaced first.

**Independent Test**: Can be tested by uploading multiple custom assets for the same OS/architecture, deploying a machine with explicit asset selection, and deploying another without selection (verifying it uses the official Simplestreams asset).

**Acceptance Scenarios**:

1. **Given** multiple custom boot assets exist for the same OS/architecture, **When** a user with deployment permissions deploys a machine, **Then** they can select a specific asset by its name (filtered to those matching the machine's architecture). The deployment always uses the latest version of the selected asset.
2. **Given** custom assets exist but the user does not select one, **When** deployment proceeds, **Then** the system uses the official Ubuntu boot asset from Simplestreams as the default.
3. **Given** a user without deployment permissions, **When** they attempt to select a boot asset, **Then** the system denies access with an appropriate permissions error.
4. **Given** a machine was deployed with version N of an asset, **When** version N+1 is uploaded, **Then** the already-deployed machine continues using version N until redeployed. New deployments use version N+1.

---

### User Story 5 - Rack Controller Caching Proxy (Priority: P3)

The Rack Controller already acts as a caching proxy for standard boot assets. Custom boot assets must be served through the same existing caching proxy infrastructure. When a machine requests a custom boot asset, the Rack Controller serves it from local cache if available, or fetches it from the Region Controller on a cache miss. Subsequent requests for the same asset are served from the local cache.

**Why this priority**: Leveraging the existing Rack caching proxy for custom assets requires integration work but is lower priority since the infrastructure already exists; core upload and metadata management must come first.

**Independent Test**: Can be tested by requesting an asset from a Rack Controller, verifying it fetches from the Region Controller on first access, and serves from cache on subsequent access.

**Acceptance Scenarios**:

1. **Given** a boot asset exists on the Region Controller but not on the Rack Controller, **When** a machine requests the asset via the Rack Controller, **Then** the Rack Controller fetches it from the Region, caches it locally, and serves it to the machine.
2. **Given** a boot asset is already cached on the Rack Controller, **When** a machine requests it, **Then** the Rack Controller serves it directly from local cache without contacting the Region Controller.
3. **Given** a cached asset version has been superseded by a newer version on the Region Controller, **When** the Temporal boot asset sync workflow runs, **Then** the Rack Controller's cache is updated with the new version. (Note: cleanup of old cached versions is deferred to future work along with garbage collection.)

---

## Out of Scope

- **Curtin-side deployment logic**: The actual installation of custom kernels and bootloaders onto the target machine's disk during deployment is performed by Curtin. Changes to Curtin required to support writing custom boot assets to disk are out of scope for this spec. A separate specification document will be produced for the Curtin team describing the required Curtin-side support.
- **MAAS Site Manager Simplestreams support**: The new Simplestreams index format for multiple bootloaders per architecture will also require changes in MAAS Site Manager. Site Manager updates are out of scope for this spec; the Site Manager team must be provided with the new index format specification to implement their own support.
- **Secure Boot signing automation**: MAAS does not sign binaries; signing is the user's responsibility.
- **Manual rollback to a previous version**: Operators cannot pin or manually select an older version of an asset; new deployments always use the latest version. Rollback requires re-uploading the desired content as a new version.
- **Version usage tracking**: Tracking which machines are using which version of a boot asset is deferred to a future iteration. This spike does not maintain references between deployed/queued machines and specific asset versions.
- **Garbage collection of old versions**: Automatic cleanup of old, unused asset versions is deferred to a future iteration. Old versions accumulate indefinitely in this spike; operators can manually delete versions without in-use protection (since usage is not tracked).

---

## Functional Requirements *(mandatory)*

### FR-1: Bootloader Tarball Upload and Extraction

The system must accept bootloader uploads in tarball format via the **v3 API** (FastAPI, `src/maasapiserver`) and extract their contents into an isolated directory. Each upload to the same composite identity (`name + architecture`) creates a new version of the asset (following the same versioning convention as custom images). Previous versions are retained indefinitely (garbage collection is deferred to future work). Note: `kflavor` is not part of bootloader identity.

### FR-2: Complete Kernel Asset Pair Enforcement

The system must require both a kernel binary and an associated initrd file for every kernel upload. Partial uploads (kernel without initrd, or initrd without kernel) are rejected with an informative error message.

### FR-3: Dual-Purpose Kernel Support

Uploaded kernel pairs must be usable for both ephemeral environments (commissioning, testing) and final disk deployments without requiring separate uploads for each use case. For disk deployments, MAAS is responsible for serving the assets to the deployment environment; the actual writing of kernel and initrd to the target disk is performed by Curtin (out of scope for this spec).

### FR-4: Asset Identity, Versioning, and Property Model

All boot assets are identified by a name that typically follows the `{os}/{series}` format (e.g., `ubuntu/jammy`, `ubuntu/noble`), though the name field is free-text. Each asset record carries the following properties as separate metadata fields:
- **architecture** — a single field storing the combined `{arch}/{subarch}` value (e.g., `amd64/generic`, `arm64/generic`, `arm64/xgene-uboot`). The default subarch is `generic`.
- **kflavor** *(kernel assets only)* — the kernel flavour (e.g., `generic`, `lowlatency`, `hwe`). This field is present only on kernel boot assets (kernel+initrd pairs); it is not applicable to bootloader assets.
- **version** — an auto-generated identifier (e.g., monotonically increasing integer or timestamp) assigned on each upload to the same composite key. Each upload creates a new version.

The uniqueness constraint differs by asset type:
- **Bootloader assets**: uniquely identified by `name + architecture + version`.
- **Kernel assets**: uniquely identified by `name + architecture + kflavor + version`.

The composite key for asset *identity* (excluding version) determines which asset "lineage" an upload belongs to:
- **Bootloader identity**: `name + architecture`.
- **Kernel identity**: `name + architecture + kflavor`.

Multiple versions of the same identity can coexist. New deployments always resolve to the latest version of the selected identity. Assets are looked up and matched to machines by name plus their architecture (and kflavor for kernels); version resolution is automatic (latest).

### FR-5: Inter-Region Synchronization via Temporal Workflow

Boot assets are synchronized between Region Controllers using an existing Temporal workflow that already handles boot asset distribution. Custom boot assets must be integrated into this same Temporal-based sync workflow — no new synchronization mechanism is required. New or updated custom assets must appear on other regions after the next sync cycle triggered by the workflow.

### FR-6: Rack Controller Caching Proxy

Rack Controllers must serve custom boot assets to machines by leveraging the existing Rack Controller caching proxy infrastructure (already used for standard boot assets). No new proxy mechanism is required. On cache miss, the Rack Controller fetches the asset from the Region Controller. Cached assets are served locally on subsequent requests.

### FR-7: Simplestreams Index Format Evolution for Multiple Bootloaders

The current Simplestreams bootloader index (`com.ubuntu.maas:candidate:1:bootloader-download.json`) supports only a single bootloader per architecture. To enable syncing multiple/custom bootloaders per architecture from Simplestreams, MAAS must:
1. Consume a **new** Simplestreams index file (format TBD via proposal — see External Dependencies) that supports multiple bootloader entries per architecture.
2. Continue consuming the **existing** index file for backward-compatible single-bootloader-per-arch sync (used by older MAAS versions).
3. When the new index is available, prefer it for bootloader discovery; fall back to the existing index if the new index is absent.

This requirement does not block the upload/management path (FR-1 through FR-6) but is required for full Simplestreams-based bootloader distribution to support multiple bootloaders per architecture.

### FR-8: Asset Selection (Explicit Only, Latest Version)

Users with deployment permissions must be able to explicitly select a specific custom boot asset for a deployment: by `name + architecture` for bootloaders, or by `name + architecture + kflavor` for kernel assets. The system automatically resolves the selection to the **latest version** of that asset identity. Users do not select a specific version — version resolution is always "latest". If no custom asset is explicitly selected, the system always uses the official Ubuntu boot asset synced from Simplestreams. There is no automatic selection heuristic among custom assets; custom assets are only used when a user explicitly chooses one.

**API layer**: Asset selection during deployment is performed via the **legacy v2 API** (Django, `src/maasserver`) deploy endpoint, as this endpoint does not yet have a v3 equivalent. Asset listing (for selection UIs) uses the **existing v3 `/custom_images` list endpoint** with filter parameters to retrieve only bootloader or kernel assets; no new list endpoint is needed.

### FR-9: Permission-Based Access Control

Only users with deployment permissions can select boot assets for deployment (via v2 deploy endpoint). Asset upload operations (new bootloader and kernel upload endpoints) are restricted to operators with appropriate administrative permissions and are served by the v3 API. Asset listing, retrieval, and deletion reuse the existing v3 `/custom_images` endpoints (which already enforce appropriate permissions).

### FR-10: No Signature Verification

MAAS does not perform cryptographic signature verification on uploaded boot assets. Secure Boot compliance and binary signing are entirely the responsibility of the user uploading the assets.

### FR-12: DHCP Configuration Update for Custom Bootloader Delivery

When a machine is assigned a custom bootloader (at deploy time or via machine configuration), MAAS must update the DHCP server configuration on the relevant Rack Controller to deliver the correct bootloader file to that specific machine. The DHCP server matches machines by MAC address and sets the appropriate boot filename (DHCP option 67) to point to the custom bootloader path. Without this update, PXE/network-booting machines would always receive the default bootloader regardless of custom bootloader assignment.

### FR-11: Asset Listing and Deletion (Reuse Existing Endpoints)

Custom bootloaders and kernel pairs share `rtype=UPLOADED` with custom images, so the **existing v3 `/custom_images` endpoints** (list, get by ID, delete by ID, bulk delete) apply to custom boot assets without modification. No new list or delete endpoints are required. The existing list endpoint gains filter parameters (e.g., `?type=bootloader|kernel|image`) to allow callers to retrieve only the relevant asset type.

Deletion operates at the **BootResource level** (all versions of an asset identity). Per-version deletion is **not supported** — this is consistent with how custom images work today. Since version usage tracking is not implemented in this spike, deletion is unconditional — no in-use protection is enforced. Operators are responsible for ensuring deleted assets are not actively needed by deployed machines.

Only new **upload** endpoints are required: one for bootloader tarballs (FR-1) and one for kernel+initrd pairs (FR-2), since their upload/processing logic differs from custom images.

---

## Success Criteria *(mandatory)*

1. **Asset availability**: Uploaded boot assets (new versions) are available for deployment within 5 minutes of upload across all connected Region Controllers.
2. **Cache efficiency**: After initial fetch, Rack Controllers serve cached boot assets without Region Controller involvement for at least 95% of requests.
3. **Upload validation**: 100% of incomplete kernel uploads (missing kernel or initrd) are rejected before storage.
4. **Multi-architecture support**: Operators can manage boot assets for at least 4 distinct identity combinations (bootloaders: name/architecture; kernels: name/architecture/kflavor) simultaneously without identity conflicts.
5. **Default boot asset behavior**: 100% of deployments without an explicit custom asset selection use the official Ubuntu boot asset from Simplestreams.
6. **Deployment success**: Machines boot successfully using custom boot assets in ephemeral mode with the same success rate as standard MAAS-provided assets. Disk deployment success additionally depends on Curtin support (out of scope).
7. **Permission enforcement**: Unauthorized users cannot select or modify boot asset assignments, with zero permission bypass incidents.
8. **Latest version resolution**: 100% of new deployments selecting a custom asset resolve to the latest uploaded version of that asset identity.
9. **DHCP bootloader delivery**: 100% of machines assigned a custom bootloader have their Rack Controller's DHCP configuration updated to serve the correct bootloader file (via DHCP option 67, matched by MAC address) before the machine's next PXE boot.

---

## Key Entities

| Entity | Description | Relationships |
|--------|-------------|---------------|
| Bootloader | A tarball containing bootloader files, extracted into an isolated directory | Identified by name (typically `{os}/{series}`); has `architecture` (format: `{arch}/{subarch}`, default subarch: `generic`); identity key: `name + architecture`; `kflavor` does NOT apply; versioned (each upload creates a new version) |
| Kernel Pair | A complete set of kernel binary + initrd file | Identified by name (typically `{os}/{series}`); has `architecture` (format: `{arch}/{subarch}`, default subarch: `generic`) and `kflavor` properties; identity key: `name + architecture + kflavor`; versioned (each upload creates a new version) |
| Boot Asset Identity | The composite key (varies by type) | Bootloaders: `name + architecture`; Kernel Pairs: `name + architecture + kflavor`; name is free-text but typically `{os}/{series}` (e.g., `ubuntu/jammy`); architecture stores `{arch}/{subarch}` (e.g., `amd64/generic`) |
| Boot Asset Version | A specific uploaded revision of a boot asset identity | Auto-generated on each upload; multiple versions coexist; old versions retained indefinitely (GC deferred to future work); new deployments always use latest version |
| Rack Controller Cache | Local copy of boot assets on a Rack Controller | References Boot Assets from Region via existing caching proxy |

---

## Security & Compliance

### Authorization

- **Asset Upload**: Restricted to operators with administrative permissions
- **Asset Selection for Deployment**: Requires deployment permissions on the target machine
- **Asset Listing**: Available to any authenticated user with view permissions

### User Responsibility

- **Secure Boot Signing**: MAAS does not verify signatures; users must ensure binaries are properly signed for Secure Boot environments
- **Asset Integrity**: Users are responsible for verifying the integrity and provenance of uploaded boot assets
- **Compliance**: Users must ensure uploaded assets comply with their organization's security policies

---

## Assumptions

- Inter-region synchronization of boot assets is performed by an existing Temporal workflow. Custom boot assets must extend/leverage this same Temporal workflow for region-to-region sync rather than introducing a separate mechanism.
- The existing Temporal boot asset sync workflow can accommodate custom boot asset distribution without architectural changes.
- Rack Controllers have sufficient local storage to cache the boot assets they serve. Typical asset sizes: bootloader tarballs are a few MB, kernel binaries are a few MB, and initrd files are a few hundred MB. Storage planning and transfer timeouts should account for these sizes.
- Upload size limits, if enforced, must accommodate initrd files up to several hundred MB. Any HTTP timeout or chunk-transfer configuration must allow completion of uploads at this scale over expected network conditions.
- The tarball format for bootloaders follows a conventional structure that MAAS can extract without special handling.
- When no custom boot asset is explicitly selected, the system always defaults to the official Ubuntu asset from Simplestreams. No automatic selection logic exists among custom assets.
- Operating system identifiers and architecture names follow established MAAS conventions (e.g., matching existing OS and architecture enumerations).
- Users uploading assets have verified them externally for functionality and security.
- Deploying custom kernels and bootloaders to disk (writing them to the target machine's filesystem) is performed by Curtin. Curtin changes are out of scope for this spec; a separate Curtin specification will be delivered to the Curtin team.
- **API layer constraint**: Only new **upload** endpoints (bootloader tarball upload, kernel+initrd pair upload) must be implemented in the **v3 API** (FastAPI, `src/maasapiserver`). Listing, retrieval, and deletion of custom boot assets reuse the **existing v3 `/custom_images` endpoints** (which already cover all `rtype=UPLOADED` BootResources), with filter parameters added to distinguish asset types. The deploy endpoint does not yet have a v3 equivalent, so deploy-time custom asset selection must be implemented in the **legacy v2 API** (Django, `src/maasserver`). No other v2/legacy API modifications should be made for this feature.
- **DHCP management**: MAAS manages the DHCP server configuration on Rack Controllers. When a machine is assigned a custom bootloader, MAAS updates the DHCP configuration to set the boot filename (DHCP option 67) for that machine's MAC address, ensuring PXE-booting machines receive the correct custom bootloader.
- **Simplestreams backward compatibility**: The existing Simplestreams bootloader index file (`https://images.maas.io/ephemeral-v3/candidate/streams/v1/com.ubuntu.maas:candidate:1:bootloader-download.json`) must NOT be modified. This index only supports one bootloader per architecture and is consumed by all existing MAAS versions. To support multiple bootloaders per architecture, a new companion index file must be introduced alongside the existing one. Older MAAS versions that do not understand the new index will continue to function using the existing index unchanged.

---

## External Dependencies & Deliverables

| Dependency | Owner | Description | Status |
|-----------|-------|-------------|--------|
| Curtin custom boot asset support | Curtin team | A specification document describing the changes Curtin needs to write custom kernels and bootloaders to the deployed machine's disk. To be produced as a deliverable of this feature's design phase. | Spec to be written |
| Simplestreams bootloader index format proposal | MAAS / Simplestreams team | The current bootloader Simplestreams index (`com.ubuntu.maas:candidate:1:bootloader-download.json`) only supports one bootloader per architecture. A proposal for a new index file format that supports multiple bootloaders per architecture must be produced. The existing index file must remain unchanged for backward compatibility with older MAAS versions; a new index file will be introduced alongside it. | Proposal to be written |
| MAAS Site Manager support for new Simplestreams index | Site Manager team | MAAS Site Manager also consumes the Simplestreams bootloader index and will need to be updated to support the new multi-bootloader index format. The Site Manager team must be provided with the finalised index format specification. Changes to Site Manager are out of scope for this spec. | Pending index format proposal |

---

## Clarifications

### Session 2025-07-17

- Q: Should custom boot asset caching on the Rack create new proxy infrastructure or reuse existing? → A: Leverage existing Rack caching proxy infrastructure.

### Session 2026-05-04

- Q: Should custom boot asset caching on the Rack create new proxy infrastructure or reuse existing? → A: Leverage existing Rack caching proxy infrastructure; the Rack already behaves as a caching proxy for boot assets.
- Q: What naming/versioning scheme identifies boot asset versions? → A: Boot assets are named as {os}/{series} (e.g., `ubuntu/jammy`); the name field is free-text but typically follows os/series format. Architecture stores `{arch}/{subarch}` (e.g., `amd64/generic`) in a single field, and kflavor is a separate property on the asset record.
- Q: How are multiple revisions of the same asset handled? → A: ~~Each upload replaces the previous content (single version only, no revision tracking).~~ **SUPERSEDED** — see Session 2025-07-18 below.
- Q: Can an in-use boot asset be deleted or replaced while deployments reference it? → A: ~~Allow deletion/replacement unconditionally.~~ **SUPERSEDED** — see Session 2025-07-18 below.
- Q: How does asset selection work when no custom asset is explicitly chosen? → A: The default boot asset is always the official Ubuntu asset synced from Simplestreams. Custom assets are ONLY used when a user explicitly selects one. There is no automatic selection heuristic among custom assets.
- Q: What are typical asset sizes and maximum upload constraints? → A: Bootloader tarballs are typically a few MB, kernel binaries are typically a few MB, and initrd files are typically a few hundred MB. Upload limits and transfer timeouts must accommodate these sizes.
- Q: How should custom boot assets be synchronized between Region Controllers? → A: Inter-region boot asset sync already uses a Temporal workflow. Custom boot assets must reuse the same existing Temporal workflow mechanism — no new sync mechanism should be designed.
- Q: Who is responsible for writing custom boot assets to the deployed machine's disk? → A: Curtin performs disk deployment of kernels/bootloaders. Curtin changes are out of scope; a separate spec will be produced for the Curtin team.
- Q: How are architecture/subarchitecture and kernel flavour related to boot asset identity? → A: There is a single `architecture` field that stores `{arch}/{subarch}` (e.g., `amd64/generic`, `arm64/generic`, `arm64/xgene-uboot`). The default subarch is `generic`. Kernel flavour is stored as a separate `kflavor` property. A boot asset is uniquely identified by name + architecture + kflavor.
- Q: Are architecture and subarchitecture stored as separate fields? → A: No. There is one `architecture` field storing `{arch}/{subarch}` as a combined value. The default subarch is `generic` (e.g., `amd64/generic`). The composite key is name + architecture + kflavor.
- Q: Does kflavor apply to all boot asset types? → A: No. `kflavor` is used only by kernel boot assets (kernel+initrd pairs). For bootloader assets, `arch + name` must be unique — the composite key is `name + architecture` only. For kernel assets, the composite key is `name + architecture + kflavor`.
- Q: Which API layer should new boot asset endpoints use? → A: ~~Only API v3 (FastAPI, `src/maasapiserver`) should be used for all new boot asset management endpoints (upload, list, delete).~~ **SUPERSEDED** — see Session 2025-07-22 below. Only new **upload** endpoints are needed in v3. Listing and deletion reuse existing `/custom_images` endpoints. The deploy endpoint (asset selection during deployment) has no v3 equivalent yet, so deploy-time asset selection must be implemented in the legacy v2 API (Django, `src/maasserver`). No other v2/legacy API changes should be made.
- Q: Does the current Simplestreams bootloader index support multiple bootloaders per architecture? → A: No. The existing index (`com.ubuntu.maas:candidate:1:bootloader-download.json`) supports only one bootloader per architecture. To support multiple/custom bootloaders per architecture, a new index file must be introduced alongside the existing one (backward compatibility is mandatory). A Simplestreams index format proposal is a deliverable of this feature.
- Q: Does the new Simplestreams index format affect MAAS Site Manager? → A: Yes. MAAS Site Manager also needs to support the new multi-bootloader Simplestreams index format, but Site Manager changes are out of scope for this spec. The Site Manager team must be provided with the finalised index format details.

- Q: How does the DHCP server deliver the correct bootloader to a specific machine? → A: MAAS updates the DHCP server configuration on the Rack Controller to set the boot filename (DHCP option 67) for the machine's MAC address, ensuring PXE-booting machines receive the correct custom bootloader.

### Session 2025-07-18

- Q: How are multiple revisions of the same asset handled (versioning model)? → A: **Custom boot assets follow the existing versioning convention for custom images**: each upload of a given asset (same composite identity key) generates a new version. Multiple versions coexist. Old versions are garbage-collected automatically ONLY when not in use by any existing machine (deployed or queued). New deployments always use the latest version. This supersedes the earlier "single version, replace on upload" answer.
- Q: Can an in-use boot asset version be deleted? → A: No. Old versions are protected while referenced by any machine. Deletion/garbage-collection occurs only for unreferenced versions. This supersedes the earlier "unconditional deletion" answer.
- Q: How is garbage collection of old boot asset versions performed? → A: GC is handled by the existing Temporal boot asset sync workflow — the same workflow that periodically synchronizes boot assets between Region Controllers. During its sync cycle, the workflow identifies and removes old versions no longer referenced by any machine. No separate GC mechanism or scheduled task is needed.

### Session 2025-07-21

- Q: What is the scope of this feature iteration? → A: This is a **SPIKE** (exploratory/foundational implementation). Version usage tracking (tracking which machines reference which asset versions) and garbage collection of old versions are deferred to future work. The versioning model stays (uploads create new versions, new deployments use latest), but no usage tracking or automatic cleanup is implemented in this iteration. Deletion is unconditional (no in-use protection since usage is not tracked). This supersedes the Session 2025-07-18 answers regarding GC and in-use deletion protection.

### Session 2025-07-22

- Q: Should custom boot assets have separate list/delete API endpoints or reuse existing ones? → A: Reuse existing v3 `/custom_images` endpoints for listing and deleting custom bootloaders and kernels (all share `rtype=UPLOADED`). Add filter parameters to the list endpoint (e.g., `?type=bootloader|kernel|image`). Deletion operates at the BootResource level (all versions); per-version deletion is NOT supported (consistent with custom images). Only new upload endpoints are needed (one for bootloader tarballs, one for kernel+initrd pairs).

---

## Future Work

The following capabilities are explicitly deferred from this spike and will be implemented in a subsequent iteration:

### Version Usage Tracking
- Track which machines (deployed or queued) reference which specific version of a boot asset.
- Maintain a reference count or association table between machine boot configurations and asset versions.
- Enable queries like "which machines are using version N of bootloader X?"

### Garbage Collection of Old Versions
- Automatically delete old asset versions that are no longer referenced by any machine.
- GC to be performed by the existing Temporal boot asset sync workflow during its periodic sync cycle.
- In-use protection: prevent deletion of versions still referenced by deployed/queued machines.
- Rack Controller cache cleanup of versions garbage-collected from the Region.

### Success Criteria (Deferred)
- **Version lifecycle**: Old asset versions referenced by deployed/queued machines are never garbage-collected while still in use. Garbage collection of unreferenced old versions is performed by the existing Temporal boot asset sync workflow during its periodic sync cycle.

---

## Open Questions

*All open questions have been resolved.*

---

**Next Step**: Implement per `plan.md` → Run `/speckit.plan` to generate detailed design.
