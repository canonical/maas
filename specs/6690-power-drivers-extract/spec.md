# Feature Specification: Extract Power Drivers to Independent Repositories

**Feature Branch**: `6690-power-drivers-extract`  
**Created**: 2025-01-13  
**Status**: Draft  
**Input**: Move power drivers to their own repositories as snap services communicating over UNIX sockets, with rack-to-region driver lifecycle notifications.

## Clarifications

- **Language-agnostic**: Power drivers may be implemented in any programming language (Python, Go, Rust, etc.). The interface between MAAS and drivers is HTTP over UNIX domain sockets, not a language-specific API.
- **Driver services**: Each power driver runs as a long-running snap service. The rack controller (`rackd`) communicates with driver services over HTTP on UNIX domain sockets exposed through the snap interface.
- **No metadata JSON**: Driver capabilities are discovered by querying the live service at its UNIX socket. There is no static metadata file.
- **`maas-power` removed entirely**: The `maas-power` command (currently in `provisioningserver/power_driver_command.py`) is removed. It is not deprecated — it simply no longer exists. Driver snaps provide their own CLI tools for testing and direct invocation.
- **Independent repositories**: Each power driver lives in its own git repository as an independent project. No driver grouping — one driver per repo, one driver per snap.
- **`webhook` and `manual` builtin**: The `webhook` and `manual` power drivers remain builtin in MAAS core (no external dependencies). `webhook` is useful for custom integrations; `manual` is useful for nodes without automated BMC access. All other drivers are external snaps.
- **Rack-to-region driver lifecycle (v3 internal API)**: When drivers appear or disappear (snap connect/disconnect), the rack controller notifies the region controller via the v3 internal API so the region's view of available power types stays in sync. This is not the legacy RPC channel.
- **Per-rack driver versions**: Each rack can run a different version of the same driver. For example, rack A may run `ipmi` 1.0.0 while rack B runs `ipmi` 2.0.0. The region merges all registered driver versions across racks and associates machines with the correct driver version based on which rack manages them.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Rack controller discovers driver services via UNIX sockets (Priority: P1)

**Description**: When a power driver snap is installed, connected, and its service is running, the rack controller (`rackd`) discovers the driver by connecting to its UNIX domain socket through the snap interface. The rack queries the service to learn the driver's name, capabilities, and parameter schema. No MAAS core changes are required to add new drivers — installing, connecting, and starting a driver snap is sufficient.

**Why this priority**: This is the foundational capability. Without service-based discovery, the entire separation architecture cannot function. All other stories depend on this working correctly.

**Independent Test**: Can be fully tested by building a minimal driver snap that runs a service listening on a UNIX socket, connecting it to the MAAS snap, and verifying that `rackd` discovers the driver and populates `PowerDriverRegistry`.

**Acceptance Scenarios**:

1. **Given** a fresh MAAS installation with no driver snaps connected, **When** `rackd` starts, **Then** only the builtin `webhook` and `manual` drivers are available in `PowerDriverRegistry`
2. **Given** a driver snap `maas-power-driver-ipmi` is installed, connected, and its service is running, **When** `rackd` discovers available sockets, **Then** the `ipmi` driver is discoverable via `PowerDriverRegistry.get_item("ipmi")`
3. **Given** multiple driver snaps are connected and running, **When** `rackd` discovers available sockets, **Then** all drivers are registered and available
4. **Given** a driver snap is disconnected or its service stops, **When** `rackd` detects the socket is unavailable, **Then** that driver is removed from the registry
5. **Given** a driver service is unresponsive, **When** `rackd` attempts to query it, **Then** `rackd` logs a warning and marks the driver as unavailable but continues operating with other drivers
6. **Given** a driver snap is connected and its service starts while `rackd` is running, **When** `rackd` detects the new socket, **Then** the new driver becomes available without a `rackd` restart

### User Story 2 - Rack controller queries driver services for capabilities (Priority: P1)

**Description**: When `rackd` connects to a driver service's UNIX socket, it sends a capabilities request. The service responds with its driver name, description, version, supported actions, parameter schema, and capability flags. This replaces any static metadata file — the live service is the source of truth.

