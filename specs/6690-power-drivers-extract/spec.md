# Feature Specification: Extract Power Drivers to Independent Repositories

**Feature Branch**: `6690-power-drivers-extract`  
**Created**: 2025-01-13  
**Status**: Draft  
**Input**: Move power drivers to their own repositories with snap plug/slot discovery mechanism, language-agnostic interface via JSON metadata, and snap distribution.

## Clarifications

- **Language-agnostic**: Power drivers may be implemented in any programming language (Python, Go, Rust, etc.). The interface between MAAS and drivers is a JSON-based protocol, not a language-specific API.
- **Snap plug/slot discovery**: Drivers are distributed as separate snaps. When a driver snap connects to the MAAS snap (via a content plug and slot), it exposes driver metadata as a JSON file at a known path. MAAS discovers drivers by scanning these JSON files at runtime.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - MAAS discovers power drivers via snap plug/slot connections (Priority: P1)

**Description**: When a power driver snap is installed and connected to the MAAS snap, MAAS automatically discovers the driver by reading a JSON metadata file exposed through the snap's content interface. No MAAS core changes are required to add new drivers — installing and connecting a driver snap is sufficient.

**Why this priority**: This is the foundational capability. Without snap-based discovery, the entire separation architecture cannot function. All other stories depend on this working correctly.

**Independent Test**: Can be fully tested by building a minimal driver snap with a valid metadata JSON, installing it, connecting it to the MAAS snap, and verifying that `PowerDriverRegistry` contains the driver after MAAS reloads its driver list.

**Acceptance Scenarios**:

1. **Given** a fresh MAAS installation with no driver snaps connected, **When** the rack controller starts, **Then** only builtin drivers (e.g., `manual`) are available in `PowerDriverRegistry`
2. **Given** a driver snap `maas-power-driver-ipmi` is installed and connected to MAAS, **When** MAAS reloads its driver list, **Then** the `ipmi` driver is discoverable via `PowerDriverRegistry.get_item("ipmi")`
3. **Given** multiple driver snaps are connected, **When** MAAS reloads its driver list, **Then** all drivers from all connected snaps are registered and available
4. **Given** a driver snap is disconnected, **When** MAAS reloads its driver list, **Then** that driver is no longer available in the registry
5. **Given** a driver snap's metadata JSON is malformed, **When** MAAS attempts to discover it, **Then** MAAS logs a warning and skips that driver but continues discovering others
6. **Given** a driver snap is connected while MAAS is running, **When** MAAS detects the new connection (via snap change notification or periodic scan), **Then** the new driver becomes available without a full MAAS restart

### User Story 2 - Driver snaps expose metadata via JSON at the snap interface (Priority: P1)

**Description**: Each power driver snap exposes a JSON metadata file at a known path through its content interface. This file describes the driver's capabilities, parameters, and how MAAS should invoke it. The JSON schema is defined by the MAAS power driver interface contract.

**Why this priority**: This defines the contract between MAAS and driver snaps. Without a standardized metadata format, discovery and invocation cannot work.

**Independent Test**: Can be tested by creating a minimal driver snap that exposes a metadata JSON file, connecting it to MAAS, and verifying that MAAS can read and validate the metadata.

**Acceptance Scenarios**:

1. **Given** a driver snap connected to MAAS, **When** MAAS reads the metadata JSON at the interface path, **Then** the JSON is valid against the power driver metadata schema
2. **Given** a metadata JSON file, **When** validated, **Then** it contains: driver `name`, `description`, `version`, `settings` (parameter schema), `executable` path, and supported `actions`
3. **Given** a metadata JSON with invalid or missing required fields, **When** MAAS validates it, **Then** MAAS rejects the driver and logs the validation error
4. **Given** a driver snap is updated (new version), **When** the metadata JSON changes, **Then** MAAS detects the change and reloads the driver metadata
5. **Given** the metadata JSON, **When** inspected, **Then** it contains no language-specific information — the format is identical regardless of whether the driver is written in Python, Go, Rust, or any other language

### User Story 3 - MAAS invokes power drivers via a language-agnostic protocol (Priority: P1)

**Description**: MAAS communicates with power drivers through a language-agnostic protocol (subprocess with JSON on stdin/stdout, or a local HTTP endpoint). MAAS core code never imports or links against driver code directly. Power actions (on, off, query, cycle, reset) are sent as structured requests and receive structured responses.

**Why this priority**: This ensures true decoupling. Drivers can be written in any language and updated independently of MAAS. The protocol is the only contract between MAAS and drivers.

**Independent Test**: Can be tested by implementing a minimal driver in a non-Python language (e.g., a shell script or Go binary) that speaks the protocol, connecting it via a test snap, and verifying that MAAS can execute power actions through it.

