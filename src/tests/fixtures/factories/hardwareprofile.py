#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime, timezone
from typing import Any

from maasservicelayer.db.tables import HardwareProfileTable
from maasservicelayer.models.hardwareprofile import HardwareProfile
from maastesting.factory import factory
from tests.fixtures.factories.node import create_test_machine_entry
from tests.maasapiserver.fixtures.db import Fixture


def _make_storage_group() -> dict[str, Any]:
    return {
        "count": 1,
        "disk_type": "ssd",
        "size_bytes": 512 * 1024 * 1024 * 1024,
        "items": [
            {
                "name": factory.make_name("disk"),
                "size_bytes": 512 * 1024 * 1024 * 1024,
                "block_size": 512,
                "id_path": None,
                "model": factory.make_name("model"),
                "serial": factory.make_name("serial"),
                "firmware_version": None,
                "numa_node": 0,
            }
        ],
    }


def _make_network_group() -> dict[str, Any]:
    return {
        "count": 1,
        "speed_mbps": 1000,
        "vendor": factory.make_name("vendor"),
        "product": factory.make_name("product"),
        "items": [
            {
                "name": factory.make_name("eth"),
                "mac_address": factory.make_mac_address(),
                "link_speed": 1000,
                "sriov_max_vf": 0,
                "numa_node": 0,
            }
        ],
    }


def _make_accelerator_group() -> dict[str, Any]:
    return {
        "count": 1,
        "vendor": factory.make_name("vendor"),
        "product": factory.make_name("product"),
        "items": [
            {
                "vendor_id": "0x10de",
                "product_id": "0x1eb8",
                "pci_address": "0000:00:1c.0",
                "numa_node": 0,
            }
        ],
    }


async def create_test_hardware_profile_entry(
    fixture: Fixture,
    node_id: int | None = None,
    **extra_details: Any,
) -> HardwareProfile:
    now = datetime.now(timezone.utc)

    if not node_id:
        node = await create_test_machine_entry(fixture)
        node_id = node["id"]

    hardware_profile: dict[str, Any] = {
        "created": now,
        "updated": now,
        "node_id": node_id,
        "architecture": "amd64/generic",
        "cpu_cores": 4,
        "cpu_speed_mhz": 2400,
        "memory_mb": 4096,
        "disk_count": 1,
        "total_storage_bytes": 512 * 1024 * 1024 * 1024,
        "nic_count": 1,
        "gpu_count": 0,
        "system_vendor": None,
        "system_product": None,
        "hardware_fingerprint": "a" * 64,
        "storage": [_make_storage_group()],
        "network": [_make_network_group()],
        "accelerators": [_make_accelerator_group()],
    }
    hardware_profile.update(extra_details)

    [created] = await fixture.create(
        HardwareProfileTable.name, hardware_profile
    )

    return HardwareProfile(**created)
