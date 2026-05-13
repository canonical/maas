# Feature Specification: Extract Power Drivers to Independent Repositories

**Feature Branch**: `6690-power-drivers-extract`  
**Created**: 2025-01-13  
**Status**: Draft  
**Input**: Move power drivers to their own repositories with entry point discovery mechanism, common interface, and snap distribution.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - MAAS discovers installed power drivers at startup (Priority: P1)

**Description**: When MAAS region or rack controller starts, it automatically discovers all installed power driver packages through Python entry points. Administrators install power driver packages separately, and MAAS recognizes them without requiring changes to MAAS core.

**Why this priority**: This is the foundational capability. Without runtime discovery, the entire separation architecture cannot function. All other stories depend on this working correctly.

**Independent Test**: Can be fully tested by installing a mock power driver package with an entry point, starting the rack controller, and verifying that `PowerDriverRegistry` contains the driver. Delivers a working plugin architecture.

**Acceptance Scenarios**:

1. **Given** a fresh MAAS installation with no external power drivers, **When** the rack controller starts, **Then** only builtin drivers (e.g., `manual`) are available in `PowerDriverRegistry`
2. **Given** a MAAS installation with `maas-power-driver-ipmi` package installed, **When** the rack controller starts, **Then** the `ipmi` driver is discoverable via `PowerDriverRegistry.get_item("ipmi")`
3. **Given** multiple power driver packages are installed, **When** the rack controller starts, **Then** all drivers from all packages are registered and available
4. **Given** a power driver package is uninstalled, **When** the rack controller restarts, **Then** that driver is no longer available in the registry
5. **Given** a power driver package fails to load (import error), **When** the rack controller starts, **Then** MAAS logs a warning but continues startup with remaining drivers

### User Story 2 - Power driver packages declare themselves via standard entry point (Priority: P1)

**Description**: Power driver package authors implement the `PowerDriverBase` interface and register their driver under the `maas.power_drivers` entry point group. The package declares its dependency on `maas-power-driver-interface`.

**Why this priority**: This defines the contract between MAAS and driver packages. Without a standardized registration mechanism, discovery cannot work.

**Independent Test**: Can be tested by creating a minimal Python package with an entry point that loads a driver class, verifying that `importlib.metadata.entry_points(group="maas.power_drivers")` returns it, and that the loaded class implements the required interface.

**Acceptance Scenarios**:

1. **Given** a driver package with `maas.power_drivers` entry point, **When** `importlib.metadata.entry_points(group="maas.power_drivers")` is called, **Then** the entry point is returned with the driver's name and import path
2. **Given** an entry point loads successfully, **When** instantiated, **Then** the driver class implements all required properties (`name`, `description`, `settings`, `ip_extractor`, `queryable`, `chassis`, `can_probe`, `can_set_boot_order`)
3. **Given** an entry point loads successfully, **When** instantiated, **Then** the driver class implements all required methods (`on`, `off`, `query`, `cycle`, `reset`)
4. **Given** a driver package depends on `maas-power-driver-interface`, **When** the package is installed, **Then** the interface package is installed as a dependency

### User Story 3 - MAAS core uses power drivers without importing them directly (Priority: P1)

**Description**: MAAS region and rack controllers interact with power drivers exclusively through `PowerDriverRegistry`. MAAS core code never imports a specific power driver implementation. Power actions (on, off, query, cycle, reset) flow through the registry.

**Why this priority**: This ensures true decoupling. If MAAS core imports specific drivers, the separation is incomplete and drivers cannot be moved to separate repositories.

**Independent Test**: Can be tested by running the existing power action test suite with all driver imports removed from MAAS core, verifying that power actions still succeed through registry lookups.

**Acceptance Scenarios**:

1. **Given** a machine with power type `ipmi`, **When** a power query is requested via RPC, **Then** the rack controller looks up the driver via `PowerDriverRegistry.get_item("ipmi")` and executes the query
2. **Given** a machine with power type `redfish`, **When** a power-on action is requested, **Then** the action succeeds without MAAS core importing the redfish driver directly
3. **Given** `provisioningserver` source code, **When** searched for direct driver imports, **Then** no import of `provisioningserver.drivers.power.ipmi`, `provisioningserver.drivers.power.redfish`, etc. exists (only registry imports)
4. **Given** `maasserver` source code, **When** searched for direct driver imports, **Then** no import of specific power driver implementations exists

### User Story 4 - Power drivers are distributed as installable packages (Priority: P2)

**Description**: Power drivers are packaged as Python packages that can be installed via pip or included in snap builds. Each driver package includes its system-level dependencies (e.g., `freeipmi-tools` for IPMI).

**Why this priority**: This enables the operational model where drivers can be installed/uninstalled independently of MAAS core. Lower priority than discovery because it's about distribution, not functionality.