**Acceptance Scenarios**:

1. **Given** a machine with power type `ipmi`, **When** a power query is requested via RPC, **Then** MAAS invokes the driver through the protocol and receives the power state
2. **Given** a driver implemented in Go, **When** connected via snap, **Then** MAAS can execute all supported power actions through it
3. **Given** a driver implemented in Python, **When** connected via snap, **Then** MAAS can execute all supported power actions through it
4. **Given** a driver crashes or becomes unresponsive, **When** MAAS attempts to invoke it, **Then** MAAS receives a clear error and reports it to the user
5. **Given** `provisioningserver` source code, **When** searched for direct driver imports, **Then** no import of specific power driver implementations exists (only the protocol client and registry)

### User Story 4 - Power drivers are distributed as standalone snaps (Priority: P2)

**Description**: Each power driver (or group of related drivers) is packaged as a standalone snap. The snap includes the driver executable, its metadata JSON, and any system-level dependencies. Installing a driver is `snap install` + `snap connect`.

**Why this priority**: This enables the operational model where drivers can be installed, updated, and uninstalled independently of MAAS core and independently of each other.

**Independent Test**: Can be tested by building a driver snap with `snapcraft`, installing it locally, connecting it to MAAS, and verifying that the driver is discovered and functional.

**Acceptance Scenarios**:

1. **Given** a driver snap, **When** `snap install --dangerous driver.snap` is run, **Then** the snap installs successfully
2. **Given** a driver snap is installed, **When** `snap connect maas:power-drivers driver:power-drivers` is run, **Then** the driver's metadata becomes visible to MAAS
3. **Given** a driver snap is removed, **When** `snap remove driver` is run, **Then** the driver is no longer available to MAAS
4. **Given** a driver snap is updated, **When** `snap refresh driver` is run, **Then** MAAS picks up the updated driver metadata and version

### User Story 5 - The MAAS snap exposes a content slot for driver discovery (Priority: P1)

**Description**: The MAAS snap declares a content slot (`power-drivers`) that driver snaps connect to via a content plug. When connected, the slot provides MAAS with access to driver metadata JSON files. The slot path is a directory that driver snaps populate with their metadata.

**Why this priority**: This is the mechanism that makes discovery work. Without the snap content interface, MAAS cannot find or read driver metadata.

**Independent Test**: Can be tested by verifying that the MAAS snap declares the content slot, that a test driver snap can connect to it, and that MAAS can read the metadata JSON from the connected path.

**Acceptance Scenarios**:

1. **Given** the MAAS snap, **When** `snap info maas` is run, **Then** a `power-drivers` content slot is declared
2. **Given** a driver snap with a `power-drivers` content plug, **When** `snap connect maas:power-drivers driver:power-drivers` is run, **Then** the connection succeeds and the driver's metadata JSON is accessible at the slot path
3. **Given** multiple driver snaps connected, **When** MAAS scans the slot path, **Then** each driver's metadata JSON is found and loaded
4. **Given** a driver snap is disconnected, **When** MAAS scans the slot path, **Then** the disconnected driver's metadata is no longer present

### User Story 6 - Existing power functionality is preserved after extraction (Priority: P1)

**Description**: After moving drivers to separate packages, all existing power actions (on, off, query, cycle, reset, set-boot-order) continue to work as before. The `maas-power` CLI, RPC power commands, and UI power controls function identically.

**Why this priority**: This is a refactoring feature. If existing functionality breaks, the extraction has failed. Must be verified for all 21 existing driver types.

**Independent Test**: Can be tested by running the full existing power driver test suite against the refactored code, verifying all tests pass.

**Acceptance Scenarios**:

1. **Given** the refactored code with drivers in separate packages, **When** the existing test suite `bin/test.rack` is run for power drivers, **Then** all tests pass
2. **Given** the refactored code, **When** `maas-power ipmi status --power-address 10.0.0.1 --power-user admin --power-pass secret` is run, **Then** the command executes and returns power status
3. **Given** the refactored code, **When** the region controller requests power types from the rack controller via `DescribePowerTypes` RPC, **Then** all installed drivers are returned in the schema
4. **Given** the refactored code, **When** a BMC's power parameters are sanitized, **Then** secret parameters are correctly separated from non-secret parameters using `sanitise_power_parameters()`

## Assumptions

