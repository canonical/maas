# Data Model: Rack Power Drivers

## New Table: `rack_power_drivers`

Stores per-rack power driver registrations, received from rack controllers via the v3 internal API.

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | Serial | PK |
| `rack_system_id` | String | FK → `rackcontrollers.system_id`, NOT NULL |
| `driver_name` | String | NOT NULL |
| `driver_version` | String | NOT NULL |
| `schema` | JSON | NOT NULL (driver metadata from `GET /metadata`) |
| `last_seen` | DateTime | NOT NULL, default `now()` |

**Indexes:**
- `UK_rack_power_drivers_rack_driver_version` — unique on `(rack_system_id, driver_name, driver_version)`
- `idx_rack_power_drivers_last_seen` — on `last_seen` for staleness queries

**Lifecycle:**
- **Upsert** on driver registration (new or updated metadata)
- **Delete** on driver unregistration
- **Bulk delete** on rack disconnect (cleanup stale entries)
- **Periodic cleanup** of entries where `last_seen` exceeds staleness threshold

**Migration:** Alembic autogenerate, test up/down.