**Why this priority**: This defines the contract between `rackd` and driver services. Without a standardized capabilities query, `rackd` cannot know what a driver supports.

**Independent Test**: Can be tested by implementing a minimal driver service that responds to a capabilities query on its UNIX socket, connecting it to MAAS, and verifying that `rackd` receives and registers the driver's capabilities.

**Acceptance Scenarios**:

1. **Given** a driver service is running and accessible via its UNIX socket, **When** `rackd` sends a capabilities request, **Then** the service responds with: driver `name`, `description`, `version`, `actions`, `settings` (parameter schema), and `capabilities` (flags)
2. **Given** a capabilities response, **When** validated by `rackd`, **Then** all required fields are present and well-formed
3. **Given** a driver service responds with an invalid or incomplete capabilities message, **When** `rackd` processes it, **Then** `rackd` rejects the driver and logs the validation error
4. **Given** a driver service is updated (new version), **When** `rackd` queries it again, **Then** `rackd` receives the updated capabilities and version
5. **Given** the capabilities response, **When** inspected, **Then** it contains no language-specific information — the format is identical regardless of whether the driver is written in Python, Go, Rust, or any other language

### User Story 3 - Rack controller invokes power drivers over UNIX sockets (Priority: P1)

**Description**: `rackd` communicates with power driver services over UNIX domain sockets. Power actions (on, off, query, cycle, reset, set-boot-order) are sent as structured JSON requests and receive structured JSON responses. The driver service is long-running — `rackd` does not start or stop it.

**Why this priority**: This ensures true decoupling. Drivers can be written in any language and updated independently of MAAS. The UNIX socket protocol is the only contract between `rackd` and drivers.

**Independent Test**: Can be tested by implementing a minimal driver service in any language that listens on a UNIX socket and responds to power action requests, connecting it via snap, and verifying that `rackd` can execute power actions through it.

**Acceptance Scenarios**:

1. **Given** a machine with power type `ipmi`, **When** a power query is requested via RPC, **Then** `rackd` sends a query request to the ipmi driver's UNIX socket and receives the power state
2. **Given** a driver implemented in Go, **When** connected via snap and running as a service, **Then** `rackd` can execute all supported power actions through its UNIX socket
3. **Given** a driver implemented in Python, **When** connected via snap and running as a service, **Then** `rackd` can execute all supported power actions through its UNIX socket
4. **Given** a driver service crashes or becomes unresponsive, **When** `rackd` attempts to send a request, **Then** `rackd` receives a clear error and reports it to the user
5. **Given** `provisioningserver` source code, **When** searched for direct driver imports, **Then** no import of specific power driver implementations exists (only the socket client and registry)

### User Story 4 - Each power driver is an independent project (Priority: P1)

**Description**: Each power driver is maintained in its own git repository as a fully independent project. There is no driver grouping — one driver per repository, one driver per snap. Driver teams can develop, version, and release independently of MAAS core and independently of each other.

**Why this priority**: Independent repositories enable independent versioning, separate CI pipelines, and clear ownership. Without this, drivers cannot truly be maintained separately from MAAS.

**Independent Test**: Can be tested by verifying that a driver repository contains its own test suite (runnable without the MAAS monorepo), its own documentation, and its own `snap/snapcraft.yaml` for building the driver snap.

**Acceptance Scenarios**:

1. **Given** a driver repository (e.g., `maas-power-driver-ipmi`), **When** cloned and built standalone, **Then** its test suite runs and passes without requiring the MAAS monorepo
2. **Given** a driver repository, **When** inspected, **Then** it contains documentation describing the driver's supported BMC types, configuration parameters, and known limitations
3. **Given** a driver repository, **When** `snapcraft` is run, **Then** a driver snap is produced that can be installed and connected to MAAS
4. **Given** a driver repository, **When** its version is bumped and released, **Then** the new driver snap can be released without touching the MAAS repository
5. **Given** the MAAS monorepo after extraction, **When** searched for driver implementation code, **Then** no driver implementation files exist (only the protocol client, registry, and builtin `webhook` and `manual` drivers remain)

