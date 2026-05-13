# API Contracts: Power Driver Extraction

## Driver Service Protocol (HTTP over UNIX Socket)

Each power driver runs an HTTP server on a UNIX domain socket in the MAAS runtime directory:
- Snap: `/run/snap.<instance>/power-drivers/<driver-name>.sock`
- Deb: `/run/maas/power-drivers/<driver-name>.sock`

### `GET /metadata`

Returns driver capabilities. No body required.

**Response 200:**
```json
{
  "name": "ipmi",
  "description": "IPMI power driver",
  "version": "1.0.0",
  "actions": ["query", "on", "off", "cycle", "reset"],
  "settings": [
    {
      "name": "power_address",
      "label": "BMC IP address",
      "field_type": "ip_address",
      "required": true,
      "scope": "bmc"
    }
  ],
  "capabilities": {
    "queryable": true,
    "chassis": false,
    "can_probe": true,
    "can_set_boot_order": false
  },
  "ip_extractor": {
    "field_name": "power_address",
    "pattern": "^(?P<address>.+?)$"
  }
}
```

### `POST /query`

Query the current power state of a node.

**Request body:**
```json
{
  "system_id": "ABC123",
  "context": {
    "power_address": "10.0.0.1",
    "power_user": "admin",
    "power_pass": "secret"
  }
}
```

**Response 200:**
```json
{ "status": "ok", "state": "on" }
```

Possible states: `"on"`, `"off"`, `"unknown"`.

### `POST /on`

Power on a node.

**Request body:**
```json
{
  "system_id": "ABC123",
  "context": { "power_address": "10.0.0.1", ... }
}
```

**Response 200:**
```json
{ "status": "ok" }
```

### `POST /off`

Power off a node. Same request/response format as `/on`.

### `POST /cycle`

Cycle power (off then on). Same request/response format as `/on`.

### `POST /reset`

Reset power (force on). Same request/response format as `/on`.

### `POST /set-boot-order`

Configure boot order. Only available if driver's `can_set_boot_order` is `true`.

**Request body:**
```json
{
  "system_id": "ABC123",
  "context": { "power_address": "10.0.0.1", ... },
  "order": ["network", "disk"]
}
```

**Response 200:**
```json
{ "status": "ok" }
```

### Error Responses

**400 Bad Request** — invalid parameters:
```json
{ "status": "error", "error_type": "invalid_parameters", "error_message": "Missing required field: power_address" }
```

**500 Internal Server Error** — driver error:
```json
{ "status": "error", "error_type": "power_action", "error_message": "Could not authenticate to BMC" }
```

**503 Service Unavailable** — driver unavailable:
```json
{ "status": "error", "error_type": "unavailable", "error_message": "BMC not reachable" }
```

---

## v3 Internal API — Rack Power Drivers

Base path: `/MAAS/api/v3/internal`

Auth: mTLS client certificate (CN = rack system_id).

### `POST /rack-power-drivers:register`

Register one or more power drivers for a rack controller.

**Request body:**
```json
{
  "drivers": [
    {
      "name": "ipmi",
      "schema": {
        "name": "ipmi",
        "description": "IPMI power driver",
        "version": "1.0.0",
        "actions": ["query", "on", "off", "cycle", "reset"],
        "settings": [...],
        "capabilities": {...},
        "ip_extractor": {...}
      }
    }
  ]
}
```

**Response:** `204 No Content`

### `DELETE /rack-power-drivers:unregister`

Unregister a power driver for a rack controller.

**Request body:**
```json
{ "driver_name": "ipmi" }
```

**Response:** `204 No Content`

### `GET /rack-power-drivers`

List all registered power drivers for a rack controller.

**Response 200:**
```json
{
  "drivers": [
    {
      "name": "ipmi",
      "schema": { ... }
    }
  ]
}
```
