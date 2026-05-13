# Service Contracts: Rack Power Drivers

## `PowerDriversService`

**Location**: `src/maasservicelayer/services/power_drivers.py`

**Base class**: `BaseService[PowerDriver, PowerDriversRepository, PowerDriverBuilder]`

### Inherited Methods

All standard CRUD methods are inherited from `BaseService`:

| Method | Description |
|--------|-------------|
| `create(builder: PowerDriverBuilder) -> PowerDriver` | Register a new driver |
| `create_many(builders: list[PowerDriverBuilder]) -> list[PowerDriver]` | Register multiple drivers |
| `delete_one(query: QuerySpec) -> PowerDriver \| None` | Unregister a specific driver |
| `delete_many(query: QuerySpec) -> list[PowerDriver]` | Unregister all drivers for a rack |
| `get_one(query: QuerySpec) -> PowerDriver \| None` | Fetch one by query |
| `get_many(query: QuerySpec) -> list[PowerDriver]` | Fetch many by query |
| `list(page, size, query) -> ListResult[PowerDriver]` | Paginated list |

### Custom Methods

#### `get_available_power_types() -> list[dict]`

Get the merged set of available power types across all racks plus builtin drivers.

- **Returns**: `list[dict]` — list of driver schemas (merged, deduplicated by name)
- **Logic**:
  1. Query `rack_power_drivers` for all entries via `list_all()`
  2. Merge with builtin driver schemas (`manual`, `webhook`)
  3. Deduplicate by driver name (rack-registered takes precedence)
  4. Return combined list

### Usage Examples

```python
# Register a driver (schema validated before create)
from maasservicelayer.models.power_drivers import DriverSchema, PowerDriverBuilder

# Validate the incoming schema dict against the contract
validated = DriverSchema(**raw_schema_dict)

await service.create(
    PowerDriverBuilder(
        rack_system_id="ABCD1234",
        driver_name="ipmi",
        driver_version="1.0.0",
        schema=validated.model_dump(),
    )
)

# Unregister a specific driver version for a rack
from maasservicelayer.db.filters import QuerySpec, ClauseFactory
from maasservicelayer.db.repositories.power_drivers import PowerDriverClauseFactory

await service.delete_one(
    query=QuerySpec(
        where=ClauseFactory.and_clauses([
            PowerDriverClauseFactory.with_rack_system_id("ABCD1234"),
            PowerDriverClauseFactory.with_driver_name("ipmi"),
            PowerDriverClauseFactory.with_driver_version("1.0.0"),
        ])
    )
)

# Unregister all drivers for a rack (rack disconnect)
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
