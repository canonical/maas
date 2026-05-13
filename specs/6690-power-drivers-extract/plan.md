# Implementation Plan: Extract Power Drivers to Independent Repositories

**Branch**: `6690-power-drivers-extract` | **Date**: 2025-01-13 | **Spec**: [spec.md](./spec.md)

## Summary

Extract 19 power drivers from the MAAS monorepo into independent snap-service projects. Each driver runs as a long-running HTTP service over UNIX domain sockets. `rackd` discovers drivers by scanning a shared socket directory (via snap content interface), queries `GET /metadata` for capabilities, and invokes power actions via `POST /query`, `POST /on`, etc. The rack controller notifies the region of driver lifecycle changes via a new v3 internal API endpoint. The `maas-power` CLI is removed entirely. Two drivers (`manual`, `webhook`) remain builtin.

## Technical Context

**Language/Version**: Python 3.14 (MAAS core), any language (drivers)
**Primary Dependencies**: Twisted (rackd HTTP client), FastAPI (v3 internal API), httpx (rack→region HTTP)
**Database**: PostgreSQL — new table for per-rack power driver registrations
**Testing**: pytest + asyncio (Python), existing testtools suite (legacy rack tests)
**Target Components**:
- `provisioningserver` — socket discovery, HTTP client, registry refactor, v3 internal API client
- `maasapiserver` — new v3 internal API handler for power driver registration
- `maasservicelayer` — new service/repository for rack power driver data
- `maasserver` — update `get_all_power_types()` to merge rack-registered drivers
- `snap/snapcraft.yaml` — add content slot, remove `maas-power` app, remove driver stage-packages
- `pyproject.toml` — remove `scripts.maas-power`
- **External repos** — 19 new driver repositories (one per driver)

**Scope**: ~6 files deleted, ~10 files modified, ~8 files created in MAAS monorepo; 19 new repositories

---

## Constitution Check

- ✅ Feature does not touch v3 public API — uses internal API and legacy RPC
- ✅ Database changes planned as Alembic migration
- ✅ Testing strategy covers rack tests, API tests, functional tests
- ✅ Ruff formatting: 79 chars, double quotes
- ✅ No ORM in v3 API repositories (SQLAlchemy Core only)

---

## Research Findings

### Current Architecture

**Power driver invocation flow (today):**

```
region → AMP PowerQuery → rackd clusterservice.power_query()
  → rpc/power.get_power_state()
    → PowerDriverRegistry.get_item(power_type)
      → driver.query(system_id, context)  # Python method call
```

**`DescribePowerTypes` flow (today):**

```
region → AMP DescribePowerTypes → rackd clusterservice.describe_power_types()
  → PowerDriverRegistry.get_schema()  # returns JSON schema of all drivers
```

**`PowerDriverRegistry` (today):**

- Eagerly populated at import time in `registry.py`
- All 22 drivers instantiated and registered
- Pod drivers (lxd, virsh) also registered
- `sanitise_power_parameters()` uses registry to extract secrets

**v3 Internal API (today):**

- FastAPI-based, served on separate uvicorn with mTLS
- Prefix: `/MAAS/api/v3/internal`
- Existing handlers: `RootHandler`, `AgentHandler`, `LeasesHandler`
- Auth: `RequireClientCertMiddleware` (client cert CN identifies caller)
- **No power driver registration endpoint exists** — must be created

### Key Design Decisions

1. **Protocol**: HTTP over UNIX socket — standard HTTP semantics, JSON bodies. No custom framing.
2. **Discovery**: `rackd` scans a shared directory for `.sock` files. Each socket is a driver service.
3. **Metadata**: `GET /metadata` on each socket returns driver capabilities. No static files.
4. **System identification**: `system_id` only (no `hostname` in request body).
5. **Rack→Region notification**: New v3 internal API endpoint. Not legacy AMP/RPC.
6. **Builtin drivers**: `manual` and `webhook` stay in MAAS monorepo. All others are external snaps.
7. **`maas-power`**: Removed entirely. No deprecation period.

