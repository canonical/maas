# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any

from sqlalchemy.sql.operators import and_

from maasservicelayer.db.tables import DiscoveryView
from maasservicelayer.models.discoveries import Discovery
from tests.fixtures.factories.interface import create_test_interface_entry
from tests.fixtures.factories.mdns import create_test_mdns_entry
from tests.fixtures.factories.neighbours import create_test_neighbour_entry
from tests.fixtures.factories.vlan import create_test_vlan_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.test_subnet_utilization import (
    create_test_rack_controller_entry,
)


async def create_test_discovery(
    fixture: Fixture,
    hostname: str | None = None,
    rack_controller: dict[str, Any] | None = None,
) -> Discovery:
    if rack_controller is None:
        rack_controller = await create_test_rack_controller_entry(fixture)
    vlan = await create_test_vlan_entry(fixture)
    interface = await create_test_interface_entry(
        fixture, node=rack_controller, vlan=vlan
    )
    neighbour = await create_test_neighbour_entry(
        fixture, interface_id=interface.id
    )
    if hostname is not None:
        await create_test_mdns_entry(
            fixture,
            hostname=hostname,
            ip=neighbour.ip,
            interface_id=interface.id,
        )
    discoveries = await fixture.get_typed(
        "maasserver_discovery",
        Discovery,
        and_(
            DiscoveryView.c.mac_address == neighbour.mac_address,
            DiscoveryView.c.ip == neighbour.ip,
        ),
    )
    return discoveries[0]
