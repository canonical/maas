# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.context import Context
from maasservicelayer.db.mappers.base import UnsupportedFilterError
from maasservicelayer.db.repositories.machines_v2 import MachinesV2Repository
from maasservicelayer.filters.nodes import NodeFilters
from maasservicelayer.filters.query import OrderBy, QuerySpec
from maasservicelayer.models.machine_details import MachineRecord
from maasservicelayer.models.nodes import Node
from tests.fixtures.factories.interface import create_test_interface_dict
from tests.fixtures.factories.node import create_test_machine_entry
from tests.fixtures.factories.staticipaddress import (
    create_test_staticipaddress_entry,
)
from tests.fixtures.factories.vlan import create_test_vlan_entry
from tests.maasapiserver.fixtures.db import Fixture


async def test_machine_projection_filters_and_orders_actual_rows(
    db_connection: AsyncConnection, fixture: Fixture
) -> None:
    first = await create_test_machine_entry(fixture, hostname="alpha")
    second = await create_test_machine_entry(fixture, hostname="bravo")
    await create_test_machine_entry(fixture, hostname="charlie")
    ips = await create_test_staticipaddress_entry(fixture, ip="192.0.2.10")
    await create_test_interface_dict(fixture, node=first, ips=ips)
    repository = MachinesV2Repository(Context(connection=db_connection))

    rows = await repository.get_many(
        QuerySpec(
            where=NodeFilters.with_ids([first["id"], second["id"]]),
            order_by=(OrderBy(Node, "hostname", descending=True),),
        )
    )

    assert [(row.id, row.hostname, row.system_id) for row in rows] == [
        (second["id"], "bravo", second["system_id"]),
        (first["id"], "alpha", first["system_id"]),
    ]
    assert all(isinstance(row, MachineRecord) for row in rows)
    assert rows[1].ips == ["192.0.2.10"]
    assert rows[1].is_boot_ips == [True]
    assert rows[1].memory == Decimal("4.0")
    assert rows[0].ips == []
    assert rows[0].physical_disk_count == 0
    assert rows[0].storage == 0
    assert rows[0].testing_status_combined == -1
    assert rows[0].domain_id is None
    assert rows[0].domain_name is None


async def test_machine_projection_preserves_nullable_columns(
    db_connection: AsyncConnection, fixture: Fixture
) -> None:
    machine = await create_test_machine_entry(
        fixture, domain_id=None, pool_id=None, architecture=None
    )
    [space] = await fixture.create(
        "maasserver_space",
        [
            {
                "created": machine["created"],
                "updated": machine["updated"],
                "name": None,
                "description": "",
            }
        ],
    )
    vlan = await create_test_vlan_entry(fixture, space_id=space["id"])
    await create_test_interface_dict(fixture, node=machine, vlan=vlan)
    await create_test_interface_dict(fixture, node=machine, mac_address=None)
    repository = MachinesV2Repository(Context(connection=db_connection))

    [record] = await repository.get_many(
        QuerySpec(where=NodeFilters.with_ids([machine["id"]]))
    )

    assert record.domain_id is None
    assert record.domain_name is None
    assert record.pool_id is None
    assert record.pool_name is None
    assert record.architecture is None
    assert record.fqdn == f"{machine['hostname']}."
    assert record.boot_vlan_id is None
    assert record.boot_vlan_name == ""
    assert record.boot_fabric_id is None
    assert record.boot_fabric_name is None
    assert record.power_type is None
    assert record.status_message is None
    assert record.fabrics == [None]
    assert record.spaces == [None]
    assert record.extra_macs == [None]


async def test_machine_projection_rejects_record_model_ordering() -> None:
    repository = MachinesV2Repository(Context())

    with pytest.raises(UnsupportedFilterError):
        await repository.get_many(
            QuerySpec(order_by=(OrderBy(MachineRecord, "hostname"),))
        )