- Power drivers may be written in any programming language (Python, Go, Rust, C, shell, etc.)
- The communication protocol between MAAS and drivers is language-agnostic (JSON over subprocess stdin/stdout or local HTTP)
- Snap content interfaces (plug/slot) are the discovery mechanism — not Python entry points, shared libraries, or other language-specific mechanisms
- Driver snaps run with `strict` confinement (same as MAAS)
- System-level dependencies (e.g., `freeipmi-tools`, `amtterm`) are included in the driver snap, not the MAAS snap
- The `manual` power driver remains builtin in MAAS core (no external dependencies, always available)
- Pod drivers (LXD, Virsh) follow a similar but separate extraction path (out of scope for this feature)
- Third-party power drivers are a valid use case (anyone can build a driver snap)
- The metadata JSON schema is versioned to allow backward-compatible evolution

## Key Entities

### Power Driver Metadata JSON
- **Purpose**: Describes a driver's capabilities, parameters, and invocation details to MAAS
- **Location**: Exposed at the snap content interface path when the driver snap is connected
- **Schema** (key fields):
  - `name`: Unique driver identifier (e.g., `ipmi`, `redfish`)
  - `description`: Human-readable description
  - `version`: Driver version string
  - `actions`: List of supported actions (`on`, `off`, `query`, `cycle`, `reset`, `set-boot-order`)
  - `settings`: Array of parameter definitions (name, label, type, required, choices, scope, secret)
  - `ip_extractor`: Field name and regex pattern for extracting IP address from parameters
  - `executable`: Path to the driver binary/script within the snap
  - `protocol`: Communication method (`subprocess` or `http`)
  - `capabilities`: Flags (`queryable`, `chassis`, `can_probe`, `can_set_boot_order`)
- **Validation**: MAAS validates metadata against a JSON Schema before accepting the driver

### Power Driver Protocol
- **Purpose**: Language-agnostic communication between MAAS and driver processes
- **Transport**: Subprocess with JSON lines on stdin/stdout (primary), or local HTTP (alternative)
- **Request format**: JSON object with `action`, `system_id`, `hostname`, `context` (power parameters)
- **Response format**: JSON object with `state` (for query) or `status`/`error` (for actions)
- **Error format**: JSON object with `error_type` and `error_message`
- **Lifecycle**: Driver process is started per-action (subprocess) or long-running (HTTP)

### Power Driver Registry
- **Purpose**: Runtime registry of all discovered power drivers
- **Operations**: `register_item()`, `get_item()`, `get_schema()`, iteration over registered drivers
- **Discovery**: Populated by scanning the snap content slot path for metadata JSON files
- **Reload**: Supports hot-reload when snaps are connected/disconnected/updated

### Snap Content Interface
- **Purpose**: The snap plug/slot mechanism that exposes driver metadata to MAAS
- **Slot** (MAAS snap): `power-drivers` — a directory where driver metadata JSON files appear
- **Plug** (driver snap): `power-drivers` — connects to MAAS's slot, provides metadata JSON
- **Path convention**: Each driver writes a single metadata JSON file named `<driver-name>.json`

### Driver Grouping
- **Purpose**: Logical grouping of related drivers into shared snaps
- **Groups**:
  - `maas-power-drivers-core`: `manual` (builtin in MAAS snap)
  - `maas-power-driver-ipmi`: `ipmi`, `moonshot`
  - `maas-power-driver-redfish`: `redfish`, `openbmc`
  - `maas-power-driver-ibm`: `hmc`, `hmcz`, `mscm`
  - `maas-power-driver-amt`: `amt`
  - `maas-power-driver-apc`: `apc`
  - `maas-power-driver-vmware`: `vmware`, `proxmox`
  - `maas-power-driver-webhook`: `webhook`
  - `maas-power-drivers-legacy`: `dli`, `eaton`, `raritan`, `recs`, `seamicro`, `ucsm`, `wedge`

## Success Criteria

- MAAS rack controller discovers all connected driver snaps within 1 second of snap connection
- Zero power driver tests fail after extraction (100% test pass rate preserved)
- All 21 existing power driver types remain functional after extraction
- The `maas-power` CLI works with all connected drivers without modification
- A new power driver can be added by building and connecting a driver snap (no MAAS core changes required)
- A power driver written in a non-Python language (e.g., Go) can be discovered and invoked by MAAS
- The metadata JSON schema is published and versioned for third-party driver authors
- No breaking changes to existing MAAS APIs or RPC interfaces
- The MAAS snap declares a `power-drivers` content slot that driver snaps can connect to

## Non-Goals

- This feature does not extract pod drivers (LXD, Virsh) — they are out of scope
- This feature does not create a new API for power management — existing APIs are preserved
- This feature does not change how power parameters are stored in the database
- This feature does not introduce a new authentication or authorization model for drivers
- This feature does not require changes to the MAAS UI
- This feature does not publish driver snaps to the Snap Store (that is a follow-up)
- This feature does not define a driver SDK or CLI tooling for driver authors (that is a follow-up)
