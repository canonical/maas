MAAS 3.8 introduces a new relationship-based access control (ReBAC) system for managing users, groups, and permissions. This replaces the previous Canonical RBAC integration, which is deprecated in 3.8 and removed in MAAS 4.0.

This guide explains how the access control model works and how to use user groups and entitlements to control access to MAAS resources. For full CLI command syntax, see the [user-group CLI reference](/t/user-group/15754).

## How access control works

MAAS access control is built around three concepts:

- **Users** - individual accounts that authenticate with MAAS.
- **Groups** - collections of users. Permissions are always granted to groups, not to individual users.
- **Entitlements** - permissions assigned to a group for a specific resource. An entitlement defines *what* a group *can do* with a *resource*.

The access model follows the chain: **user → group → entitlement → resource**. A user has a permission only if they belong to a group that holds the corresponding entitlement.

### Default groups

MAAS creates two built-in groups:

| Group | Description |
|-------|-------------|
| **Administrators** | Full access to all resources. |
| **Users** | Can view available machines, deploy them, and view global entities. |

When you create a user through the `users` endpoint or the `createadmin` command, MAAS automatically assigns them to the appropriate default group: admins are added to *Administrators* and regular users to *Users*. You can modify or delete these default groups. If you delete and recreate the default groups with the same name, MAAS will still automatically assign users to them based on their admin status.

## Entitlements and permissions

Entitlements are scoped to a **resource type** and a **resource ID**:

| Resource type | Resource ID | Scope |
|---------------|-------------|-------|
| `maas` | Always `0` | Global - applies across all resource pools. |
| `pool` | The resource pool ID | Per-pool - applies only to the specified pool. |

### Permission inheritance

Permissions follow two inheritance rules:

1. **Higher permissions imply lower ones.** For any resource, `can_edit_*` implies `can_view_*`. For machines specifically, the full hierarchy is:

    ```nohighlight
    can_edit_machines
    ├── can_deploy_machines
    │   └── can_view_machines
    │       └── can_view_available_machines
    ├── can_view_machines
    │   └── can_view_available_machines
    └── can_view_available_machines
    ```

    Other resources follow the same `can_edit_* → can_view_*` pattern (e.g., `can_edit_global_entities` implies `can_view_global_entities`).

2. **MAAS-level machine permissions cascade to pools.** If a group has `can_view_machines` on the `maas` resource, it automatically has `can_view_machines` on every resource pool. Pool-level entitlements grant *additional* access for specific pools only.

### Available entitlements

#### Global (`maas`) entitlements

| Entitlement | Description |
|-------------|-------------|
| `can_edit_machines` | Edit machines in every resource pool. |
| `can_deploy_machines` | Deploy machines in every resource pool. |
| `can_view_machines` | View all machines in every resource pool. |
| `can_view_available_machines` | View owned and unowned (available) machines in every resource pool. |
| `can_edit_global_entities` | Edit domains, DNS records, fabrics, resource pool metadata, spaces, subnets, tags, static routes, and VLANs. |
| `can_view_global_entities` | View global entities. |
| `can_edit_controllers` | Edit controllers. |
| `can_view_controllers` | View controllers. |
| `can_edit_identities` | Edit users, user groups, permissions, and OIDC providers. |
| `can_view_identities` | View users, user groups, permissions, and OIDC providers. |
| `can_edit_configurations` | Edit configurations. |
| `can_view_configurations` | View configurations. |
| `can_edit_notifications` | Edit notifications. |
| `can_view_notifications` | View all notifications. |
| `can_edit_boot_entities` | Edit boot resources and boot sources. |
| `can_view_boot_entities` | View boot resources and boot sources. |
| `can_edit_license_keys` | Edit license keys. |
| `can_view_license_keys` | View license keys. |
| `can_view_devices` | View all devices. |
| `can_view_ipaddresses` | View all IP addresses. |
| `can_view_dnsrecords` | View all DNS resource record sets. |

#### Per-pool (`pool`) entitlements

| Entitlement | Description |
|-------------|-------------|
| `can_edit_machines` | Edit machines in the specified resource pool. |
| `can_deploy_machines` | Deploy machines in the specified resource pool. |
| `can_view_machines` | View all machines in the specified resource pool. |
| `can_view_available_machines` | View owned and unowned (available) machines in the specified resource pool. |

## Common tasks

### Create a group and assign members

- **CLI**:
    ```bash
    GROUP_ID=$(maas $PROFILE user-groups create name=developers description="Dev team" | jq '.id')
    maas $PROFILE user-group add-member $GROUP_ID username=alice
    maas $PROFILE user-group add-member $GROUP_ID username=bob
    ```

### Grant a group access to a specific resource pool

Assuming that the resource pool with ID 2 exists, you can grant a group permissions for that pool. For example, to allow members of group $GROUP_ID to deploy machines in pool 2:

- **CLI**:
    ```bash
    maas $PROFILE user-group add-entitlement $GROUP_ID resource_type=pool resource_id=2 entitlement=can_deploy_machines
    ```

### Grant global read-only access

- **CLI**:
    ```bash
    maas $PROFILE user-group add-entitlement $GROUP_ID resource_type=maas resource_id=0 entitlement=can_view_machines
    maas $PROFILE user-group add-entitlement $GROUP_ID resource_type=maas resource_id=0 entitlement=can_view_global_entities
    ```

### Review a group's permissions

- **CLI**:
    ```bash
    maas $PROFILE user-group list-members $GROUP_ID
    maas $PROFILE user-group list-entitlements $GROUP_ID
    ```

Deleting a group removes all of its entitlements. Members are not deleted: they remain as MAAS users.