**Independent Test**: Can be tested by building a driver package with `build`, installing it with `pip install`, and verifying that the driver is discovered by MAAS.

**Acceptance Scenarios**:

1. **Given** a power driver package repository, **When** `pip install .` is run, **Then** the package installs with its entry point registered
2. **Given** a power driver package, **When** `python -m build` is run, **Then** a wheel and sdist are produced
3. **Given** a power driver package with system dependencies, **When** the package metadata is inspected, **Then** the system dependencies are documented (via package metadata or documentation)

### User Story 5 - Power drivers are available in the MAAS snap (Priority: P2)

**Description**: Power driver packages are included in the MAAS snap alongside the core MAAS installation. The snap declares system-level dependencies for each included driver.

**Why this priority**: This is the primary distribution channel for MAAS. Drivers must be available in the snap for production use. Lower priority because the snap configuration depends on the package structure being finalized.

**Independent Test**: Can be tested by building the MAAS snap with driver packages included, installing the snap, and verifying that `maas-power` CLI shows all expected drivers.

**Acceptance Scenarios**:

1. **Given** the MAAS snap with power driver packages included, **When** the snap is installed, **Then** `maas-power --help` lists all included driver types as subcommands
2. **Given** the MAAS snap, **When** a power driver's system dependency is missing, **Then** the driver reports missing packages via `detect_missing_packages()` rather than failing at import
3. **Given** the MAAS snap with drivers, **When** `snap list` is run, **Then** the snap includes the driver packages

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

- Python 3.14+ is available (MAAS already requires this)
- `importlib.metadata.entry_points()` with `group` parameter is available (Python 3.10+)
- The existing `PowerDriverBase` ABC is sufficient as the interface contract
- Driver packages target the same Python version as MAAS core
- System-level dependencies (e.g., `freeipmi-tools`, `amtterm`) remain as snap stage-packages, not Python packages
- The `manual` power driver remains builtin in MAAS core (no external dependencies, always available)
- Pod drivers (LXD, Virsh) follow a similar but separate extraction path (out of scope for this feature)
- Third-party power drivers are a valid use case (hence the public interface package)

## Key Entities

### Power Driver Interface
- **Purpose**: Defines the contract that all power drivers must implement
- **Properties**: `name`, `description`, `settings`, `ip_extractor`, `queryable`, `chassis`, `can_probe`, `can_set_boot_order`
- **Methods**: `on()`, `off()`, `query()`, `cycle()`, `reset()`, `set_boot_order()`, `detect_missing_packages()`, `get_schema()`

### Power Driver Registry
- **Purpose**: Runtime registry of all discovered power drivers
- **Operations**: `register_item()`, `get_item()`, `get_schema()`, iteration over registered drivers
- **Discovery**: Populated via `importlib.metadata.entry_points(group="maas.power_drivers")` at startup

### Power Driver Package
- **Purpose**: A Python package containing one or more power driver implementations
- **Structure**: Standard Python package with `pyproject.toml` declaring entry points and dependencies
- **Entry Point Group**: `maas.power_drivers`
- **Dependency**: `maas-power-driver-interface`

### Driver Grouping
- **Purpose**: Logical grouping of related drivers into shared packages
- **Groups**:
  - `maas-power-drivers-core`: `manual` (builtin)
  - `maas-power-driver-ipmi`: `ipmi`, `moonshot`
  - `maas-power-driver-redfish`: `redfish`, `openbmc`
  - `maas-power-driver-ibm`: `hmc`, `hmcz`, `mscm`
  - `maas-power-driver-amt`: `amt`
  - `maas-power-driver-apc`: `apc`
  - `maas-power-driver-vmware`: `vmware`, `proxmox`
  - `maas-power-driver-webhook`: `webhook`
  - `maas-power-drivers-legacy`: `dli`, `eaton`, `raritan`, `recs`, `seamicro`, `ucsm`, `wedge`

## Success Criteria

- MAAS rack controller discovers all installed power drivers within 1 second of startup
- Zero power driver tests fail after extraction (100% test pass rate preserved)
- All 21 existing power driver types remain functional after extraction
- The `maas-power` CLI works with all installed drivers without modification
- A new power driver can be added by creating a Python package (no MAAS core changes required)
- Power driver interface package can be published to PyPI for third-party consumption
- No breaking changes to existing MAAS APIs or RPC interfaces
- The MAAS snap builds and installs successfully with driver packages included

## Non-Goals

- This feature does not extract pod drivers (LXD, Virsh) — they are out of scope
- This feature does not create a new API for power management — existing APIs are preserved
- This feature does not change how power parameters are stored in the database
- This feature does not introduce a new authentication or authorization model for drivers
- This feature does not require changes to the MAAS UI
- This feature does not publish packages to PyPI (that is a follow-up)
