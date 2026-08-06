#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any

from maasservicelayer.db.tables import HardwareProfileTable
from maasservicelayer.models.hardwareprofile import (
    HardwareAcceleratorGroup,
    HardwareAcceleratorItem,
    HardwareNetworkGroup,
    HardwareNetworkItem,
    HardwareProfile,
    HardwareStorageGroup,
    HardwareStorageItem,
)
from maasservicelayer.utils.date import utcnow
from maastesting.factory import factory
from tests.fixtures.factories.node import create_test_machine_entry
from tests.maasapiserver.fixtures.db import Fixture


def _make_storage_group() -> HardwareStorageGroup:
    return HardwareStorageGroup(
        count=1,
        disk_type="ssd",
        size_bytes=512 * 1024 * 1024 * 1024,
        items=[
            HardwareStorageItem(
                name=factory.make_name("disk"),
                size_bytes=512 * 1024 * 1024 * 1024,
                block_size=512,
                id_path=None,
                model=factory.make_name("model"),
                serial=factory.make_name("serial"),
                firmware_version=None,
                numa_node=0,
            )
        ],
    )


def _make_network_group() -> HardwareNetworkGroup:
    return HardwareNetworkGroup(
        count=1,
        speed_mbps=1000,
        vendor_id="8086",
        product_id="10fb",
        vendor=factory.make_name("vendor"),
        product=factory.make_name("product"),
        items=[
            HardwareNetworkItem(
                name=factory.make_name("eth"),
                mac_address=factory.make_mac_address(),
                link_speed=1000,
                sriov_max_vf=0,
                numa_node=0,
            )
        ],
    )


def _make_accelerator_group() -> HardwareAcceleratorGroup:
    return HardwareAcceleratorGroup(
        count=1,
        vendor_id="10de",
        product_id="1eb8",
        vendor=factory.make_name("vendor"),
        product=factory.make_name("product"),
        items=[
            HardwareAcceleratorItem(
                pci_address="0000:00:1c.0",
                numa_node=0,
                sriov_max_vf=0,
            )
        ],
    )


def make_hardware_profile_dict(node_id: int, **kwargs) -> dict[str, Any]:
    fields = {
        "node_id": node_id,
        "architecture": "amd64/generic",
        "cpu_cores": 4,
        "cpu_speed_mhz": 2400,
        "memory_mb": 4096,
        "disk_count": 1,
        "total_storage_bytes": 512 * 1024**3,
        "nic_count": 1,
        "gpu_count": 1,
        "system_vendor": "LENOVO",
        "system_product": "20HRCTO1WW",
        "hardware_fingerprint": "a" * 64,
        "storage": [_make_storage_group()],
        "network": [_make_network_group()],
        "accelerators": [_make_accelerator_group()],
    }
    fields.update(kwargs)
    return fields


async def create_test_hardware_profile_entry(
    fixture: Fixture, node_id: int | None = None, **kwargs
) -> HardwareProfile:
    if not node_id:
        node = await create_test_machine_entry(fixture)
        node_id = node["id"]

    hardware_profile = make_hardware_profile_dict(node_id, **kwargs)
    now = utcnow()
    hardware_profile["created"] = now
    hardware_profile["updated"] = now
    [created] = await fixture.create(
        HardwareProfileTable.name, hardware_profile
    )

    return HardwareProfile(**created)
