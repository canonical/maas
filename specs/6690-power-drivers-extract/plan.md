# Implementation Plan: Extract Power Drivers to Independent Repositories

**Branch**: `6690-power-drivers-extract` | **Date**: 2025-01-13 | **Spec**: [spec.md](./spec.md)

## Summary

Extract 19 power drivers from the MAAS monorepo into independent snap-service projects. Each driver runs as a long-running HTTP service over UNIX domain sockets. The `maas-agent` (Go) discovers drivers by scanning a shared socket directory (via snap content interface), queries `GET /metadata` for capabilities, and invokes power actions via `POST /query`, `POST /on`, etc. The maas-agent registers discovered drivers with the region via a new v3 internal API endpoint. Custom snap hooks (`connect`/`disconnect`) send `SIGHUP` to maas-agent to trigger re-scans. The `maas-power` CLI is removed entirely. Two drivers (`manual`, `webhook`) remain builtin in provisioningserver.

## Technical Context

**Language/Version**: Go (maas-agent), Python 3.14 (MAAS core / builtin drivers), any language (external drivers)
**Primary Dependencies**: Go `net/http` (maas-agent HTTP client over UNIX sockets), FastAPI (v3 internal API), httpx (region-side HTTP)
**Database**: PostgreSQL — new table for per-rack power driver registrations
**Testing**: Go `testing` + `testify` (maas-agent), pytest + asyncio (Python), existing testtools suite (legacy rack tests)
**Target Components**:
- `src/maasagent` — socket discovery, SIGHUP handler, HTTP client over UNIX sockets, v3 internal API client, power execution (replaces `maas-power` CLI)
- `maasapiserver` — new v3 internal API handler for power driver registration
- `maasservicelayer` — new service/repository for rack power driver data
- `maasserver` — update `get_all_power_types()` to merge rack-registered drivers
- `snap/snapcraft.yaml` — add content slot, remove `maas-power` app, remove driver stage-packages, add custom `connect`/`disconnect` hooks
- `snap/hooks` — custom hooks for `connect`/`disconnect` that send SIGHUP to maas-agent
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
2. **Discovery**: `maas-agent` scans a shared directory for `.sock` files. Each socket is a driver service.
3. **Metadata**: `GET /metadata` on each socket returns driver capabilities. No static files.
4. **System identification**: `system_id` only (no `hostname` in request body).
5. **Agent→Region notification**: New v3 internal API endpoint. Not legacy AMP/RPC.
6. **Builtin drivers**: `manual` and `webhook` stay in MAAS monorepo (provisioningserver). All others are external snaps.
7. **`maas-power`**: Removed entirely. No deprecation period. Power execution moves to maas-agent.
8. **SIGHUP-driven re-scan**: Custom snap hooks (`connect`/`disconnect`) send `SIGHUP` to maas-agent, triggering a re-scan of the socket directory. No background watcher or polling.
9. **maas-agent owns power**: The Go maas-agent handles both driver discovery and power action execution, replacing the Python `maas-power` CLI.
10. **Communication paths**:
    - **Driver lifecycle** (register/unregister) → v3 internal API (agent→region HTTP with mTLS). Not legacy AMP/RPC.
    - **Power actions** (on/off/query/cycle/reset) → Temporal workflows (unchanged). Region schedules Temporal activities → maas-agent picks them up → calls driver sockets directly. No change to the established Temporal path.

---

## Implementation Phases

### Phase 0: maas-agent — Socket Client & Discovery (Go)

**Goal**: Implement the Go components in maas-agent for driver discovery, HTTP-over-UNIX-socket client, and SIGHUP-driven re-scanning.

**Changes in `src/maasagent`:**

1. **Create `internal/power/discovery.go`**
   - `ScanSocketDirectory(path string) ([]SocketDriver, error)` — scans for `.sock` files, queries `GET /metadata` on each
   - `SocketDriver` struct: `Name`, `SocketPath`, `Metadata`
   - Filters out stale sockets (service not responding)

2. **Create `internal/power/socketclient.go`**
   - HTTP client that speaks to UNIX sockets via `net/http` with custom `DialContext`
   - Methods: `GetMetadata()`, `Query(systemID, context)`, `On(systemID, context)`, `Off(...)`, `Cycle(...)`, `Reset(...)`, `SetBootOrder(systemID, context, order)`
   - Timeout handling, retry logic with backoff
   - Converts HTTP errors to typed Go errors (`PowerConnError`, `PowerActionError`, etc.)

3. **Create `internal/power/registry.go`**
   - In-memory registry of discovered drivers, keyed by `driver_name`
   - `Register(driver SocketDriver)` — add or update
   - `Unregister(driverName string)` — remove
   - `Get(driverName string) (SocketDriver, bool)` — lookup
   - `GetAll() []SocketDriver` — list all
   - `Diff(previous []SocketDriver, current []SocketDriver) (added, removed []SocketDriver)` — compute changes for region notification

