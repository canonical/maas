---
description: "Task list for power drivers extraction feature (Go maas-agent + Python v3 API + snap integration)"
---

# Tasks: Extract Power Drivers to Independent Repositories

**Input**: Design documents from `/specs/6690-power-drivers-extract/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Organization**: Tasks grouped by implementation phase + user story, enabling parallel work

## Format & Conventions

- **[ID]**: Unique task identifier (T001, T002, ...)
- **[P]**: Can run in parallel (independent tasks, different files)
- **[Story]**: Which user story (US1, US2, ...)
- **Exact paths**: File paths fully specified for implementation

---

## Phase 1: Setup & Configuration

**Purpose**: Project initialization, shared infrastructure, and foundational Go/Python structures

### [X] T001 [P] Create Go maas-agent power package structure

**Story**: Foundational | **Parallel**: Yes

- Create `src/maasagent/internal/power/` directory
- Establish package-level documentation for the power driver subsystem

**Files Created**:
- `src/maasagent/internal/power/` (directory)

---

### [X] T002 [P] Create Python v3 internal API handler stub

**Story**: Foundational | **Parallel**: Yes

- Create the handler file for rack power drivers in the v3 internal API
- Define the FastAPI router with mTLS auth middleware

**Files Created**:
- `src/maasapiserver/v3/api/internal/handlers/rack_power_drivers.py` (handler stub with router)

---

### [X] T003 [P] Create maasservicelayer power drivers model file

**Story**: Foundational | **Parallel**: Yes

- Create `PowerDriver` domain model with `@generate_builder()` decorator
- Create `DriverSchema` validation model with all required fields
- Define `DriverAction`, `DriverSetting`, `DriverCapabilities`, `IpExtractor` sub-models

**Files Created**:
- `src/maasservicelayer/models/power_drivers.py`

---

### [X] T004 [P] Create maasservicelayer power drivers repository stub

**Story**: Foundational | **Parallel**: Yes

- Create `PowerDriversRepository` extending `BaseRepository[PowerDriver]`
- Create `PowerDriverClauseFactory` with filter methods: `with_id`, `with_rack_system_id`, `with_driver_name`, `with_driver_version`

**Files Created**:
- `src/maasservicelayer/db/repositories/power_drivers.py`

---

### [X] T005 [P] Create maasservicelayer power drivers service stub

**Story**: Foundational | **Parallel**: Yes

- Create `PowerDriversService` extending `BaseService[PowerDriver, PowerDriversRepository, PowerDriverBuilder]`
- Add `get_available_power_types()` method signature
- Add schema validation logic using `DriverSchema` before `create()`

**Files Created**:
- `src/maasservicelayer/services/power_drivers.py`

---

## Phase 2: Foundational — Go maas-agent Socket Client & Discovery (US1, US2, US3)

**Purpose**: Core Go components for driver discovery, HTTP-over-UNIX-socket communication, and registry management. These are blocking prerequisites for all user stories involving rack-side driver interaction.

**Story Goal**: maas-agent can discover driver services via UNIX sockets, query capabilities, and invoke power actions.

**Independent Test**: Mock UNIX socket servers can be started; `ScanSocketDirectory()` discovers them; `GetMetadata()` returns valid capabilities; power action calls succeed.

### [X] T006 [P] [US1] Implement socket directory scanner in src/maasagent/internal/power/discovery.go

**Description**: Implement `ScanSocketDirectory(path string) ([]SocketDriver, error)` that scans for `.sock` files, queries `GET /metadata` on each, and filters out stale sockets.

- Define `SocketDriver` struct: `Name`, `SocketPath`, `Metadata`
- Connect to each `.sock` file via HTTP client
- Query `GET /metadata` endpoint
- Skip sockets that don't respond (log warning)
- Return list of valid `SocketDriver` instances

**Files**:
- `src/maasagent/internal/power/discovery.go`

---

### [X] T007 [P] [US2] Implement HTTP-over-UNIX-socket client in src/maasagent/internal/power/socketclient.go

**Description**: HTTP client that speaks to UNIX sockets via `net/http` with custom `DialContext`.

- Methods: `GetMetadata()`, `Query(systemID, context)`, `On(...)`, `Off(...)`, `Cycle(...)`, `Reset(...)`, `SetBootOrder(...)`
- Timeout handling and retry logic with backoff
- Convert HTTP errors to typed Go errors (`PowerConnError`, `PowerActionError`)

**Files**:
- `src/maasagent/internal/power/socketclient.go`

---

### [X] T008 [P] [US1] Implement in-memory driver registry in src/maasagent/internal/power/registry.go

**Description**: In-memory registry of discovered drivers, keyed by `driver_name`.

- `Register(driver SocketDriver)` — add or update
- `Unregister(driverName string)` — remove
- `Get(driverName string) (SocketDriver, bool)` — lookup
- `GetAll() []SocketDriver` — list all
- `Diff(previous, current) (added, removed []SocketDriver)` — compute changes for region notification

**Files**:
- `src/maasagent/internal/power/registry.go`

---

### [X] T009 [US3] Implement SIGHUP signal handler in src/maasagent/internal/power/signalhandler.go

**Description**: Registers `SIGHUP` handler that triggers re-scan of socket directory.

- `SetupSignalHandler(agent *Daemon)` — registers handler
- On `SIGHUP`: trigger re-scan of `$SNAP_COMMON/power-drivers`
- Compute diff between previous and current scan
- Notify region of added/removed drivers via v3 internal API

**Dependencies**: T006 (discovery), T008 (registry), T010 (region client)

**Files**:
- `src/maasagent/internal/power/signalhandler.go`

---

### [X] T010 [P] [US7] Implement region notification client in src/maasagent/internal/power/regionclient.go

**Description**: HTTP client for the v3 internal API (agent→region communication).

- `RegisterDrivers(drivers []SocketDriver)` — POST to register endpoint
- `UnregisterDriver(driverName, version string)` — DELETE to unregister endpoint
- Uses the rack's mTLS client certificate

**Files**:
- `src/maasagent/internal/power/regionclient.go`

---

### [X] T011 [US3] Refactor maas-agent power service to use socket client

**Description**: Replace `maas-power` CLI invocation (`exec.Command`) with direct HTTP calls to driver sockets.

- Look up driver socket from registry by `driver_type`
- Power activities (`PowerOn`, `PowerOff`, etc.) now call socket client directly
- Remove dependency on `maas-power` CLI entirely

**Dependencies**: T007 (socket client), T008 (registry)

**Files**:
- `src/maasagent/internal/power/service.go` (modify)

---

## Phase 3: Snap Integration — Content Slot, Hooks & Runtime Directory (US5, US6)

**Purpose**: Wire up the snap content interface, custom hooks, and clean up stage packages so driver snaps can be discovered.

**Story Goal**: The MAAS snap exposes a UNIX socket directory for driver services, and driver snaps run as long-running services.

**Independent Test**: MAAS snap declares `power-drivers` content slot; test driver snap connects; socket appears in shared directory; SIGHUP hook triggers maas-agent re-scan.

### [X] T012 [P] [US6] Add power-drivers content slot to snap/snapcraft.yaml

**Description**: Add the content slot that provides a shared directory for driver UNIX sockets.

- Add `slots.power-drivers` with `interface: content`, `content: power-drivers`
- Set `write` path to `$SNAP_INSTANCE_NAME/power-drivers`

**Files**:
- `snap/snapcraft.yaml` (modify)

---

### [X] T013 [P] [US6] Remove apps.power and driver stage-packages from snap/snapcraft.yaml

**Description**: Remove `maas-power` app and driver-specific system dependencies from the MAAS snap.

- Delete `apps.power` section
- Remove driver stage-packages: `amtterm`, `wsmancli`, `freeipmi-tools`, `ipmitool`, `snmp`, `wget`, `python3-seamicroclient`, `python3-zhmcclient`, `python3-pyvmomi`

**Files**:
- `snap/snapcraft.yaml` (modify)

---

### [X] T014 [P] [US5] Create connect-power-drivers snap hook

**Description**: Custom hook triggered when a driver snap connects its `power-drivers` plug.

- Send `SIGHUP` to maas-agent process to trigger re-scan
- Implementation: `kill -HUP $(pidof maas-agent)` or via Pebble

**Files**:
- `snap/hooks/connect-power-drivers` (create)

---

### [X] T015 [P] [US5] Create disconnect-power-drivers snap hook

**Description**: Custom hook triggered when a driver snap disconnects.

- Send `SIGHUP` to maas-agent process to trigger re-scan
- maas-agent detects removed sockets and unregisters stale drivers

**Files**:
- `snap/hooks/disconnect-power-drivers` (create)

---

### [X] T016 [US5] Register custom hooks in snap/snapcraft.yaml hooks section

**Description**: Register `connect-power-drivers` and `disconnect-power-drivers` hooks with network plug access.

**Dependencies**: T014, T015 (hooks must exist first)

**Files**:
- `snap/snapcraft.yaml` (modify)

---

### [X] T017 [US6] Update maas-agent daemon startup to create socket directory and perform initial scan

**Description**: On `Start()`, create the runtime socket directory if it doesn't exist, perform initial driver discovery scan, and register discovered drivers with region.

- Create `$SNAP_COMMON/power-drivers` or `/run/maas/power-drivers` (deb)
- Perform initial scan via `ScanSocketDirectory()`
- Register discovered drivers with region via `regionclient`
- Wire up `SIGHUP` signal handler

**Dependencies**: T006 (discovery), T008 (registry), T009 (signal handler), T010 (region client)

**Files**:
- `src/maasagent/internal/daemon/daemon.go` (modify)
- `src/maasagent/internal/daemon/config.go` (modify — add `PowerDriversSocketDir`)

---

## Phase 4: MAAS Core — v3 Internal API for Driver Lifecycle (US7)

**Purpose**: Create the v3 internal API endpoint that maas-agent uses to register/unregister power drivers with the region.

**Story Goal**: When drivers appear or disappear on a rack, `rackd` notifies the region controller via the v3 internal API, and the region updates its view of available power types.

**Independent Test**: POST to register endpoint creates DB entries; DELETE removes them; GET returns registered drivers; `get_all_power_types()` returns merged builtin + rack-registered drivers.

### [X] T018 [P] [US7] Add rack_power_drivers table definition to src/maasservicelayer/db/tables.py

**Description**: Define the SQLAlchemy Core table with columns: `id`, `created`, `updated`, `rack_system_id`, `driver_name`, `driver_version`, `schema` (JSONB). Add unique constraint on `(rack_system_id, driver_name, driver_version)`.

**Files**:
- `src/maasservicelayer/db/tables.py` (modify)

---

### [X] T019 [US7] Generate Alembic migration for rack_power_drivers table

**Description**: Run `alembic revision --autogenerate -m "add rack_power_drivers table"` and test migration up/down.

**Dependencies**: T018 (table must be defined)

**Files**:
- `src/maasservicelayer/db/alembic/versions/XXXXX_add_rack_power_drivers.py` (create)

---

### [X] T020 [P] [US7] Implement PowerDriver domain model and DriverSchema validation in src/maasservicelayer/models/power_drivers.py

**Description**: Complete the `PowerDriver` model with `@generate_builder()` and `DriverSchema` validation model with sub-models (`DriverAction`, `DriverSetting`, `DriverCapabilities`, `IpExtractor`).

**Files**:
- `src/maasservicelayer/models/power_drivers.py` (complete from T003 stub)

---

### [X] T021 [P] [US7] Implement PowerDriversRepository and ClauseFactory in src/maasservicelayer/db/repositories/power_drivers.py

**Description**: Complete the repository extending `BaseRepository[PowerDriver]` and `PowerDriverClauseFactory` with `with_id`, `with_rack_system_id`, `with_driver_name`, `with_driver_version`.

**Files**:
- `src/maasservicelayer/db/repositories/power_drivers.py` (complete from T004 stub)

---

### [X] T022 [P] [US7] Implement PowerDriversService in src/maasservicelayer/services/power_drivers.py

**Description**: Complete the service with `create()` (with `DriverSchema` validation), `delete_one()`, `delete_many()`, and `get_available_power_types()` (merged view across all racks + builtin drivers).

**Files**:
- `src/maasservicelayer/services/power_drivers.py` (complete from T005 stub)

---

### [X] T023 [US7] Implement v3 internal API handler in src/maasapiserver/v3/api/internal/handlers/rack_power_drivers.py

**Description**: Complete the handler with three endpoints:
- `POST /agents/{agent_uuid}/power-drivers:register` — register multiple drivers (204)
- `DELETE /agents/{agent_uuid}/power-drivers/{driver_name}/{version}` — unregister one (204)
- `GET /agents/{agent_uuid}/power-drivers` — list registered drivers (200)

**Dependencies**: T022 (service must be complete)

**Files**:
- `src/maasapiserver/v3/api/internal/handlers/rack_power_drivers.py` (complete from T002 stub)
- `src/maasapiserver/v3/api/internal/handlers/__init__.py` (register new handler)

---

### [X] T024 [US7] Update get_all_power_types() in src/maasserver/clusterrpc/driver_parameters.py

**Description**: Modify to merge builtin driver schemas with rack-registered drivers from `rack_power_drivers` DB table.

**Dependencies**: T022 (service with `get_available_power_types()`)

**Files**:
- `src/maasserver/clusterrpc/driver_parameters.py` (modify)

---

## Phase 5: MAAS Core — Remove External Driver Code (US4, US8)

**Purpose**: Delete all external driver implementations from the monorepo, keeping only `manual` and `webhook` builtin drivers.

**Story Goal**: After extraction, no driver implementation code exists in the MAAS monorepo (only protocol client, registry, and builtin drivers). Existing power functionality is preserved.

**Independent Test**: `bin/test.rack` passes; `bin/test.region` passes; no direct driver imports in provisioningserver/maasserver; `maas-power` command no longer exists.

### [X] T025 [US4] Delete external power driver files from provisioningserver

**Description**: Remove 19 external driver files and corresponding test files.

**Files Deleted**:
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

---

### [X] T026 [US4] Remove maas-power CLI and update pyproject.toml

**Description**: Delete `power_driver_command.py` and remove `scripts.maas-power` entry from `pyproject.toml`.

**Files Deleted**:
- `src/provisioningserver/power_driver_command.py`

**Files Modified**:
- `pyproject.toml` (remove `scripts.maas-power`)

---

### [X] T027 [US4] Update registry.py to remove deleted driver imports

**Description**: Remove imports of all deleted external drivers from `PowerDriverRegistry`. Keep only `manual` and `webhook`.

**Dependencies**: T025 (files must be deleted first)

**Files**:
- `src/provisioningserver/drivers/power/registry.py` (modify)

---

### [X] T028 [P] [US4] Update maasserver files to remove deleted driver imports

**Description**: Remove imports of deleted drivers from maasserver files.

**Dependencies**: T025 (files must be deleted first)

**Files**:
- `src/maasserver/api/doc.py` (modify)
- `src/maasserver/clusterrpc/driver_parameters.py` (modify)
- `src/maasserver/models/bmc.py` (modify)
- `src/maasserver/models/node.py` (modify)

---

### [X] T029 [US8] Adapt builtin manual and webhook drivers for new registry

**Description**: Ensure `manual` and `webhook` builtin drivers work with the refactored `PowerDriverRegistry` (no longer eagerly populated with external drivers).

**Dependencies**: T027 (registry must be updated)

**Files**:
- `src/provisioningserver/drivers/power/manual.py` (modify if needed)
- `src/provisioningserver/drivers/power/webhook.py` (modify if needed)

---

## Phase 6: External Driver Repositories (US4)

**Purpose**: Create the 19 independent driver repositories. Each is a fully independent project with its own test suite, documentation, and snapcraft configuration.

**Story Goal**: Each power driver is maintained in its own git repository as a fully independent project, one driver per repo, one driver per snap.

**Independent Test**: Each driver repo can be cloned, built standalone, test suite runs and passes, and `snapcraft` produces a valid snap.

### [X] T030 [P] [US4] Create maas-power-driver-ipmi repository

**Description**: Extract IPMI driver code, create HTTP server over UNIX socket, snapcraft config with `freeipmi-tools` dependency.

**Files Created** (external repo):
- `maas-power-driver-ipmi/` (full repo structure: pyproject.toml, README.md, snap/snapcraft.yaml, src/, tests/, Makefile)

---

### [X] T031 [P] [US4] Create maas-power-driver-redfish repository

**Description**: Extract Redfish driver code, create HTTP server over UNIX socket, snapcraft config with `python3-requests` dependency.

**Files Created** (external repo):
- `maas-power-driver-redfish/` (full repo structure)

---

### [X] T032 [P] [US4] Create maas-power-driver-amt repository

**Description**: Extract AMT driver code, create HTTP server over UNIX socket, snapcraft config with `amtterm`, `wsmancli` dependencies.

**Files Created** (external repo):
- `maas-power-driver-amt/` (full repo structure)

---

### [X] T033 [P] [US4] Create maas-power-driver-apc repository

**Description**: Extract APC driver code, create HTTP server over UNIX socket, snapcraft config with `snmp` dependency.

**Files Created** (external repo):
- `maas-power-driver-apc/` (full repo structure)

---

### [X] T034 [P] [US4] Create maas-power-driver-dli repository

**Description**: Extract DLI driver code, create HTTP server over UNIX socket, snapcraft config with `wget` dependency.

**Files Created** (external repo):
- `maas-power-driver-dli/` (full repo structure)

---

### [X] T035 [P] [US4] Create maas-power-driver-eaton repository

**Description**: Extract Eaton driver code, create HTTP server over UNIX socket.

**Files Created** (external repo):
- `maas-power-driver-eaton/` (full repo structure)

---

### [X] T036 [P] [US4] Create maas-power-driver-hmc repository

**Description**: Extract HMC driver code, create HTTP server over UNIX socket, snapcraft config with `python3-zhmcclient` dependency.

**Files Created** (external repo):
- `maas-power-driver-hmc/` (full repo structure)

---

### [X] T037 [P] [US4] Create maas-power-driver-hmcz repository

**Description**: Extract HMCz driver code, create HTTP server over UNIX socket, snapcraft config with `python3-zhmcclient` dependency.

**Files Created** (external repo):
- `maas-power-driver-hmcz/` (full repo structure)

---

### [X] T038 [P] [US4] Create maas-power-driver-moonshot repository

**Description**: Extract Moonshot driver code, create HTTP server over UNIX socket, snapcraft config with `ipmitool` dependency.

**Files Created** (external repo):
- `maas-power-driver-moonshot/` (full repo structure)

---

### [X] T039 [P] [US4] Create maas-power-driver-mscm repository

**Description**: Extract MSCM driver code, create HTTP server over UNIX socket, snapcraft config with `python3-zhmcclient` dependency.

**Files Created** (external repo):
- `maas-power-driver-mscm/` (full repo structure)

---

### [X] T040 [P] [US4] Create maas-power-driver-msftocs repository

**Description**: Extract MSFTOCS driver code, create HTTP server over UNIX socket.

**Files Created** (external repo):
- `maas-power-driver-msftocs/` (full repo structure)

---

### [X] T041 [P] [US4] Create maas-power-driver-openbmc repository

**Description**: Extract OpenBMC driver code, create HTTP server over UNIX socket, snapcraft config with `python3-requests` dependency.

**Files Created** (external repo):
- `maas-power-driver-openbmc/` (full repo structure)

---

### [X] T042 [P] [US4] Create maas-power-driver-proxmox repository

**Description**: Extract Proxmox driver code, create HTTP server over UNIX socket.

**Files Created** (external repo):
- `maas-power-driver-proxmox/` (full repo structure)

---

### [X] T043 [P] [US4] Create maas-power-driver-raritan repository

**Description**: Extract Raritan driver code, create HTTP server over UNIX socket.

**Files Created** (external repo):
- `maas-power-driver-raritan/` (full repo structure)

---

### [X] T044 [P] [US4] Create maas-power-driver-recs repository

**Description**: Extract RECS driver code, create HTTP server over UNIX socket.

**Files Created** (external repo):
- `maas-power-driver-recs/` (full repo structure)

---

### [X] T045 [P] [US4] Create maas-power-driver-seamicro repository

**Description**: Extract Seamount driver code, create HTTP server over UNIX socket, snapcraft config with `python3-seamicroclient` dependency.

**Files Created** (external repo):
- `maas-power-driver-seamicro/` (full repo structure)

---

### [X] T046 [P] [US4] Create maas-power-driver-ucsm repository

**Description**: Extract UCSM driver code, create HTTP server over UNIX socket.

**Files Created** (external repo):
- `maas-power-driver-ucsm/` (full repo structure)

---

### [X] T047 [P] [US4] Create maas-power-driver-vmware repository

**Description**: Extract VMware driver code, create HTTP server over UNIX socket, snapcraft config with `python3-pyvmomi` dependency.

**Files Created** (external repo):
- `maas-power-driver-vmware/` (full repo structure)

---

### [X] T048 [P] [US4] Create maas-power-driver-wedge repository

**Description**: Extract Wedge driver code, create HTTP server over UNIX socket.

**Files Created** (external repo):
- `maas-power-driver-wedge/` (full repo structure)

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final integration, validation, and cleanup.

### T049 Verify all Go tests pass in maas-agent

**Description**: Run `go test ./...` in `src/maasagent` to verify all power-related Go tests pass.

**Files**:
- `src/maasagent/internal/power/*_test.go`

---

### T050 Verify all Python tests pass

**Description**: Run `bin/test.rack -k power` and `bin/test.region -k power` to verify power driver tests pass.

---

### T051 Verify maas-power command no longer exists

**Description**: Confirm that `maas-power` is not available as a CLI command and no traces of `power_driver_command` remain in the codebase.

---

### T052 Verify no direct driver imports remain

**Description**: Search `provisioningserver` and `maasserver` for imports of specific power driver implementations. Only `manual` and `webhook` should remain.

---

### T053 Update documentation

**Description**: Update any documentation that references `maas-power`, the old driver architecture, or the removed stage-packages.

---

## Summary

| Phase | Tasks | User Stories | Description |
|-------|-------|--------------|-------------|
| 1: Setup | T001-T005 | Foundational | Project structure, stubs for Go/Python components |
| 2: Go maas-agent | T006-T011 | US1, US2, US3 | Socket client, discovery, registry, signal handler |
| 3: Snap Integration | T012-T017 | US5, US6 | Content slot, hooks, runtime directory |
| 4: v3 Internal API | T018-T024 | US7 | DB table, migration, model, repo, service, API handler |
| 5: Remove External Code | T025-T029 | US4, US8 | Delete 19 drivers, remove maas-power, adapt builtins |
| 6: External Repos | T030-T048 | US4 | Create 19 independent driver repositories |
| 7: Polish | T049-T053 | US8 | Testing, validation, documentation |

**Total tasks**: 53
**Parallel opportunities**: T001-T005 (all parallel), T006-T008 (parallel within Go), T012-T015 (parallel snap tasks), T018-T022 (parallel Python layer), T030-T048 (all 19 driver repos are parallel)
**Suggested MVP scope**: Phases 1-4 (maas-agent discovery + v3 API) — enables driver snap discovery and region notification without requiring external repos to exist yet.

## Dependencies

```
Phase 1 (Setup) → Phase 2 (Go maas-agent) → Phase 3 (Snap Integration)
                                              ↓
Phase 1 (Setup) → Phase 4 (v3 Internal API) → Phase 5 (Remove External Code)
                                                          ↓
                                                    Phase 6 (External Repos)
                                                          ↓
                                                    Phase 7 (Polish & Validation)
```

**User Story completion order**:
1. US1 (discovery) + US2 (capabilities) + US3 (invocation) — Phase 2
2. US5 (driver snaps) + US6 (socket directory) — Phase 3
3. US7 (region notification) — Phase 4
4. US4 (independent repos) — Phase 5 + Phase 6
5. US8 (preservation) — Phase 5 + Phase 7