---

## Implementation Phases

### Phase 0: MAAS Core — Protocol Client & Registry Refactor

**Goal**: Replace the Python-method-call driver invocation with HTTP-over-UNIX-socket client.

**Changes in `provisioningserver`:**

1. **Create `provisioningserver/drivers/power/socket_client.py`**
   - HTTP client that speaks to UNIX sockets
   - Methods: `get_metadata()`, `query(system_id, context)`, `on(system_id, context)`, `off(...)`, `cycle(...)`, `reset(...)`, `set_boot_order(system_id, context, order)`
   - Uses `httpx` with `http+unix://` URL scheme
   - Timeout handling, retry logic (mirrors current `PowerDriver` retry policy)
   - Converts HTTP errors to `PowerError` hierarchy (`PowerConnError`, `PowerActionError`, etc.)

2. **Create `provisioningserver/drivers/power/discovery.py`**
   - `scan_socket_directory(path)` → list of socket paths
   - `query_metadata(socket_path)` → driver metadata dict
   - `watch_for_changes(path)` → async generator yielding socket add/remove events
   - Uses `inotify` or periodic scan (configurable)

3. **Refactor `provisioningserver/drivers/power/registry.py`**
   - Remove eager driver instantiation loop
   - Add `register_from_socket(driver_name, socket_path)` method
   - Add `unregister(driver_name)` method
   - Keep `get_item()`, `get_schema()`, iteration — but backed by socket-based drivers
   - Keep `sanitise_power_parameters()` unchanged

4. **Create `provisioningserver/drivers/power/socket_driver.py`**
   - `SocketPowerDriver` class implementing the same interface as current `PowerDriver`
   - Delegates all operations to `socket_client`
   - `get_schema()` returns metadata from `GET /metadata`
   - Bridges the external HTTP service to the existing Python registry interface

5. **Refactor `provisioningserver/rpc/power.py`**
   - `get_power_state()` → looks up driver in registry (now a `SocketPowerDriver`)
   - `perform_power_driver_query()` → calls `driver.query()` which goes through socket client
   - No structural change needed — the registry interface is preserved

6. **Refactor `provisioningserver/rpc/clusterservice.py`**
   - `describe_power_types()` → returns `PowerDriverRegistry.get_schema()` (unchanged interface)
   - `power_driver_check()` → for socket drivers, always returns `[]` (packages are in the driver snap)
   - `set_boot_order()` → unchanged

7. **Remove `provisioningserver/power_driver_command.py`**
   - Delete entirely

8. **Update `pyproject.toml`**
   - Remove `scripts.maas-power` entry point

**Files created:**
- `src/provisioningserver/drivers/power/socket_client.py`
- `src/provisioningserver/drivers/power/discovery.py`
- `src/provisioningserver/drivers/power/socket_driver.py`

**Files modified:**
- `src/provisioningserver/drivers/power/registry.py`
- `src/provisioningserver/rpc/power.py`
- `src/provisioningserver/rpc/clusterservice.py`
- `pyproject.toml`

**Files deleted:**
- `src/provisioningserver/power_driver_command.py`

---

### Phase 1: MAAS Core — Socket Directory & Snap Integration

**Goal**: Wire up the snap content interface so driver sockets are discoverable.

**Changes in `snap/snapcraft.yaml`:**

1. **Add content slot:**
   ```yaml
   slots:
     power-drivers:
       interface: content
       content: power-drivers
       read:
         - $SNAP_COMMON/power-drivers
   ```

2. **Remove `apps.power`:**
   ```yaml
   # DELETE:
   # power:
   #   command: usr/bin/maas-power
   #   ...
   ```

