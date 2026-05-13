# Data Model: Rack Power Drivers

## New Table: `rack_power_drivers`

Stores per-rack power driver registrations, received from rack controllers via the v3 internal API.

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | Serial | PK |
| `created` | DateTime | NOT NULL, default `now()` |
| `updated` | DateTime | NOT NULL, default `now()` |
| `rack_system_id` | String | FK → `rackcontrollers.system_id`, NOT NULL |
| `driver_name` | String | NOT NULL |
| `schema` | JSON | NOT NULL (driver metadata from `GET /metadata`) |
| `last_seen` | DateTime | NOT NULL, default `now()` |

**Indexes:**
- `UK_rack_power_drivers_rack_driver` — unique on `(rack_system_id, driver_name)`
- `idx_rack_power_drivers_last_seen` — on `last_seen` for staleness queries

**Lifecycle:**
- **Create** on driver registration (new entry via `create()`)
- **Delete** on driver unregistration (via `delete_one()` with query)
- **Bulk delete** on rack disconnect (via `delete_many()` with query)

**Migration:** Alembic autogenerate, test up/down.

## Domain Model: `PowerDriver`

**Location**: `src/maasservicelayer/models/power_drivers.py`

```python
@generate_builder()
class PowerDriver(MaasTimestampedBaseModel):
    rack_system_id: str
    driver_name: str
    driver_version: str
    schema: dict
```

The `@generate_builder()` decorator produces `PowerDriverBuilder` (all fields default to `UNSET`).
The `schema` field is a `dict` that maps to the `JSONB` column. Validation against the
`DriverSchema` contract is performed before calling `create()`.

## Validation Model: `DriverSchema`

**Location**: `src/maasservicelayer/models/power_drivers.py`

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
It is **not** stored in the database — it is used to validate the incoming schema dict before creation.
