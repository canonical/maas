from datetime import datetime
from typing import Any

from sqlalchemy import update

from maasapiserver.common.utils.date import utcnow
from maasserver.enum import NODE_DEVICE_BUS
from maasservicelayer.db.tables import NodeTable
from maasservicelayer.models.machines import PciDevice, UsbDevice
from maastesting.factory import factory
from metadataserver.enum import HARDWARE_TYPE
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_node_config_entry(
    fixture: Fixture,
    node: dict[str, Any] | None = None,
    **extra_details: dict[str, Any],
) -> dict[str, Any]:
    created_at = datetime.utcnow().astimezone()
    updated_at = datetime.utcnow().astimezone()
    config = {
        "created": created_at,
        "updated": updated_at,
        "name": factory.make_name(),
    }
    config.update(extra_details)

    if node:
        config["node_id"] = node["id"]

    [created_config] = await fixture.create(
        "maasserver_nodeconfig",
        [config],
    )

    if node:
        stmt = (
            update(NodeTable)
            .where(
                NodeTable.c.id == node["id"],
            )
            .values(
                current_config_id=created_config["id"],
            )
        )
        await fixture.conn.execute(stmt)
        node["current_config_id"] = created_config["id"]

    return created_config


# TODO: create a NumaNode model and return it instead of dict
async def create_test_numa_node(
    fixture: Fixture, node: dict[str, Any]
) -> dict[str, Any]:
    now = utcnow()
    numa_node = {
        "created": now,
        "updated": now,
        "index": 0,
        "memory": 16384,
        "cores": [0, 1, 2, 3, 4, 5, 6, 7],
        "node_id": node["id"],
    }
    [numa_node] = await fixture.create("maasserver_numanode", [numa_node])
    return numa_node


async def create_test_usb_device(
    fixture: Fixture,
    numa_node: dict[str, Any],
    config: dict[str, Any],
    **extra_details: Any,
) -> UsbDevice:
    now = utcnow()
    device = {
        "created": now,
        "updated": now,
        "bus": NODE_DEVICE_BUS.USB,
        "hardware_type": HARDWARE_TYPE.NODE,
        "vendor_id": "0000",
        "product_id": "0000",
        "vendor_name": "vendor",
        "product_name": "product",
        "commissioning_driver": "commissioning driver",
        "bus_number": 0,
        "device_number": 0,
        "pci_address": None,
        "numa_node_id": numa_node["id"],
        "physical_blockdevice_id": None,
        "physical_interface_id": None,
        "node_config_id": config["id"],
    }
    device.update(**extra_details)
    [device] = await fixture.create("maasserver_nodedevice", [device])
    return UsbDevice(**device)


async def create_test_pci_device(
    fixture: Fixture,
    numa_node: dict[str, Any],
    config: dict[str, Any],
    **extra_details: Any,
) -> PciDevice:
    now = utcnow()
    device = {
        "created": now,
        "updated": now,
        "bus": NODE_DEVICE_BUS.PCIE,
        "hardware_type": HARDWARE_TYPE.NODE,
        "vendor_id": "0000",
        "product_id": "0000",
        "vendor_name": "vendor",
        "product_name": "product",
        "commissioning_driver": "commissioning driver",
        "bus_number": 0,
        "device_number": 0,
        "pci_address": "0000:00:00.0",
        "numa_node_id": numa_node["id"],
        "physical_blockdevice_id": None,
        "physical_interface_id": None,
        "node_config_id": config["id"],
    }
    device.update(**extra_details)
    [device] = await fixture.create("maasserver_nodedevice", [device])
    return PciDevice(**device)