4. **Create `internal/power/signalhandler.go`**
   - `SetupSignalHandler(agent *Daemon)` — registers `SIGHUP` handler
   - On `SIGHUP`: triggers re-scan of `$SNAP_COMMON/power-drivers`
   - Computes diff between previous and current scan
   - Notifies region of added/removed drivers via v3 internal API

5. **Refactor `internal/power/service.go`**
   - Replace `maas-power` CLI invocation (`exec.Command`) with direct HTTP calls to driver sockets via `socketclient`
   - Look up driver socket from registry by `driver_type`
   - Power activities (`PowerOn`, `PowerOff`, etc.) now call the socket client directly
   - Remove dependency on `maas-power` CLI entirely

6. **Create `internal/power/regionclient.go`**
   - HTTP client for the v3 internal API (agent→region communication)
   - `RegisterDrivers(drivers []SocketDriver)` — POST to register endpoint
   - `UnregisterDriver(driverName string)` — DELETE to unregister endpoint
   - Uses the rack's mTLS client certificate

7. **Update `internal/daemon/daemon.go`**
   - On `Start()`: create `$SNAP_COMMON/power-drivers` directory if it doesn't exist
   - Perform initial driver discovery scan
   - Register discovered drivers with region
   - Wire up `SIGHUP` signal handler

8. **Update `internal/daemon/config.go`**
   - Add `PowerDriversSocketDir` config field (defaults to `$SNAP_COMMON/power-drivers`)

**Files created:**
- `src/maasagent/internal/power/discovery.go`
- `src/maasagent/internal/power/socketclient.go`
- `src/maasagent/internal/power/registry.go`
- `src/maasagent/internal/power/signalhandler.go`
- `src/maasagent/internal/power/regionclient.go`

**Files modified:**
- `src/maasagent/internal/power/service.go`
- `src/maasagent/internal/daemon/daemon.go`
- `src/maasagent/internal/daemon/config.go`

**Files deleted:**
- (none in this phase; `power_driver_command.py` deleted in Phase 3)

---

### Phase 1: Snap Integration — Content Slot, Hooks & Stage Packages

**Goal**: Wire up the snap content interface, custom hooks, and clean up stage packages.

**Socket directory convention:**

The shared socket directory lives in the MAAS runtime directory:

| Environment | Path |
|---|---|
| Snap | `/run/snap.<instance>/power-drivers` |
| Deb | `/run/maas/power-drivers` |

