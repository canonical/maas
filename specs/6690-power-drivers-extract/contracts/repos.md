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

#### `with_id(id: int) -> Clause`

Match a single driver registration by its primary key.

- **SQL**: `rack_power_drivers.id = ?`

#### `with_rack_system_id(rack_system_id: str) -> Clause`

Match all driver registrations for a specific rack.

- **SQL**: `rack_power_drivers.rack_system_id = ?`

#### `with_driver_name(driver_name: str) -> Clause`

Match all registrations of a specific driver name.

- **SQL**: `rack_power_drivers.driver_name = ?`

#### `with_driver_version(driver_version: str) -> Clause`

Match all registrations of a specific driver version.

- **SQL**: `rack_power_drivers.driver_version = ?`

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