### User Story 5 - Driver snaps run as long-running services (Priority: P1)

**Description**: Each power driver snap declares a snap service that starts automatically when the snap is installed. The service listens on a UNIX domain socket at a known path within the snap's interface directory. The snap includes the driver binary, any system-level dependencies, and the snapcraft configuration. Installing a driver is `snap install` + `snap connect`.

**Why this priority**: Long-running services eliminate per-action startup overhead and allow drivers to maintain state (e.g., connection pools, session caches) between power operations.

**Independent Test**: Can be tested by building a driver snap with `snapcraft` that declares a service, installing it, connecting it to MAAS, and verifying that the service is running and listening on its UNIX socket.

**Acceptance Scenarios**:

1. **Given** a driver snap, **When** `snap install --dangerous driver.snap` is run, **Then** the snap installs and its service starts automatically
2. **Given** a driver snap is installed and connected, **When** `snap services driver` is run, **Then** the driver service is listed as active
3. **Given** a driver snap is removed, **When** `snap remove driver` is run, **Then** the service stops and the UNIX socket is removed
4. **Given** a driver snap is updated, **When** `snap refresh driver` is run, **Then** the service restarts with the updated version and `rackd` picks up the new capabilities

### User Story 6 - The MAAS snap exposes a UNIX socket directory for driver services (Priority: P1)

**Description**: The MAAS snap declares a content slot (`power-drivers`) that provides a shared directory where driver snaps place their UNIX domain sockets. When a driver snap connects its plug to MAAS's slot, its service writes a UNIX socket into that shared directory. `rackd` scans this directory to discover available driver services.

**Why this priority**: This is the mechanism that makes discovery work. Without the shared socket directory, `rackd` cannot find or connect to driver services.

**Independent Test**: Can be tested by verifying that the MAAS snap declares the content slot, that a test driver snap can connect to it, and that the driver's UNIX socket appears in the shared directory.

**Acceptance Scenarios**:

1. **Given** the MAAS snap, **When** `snap info maas` is run, **Then** a `power-drivers` content slot is declared
2. **Given** a driver snap with a `power-drivers` content plug, **When** `snap connect maas:power-drivers driver:power-drivers` is run, **Then** the connection succeeds and the driver's UNIX socket is accessible in the shared directory
3. **Given** multiple driver snaps connected, **When** `rackd` scans the shared directory, **Then** each driver's UNIX socket is found and connected to
4. **Given** a driver snap is disconnected, **When** `rackd` scans the shared directory, **Then** the disconnected driver's socket is no longer present

### User Story 7 - Rack controller notifies region of driver lifecycle changes via v3 internal API (Priority: P1)

**Description**: When drivers appear or disappear on a rack (due to snap connect/disconnect/service start/stop), `rackd` notifies the region controller of the change via the v3 internal API. The region updates its view of available power types for that rack. This ensures the region's power type list stays in sync with what each rack actually supports. This notification does not use the legacy RPC channel.

**Why this priority**: The region controller needs to know which power types each rack supports (for form generation, validation, documentation). Without lifecycle notifications, the region's view becomes stale when drivers are added or removed.

**Independent Test**: Can be tested by connecting a driver snap to a rack controller and verifying that the region controller receives a notification and updates its power type list for that rack.

**Acceptance Scenarios**:

1. **Given** a driver snap is connected to a rack controller, **When** `rackd` discovers the new driver, **Then** `rackd` calls the v3 internal API to register the driver's capabilities with the region controller
2. **Given** a driver snap is disconnected from a rack controller, **When** `rackd` detects the driver is gone, **Then** `rackd` calls the v3 internal API to remove the driver from the region controller
3. **Given** the region controller receives a driver addition via the v3 internal API, **When** it processes the notification, **Then** the new power type appears in the rack's available power types
4. **Given** the region controller receives a driver removal via the v3 internal API, **When** it processes the notification, **Then** the removed power type no longer appears in the rack's available power types
5. **Given** `rackd` starts and discovers existing driver services, **When** it communicates with the region, **Then** the region receives the complete set of available power types for that rack via the v3 internal API
6. **Given** rack A runs `ipmi` 1.0.0 and rack B runs `ipmi` 2.0.0, **When** the region merges driver registrations, **Then** both versions are tracked independently and machines on each rack use the correct version

