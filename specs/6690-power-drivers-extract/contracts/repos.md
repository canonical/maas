# Repository Contracts: Rack Power Drivers

## `PowerDriversRepository`

**Location**: `src/maasservicelayer/db/repositories/power_drivers.py`

**Base class**: `BaseRepository[PowerDriver]`

**Table**: `rack_power_drivers`

### Inherited Methods

All standard CRUD methods are inherited from `BaseRepository`:

| Method | Description |
|--------|-------------|
| `create(builder: PowerDriverBuilder) -> PowerDriver` | Insert a new driver registration |
| `create_many(builders: list[PowerDriverBuilder]) -> list[PowerDriver]` | Bulk insert |
| `get_by_id(id: int) -> PowerDriver \| None` | Fetch by primary key |
| `get_one(query: QuerySpec) -> PowerDriver \| None` | Fetch one by query |
| `get_many(query: QuerySpec) -> list[PowerDriver]` | Fetch many by query |
| `list(page, size, query) -> ListResult[PowerDriver]` | Paginated list |
| `update_by_id(id, builder) -> PowerDriver` | Update by primary key |
| `update_one(query, builder) -> PowerDriver` | Update one by query |
| `update_many(query, builder) -> list[PowerDriver]` | Update many by query |
| `delete_by_id(id) -> PowerDriver \| None` | Delete by primary key |
| `delete_one(query: QuerySpec) -> PowerDriver \| None` | Delete one by query |
| `delete_many(query: QuerySpec) -> list[PowerDriver]` | Delete many by query |

## `PowerDriverClauseFactory`

**Location**: `src/maasservicelayer/db/repositories/power_drivers.py`

**Base class**: `ClauseFactory`

Provides reusable query clauses for filtering power driver registrations.

### Methods

#### `upsert(rack_system_id, driver_name, schema)`

Match a single driver registration by its primary key.

- **SQL**: `INSERT ... ON CONFLICT (rack_system_id, driver_name) DO UPDATE SET schema = EXCLUDED.schema, last_seen = now()`
- **Args**:
  - `rack_system_id: str`
  - `driver_name: str`
  - `schema: dict` (stored as JSON)
- **Returns**: None

#### `remove(rack_system_id, driver_name)`

Match all driver registrations for a specific rack.

- **SQL**: `DELETE FROM rack_power_drivers WHERE rack_system_id = ? AND driver_name = ?`
- **Returns**: None

#### `with_driver_name(driver_name: str) -> Clause`

Match all registrations of a specific driver name.

- **SQL**: `SELECT driver_name, schema FROM rack_power_drivers WHERE rack_system_id = ?`
- **Returns**: `list[tuple[str, dict]]`

#### `with_driver_version(driver_version: str) -> Clause`

Match all registrations of a specific driver version.

- **SQL**: `SELECT DISTINCT ON (driver_name) driver_name, schema FROM rack_power_drivers ORDER BY driver_name, last_seen DESC`
- **Returns**: `list[tuple[str, dict]]`

### Usage Examples

```python
# Delete a specific driver version for a rack
await service.delete_one(
    query=QuerySpec(
        where=ClauseFactory.and_clauses([
            PowerDriverClauseFactory.with_rack_system_id("ABCD1234"),
            PowerDriverClauseFactory.with_driver_name("ipmi"),
            PowerDriverClauseFactory.with_driver_version("1.0.0"),
        ])
    )
)

# Delete all drivers for a rack (rack disconnect)
await service.delete_many(
    query=QuerySpec(
        where=PowerDriverClauseFactory.with_rack_system_id("ABCD1234")
    )
)

# List all drivers for a rack
drivers = await service.get_many(
    query=QuerySpec(
        where=PowerDriverClauseFactory.with_rack_system_id("ABCD1234")
    )
)
```
