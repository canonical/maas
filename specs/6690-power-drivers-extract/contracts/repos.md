# Repository Contracts: Rack Power Drivers

## `RackPowerDriverRepository`

**Location**: `src/maasservicelayer/db/repositories/rack_power_drivers.py`

**Base class**: `BaseRepository`

**Table**: `rack_power_drivers`

### Methods

#### `upsert(rack_system_id, driver_name, driver_version, schema)`

Insert or update a driver registration.

- **SQL**: `INSERT ... ON CONFLICT (rack_system_id, driver_name, driver_version) DO UPDATE SET schema = EXCLUDED.schema, last_seen = now()`
- **Args**:
  - `rack_system_id: str`
  - `driver_name: str`
  - `driver_version: str`
  - `schema: dict` (stored as JSON)
- **Returns**: None

#### `remove(rack_system_id, driver_name, driver_version)`

Delete a driver registration.

- **SQL**: `DELETE FROM rack_power_drivers WHERE rack_system_id = ? AND driver_name = ? AND driver_version = ?`
- **Returns**: None

#### `get_all_for_rack(rack_system_id)`

List all driver registrations for a rack.

- **SQL**: `SELECT driver_name, driver_version, schema FROM rack_power_drivers WHERE rack_system_id = ?`
- **Returns**: `list[tuple[str, str, dict]]`

#### `get_merged_across_racks()`

Get all unique driver schemas across all racks.

- **SQL**: `SELECT DISTINCT ON (driver_name, driver_version) driver_name, driver_version, schema FROM rack_power_drivers ORDER BY driver_name, driver_version, last_seen DESC`
- **Returns**: `list[tuple[str, str, dict]]`

#### `cleanup_stale(rack_system_id)`

Remove all entries for a rack.

- **SQL**: `DELETE FROM rack_power_drivers WHERE rack_system_id = ?`
- **Returns**: None
