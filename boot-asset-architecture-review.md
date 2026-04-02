# Software Architecture Review: MAAS Boot Asset Evolution

**Review Date:** March 30, 2026  
**Reviewer:** Lead Software Architect  
**Scope:** Boot Asset Pipeline (Kernels, Initrds, Bootloaders)

---

## 1. Current Architecture Summary

### 1.1 Storage Architecture

MAAS implements a **content-addressable storage (CAS)** pattern for boot assets:

- **Physical Storage:** Files stored in `image-storage/` directory with filenames based on SHA256 hash prefixes (minimum 8 characters)
- **Deduplication:** Automatic at the file level—identical content (same SHA256) stored once
- **Virtual Paths:** Boot files referenced via constructed paths: `{filename_on_disk}/{osystem}/{arch}/{subarch}/{release}/{label}/{filename}`
- **Metadata Layer:** Database tracks BootResource → BootResourceSet → BootResourceFile relationships

**Key Files:**
- [maasservicelayer/utils/image_local_files.py](src/maasservicelayer/utils/image_local_files.py#L46-L62) - Storage abstraction
- [maasserver/models/bootresourcefile.py](src/maasserver/models/bootresourcefile.py#L43-L86) - File manager with deduplication

### 1.2 Synchronization Model

**Upstream → Region (Pull-based):**
- Temporal workflow `MasterImageSyncWorkflow` orchestrates SimpleStreams fetching
- Downloads to Region's `image-storage/` directory
- Progress tracked via `BootResourceFileSync` table per Region
- Workflow: [maastemporalworker/workflow/bootresource.py](src/maastemporalworker/workflow/bootresource.py#L580-L750)

**Region → Region (Push-based):**
- `SyncBootResourcesWorkflow` propagates files to all Region controllers
- Each Region downloads from any Region with complete copy (load-balanced)
- HTTP endpoints exposed on port 5240: `/MAAS/boot-resources/{filename_on_disk}/`
- Synchronization status tracked per (file, region) pair in `BootResourceFileSync`

**Region → Rack (Static deployment):**
- **No active synchronization** - Rack controllers serve from local Region's `image-storage/`
- Region exports images from DB to filesystem on startup ([bootresources.py:L250-L350](src/maasserver/bootresources.py#L250-L350))
- Racks access files via shared filesystem or HTTP proxy to Region

**Key Files:**
- [maastemporalworker/workflow/bootresource.py](src/maastemporalworker/workflow/bootresource.py#L656-L750) - Region sync workflow
- [maasserver/api/image_sync.py](src/maasserver/api/image_sync.py#L1-L111) - Sync progress API

### 1.3 Boot Configuration Generation

**RPC Flow:**
1. Rack receives PXE/TFTP request with MAC address
2. Rack calls Region RPC `GetBootConfig` with machine context
3. Region determines: osystem, series, arch, subarch, hwe_kernel
4. Region selects **latest complete BootResourceSet** for that BootResource
5. Region constructs virtual paths for kernel/initrd/rootfs
6. Rack serves files via TFTP/HTTP from `image-storage/`

**Path Construction Logic:**
```python
# From boot.py:_get_files_map()
path = f"{filename_on_disk}/{osystem}/{arch}/{subarch}/{series}/{label}/{filename}"
# Example: "a1b2c3d4/ubuntu/amd64/hwe-22.04/jammy/release/boot-kernel"
```

**Key Files:**
- [maasserver/rpc/boot.py](src/maasserver/rpc/boot.py#L111-L170) - Path construction
- [provisioningserver/rackdservices/tftp.py](src/provisioningserver/rackdservices/tftp.py#L77-L405) - TFTP backend

### 1.3.1 Critical Limitation: Non-Ubuntu Ephemeral Deployments

**The Problem:**  
MAAS currently **forces all ephemeral deployments of non-Ubuntu systems to boot with Ubuntu commissioning kernel** ([boot.py:L810-L826](src/maasserver/rpc/boot.py#L810-L826)):

```python
# If this is an ephemeral deployment of a non-official ubuntu image
if is_ephemeral and final_osystem != "ubuntu":
    if boot_osystem != "ubuntu":
        kernel_osystem, kernel_release = (
            configs["commissioning_osystem"],
            configs["commissioning_distro_series"],
        )
    # Forces Ubuntu kernel even when deploying RHEL!
    kernel, initrd, boot_dtb, _ = get_boot_filenames(
        arch, subarch, kernel_osystem, kernel_release
    )
```

**Impact on HPC Use Case:**
- **Cannot deploy RHEL ephemerally with RHEL kernel** - This is a hard blocker
- Hardware-specific drivers unavailable (InfiniBand, GPU compute, RDMA)
- Kernel modules for HPC interconnects not present
- Performance tuning and real-time patches from vendor kernel lost
- Security compliance may require vendor-signed kernels
- Testing environment doesn't match production environment

**Current Workaround:**
None. Customers must either:
1. Use persistent (slow) deployments that don't require ephemeral boot
2. Accept kernel mismatch risk
3. Modify MAAS source code

This architectural assumption blocks entire market segments.

### 1.4 Primary Gravity/Technical Debt

**The Monolithic Set Problem:**
- Boot configuration ALWAYS uses the "latest complete set" for a BootResource
- No mechanism for per-machine version pinning
- Changing default image affects ALL machines of that arch/OS simultaneously
- Rollback requires deleting newer BootResourceSets globally

**The Push-Everything Problem:**
- Synchronization pushes complete files to ALL Regions regardless of need
- No lazy loading or on-demand fetching
- Rack controllers have no awareness of available versions
- No tenant isolation for boot assets

**The Rigid Path Problem:**
- Virtual paths hardcoded in boot config generation
- No dynamic asset resolution based on machine state
- Cannot serve different kernel versions to different machines of same OS/arch
- Path structure assumes single version per (osystem, arch, subarch, series) tuple

**The Forced Ubuntu Kernel Problem:**
- **CRITICAL LIMITATION:** Ephemeral deployments of non-Ubuntu systems are hardcoded to use Ubuntu commissioning kernel ([boot.py:L810-L826](src/maasserver/rpc/boot.py#L810-L826))
- **HPC Use Case BLOCKED:** Cannot deploy RHEL ephemerally with native RHEL kernel
- Code explicitly forces: `kernel_osystem, kernel_release = (configs["commissioning_osystem"], configs["commissioning_distro_series"])`
- This breaks HPC workloads requiring specific kernel modules, drivers, or performance characteristics
- No policy mechanism to override this behavior

---

## 2. Architectural Improvement Proposals

### Proposal A: Asset Manifests with Lazy Resolution

**The Gap:**  
Currently, Rack controllers blindly serve whatever the Region tells them via `GetBootConfig`. There's no machine-specific asset versioning, and the Region must decide upfront which exact file paths to use. This prevents:
- Testing new kernels on a subset of machines
- Per-machine kernel pinning for stability
- Gradual rollout of boot asset updates

**The Fix:**  
Introduce an **Asset Manifest Service** that decouples asset selection from boot configuration:

1. **Manifest Repository:** Store lightweight JSON manifests describing available boot assets
   ```json
   {
     "asset_id": "ubuntu-jammy-hwe-22.04-amd64-v20260315",
     "osystem": "ubuntu",
     "series": "jammy", 
     "arch": "amd64",
     "subarch": "hwe-22.04",
     "files": {
       "kernel": {"sha256": "abc123...", "size": 8388608},
       "initrd": {"sha256": "def456...", "size": 52428800}
     }
   }
   ```

2. **Machine Asset Policy:** Add `boot_asset_policy` field to Machine model
   - `latest` (default) - current behavior
   - `pinned:<asset_id>` - lock to specific version
   - `canary` - opt into pre-release assets
   - `stable` - only production-validated assets

3. **Lazy Resolution:** Modify `GetBootConfig` to return asset_id + manifest URL instead of direct file paths

**Impact:**
- ✅ Per-machine kernel version control
- ✅ Blue/green deployments for boot assets
- ✅ Canary testing on subset of fleet
- ✅ Deterministic rollback without global changes
- ⚠️ Requires manifest sync mechanism (lightweight, can be eventual consistency)

**Implementation Files:**
- Add: `maasservicelayer/services/asset_manifests.py`
- Modify: [maasserver/rpc/boot.py](src/maasserver/rpc/boot.py#L480-L550) - `get_config()`
- Modify: [maasserver/models/node.py] - Add `boot_asset_policy` field

---

### Proposal B: Pull-Based Asset Caching on Racks

**The Gap:**  
Rack controllers currently rely on filesystem access to Region's `image-storage/` or HTTP proxy. This creates:
- Unnecessary storage duplication when multiple Racks serve same subnets
- Bandwidth waste when Racks re-download frequently
- No resilience if Region is temporarily unreachable
- Coupling between Region storage and Rack serving

**The Fix:**  
Implement **demand-driven caching** on Rack controllers:

1. **Local Asset Cache:** Each Rack maintains LRU cache in `/var/lib/maas/rack-cache/`
   - Indexed by SHA256 (already content-addressable)
   - Size-limited with eviction policy
   - Integrity verified on read

2. **Cache Miss Handler:** When TFTP/HTTP request arrives:
   ```python
   def serve_asset(sha256, virtual_path):
       local_file = rack_cache.get(sha256)
       if local_file and local_file.valid():
           return serve_file(local_file)
       
       # Cache miss - fetch from Region
       manifest = region_rpc.get_asset_manifest(sha256)
       local_file = fetch_and_cache(manifest.sources, sha256)
       return serve_file(local_file)
   ```

3. **Multi-Source Fetching:** Racks can pull from:
   - Local Region (primary)
   - Peer Racks with same asset (discovered via asset registry)
   - External cache/CDN if configured

**Impact:**
- ✅ Reduced storage footprint on Racks (only cache what's actively used)
- ✅ Bandwidth optimization through LRU eviction
- ✅ Improved resilience (Racks can serve from cache if Region down)
- ✅ Enables multi-tier caching strategies
- ⚠️ Complexity in cache invalidation
- ⚠️ Race condition on first boot if cache cold

**Implementation Files:**
- Add: `provisioningserver/cache/asset_cache.py`
- Modify: [provisioningserver/rackdservices/tftp.py](src/provisioningserver/rackdservices/tftp.py#L77-L160) - `TFTPBackend.get_reader()`
- Modify: [provisioningserver/rackdservices/http.py](src/provisioningserver/rackdservices/http.py#L246-L355) - `HTTPBootResource`

---

### Proposal C: Asset Metadata Service for Dynamic Path Resolution

**The Gap:**  
Boot file paths are constructed rigidly during `GetBootConfig` RPC:
```python
path = f"{filename_on_disk}/{osystem}/{arch}/{subarch}/{series}/{label}/{filename}"
```

This hardcodes a 1:1 mapping between (osystem, arch, subarch, series) and a file path. Critical problems:
- Cannot serve machine A with kernel v1 and machine B with kernel v2 if same OS/arch
- **Ephemeral non-Ubuntu deployments forced to use Ubuntu kernel** ([boot.py:L810-L826](src/maasserver/rpc/boot.py#L810-L826))
- **HPC use case broken:** Cannot deploy RHEL with native RHEL kernel for driver compatibility
- Path structure leaks internal storage details to boot logic
- No support for A/B testing or gradual rollouts
- Rollback requires deleting data

**The Fix:**  
Introduce **Asset Metadata Service** that resolves machine context to asset references:

1. **Asset Registry Table:**
   ```sql
   CREATE TABLE boot_asset_registry (
       id SERIAL PRIMARY KEY,
       asset_id VARCHAR(255) UNIQUE,
       osystem VARCHAR(64),
       series VARCHAR(64),
       arch VARCHAR(64),
       subarch VARCHAR(64),
       lifecycle_stage VARCHAR(32), -- 'canary', 'beta', 'stable', 'deprecated'
       metadata JSONB,
       created TIMESTAMP,
       promoted TIMESTAMP
   );
   ```

2. **Dynamic Resolution Service:**
   ```python
   class AssetResolver:
       def resolve_for_machine(self, machine: Node, purpose: str) -> AssetReference:
           policy = machine.boot_asset_policy or 'latest'
           
           if policy.startswith('pinned:'):
               return self.get_asset_by_id(policy.split(':')[1])
           
           candidates = self.find_assets(
               osystem=machine.osystem,
               series=machine.distro_series,
               arch=machine.architecture,
               lifecycle=self._map_policy_to_lifecycle(policy)
           )
           
           return self.select_best_match(candidates, machine.tags)
       
       def resolve_kernel_for_ephemeral(
           self, machine: Node, deployment_os: str, deployment_series: str
       ) -> AssetReference:
           """Determine which kernel to use for ephemeral deployment.
           
           This replaces the hardcoded logic in boot.py:L810-L826 that forces
           Ubuntu commissioning kernel for all non-Ubuntu deployments.
           """
           # Check for native kernel preference (HPC use case)
           if 'use-native-kernel' in machine.tags or machine.kernel_policy == 'native':
               # Use RHEL kernel for RHEL deployment
               return self.find_kernel_asset(
                   osystem=deployment_os,
                   series=deployment_series,
                   arch=machine.architecture
               )
           
           # Check for specific kernel override
           if machine.ephemeral_kernel_override:
               return self.get_asset_by_id(machine.ephemeral_kernel_override)
           
           # Default: fall back to commissioning kernel (current behavior)
           return self.find_kernel_asset(
               osystem='ubuntu',
               series=self.config.commissioning_distro_series,
               arch=machine.architecture
           )
   ```

3. **HPC Use Case Example (RHEL with RHEL kernel):**
   ```python
   # Machine tagged for HPC workload
   machine = Node.objects.get(system_id='abc123')
   machine.tags.add('use-native-kernel', 'hpc-compute')
   machine.osystem = 'rhel'
   machine.distro_series = '9'
   machine.ephemeral_deploy = True
   
   # Asset resolver determines kernel
   resolver = AssetResolver()
   kernel_ref = resolver.resolve_kernel_for_ephemeral(
       machine, 
       deployment_os='rhel',
       deployment_series='9'
   )
   # Returns: AssetReference(asset_id='rhel-9-kernel-5.14', sha256='abc...')
   # NOT the Ubuntu commissioning kernel!
   
   rootfs_ref = resolver.resolve_for_machine(machine, purpose='xinstall')
   # Returns: AssetReference(asset_id='rhel-9-rootfs', sha256='def...')
   ```

4. **Serving Layer Indirection:**
   Instead of returning file paths, `GetBootConfig` returns:
   ```python
   {
       "kernel": {"asset_ref": "asset://rhel-9-kernel/abc123"},
       "initrd": {"asset_ref": "asset://rhel-9-initrd/def456"},
       "rootfs": {"asset_ref": "asset://rhel-9-rootfs/ghi789"}
   }
   ```
   
   Rack resolves `asset://` URLs via local cache or Region lookup.

**Impact:**
- ✅ **SOLVES HPC USE CASE:** Native kernel support for RHEL/CentOS ephemeral deployments
- ✅ Decouple machine state from asset selection
- ✅ Enable progressive rollouts (10% canary → 50% beta → 100% stable)
- ✅ No-downtime asset updates
- ✅ Machine-specific overrides via tags/annotations (`use-native-kernel`, `hpc-compute`)
- ✅ Better observability (track which machines use which assets)
- ✅ Remove hardcoded Ubuntu kernel assumption
- ⚠️ Requires migration of path-based logic
- ⚠️ Backward compatibility complexity

**Implementation Files:**
- Add: `maasservicelayer/services/asset_resolver.py`
- Add: `maasservicelayer/db/tables.py` - BootAssetRegistryTable
- Modify: [maasserver/rpc/boot.py](src/maasserver/rpc/boot.py#L172-L210) - Replace `get_boot_filenames()`
- Modify: [provisioningserver/rackdservices/tftp.py](src/provisioningserver/rackdservices/tftp.py#L200-L310) - Asset URI resolution

---

### Proposal D: Content-Addressable Network (CAN) for Multi-Region Scale

**The Gap:**  
Current Region-to-Region sync uses HTTP endpoints (`/MAAS/boot-resources/{filename}/`) with manual source selection. This is simple but doesn't scale well:
- No peer discovery (must know all Region IPs upfront)
- No load balancing beyond random source selection
- Single Region failure can block sync for downstream Regions
- Bandwidth inefficient for large deployments (no delta sync)

**The Fix:**  
Implement a **distributed hash table (DHT)** for asset location and retrieval:

1. **Asset Location Registry:**
   Each Region publishes availability to shared registry (Redis/etcd):
   ```
   SET boot-asset:sha256:abc123 '["region-1", "region-2", "region-3"]'
   SET region:region-1:health '{"status": "healthy", "load": 0.3}'
   ```

2. **Smart Source Selection:**
   ```python
   async def fetch_asset(sha256: str) -> AsyncIterator[bytes]:
       # Get all Regions with this asset
       sources = await registry.get_sources(sha256)
       
       # Filter by health and proximity
       healthy = [s for s in sources if s.health == 'healthy']
       nearest = sort_by_network_distance(healthy, current_region)
       
       # Try sources with exponential backoff
       for source in nearest[:MAX_SOURCES]:
           try:
               return await source.stream_asset(sha256)
           except TransientError:
               continue
       
       raise AssetUnavailableError(sha256)
   ```

3. **Chunk-Level Deduplication:**
   For large files (>100MB), use chunked transfer with zsync-style delta sync:
   - Split files into 4MB chunks, each with SHA256
   - Only transfer chunks not already present
   - Reassemble on destination

**Impact:**
- ✅ Automatic failover on Region failure
- ✅ Load distribution across healthy Regions
- ✅ Bandwidth savings via delta sync
- ✅ Scales to 100+ Region deployments
- ⚠️ Operational complexity (need reliable registry)
- ⚠️ Chunking adds metadata overhead

**Implementation Files:**
- Add: `maasservicelayer/services/asset_registry.py`
- Modify: [maastemporalworker/workflow/bootresource.py](src/maastemporalworker/workflow/bootresource.py#L656-L750) - Smart source selection
- Add: `maascommon/utils/chunked_transfer.py`

---

## 3. Critical Flags (Need Information)

### [maasserver/rpc/boot.py:L810-L826](src/maasserver/rpc/boot.py#L810-L826) - Hardcoded Ubuntu Kernel for Ephemeral Non-Ubuntu

**Concern:** HPC use case completely blocked by architectural assumption

**Current Code:**
```python
# If this is an ephemeral deployment of a non-official ubuntu image
if is_ephemeral and final_osystem != "ubuntu":
    # If boot_osystem != "ubuntu", it means we have to use the commissioning kernel/series.
    if boot_osystem != "ubuntu":
        kernel_osystem, kernel_release = (
            configs["commissioning_osystem"],
            configs["commissioning_distro_series"],
        )

    kernel, initrd, boot_dtb, _ = get_boot_filenames(
        arch, subarch, kernel_osystem, kernel_release
    )
```

**Problem:** This code **forces all ephemeral RHEL/CentOS deployments to use Ubuntu commissioning kernel**. This is a hard architectural constraint with no escape hatch.

**HPC Impact:**
- Cannot deploy RHEL with native RHEL kernel for driver compatibility
- Hardware-specific kernel modules unavailable (InfiniBand, GPU drivers, custom network adapters)
- Performance characteristics differ from production environment
- Security policies may require kernel from vendor-signed images
- Breaks parity between ephemeral and persistent deployments

**Risk:**
- **BLOCKER** for HPC/scientific computing deployments
- No workaround without source code modification
- Forces customers to use persistent (slow) deployments or accept kernel mismatch

**Recommendation:**
- **SHORT TERM:** Add `Machine.kernel_policy` field:
  ```python
  if machine.kernel_policy == 'native' or 'use-native-kernel' in machine.tags:
      kernel_osystem, kernel_release = final_osystem, final_series
  else:
      kernel_osystem, kernel_release = commissioning_osystem, commissioning_series
  ```

- **LONG TERM:** Implement Proposal C (Asset Metadata Service) to remove hardcoded kernel selection entirely

---

### [maastemporalworker/workflow/bootresource.py:L686-L695](src/maastemporalworker/workflow/bootresource.py#L686-L695) - State Conflict

**Concern:** Race condition during concurrent Region sync

**Current Code:**
```python
synced_regions: list[str] = await workflow.execute_activity(
    GET_SYNCED_REGIONS_ACTIVITY_NAME,
    arg=input.resource.rfile_ids[0],
    start_to_close_timeout=timedelta(seconds=30),
)

if not synced_regions:
    raise ApplicationError(
        f"File {input.resource.sha256} has no complete copy available"
    )
```

**Question:** What happens if a machine requests an asset that exists in the database (`BootResourceFile.complete == False`) but hasn't finished downloading to ANY Region yet?

**Risk:**
- Machine boot fails unnecessarily
- No queuing mechanism for pending assets
- Temporal workflow failure doesn't distinguish between "asset will never exist" vs "asset not ready yet"

**Recommendation:** Implement asset readiness checks in `GetBootConfig` and return specific error codes:
- `ASSET_PENDING` - Download in progress, retry later
- `ASSET_FAILED` - Download failed, use fallback
- `ASSET_NOT_FOUND` - No such asset configured

---

### [maasserver/bootresources.py:L250-L350](src/maasserver/bootresources.py#L250-L350) - Failure Mode

**Concern:** Region failure during boot asset serving

**Current Behavior:**
- Racks serve via HTTP from Region's `image-storage/` directory (either shared FS or HTTP proxy)
- If Region is down, Racks cannot serve boot assets
- No local caching on Rack controllers

**Question:** Is this intentional or technical debt? Do we accept that Region downtime = boot service downtime?

**Observed Code:**
```python
# provisioningserver/rackdservices/http.py:L246-L270
class HTTPBootResource(resource.Resource):
    def render_GET(self, request):
        # Delegates to TFTP backend which reads from shared FS
        d = context.call(
            {
                "local": (localHost, localPort),
                "remote": (remoteHost, remotePort),
            },
            tftp.backend.get_reader,
            path,
            skip_logging=True,
            protocol="http",
        )
```

**Risk:**
- Single point of failure for boot services
- No degraded mode operation
- Racks cannot serve from cache during Region maintenance

**Recommendation:** Implement Proposal B (Pull-Based Asset Caching on Racks) to enable degraded mode operation.

---

### [maasserver/rpc/boot.py:L111-L145](src/maasserver/rpc/boot.py#L111-L145) - Consistency Guarantee

**Concern:** Atomicity of BootResourceSet selection

**Current Code:**
```python
def _get_files_map(...):
    boot_resource = BootResource.objects.get(
        architecture=f"{arch}/{subarch}",
        name=name,
    )
    bset = boot_resource.get_latest_complete_set()
    return {
        bfile.filetype: "/".join([
            bfile.filename_on_disk,
            osystem, arch, subarch, oseries, bset.label, bfile.filename,
        ])
        for bfile in bset.files.all()
    }
```

**Question:** What guarantees exist that `bset.files.all()` returns a consistent snapshot? Could a file be deleted between `get_latest_complete_set()` and the iteration?

**Scenario:**
1. Machine A requests boot config at T0
2. Admin initiates cleanup workflow at T1 (deletes old BootResourceSet)
3. Boot config generation at T2 tries to construct paths
4. Files might be partially deleted

**Risk:**
- Race condition during cleanup
- Partial boot configurations with missing files
- No transactional guarantees across BootResourceSet selection

**Recommendation:**
- Add database transaction isolation to `get_config()` 
- OR snapshot BootResourceSet state at selection time
- OR implement soft-delete with grace period

---

### [maastemporalworker/workflow/bootresource.py:L200-L280](src/maastemporalworker/workflow/bootresource.py#L200-L280) - Disk Space Check

**Concern:** Out-of-disk detection is reactive, not proactive

**Current Code:**
```python
except LocalStoreAllocationFail as e:
    await self.report_progress(param.rfile_ids, 0)
    raise ApplicationError(
        "No space left on disk", non_retryable=True
    ) from e
except IOError as ex:
    if ex.errno == 28:  # ENOSPC
        logger.error(ex.strerror)
        raise ApplicationError(
            "No space left on disk", non_retryable=True
        ) from ex
```

**Question:** Why is disk space checked DURING download rather than BEFORE workflow start?

**Risk:**
- Wasted bandwidth downloading files that won't fit
- Partial files consume space
- No pre-flight validation in `MasterImageSyncWorkflow`

**Observed Note in AGENTS.md:**
```
# From commit message for feat(bootresources):
- Don't export images from DB if they don't fit in the disk
- Don't retry downloads on out-of-disk errors
- Notify user about out-of-disk errors
```

This suggests awareness of the problem but implementation is still reactive.

**Recommendation:**
```python
@activity_defn_with_context(name="check-disk-space")
async def check_available_disk_space(self, required_bytes: int) -> bool:
    store_path = get_bootresource_store_path()
    stat = os.statvfs(store_path)
    available = stat.f_bavail * stat.f_frsize
    # Include 10% buffer for metadata/overhead
    return available > (required_bytes * 1.1)

# In MasterImageSyncWorkflow, before download:
total_size = sum(file.size for file in files_to_download)
can_fit = await workflow.execute_activity(
    "check-disk-space",
    total_size,
    start_to_close_timeout=timedelta(seconds=10),
)
if not can_fit:
    raise ApplicationError("Insufficient disk space", non_retryable=True)
```

---

## 4. Implementation Nit-picks

### [maasserver/models/bootresourcefile.py:L43-L86](src/maasserver/models/bootresourcefile.py#L43-L86) - Missing Type Hints

**Issue:** Manager methods lack return type annotations

```python
# Current
def filestore_remove_file(self, rfile: BootResourceFile):
    qs = self.filter(sha256=rfile.sha256).exclude(id=rfile.id)
    # ...

# Should be
def filestore_remove_file(self, rfile: BootResourceFile) -> None:
    qs = self.filter(sha256=rfile.sha256).exclude(id=rfile.id)
    # ...
```

**Impact:** Minor - reduces IDE code intelligence and type safety

---

### [maasservicelayer/services/bootresourcefiles.py:L51-L86](src/maasservicelayer/services/bootresourcefiles.py#L51-L86) - Collision Detection is O(n)

**Issue:** SHA256 prefix collision detection iterates all matching prefixes

```python
async def calculate_filename_on_disk(self, sha256: str) -> str:
    # ... 
    for i in range(SHORTSHA256_MIN_PREFIX_LEN + 1, 64):
        sha = sha256[:i]
        if all(not f.filename_on_disk.startswith(sha) for f in collisions):
            return sha
```

**Recommendation:** Use trie-based index for O(log n) lookup or database prefix query:
```python
collision_count = await self.repository.count_prefix_matches(sha256[:i])
```

**Impact:** Low - only affects bulk import scenarios, not runtime performance

---

### [maascommon/workflows/bootresource.py:L1-L30](src/maascommon/workflows/bootresource.py#L1-L30) - Magic Constants

**Issue:** Timeout values scattered throughout codebase

```python
REPORT_INTERVAL = timedelta(seconds=10)
HEARTBEAT_TIMEOUT = timedelta(seconds=10)
DISK_TIMEOUT = timedelta(minutes=15)
DOWNLOAD_TIMEOUT = timedelta(hours=2)
```

**Recommendation:** Move to configuration with environment variable overrides for testing:
```python
@dataclass
class BootResourceWorkflowConfig:
    report_interval: timedelta = field(
        default_factory=lambda: timedelta(
            seconds=int(os.getenv('MAAS_BOOT_REPORT_INTERVAL', '10'))
        )
    )
```

**Impact:** Low - improves testability

---

### [provisioningserver/rackdservices/tftp.py:L77-L160](src/provisioningserver/rackdservices/tftp.py#L77-L160) - Client Caching by IP

**Issue:** RPC client cached by remote_ip could be problematic with NAT

```python
def get_client_for(self, params):
    remote_ip = params.get("remote_ip")
    if remote_ip:
        client = self.client_to_remote.get(remote_ip, None)
```

**Concern:** Multiple machines behind NAT would share same RPC client, potentially causing request fanout consolidation bugs

**Recommendation:** Document this behavior or use (remote_ip, remote_port) tuple as key

**Impact:** Low - edge case in NAT scenarios

---

### [maasservicelayer/db/repositories/bootresources.py:L89-L100](src/maasservicelayer/db/repositories/bootresources.py#L89-L100) - N+1 Query Pattern

**Issue:** Selection validation iterates selections without eager loading

```python
@classmethod
def with_selection_boot_source_id(cls, boot_source_id: int) -> Clause:
    return Clause(
        condition=eq(
            BootSourceSelectionTable.c.boot_source_id, boot_source_id
        ),
        joins=[
            join(
                BootSourceSelectionTable,
                BootResourceTable,
                eq(
                    BootResourceTable.c.selection_id,
                    BootSourceSelectionTable.c.id,
                ),
            )
        ],
    )
```

This forces a JOIN every time. Should prefetch selections when loading BootResources.

**Recommendation:** Add repository method:
```python
async def get_many_with_selections(
    self, query: QuerySpec
) -> list[tuple[BootResource, BootSourceSelection]]:
    # Single query with LEFT JOIN
```

**Impact:** Medium - affects image listing performance in UI

---

## 5. Standards Compliance Check

### AGENTS.md Alignment

✅ **Three-tier architecture:** Proposals A & C align with service layer pattern  
✅ **Type hints:** New code would use Pydantic models and full type coverage  
✅ **Testing:** Each proposal would include repository + service + integration tests  
⚠️ **RPC overhead:** Proposal C increases RPC calls (asset resolution), needs caching  

### Cloud-Init/Curtin Integration

✅ **Proposal A (Manifests):** Simplifies preseed templates - asset selection decoupled from cloud-init  
⚠️ **Proposal B (Rack caching):** Adds latency on cache miss - first boot might be slower  
✅ **Proposal C (Dynamic resolution):** No impact - asset URIs resolved before curtin runs  

---

## 6. Migration Path Recommendations

### Phase 0: Critical HPC Blocker Fix (1-2 months)
**Unblock RHEL ephemeral deployments immediately:**

1. Add `kernel_policy` field to Node model:
   ```python
   # maasserver/models/node.py
   class Node(CleanSave, TimestampedModel):
       # ... existing fields ...
       kernel_policy = CharField(
           max_length=32,
           choices=[
               ('auto', 'Automatic (Ubuntu for non-Ubuntu)'),
               ('native', 'Use OS-native kernel'),
               ('commissioning', 'Always use commissioning kernel'),
           ],
           default='auto',
           help_text="Kernel selection policy for ephemeral deployments"
       )
   ```

2. Modify boot config logic ([boot.py:L810-L826](src/maasserver/rpc/boot.py#L810-L826)):
   ```python
   # Replace hardcoded logic with policy check
   if is_ephemeral and final_osystem != "ubuntu":
       use_native_kernel = (
           machine is not None and 
           (machine.kernel_policy == 'native' or 
            'use-native-kernel' in machine.tags)
       )
       
       if use_native_kernel:
           # HPC use case: use RHEL kernel for RHEL deployment
           kernel_osystem, kernel_release = final_osystem, final_series
       elif boot_osystem != "ubuntu":
           # Legacy behavior: fall back to commissioning kernel
           kernel_osystem, kernel_release = (
               configs["commissioning_osystem"],
               configs["commissioning_distro_series"],
           )
       
       kernel, initrd, boot_dtb, _ = get_boot_filenames(
           arch, subarch, kernel_osystem, kernel_release
       )
   ```

3. Add API/UI controls:
   - WebUI: Add kernel policy dropdown in machine edit form
   - CLI: `maas $PROFILE machine set-kernel-policy $SYSTEM_ID native`
   - Tag-based: Allow `use-native-kernel` tag for bulk operations

**Impact:**
- ✅ Unblocks HPC customers immediately
- ✅ Minimal code change (10-20 lines)
- ✅ Backward compatible (default='auto' preserves current behavior)
- ✅ Provides escape hatch while longer-term solution developed

### Phase 1: Non-Breaking Enhancements (3-6 months)
1. Implement Proposal B (Rack caching) as opt-in feature
2. Add disk space pre-checks to workflows
3. Fix critical race conditions (state conflict, consistency)
4. Add observability (asset usage metrics)

### Phase 2: Gradual Decoupling (6-12 months)
1. Introduce Asset Metadata Service (Proposal C) alongside existing path logic
2. Dual-write to both systems during migration
3. Add feature flag for machine-specific asset selection
4. Migrate 10% → 50% → 100% of boot configs

### Phase 3: Scale & Polish (12+ months)
1. Implement Asset Manifests (Proposal A) for all boot types
2. Deploy Content-Addressable Network (Proposal D) for large deployments
3. Deprecate old path-based boot config
4. Remove legacy BootResourceSet.get_latest_complete_set() logic

---

## 7. Summary

**Current State Strengths:**
- ✅ Content-addressable storage with automatic deduplication
- ✅ Temporal workflows provide reliability and observability  
- ✅ Clear separation between Region (orchestration) and Rack (serving)

**Primary Improvement Opportunities:**
1. **Granularity:** Enable per-machine asset version control (Proposals A & C)
2. **Efficiency:** Reduce unnecessary synchronization and storage (Proposals B & D)
3. **Resilience:** Eliminate single points of failure for boot serving (Proposal B)
4. **Flexibility:** Remove hardcoded kernel selection for non-Ubuntu ephemeral deployments (Proposal C)

**Critical Production Blockers:**
- ❌ **HPC Use Case Broken:** Cannot deploy RHEL ephemerally with RHEL kernel ([boot.py:L810-L826](src/maasserver/rpc/boot.py#L810-L826))
- ⚠️ Race conditions during sync/cleanup could cause boot failures
- ⚠️ No resilience to Region downtime (Rack controllers cannot cache)

**Highest ROI:**  
**Proposal C (Asset Metadata Service)** - Provides immediate value:
- ✅ Unblocks HPC use case (native kernel support)
- ✅ Enables canary deployments and version pinning
- ✅ Enables A/B testing and gradual rollouts
- ✅ Table-stakes for modern infrastructure management

**Alternative Quick Win:**  
Add `Machine.kernel_policy` field as short-term fix for HPC blocker while longer-term Asset Metadata Service is being built.

**Biggest Risk:**  
Current architecture assumes boot asset synchronization is complete and consistent. Several race conditions and state conflicts could cause production boot failures during cleanup or sync operations. The hardcoded Ubuntu kernel assumption blocks entire customer segments (HPC, scientific computing). Recommend prioritizing these fixes before large-scale deployments.