3. **Remove driver stage-packages from `parts.maas`:**
   - Remove: `amtterm`, `wsmancli`, `freeipmi-tools`, `ipmitool`, `snmp`, `wget`, `python3-seamicroclient`, `python3-zhmcclient`, `python3-pyvmomi`
   - Keep: packages needed for builtin drivers (`webhook` needs nothing extra, `manual` needs nothing)

4. **Add `SNAP_COMMON/power-drivers` directory creation** in rack startup

**Changes in `provisioningserver`:**

5. **Update `provisioningserver/server.py` (rack startup):**
   - On startup: create `$SNAP_COMMON/power-drivers` if it doesn't exist
   - Start socket directory watcher
   - On first scan: register all discovered drivers, notify region

6. **Update `provisioningserver/path.py`:**
   - Add `get_power_drivers_socket_dir()` function

**Files modified:**
- `snap/snapcraft.yaml`
- `src/provisioningserver/server.py`
- `src/provisioningserver/path.py`

---

### Phase 2: MAAS Core — v3 Internal API for Driver Lifecycle

**Goal**: Create the v3 internal API endpoint that rack controllers use to register/unregister power drivers with the region.

**New database table** (`src/maasservicelayer/db/tables.py`):

```python
rack_power_drivers = Table(
    "rack_power_drivers",
    Column("id", Serial, primary_key=True),
    Column("rack_system_id", String, ForeignKey("rackcontrollers.system_id"), nullable=False),
    Column("driver_name", String, nullable=False),
    Column("schema", JSON, nullable=False),  # driver metadata from GET /metadata
    Column("last_seen", DateTime, nullable=False, server_default=func.now()),
    UniqueConstraint("rack_system_id", "driver_name", name="UK_rack_power_drivers_rack_driver"),
)
```

**New repository** (`src/maasservicelayer/db/repositories/rack_power_drivers.py`):
- `upsert(rack_system_id, driver_name, schema)` — insert or update
- `remove(rack_system_id, driver_name)` — delete
- `get_all_for_rack(rack_system_id)` — list all drivers for a rack
- `get_merged_across_racks()` — merge unique drivers across all racks
- `cleanup_stale(rack_system_id)` — remove all entries for a disconnected rack

**New service** (`src/maasservicelayer/services/rack_power_drivers.py`):
- `register_driver(rack_system_id, driver_name, schema)`
- `unregister_driver(rack_system_id, driver_name)`
- `unregister_all(rack_system_id)` — called on rack disconnect
- `get_available_power_types()` — merged view across all racks + builtin drivers

**New v3 internal API handler** (`src/maasapiserver/v3/api/internal/handlers/rack_power_drivers.py`):

```
POST /MAAS/api/v3/internal/rack-power-drivers:register
  - Body: { "drivers": [ { "name": "...", "schema": {...} }, ... ] }
  - Auth: mTLS client cert (CN = rack system_id)
  - Response: 204 No Content

DELETE /MAAS/api/v3/internal/rack-power-drivers:unregister
  - Body: { "driver_name": "..." }
  - Auth: mTLS client cert
  - Response: 204 No Content

GET /MAAS/api/v3/internal/rack-power-drivers
  - Auth: mTLS client cert
  - Response: 200 { "drivers": [...] }
```

**Changes to `maasserver`:**

- Update `src/maasserver/clusterrpc/driver_parameters.py`:
  - `get_all_power_types()` → merge builtin drivers + rack-registered drivers from DB
  - This is the function the region uses to populate Django forms and API responses

**Changes to `provisioningserver`:**

- Create `provisioningserver/rpc/driver_lifecycle_client.py`:
  - HTTP client for the v3 internal API
  - `register_drivers(rack_system_id, drivers)` — POST to register endpoint
  - `unregister_driver(rack_system_id, driver_name)` — DELETE to unregister endpoint
  - Uses the rack's mTLS client certificate

- Update `provisioningserver/server.py`:
  - On driver discovery: call `register_drivers()`
  - On driver removal: call `unregister_driver()`
  - On rack startup: register all discovered drivers