### User Story 8 - Existing power functionality is preserved after extraction (Priority: P1)

**Description**: After moving drivers to separate snap services, all existing power actions (on, off, query, cycle, reset, set-boot-order) continue to work as before. RPC power commands and UI power controls function identically. The `maas-power` command no longer exists.

**Why this priority**: This is a refactoring feature. If existing functionality breaks, the extraction has failed. Must be verified for all 21 existing driver types.

**Independent Test**: Can be tested by running the full existing power driver test suite against the refactored code, verifying all tests pass.

**Acceptance Scenarios**:

1. **Given** the refactored code with drivers as snap services, **When** the existing test suite `bin/test.rack` is run for power drivers, **Then** all tests pass
2. **Given** the refactored code, **When** the region controller requests power types from the rack controller via `DescribePowerTypes` RPC, **Then** all connected drivers are returned in the schema
3. **Given** the refactored code, **When** a BMC's power parameters are sanitized, **Then** secret parameters are correctly separated from non-secret parameters using `sanitise_power_parameters()`
4. **Given** a driver snap is connected to a rack, **When** the region queries that rack for available power types, **Then** the new driver appears in the rack's power type list
5. **Given** the MAAS monorepo after extraction, **When** searched for `maas-power` or `power_driver_command`, **Then** no traces of the command remain

## Assumptions

- Power drivers may be written in any programming language (Python, Go, Rust, C, shell, etc.)
- Each driver runs as a long-running service communicating over HTTP on UNIX domain sockets
- Driver capabilities are discovered by querying the live service — there is no static metadata JSON file
- Snap content interfaces (plug/slot) provide a shared directory for UNIX sockets
- Driver snaps run with `strict` confinement (same as MAAS)
- System-level dependencies (e.g., `freeipmi-tools`, `amtterm`) are included in the driver snap, not the MAAS snap
- The `webhook` and `manual` power drivers remain builtin in MAAS core (no external dependencies)
- Each driver is an independent project — no driver grouping, one driver per repo and per snap, with the exception of built-in power drivers.
- Pod drivers (LXD, Virsh) follow a similar but separate extraction path (out of scope for this feature)
- Driver code, tests, and documentation are maintained in driver repositories, not the MAAS monorepo, with the exception of built-in power drivers.
- Third-party power drivers are a valid use case (anyone can build a driver snap)
- Each driver repository has its own CI pipeline for testing and snap building
- The rack controller is responsible for driver discovery and for notifying the region of driver lifecycle changes via the v3 internal API

## Key Entities

### Driver Service Protocol (HTTP over UNIX Socket)
- **Purpose**: Language-agnostic communication between `rackd` and driver services
- **Transport**: HTTP over UNIX domain socket in the shared snap content directory
- **Wire format**: Standard HTTP requests/responses with JSON bodies
- **Endpoints**:
  - `GET /metadata` — returns driver metadata (name, description, version, actions, settings, capability flags)
  - `POST /query` — returns current power state (`on`, `off`, `unknown`)
  - `POST /on` — powers on the node
  - `POST /off` — powers off the node
  - `POST /cycle` — cycles power
  - `POST /reset` — resets power
  - `POST /set-boot-order` — configures boot order
- **Request body**: JSON object with `system_id` and `context` (power parameters). `system_id` alone is sufficient to identify the target system.
- **Response format**: JSON object with `status` (`ok`/`error`), optional `state` (for queries), optional `error_type` and `error_message`
- **HTTP status codes**: 200 for success, 503 for unavailable, 400 for invalid parameters, 500 for driver errors
- **Lifecycle**: Driver is a long-running service; `rackd` connects as needed, does not manage the service lifecycle

