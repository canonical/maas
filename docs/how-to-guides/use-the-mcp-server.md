# Use the MAAS MCP server

The MAAS MCP (Model Context Protocol) server exposes MAAS fleet discovery, network management, diagnostics, and boot-source tools to AI assistants such as Claude, Cursor, and any MCP-compatible client. It runs on the region controller and listens on TCP port `5275`.

## Prerequisites

- MAAS region controller installed and running.
- The `maas-mcp-server` package installed (included with the region controller).
- A MAAS user account with API access.

## Obtain a Bearer token

The MCP server authenticates requests using a Bearer token obtained from the MAAS API v3 login endpoint. This is distinct from the OAuth key used by the MAAS CLI.

```text
curl -s -X POST $MAAS_URL/MAAS/a/v3/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "<your-username>", "password": "<your-password>"}' \
  | jq -r '.token'
```

Replace `$MAAS_URL` with your region controller URL (e.g. `http://region-host:5240`). Save the returned token — you will pass it as a Bearer token in every MCP request.

## Connect an MCP client

All requests to the MCP server must include an `Authorization` header:

```text
Authorization: Bearer <token>
```

The MCP server endpoint is:

```text
http://<region-host>:5275/mcp
```

### Claude Desktop

Add the following to your Claude Desktop MCP configuration (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "maas": {
      "url": "http://<region-host>:5275/mcp",
      "headers": {
        "Authorization": "Bearer <token>"
      }
    }
  }
}
```

### curl (manual test)

Verify the server is reachable and list available tools:

```text
curl -s -X POST http://<region-host>:5275/mcp \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

## Available tools

| Tool | Description |
|------|-------------|
| `list_machines` | Paginated list of machines, with optional filters |
| `get_machine` | Full detail for a single machine by hostname or system ID |
| `get_machine_power_state` | Current power state for a machine |
| `list_resource_pools` | All resource pools |
| `list_zones` | All availability zones |
| `get_maas_info` | Deployment name and rack controller status |
| `list_fabrics` | All network fabrics |
| `get_fabric` | Detail for a single fabric |
| `list_vlans` | VLANs for a fabric |
| `get_vlan` | Detail for a single VLAN |
| `create_vlan` | Create a VLAN on a fabric |
| `update_vlan` | Update a VLAN |
| `delete_vlan` | Delete a VLAN |
| `list_subnets` | Subnets for a VLAN |
| `get_subnet` | Detail for a single subnet |
| `create_subnet` | Create a subnet |
| `update_subnet` | Update a subnet |
| `delete_subnet` | Delete a subnet |
| `list_boot_sources` | Configured boot sources and selections |
| `trigger_boot_source_sync` | Trigger an async sync for a boot source selection |
| `delete_boot_source` | Delete a boot source |
| `list_boot_source_selections` | Image selections for a boot source |
| `list_available_images` | OS images available from all boot sources |
| `list_selections` | Active image selections across all boot sources |
| `list_custom_images` | Custom (uploaded) boot images |
| `get_machine_events` | Recent audit and lifecycle events for a machine |
| `get_script_results` | Commissioning or testing script results for a machine |
| `list_events` | Paginated MAAS audit events, optionally filtered by machine |

## Firewall

Port `5275` must be open on the region controller for MCP clients to connect. See [Manage network ports](/how-to-guides/enhance-maas-security.md#manage-network-ports).

## Token expiry

Tokens obtained from `/MAAS/a/v3/auth/login` are session tokens and may expire. If requests begin returning `401 Unauthorized`, re-authenticate and update the token in your MCP client configuration.
