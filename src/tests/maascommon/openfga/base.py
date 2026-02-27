#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

PERMISSION_METHODS = [
    ("can_edit_machines", ("u1",), "can_edit_machines", "maas:0"),
    (
        "can_edit_machines_in_pool",
        ("u1", "p1"),
        "can_edit_machines",
        "pool:p1",
    ),
    (
        "can_deploy_machines_in_pool",
        ("u1", "p1"),
        "can_deploy_machines",
        "pool:p1",
    ),
    (
        "can_view_machines_in_pool",
        ("u1", "p1"),
        "can_view_machines",
        "pool:p1",
    ),
    (
        "can_view_available_machines_in_pool",
        ("u1", "p1"),
        "can_view_available_machines",
        "pool:p1",
    ),
    (
        "can_edit_global_entities",
        ("u1",),
        "can_edit_global_entities",
        "maas:0",
    ),
    (
        "can_view_global_entities",
        ("u1",),
        "can_view_global_entities",
        "maas:0",
    ),
    ("can_edit_controllers", ("u1",), "can_edit_controllers", "maas:0"),
    ("can_view_controllers", ("u1",), "can_view_controllers", "maas:0"),
    ("can_edit_identities", ("u1",), "can_edit_identities", "maas:0"),
    ("can_view_identities", ("u1",), "can_view_identities", "maas:0"),
    ("can_edit_configurations", ("u1",), "can_edit_configurations", "maas:0"),
    ("can_view_configurations", ("u1",), "can_view_configurations", "maas:0"),
    ("can_edit_notifications", ("u1",), "can_edit_notifications", "maas:0"),
    ("can_view_notifications", ("u1",), "can_view_notifications", "maas:0"),
    ("can_edit_boot_entities", ("u1",), "can_edit_boot_entities", "maas:0"),
    ("can_view_boot_entities", ("u1",), "can_view_boot_entities", "maas:0"),
    ("can_edit_license_keys", ("u1",), "can_edit_license_keys", "maas:0"),
    ("can_view_license_keys", ("u1",), "can_view_license_keys", "maas:0"),
    ("can_view_devices", ("u1",), "can_view_devices", "maas:0"),
    ("can_view_ipaddresses", ("u1",), "can_view_ipaddresses", "maas:0"),
]

LIST_METHODS = [
    ("list_pools_with_view_machines_access", "can_view_machines"),
    (
        "list_pools_with_view_available_machines_access",
        "can_view_available_machines",
    ),
    ("list_pool_with_deploy_machines_access", "can_deploy_machines"),
    ("list_pools_with_edit_machines_access", "can_edit_machines"),
]
