# Research: Power Driver Extraction

## Current Power Driver Invocation Flow

```
region → AMP PowerQuery → rackd clusterservice.power_query()
  → rpc/power.get_power_state()
    → PowerDriverRegistry.get_item(power_type)
      → driver.query(system_id, context)  # Python method call
```

## Current DescribePowerTypes Flow

```
region → AMP DescribePowerTypes → rackd clusterservice.describe_power_types()
  → PowerDriverRegistry.get_schema()  # returns JSON schema of all drivers
```

## PowerDriverRegistry (Today)

- Eagerly populated at import time in `registry.py`
- All 22 drivers instantiated and registered
- Pod drivers (lxd, virsh) also registered
- `sanitise_power_parameters()` uses registry to extract secrets

## v3 Internal API (Today)

- FastAPI-based, served on separate uvicorn with mTLS
- Prefix: `/MAAS/api/v3/internal`
- Existing handlers: `RootHandler`, `AgentHandler`, `LeasesHandler`
- Auth: `RequireClientCertMiddleware` (client cert CN identifies caller)
- **No power driver registration endpoint exists** — must be created

## Key Decisions

1. **Protocol**: HTTP over UNIX socket — standard HTTP semantics, JSON bodies
2. **Discovery**: `rackd` scans a shared directory for `.sock` files
3. **Metadata**: `GET /metadata` on each socket returns driver capabilities
4. **System identification**: `system_id` only (no `hostname` in request body)
5. **Rack→Region notification**: New v3 internal API endpoint, not legacy AMP/RPC
6. **Builtin drivers**: `manual` and `webhook` stay in MAAS monorepo
7. **`maas-power`**: Removed entirely

## Files to Delete

- `src/provisioningserver/power_driver_command.py`
- 19 external driver files in `src/provisioningserver/drivers/power/`
- Corresponding test files

## Files to Modify

- `src/provisioningserver/drivers/power/registry.py`
- `src/provisioningserver/rpc/power.py`
- `src/provisioningserver/rpc/clusterservice.py`
- `src/provisioningserver/server.py`
- `src/provisioningserver/path.py`
- `src/maasserver/clusterrpc/driver_parameters.py`
- `snap/snapcraft.yaml`
- `pyproject.toml`

## Files to Create (MAAS Monorepo)

- `src/provisioningserver/drivers/power/socket_client.py`
- `src/provisioningserver/drivers/power/discovery.py`
- `src/provisioningserver/drivers/power/socket_driver.py`
- `src/provisioningserver/rpc/driver_lifecycle_client.py`
- `src/maasservicelayer/db/repositories/rack_power_drivers.py`
- `src/maasservicelayer/services/rack_power_drivers.py`
- `src/maasapiserver/v3/api/internal/handlers/rack_power_drivers.py`
- Alembic migration

## External Repositories

19 new repositories, one per driver. Each contains an HTTP server over UNIX socket, BMC-specific logic, metadata, and snapcraft configuration.