**Alembic migration**: `alembic revision --autogenerate -m "add rack_power_drivers table"`

**Files created:**
- `src/maasservicelayer/db/repositories/rack_power_drivers.py`
- `src/maasservicelayer/services/rack_power_drivers.py`
- `src/maasapiserver/v3/api/internal/handlers/rack_power_drivers.py`
- `src/provisioningserver/rpc/driver_lifecycle_client.py`
- `src/maasservicelayer/db/alembic/versions/XXXXX_add_rack_power_drivers.py`

**Files modified:**
- `src/maasservicelayer/db/tables.py`
- `src/maasserver/clusterrpc/driver_parameters.py`
- `src/provisioningserver/server.py`
- `src/maasapiserver/v3/api/internal/handlers/__init__.py` (register new handler)

---

### Phase 3: MAAS Core — Remove External Driver Code

**Goal**: Delete all external driver implementations from the monorepo. Keep `manual` and `webhook`.

**Files deleted:**
- `src/provisioningserver/drivers/power/ipmi.py`
- `src/provisioningserver/drivers/power/redfish.py`
- `src/provisioningserver/drivers/power/amt.py` (+ `.xml` files)
- `src/provisioningserver/drivers/power/apc.py`
- `src/provisioningserver/drivers/power/dli.py`
- `src/provisioningserver/drivers/power/eaton.py`
- `src/provisioningserver/drivers/power/hmc.py`
- `src/provisioningserver/drivers/power/hmcz.py`
- `src/provisioningserver/drivers/power/moonshot.py`
- `src/provisioningserver/drivers/power/mscm.py`
- `src/provisioningserver/drivers/power/msftocs.py`
- `src/provisioningserver/drivers/power/openbmc.py`
- `src/provisioningserver/drivers/power/proxmox.py`
- `src/provisioningserver/drivers/power/raritan.py`
- `src/provisioningserver/drivers/power/recs.py`
- `src/provisioningserver/drivers/power/seamicro.py`
- `src/provisioningserver/drivers/power/ucsm.py`
- `src/provisioningserver/drivers/power/vmware.py`
- `src/provisioningserver/drivers/power/wedge.py`
- Corresponding test files in `src/provisioningserver/drivers/power/tests/`

**Files modified:**
- `src/provisioningserver/drivers/power/registry.py` — remove imports of deleted drivers
- `src/maasserver/api/doc.py` — remove imports of deleted drivers
- `src/maasserver/clusterrpc/driver_parameters.py` — remove imports of deleted drivers
- `src/maasserver/models/bmc.py` — remove imports of deleted drivers
- `src/maasserver/models/node.py` — remove imports of deleted drivers
- `src/maasserver/migrations/` — migrations that reference specific drivers (these are one-time, may need to keep imports or refactor)

**Builtin drivers:**
- `src/provisioningserver/drivers/power/manual.py` — keep, but adapt to work with the new registry
- `src/provisioningserver/drivers/power/webhook.py` — keep, but adapt to work with the new registry

---

### Phase 4: External Driver Repositories

**Goal**: Create the 19 independent driver repositories.

**Template structure** (per driver):

```
maas-power-driver-<name>/
  pyproject.toml
  README.md
  snap/snapcraft.yaml
  src/maas_power_driver_<name>/
    __init__.py
    server.py          # HTTP server over UNIX socket
    driver.py          # BMC-specific logic
    metadata.json      # Static metadata (name, description, version, settings schema)
  tests/
    test_driver.py
    test_server.py
  Makefile
```

**`server.py`** (common pattern):
- HTTP server listening on UNIX socket
- Endpoints: `GET /metadata`, `POST /query`, `POST /on`, `POST /off`, `POST /cycle`, `POST /reset`, `POST /set-boot-order`
- Reads `metadata.json` for driver capabilities
- Delegates power actions to `driver.py`