This follows the canonical MAAS pattern (same as the Go agent's `RunDir()` function). The directory is created at rack startup if it doesn't exist.

**Changes in `snap/snapcraft.yaml`:**

1. **Add content slot:**
   ```yaml
   slots:
     power-drivers:
       interface: content
       content: power-drivers
       default-provider: maas-power-ipmi
       write:
         - $SNAP_INSTANCE_NAME/power-drivers   # snap: /run/snap.<name>/power-drivers
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

4. **Register custom hooks in `hooks:` section:**
   ```yaml
   hooks:
     ...
     connect-power-drivers:
       plugs:
         - network  # to send SIGHUP and potentially query region
     disconnect-power-drivers:
       plugs:
         - network
   ```

**Custom snap hooks (`snap/hooks/`):**

5. **Create `snap/hooks/connect-power-drivers`:**
   - Triggered when a driver snap connects its `power-drivers` plug to MAAS's slot
   - Sends `SIGHUP` to the `maas-agent` process to trigger a re-scan of the runtime socket directory
   - Implementation: `kill -HUP $(pidof maas-agent)` or via Pebble `pebble signal --signal=HUP maas-agent`

6. **Create `snap/hooks/disconnect-power-drivers`:**
   - Triggered when a driver snap disconnects its `power-drivers` plug
   - Sends `SIGHUP` to the `maas-agent` process to trigger a re-scan
   - maas-agent will detect removed sockets and unregister stale drivers from the region

**Changes in `src/maasagent`:**

7. **Update `internal/daemon/daemon.go` (agent startup):**
   - On startup: create the runtime socket directory if it doesn't exist (using `RunDir()` convention)
   - Perform initial driver discovery scan
   - Register discovered drivers with region via v3 internal API
   - Wire up `SIGHUP` handler (from Phase 0)

8. **Update `internal/pathutil/` (or equivalent):**
   - Add `GetPowerDriversSocketDir()` function using the same logic as the Go agent's `RunDir()`:
     - If `SNAP_INSTANCE_NAME` is set: `/run/snap.<name>/power-drivers`
     - Otherwise: `/run/maas/power-drivers`

**Driver snap convention:**

Each driver snap writes its socket to the same runtime directory:
- Snap: `/run/snap.<instance>/power-drivers/<driver-name>.sock`
- The driver snap's service starts and writes its socket here

**Files created:**
- `snap/hooks/connect-power-drivers`
- `snap/hooks/disconnect-power-drivers`

**Files modified:**
- `snap/snapcraft.yaml`
- `src/maasagent/internal/daemon/daemon.go`
- `src/maasagent/internal/daemon/config.go`

---

### Phase 2: MAAS Core — v3 Internal API for Driver Lifecycle

**Goal**: Create the v3 internal API endpoint that maas-agent uses to register/unregister power drivers with the region.

**New database table** (`src/maasservicelayer/db/tables.py`):

```python
PowerDriverTable = Table(
    "rack_power_drivers",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("rack_system_id", String(255), nullable=False),
    Column("driver_name", String(255), nullable=False),
    Column("driver_version", String(255), nullable=False),
    Column("schema", JSONB, nullable=False),  # driver metadata from GET /metadata
    UniqueConstraint("rack_system_id", "driver_name", "driver_version"),
)
```

**New model** (`src/maasservicelayer/models/power_drivers.py`):

```python
@generate_builder()
class PowerDriver(MaasTimestampedBaseModel):
    rack_system_id: str
    driver_name: str
    driver_version: str
    schema: dict
```

The `@generate_builder()` decorator produces `PowerDriverBuilder` (all fields default to `UNSET`).

**Validation model** (`src/maasservicelayer/models/power_drivers.py`):

```python
class DriverSchema(BaseModel):
    name: str
    description: str
    version: str
    actions: list[DriverAction]
    settings: list[DriverSetting]
    capabilities: DriverCapabilities
    ip_extractor: IpExtractor | None
```

This enforces the general contract that every power driver service must comply with when registering.

**New ClauseFactory** (`src/maasservicelayer/db/repositories/power_drivers.py`):
- `with_id(id: int)` — match by primary key
- `with_rack_system_id(rack_system_id: str)` — match all drivers for a rack
- `with_driver_name(driver_name: str)` — match by driver name
- `with_driver_version(driver_version: str)` — match by driver version

**New repository** (`src/maasservicelayer/db/repositories/power_drivers.py`):
- Extends `BaseRepository[PowerDriver]` — inherits all standard CRUD methods (`create`, `create_many`, `get_by_id`, `get_one`, `get_many`, `list`, `update_by_id`, `update_one`, `update_many`, `delete_by_id`, `delete_one`, `delete_many`)

**New service** (`src/maasservicelayer/services/power_drivers.py`):
- Extends `BaseService[PowerDriver, PowerDriversRepository, PowerDriverBuilder]` — inherits all standard CRUD methods
- `create(builder)` — register a new driver (schema validated against `DriverSchema` before create)
- `delete_one(query)` — unregister a specific driver version for a rack
- `delete_many(query)` — unregister all drivers for a rack (called on rack disconnect)
- `get_available_power_types()` — merged view across all racks + builtin drivers

**New v3 internal API handler** (`src/maasapiserver/v3/api/internal/handlers/rack_power_drivers.py`):

```
POST /MAAS/api/v3/internal/agents/{agent_uuid}/power-drivers:register
  - Body: { "drivers": [ { "name": "...", "version": "...", "schema": {...} }, ... ] }
  - Auth: mTLS client cert (CN = agent UUID)
  - Response: 204 No Content

DELETE /MAAS/api/v3/internal/agents/{agent_uuid}/power-drivers/{driver_name}/{version}
  - Auth: mTLS client cert
  - Response: 204 No Content

GET /MAAS/api/v3/internal/agents/{agent_uuid}/power-drivers
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
  - `register_drivers(agent_uuid, drivers)` — POST to `/agents/{agent_uuid}/power-drivers:register`
  - `unregister_driver(agent_uuid, driver_name, version)` — DELETE to `/agents/{agent_uuid}/power-drivers/{driver_name}/{version}`
  - Uses the rack's mTLS client certificate

- Update `provisioningserver/server.py`:
  - On driver discovery: call `register_drivers()`
  - On driver removal: call `unregister_driver()`
  - On rack startup: register all discovered drivers

**Alembic migration**: `alembic revision --autogenerate -m "add rack_power_drivers table"`

**Files created:**
- `src/maasservicelayer/models/power_drivers.py`
- `src/maasservicelayer/db/repositories/power_drivers.py`
- `src/maasservicelayer/services/power_drivers.py`
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
- Service writes socket to `<run-dir>/power-drivers/<driver-name>.sock` (where run-dir is `/run/snap.<instance>` in snap or `/run/maas` in deb)

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
   - `internal/power/discovery_test.go` — mock socket directory, verify scan and metadata queries
   - `internal/power/socketclient_test.go` — mock UNIX socket server, verify HTTP calls and error handling
   - `internal/power/registry_test.go` — verify register/unregister/diff operations
   - `internal/power/signalhandler_test.go` — verify SIGHUP triggers re-scan and region notification
   - `internal/power/regionclient_test.go` — mock v3 internal API, verify HTTP calls
   - `internal/power/service_test.go` — verify power activities call socket client directly (no CLI)
   - `rack_power_drivers` repository (Python) — real DB, verify CRUD
   - `rack_power_drivers` service (Python) — mock repo, verify business logic
   - v3 internal API handler (Python) — mock service, verify HTTP responses

2. **Integration tests** (MAAS monorepo):
   - maas-agent startup with connected driver snap → drivers registered in region
   - Driver snap disconnect (SIGHUP via hook) → drivers removed from registry
   - Agent→region driver registration via v3 internal API
   - `get_all_power_types()` returns merged builtin + agent-registered drivers
   - `DescribePowerTypes` RPC still works

3. **Functional tests** (MAAS monorepo):
   - Full flow: connect driver snap → maas-agent discovers → region notified → power action succeeds
   - SIGHUP triggers re-scan: connect new driver snap → hook fires → agent picks up new driver
   - SIGHUP triggers cleanup: disconnect driver snap → hook fires → agent removes stale driver
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
| `created` | DateTime | NOT NULL, default `now()` |
| `updated` | DateTime | NOT NULL, default `now()` |
| `rack_system_id` | String | FK → `rackcontrollers.system_id`, NOT NULL |
| `driver_name` | String | NOT NULL |
| `driver_version` | String | NOT NULL |
| `schema` | JSONB | NOT NULL (driver metadata from `/metadata`) |

**Indexes:**
- `UK_rack_power_drivers_rack_driver_version` — unique on `(rack_system_id, driver_name, driver_version)`

**Migration**: Alembic autogenerate, test up/down.

### Domain Model: `PowerDriver`

```python
@generate_builder()
class PowerDriver(MaasTimestampedBaseModel):
    rack_system_id: str
    driver_name: str
    driver_version: str
    schema: dict
```

`@generate_builder()` produces `PowerDriverBuilder`. The `schema` field maps to the `JSONB` column.

### Validation Model: `DriverSchema`

```python
class DriverSchema(BaseModel):
    name: str
    description: str
    version: str
    actions: list[DriverAction]
    settings: list[DriverSetting]
    capabilities: DriverCapabilities
    ip_extractor: IpExtractor | None
```

Enforces the general contract every power driver must comply with. Used to validate the incoming schema dict before `create()`.

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
| Driver service crashes during power action | `socketclient` retries with backoff; maas-agent reports error to region |
| Socket directory permissions (strict confinement) | Snap content interface handles mount; socket dir created with correct perms |
| Region stale driver data (agent disconnects without cleanup) | `delete_many()` with `with_rack_system_id` clause on rack disconnect; agent re-registers on next startup |
| Migration breaks existing rack registrations | Down migration tested; agent re-registers on next startup |
| Existing tests break during transition | Phase 3 (driver deletion) done last; test suite runs between phases |
| Driver snap confinement blocks BMC access | Driver snap declares `network` plug; system tools included in driver snap |
| `DescribePowerTypes` RPC still used by region | Keep working alongside v3 internal API; deprecate later |
| SIGHUP arrives before maas-agent is ready | Signal handler checks if discovery is initialized; drops signal if not ready |

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

- ✅ `maas-agent` discovers driver services via UNIX sockets within 1 second
- ✅ `maas-agent` queries `GET /metadata` for driver capabilities
- ✅ Power actions succeed over HTTP on UNIX sockets (no `maas-power` CLI)
- ✅ Region receives driver lifecycle notifications via v3 internal API
- ✅ SIGHUP triggers re-scan: new drivers registered, stale drivers removed
- ✅ Custom snap hooks (`connect-power-drivers`, `disconnect-power-drivers`) fire correctly
- ✅ `get_all_power_types()` returns merged builtin + agent-registered drivers
- ✅ `manual` and `webhook` builtin drivers work without external snaps
- ✅ `maas-power` command and `power_driver_command.py` removed
- ✅ No direct driver imports in `provisioningserver` or `maasserver`
- ✅ All 19 external driver repos build, test, and produce snaps
- ✅ Existing test suite passes (adapted for new architecture)
- ✅ Alembic migration up/down works

---

**Next Step**: Run `/speckit.tasks` to generate actionable task list per phase.
