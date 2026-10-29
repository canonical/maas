# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maascommon.enums.node import NodeStatus
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.machines_v2 import MachinesV2Repository
from maasservicelayer.services.machines_v2 import (
    MachineListGroupRequest,
    MachineListRequest,
    MachineRequest,
    MachinesV2Service,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("pxe_mac", [None, "00:11:22:33:44:55"])
async def test_list_preserves_requested_groups_and_machine_details(pxe_mac):
    record = {
        "id": 1,
        "system_id": "abc123",
        "hostname": "machine",
        "description": "A machine",
        "pool_id": 0,
        "pool_name": "default",
        "domain_id": 0,
        "domain_name": "maas",
        "owner": "admin",
        "parent": None,
        "error_description": "",
        "zone_id": 0,
        "zone_name": "default",
        "cpu_count": 4,
        "memory": 8192,
        "power_state": "on",
        "locked": False,
        "fqdn": "machine.maas",
        "tags": [3],
        "physical_disk_count": 1,
        "storage": 1024,
        "testing_status_combined": -1,
        "architecture": "amd64/generic",
        "osystem": "ubuntu",
        "distro_series": "noble",
        "status_code": NodeStatus.READY,
        "ephemeral_deploy": False,
        "fabrics": ["fabric-0"],
        "spaces": ["space-0"],
        "extra_macs": [],
        "status_message": "Ready",
        "pxe_mac": pxe_mac,
        "power_type": "ipmi",
        "boot_vlan_id": 1,
        "boot_vlan_name": "untagged",
        "boot_fabric_id": 0,
        "boot_fabric_name": "fabric-0",
        "ips": ["10.0.0.2"],
        "is_boot_ips": [True],
        "cpu_test_status_combined": -1,
        "memory_test_status_combined": -1,
        "network_test_status_combined": -1,
        "storage_test_status_combined": -1,
        "is_dpu": False,
    }
    repository = Mock(MachinesV2Repository)
    repository.get_many.return_value = [
        record,
        {**record, "id": 2, "system_id": "def456"},
    ]
    service = MachinesV2Service(Context())
    service.repository = repository
    request = MachineListRequest(
        count=9,
        cur_page=2,
        num_pages=5,
        groups=[
            MachineListGroupRequest(
                name="status",
                value="ready",
                count=2,
                collapsed=False,
                items=[
                    MachineRequest(
                        id=2, actions=["deploy"], permissions=["edit"]
                    ),
                    MachineRequest(
                        id=1, actions=["commission"], permissions=["view"]
                    ),
                ],
            ),
            MachineListGroupRequest(
                name="status", value="new", count=7, collapsed=True, items=[]
            ),
        ],
    )

    response = await service.list(request)

    assert (response.count, response.cur_page, response.num_pages) == (9, 2, 5)
    assert response.groups is not None
    ready, new = response.groups
    assert (ready.name, ready.value, ready.count, ready.collapsed) == (
        "status",
        "ready",
        2,
        False,
    )
    assert ready.items is not None
    assert [machine.id for machine in ready.items] == [2, 1]
    assert [machine.actions for machine in ready.items] == [
        ["deploy"],
        ["commission"],
    ]
    assert [machine.permissions for machine in ready.items] == [
        ["edit"],
        ["view"],
    ]
    assert (new.value, new.count, new.collapsed, new.items) == (
        "new",
        7,
        True,
        [],
    )
    machine = ready.items[0]
    assert machine.status_code == NodeStatus.READY
    assert machine.fqdn == "machine.maas"
    assert machine.vlan is not None
    assert machine.vlan.fabric_name == "fabric-0"
    if pxe_mac:
        assert machine.ip_addresses is not None
        assert [(ip.ip, ip.is_boot) for ip in machine.ip_addresses] == [
            ("10.0.0.2", True)
        ]
        assert machine.power_type == "ipmi"
    else:
        assert machine.ip_addresses is None
        assert machine.power_type is None