**`snapcraft.yaml`** (common pattern):
- Declares snap service
- Declares `power-drivers` content plug
- Stage-packages for system dependencies (e.g., `freeipmi-tools` for ipmi)
- Service writes socket to `$SNAP_COMMON/power-drivers/<driver-name>.sock`

**Drivers to create (19):**
1. `maas-power-driver-ipmi` (deps: `freeipmi-tools`)
2. `maas-power-driver-redfish` (deps: `python3-requests`)
3. `maas-power-driver-amt` (deps: `amtterm`, `wsmancli`)
4. `maas-power-driver-apc` (deps: `snmp`)
5. `maas-power-driver-dli` (deps: `wget`)
6. `maas-power-driver-eaton` (deps: none special)
7. `maas-power-driver-hmc` (deps: `python3-zhmcclient`)
8. `maas-power-driver-hmcz` (deps: `python3-zhmcclient`)
9. `maas-power-driver-moonshot` (deps: `ipmitool`)
10. `maas-power-driver-mscm` (deps: `python3-zhmcclient`)
11. `maas-power-driver-msftocs` (deps: none special)
12. `maas-power-driver-openbmc` (deps: `python3-requests`)
13. `maas-power-driver-proxmox` (deps: none special)
14. `maas-power-driver-raritan` (deps: none special)
15. `maas-power-driver-recs` (deps: none special)
16. `maas-power-driver-seamicro` (deps: `python3-seamicroclient`)
17. `maas-power-driver-ucsm` (deps: none special)
18. `maas-power-driver-vmware` (deps: `python3-pyvmomi`)
19. `maas-power-driver-wedge` (deps: none special)

**Migration strategy**: Extract existing driver code from `provisioningserver/drivers/power/<name>.py` into each new repo's `driver.py`. Adapt to the HTTP server model.

---

### Phase 5: Testing & Validation

**Goal**: Verify all acceptance criteria.

**Test categories:**

1. **Unit tests** (MAAS monorepo):
   - `socket_client.py` — mock UNIX socket server, verify HTTP calls
   - `discovery.py` — mock socket directory, verify scan/watch
   - `socket_driver.py` — mock client, verify registry interface
   - `driver_lifecycle_client.py` — mock v3 internal API, verify HTTP calls
   - `rack_power_drivers` repository — real DB, verify CRUD
   - `rack_power_drivers` service — mock repo, verify business logic
   - v3 internal API handler — mock service, verify HTTP responses

2. **Integration tests** (MAAS monorepo):
   - Rack startup with connected driver snap → drivers registered in registry
   - Driver snap disconnect → drivers removed from registry
   - Rack→region driver registration via v3 internal API
   - `get_all_power_types()` returns merged builtin + rack-registered drivers
   - `DescribePowerTypes` RPC still works

3. **Functional tests** (MAAS monorepo):
   - Full flow: connect driver snap → rack discovers → region notified → power action succeeds
   - Builtin `manual` driver still works
   - Builtin `webhook` driver still works

4. **Driver repo tests** (per external repo):
   - Service starts, listens on socket
   - `GET /metadata` returns correct capabilities
   - Power actions work against mocked BMC
   - Snap builds successfully

5. **Regression tests**:
   - `bin/test.rack` passes (adapted for new architecture)
   - `bin/test.region` passes
   - `maas-power` command no longer exists
   - No direct driver imports in `provisioningserver` or `maasserver`

---

## Data Model

### New Table: `rack_power_drivers`

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | Serial | PK |
| `rack_system_id` | String | FK → `rackcontrollers.system_id`, NOT NULL |
| `driver_name` | String | NOT NULL |
| `schema` | JSON | NOT NULL (driver metadata from `/metadata`) |
| `last_seen` | DateTime | NOT NULL, default `now()` |

**Indexes:**
- `UK_rack_power_drivers_rack_driver` — unique on `(rack_system_id, driver_name)`
- `idx_rack_power_drivers_last_seen` — on `last_seen` for staleness queries

