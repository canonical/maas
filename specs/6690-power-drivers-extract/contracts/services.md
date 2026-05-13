# Service Contracts: Rack Power Drivers

## `RackPowerDriverService`

**Location**: `src/maasservicelayer/services/rack_power_drivers.py`

**Base class**: `BaseService`

### Methods

#### `register_driver(rack_system_id, driver_name, driver_version, schema)`

Register or update a power driver for a rack.

- **Args**:
  - `rack_system_id: str` — the rack's system ID
  - `driver_name: str` — unique driver identifier (e.g., `"ipmi"`)
  - `driver_version: str` — driver version (e.g., `"1.0.0"`)
  - `schema: dict` — driver metadata from `GET /metadata`
- **Side effects**: Upserts row in `rack_power_drivers` table
- **Returns**: None

#### `unregister_driver(rack_system_id, driver_name, driver_version)`

Remove a specific version of a power driver registration for a rack.

- **Args**:
  - `rack_system_id: str`
  - `driver_name: str`
  - `driver_version: str`
- **Side effects**: Deletes row from `rack_power_drivers` table
- **Returns**: None

#### `unregister_all(rack_system_id)`

Remove all power driver registrations for a rack (called on rack disconnect).

- **Args**: `rack_system_id: str`
- **Side effects**: Deletes all rows for the rack
- **Returns**: None

#### `get_available_power_types()`

Get the merged set of available power types across all racks plus builtin drivers.

- **Returns**: `list[dict]` — list of driver schemas (merged, deduplicated by name)
- **Logic**:
  1. Query `rack_power_drivers` for all entries
  2. Merge with builtin driver schemas (`manual`, `webhook`)
  3. Deduplicate by driver name (rack-registered takes precedence)
  4. Return combined list