### Power Driver Registry
- **Purpose**: Runtime registry of all discovered power drivers on a rack
- **Operations**: `register_item()`, `get_item()`, `get_schema()`, iteration over registered drivers
- **Discovery**: Populated by `rackd` scanning the shared socket directory and querying each service for capabilities
- **Reload**: Supports hot-reload when driver services appear or disappear

### Snap Content Interface
- **Purpose**: The snap plug/slot mechanism that provides a shared directory for UNIX sockets
- **Slot** (MAAS snap): `power-drivers` — a directory where driver services place their UNIX sockets
- **Plug** (driver snap): `power-drivers` — connects to MAAS's slot, driver service writes its socket here
- **Socket naming**: Each driver writes a UNIX socket named `<driver-name>.sock`

### Rack-to-Region Driver Lifecycle Notification
- **Purpose**: Keeps the region's view of available power types in sync with each rack
- **Trigger**: Driver service appears (snap connect + service start) or disappears (snap disconnect / service stop)
- **Direction**: Rack controller → Region controller (via v3 internal API, not legacy RPC)
- **Payload**: Driver metadata (same as the `/metadata` endpoint response) for additions; driver name for removals
- **On rack startup**: `rackd` registers the complete set of available drivers with the region via the v3 internal API

### Driver Repository Structure
- **Purpose**: Standard layout for each driver's git repository
- **Contents**:
  - Driver implementation source code (service binary)
  - Test suite (unit tests, integration tests against real or mocked BMCs)
  - Documentation (driver-specific README, supported hardware, configuration guide)
  - `snap/snapcraft.yaml` (snap build configuration, declares the service and content plug)
  - Protocol client library (for testing: a small client that speaks the UNIX socket protocol)
- **Independence**: Each repository builds, tests, and releases without requiring the MAAS monorepo

### Driver Listing
- **Purpose**: Each driver is an independent project — no grouping
- **Drivers**:
  - `manual` (builtin in MAAS snap)
  - `webhook` (builtin in MAAS snap)
  - `ipmi` (independent snap)
  - `redfish` (independent snap)
  - `amt` (independent snap)
  - `apc` (independent snap)
  - `dli` (independent snap)
  - `eaton` (independent snap)
  - `hmc` (independent snap)
  - `hmcz` (independent snap)
  - `moonshot` (independent snap)
  - `mscm` (independent snap)
  - `msftocs` (independent snap)
  - `openbmc` (independent snap)
  - `proxmox` (independent snap)
  - `raritan` (independent snap)
  - `recs` (independent snap)
  - `seamicro` (independent snap)
  - `ucsm` (independent snap)
  - `vmware` (independent snap)
  - `wedge` (independent snap)

## Success Criteria

- MAAS rack controller discovers all connected driver services within 1 second of service start
- Zero power driver tests fail after extraction (100% test pass rate preserved)
- All 19 external power driver types remain functional after extraction (manual and webhook stay builtin)
- A new power driver can be added by building and connecting a driver snap (no MAAS core changes required)
- A power driver written in a non-Python language (e.g., Go) can be discovered and invoked by `rackd`
- The HTTP-over-UNIX-socket protocol specification is published for third-party driver authors
- No breaking changes to existing MAAS APIs or RPC interfaces
- The MAAS snap declares a `power-drivers` content slot that driver snaps can connect to
- The region controller receives timely notifications via the v3 internal API when drivers are added or removed from a rack
- The `maas-power` command and `power_driver_command.py` are completely removed from the MAAS codebase
- Each driver repository is self-contained (code, tests, docs, snapcraft config) and builds independently

## Non-Goals

- This feature does not extract pod drivers (LXD, Virsh) — they are out of scope
- This feature does not create a new API for power management — existing APIs are preserved
- This feature does not change how power parameters are stored in the database
- This feature does not introduce a new authentication or authorization model for drivers
- This feature does not require changes to the MAAS UI
- This feature does not publish driver snaps to the Snap Store (that is a follow-up)
- This feature does not define a driver SDK or CLI tooling for driver authors (that is a follow-up)
- This feature does not define a driver SDK or language bindings for the HTTP-over-UNIX-socket protocol (that is a follow-up)
- This feature does not preserve the `maas-power` command — it is removed entirely