**Migration**: Alembic autogenerate, test up/down.

---

## API Contracts

### Driver Service Protocol (HTTP over UNIX Socket)

```
GET  /metadata          → 200 { "name": "ipmi", "description": "...", "version": "1.0.0", "actions": [...], "settings": [...], "capabilities": {...} }
POST /query             → 200 { "status": "ok", "state": "on" }
                         Body: { "system_id": "ABC123", "context": { "power_address": "10.0.0.1", ... } }
POST /on                → 200 { "status": "ok" }
POST /off               → 200 { "status": "ok" }
POST /cycle             → 200 { "status": "ok" }
POST /reset             → 200 { "status": "ok" }
POST /set-boot-order    → 200 { "status": "ok" }
                         Body: { "system_id": "ABC123", "context": {...}, "order": ["network", "disk"] }
```

Error responses:
```
400 { "status": "error", "error_type": "invalid_parameters", "error_message": "..." }
500 { "status": "error", "error_type": "power_action", "error_message": "..." }
503 { "status": "error", "error_type": "unavailable", "error_message": "..." }
```

### v3 Internal API — Rack Power Drivers

```
POST /MAAS/api/v3/internal/rack-power-drivers:register
  Auth: mTLS (CN = rack system_id)
  Body: { "drivers": [ { "name": "ipmi", "schema": {...} }, ... ] }
  204 No Content

DELETE /MAAS/api/v3/internal/rack-power-drivers:unregister
  Auth: mTLS (CN = rack system_id)
  Body: { "driver_name": "ipmi" }
  204 No Content

GET /MAAS/api/v3/internal/rack-power-drivers
  Auth: mTLS (CN = rack system_id)
  200 { "drivers": [ { "name": "ipmi", "schema": {...} }, ... ] }
```

---

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Driver service crashes during power action | `socket_client` retries with backoff; `rackd` reports error to region |
| Socket directory permissions (strict confinement) | Snap content interface handles mount; socket dir created with correct perms |
| Region stale driver data (rack disconnects without cleanup) | `last_seen` timestamp + periodic cleanup of stale entries |
| Migration breaks existing rack registrations | Down migration tested; rack re-registers on next startup |
| Existing tests break during transition | Phase 3 (driver deletion) done last; test suite runs between phases |
| Driver snap confinement blocks BMC access | Driver snap declares `network` plug; system tools included in driver snap |
| `DescribePowerTypes` RPC still used by region | Keep working alongside v3 internal API; deprecate later |

---

## Rollout Plan

1. **Phase 0+1**: MAAS core ready for socket-based drivers (no drivers extracted yet)
2. **Phase 2**: v3 internal API for driver lifecycle (region ready to receive notifications)
3. **Phase 3**: Remove external driver code from monorepo (keep builtin `manual` + `webhook`)
4. **Phase 4**: Create external driver repositories (one at a time, starting with `ipmi`)
5. **Phase 5**: Full test suite validation

Each phase is independently testable. Phase 4 can proceed in parallel for different drivers.

---

## Success Criteria

- ✅ `rackd` discovers driver services via UNIX sockets within 1 second
- ✅ `rackd` queries `GET /metadata` for driver capabilities
- ✅ Power actions succeed over HTTP on UNIX sockets
- ✅ Region receives driver lifecycle notifications via v3 internal API
- ✅ `get_all_power_types()` returns merged builtin + rack-registered drivers
- ✅ `manual` and `webhook` builtin drivers work without external snaps
- ✅ `maas-power` command and `power_driver_command.py` removed
- ✅ No direct driver imports in `provisioningserver` or `maasserver`
- ✅ All 19 external driver repos build, test, and produce snaps
- ✅ Existing test suite passes (adapted for new architecture)
- ✅ Alembic migration up/down works

---

**Next Step**: Run `/speckit.tasks` to generate actionable task list per phase.
