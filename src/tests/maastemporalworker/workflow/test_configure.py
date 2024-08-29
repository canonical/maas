# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.db import Database
from maasservicelayer.db.tables import VlanTable
from maastemporalworker.workflow.configure import (
    ConfigureAgentActivity,
    GetRackControllerVLANsInput,
    GetRackControllerVLANsResult,
    GetRegionControllerEndpointsResult,
)
from tests.fixtures.factories.interface import create_test_interface_entry
from tests.fixtures.factories.node import (
    create_test_rack_and_region_controller_entry,
    create_test_rack_controller_entry,
    create_test_region_controller_entry,
)
from tests.fixtures.factories.node_config import create_test_node_config_entry
from tests.fixtures.factories.staticipaddress import (
    create_test_staticipaddress_entry,
)
from tests.fixtures.factories.subnet import create_test_subnet_entry
from tests.fixtures.factories.vlan import create_test_vlan_entry
from tests.maasapiserver.fixtures.db import Fixture


@pytest.mark.asyncio
@pytest.mark.usefixtures("maasdb")
class TestConfigureAgentActivity:
    async def test_get_rack_controller_vlans_no_rack_controller(
        self, db: Database, db_connection: AsyncConnection
    ):
        configure_activities = ConfigureAgentActivity(
            db, connection=db_connection
        )

        result = await configure_activities.get_rack_controller_vlans(
            GetRackControllerVLANsInput(system_id="abc")
        )
        assert result == GetRackControllerVLANsResult([])

    async def test_get_rack_controller_vlans_valid_system_id(
        self, db: Database, db_connection: AsyncConnection, fixture: Fixture
    ):
        subnet = await create_test_subnet_entry(fixture)
        rack_controller = await create_test_rack_controller_entry(fixture)
        [ip] = await create_test_staticipaddress_entry(fixture, subnet=subnet)
        await create_test_interface_entry(
            fixture, node=rack_controller, ips=[ip]
        )
        configure_activities = ConfigureAgentActivity(
            db, connection=db_connection
        )

        result = await configure_activities.get_rack_controller_vlans(
            GetRackControllerVLANsInput(system_id=rack_controller["system_id"])
        )
        vlan_stmt = (
            select(
                VlanTable.c.id,
            )
            .select_from(VlanTable)
            .filter(VlanTable.c.id == subnet["vlan_id"])
        )
        [vlan] = (await db_connection.execute(vlan_stmt)).one_or_none()
        assert result == GetRackControllerVLANsResult([vlan])

    async def test_get_rack_controller_vlans_region_and_rack_controller(
        self, db: Database, db_connection: AsyncConnection, fixture: Fixture
    ):
        subnet = await create_test_subnet_entry(fixture)
        rack_controller = await create_test_rack_and_region_controller_entry(
            fixture
        )
        [ip] = await create_test_staticipaddress_entry(fixture, subnet=subnet)
        await create_test_interface_entry(
            fixture, node=rack_controller, ips=[ip]
        )
        configure_activities = ConfigureAgentActivity(
            db, connection=db_connection
        )

        result = await configure_activities.get_rack_controller_vlans(
            GetRackControllerVLANsInput(system_id=rack_controller["system_id"])
        )
        vlan_stmt = (
            select(
                VlanTable.c.id,
            )
            .select_from(VlanTable)
            .filter(VlanTable.c.id == subnet["vlan_id"])
        )
        [vlan] = (await db_connection.execute(vlan_stmt)).one_or_none()
        assert result == GetRackControllerVLANsResult([vlan])

    async def test_get_rack_controller_vlans_multiple_vlans(
        self, db: Database, db_connection: AsyncConnection, fixture: Fixture
    ):
        vlan1 = await create_test_vlan_entry(fixture)
        vlan2 = await create_test_vlan_entry(fixture)
        subnet1 = await create_test_subnet_entry(fixture, vlan_id=vlan1["id"])
        subnet2 = await create_test_subnet_entry(fixture, vlan_id=vlan2["id"])
        rack_controller = await create_test_rack_controller_entry(fixture)
        current_node_config = await create_test_node_config_entry(
            fixture, node=rack_controller
        )
        rack_controller["current_config_id"] = current_node_config["id"]
        [ip1] = await create_test_staticipaddress_entry(
            fixture, subnet=subnet1
        )
        [ip2] = await create_test_staticipaddress_entry(
            fixture, subnet=subnet2
        )
        await create_test_interface_entry(
            fixture, node=rack_controller, ips=[ip1]
        )
        await create_test_interface_entry(
            fixture, node=rack_controller, ips=[ip2]
        )
        configure_activities = ConfigureAgentActivity(
            db, connection=db_connection
        )
        result = await configure_activities.get_rack_controller_vlans(
            GetRackControllerVLANsInput(system_id=rack_controller["system_id"])
        )
        assert isinstance(result, GetRackControllerVLANsResult)
        assert set(result.vlans) == set([vlan1["id"], vlan2["id"]])

    async def test_get_region_controller_endpoints_no_region_controller(
        self, db: Database, db_connection: AsyncConnection
    ):
        configure_activities = ConfigureAgentActivity(
            db, connection=db_connection
        )

        result = await configure_activities.get_region_controller_endpoints()
        assert result == GetRegionControllerEndpointsResult([])

    async def test_get_region_controller_endpoints_one_region_controller(
        self, db: Database, db_connection: AsyncConnection, fixture: Fixture
    ):
        subnet = await create_test_subnet_entry(fixture)
        region_controller = await create_test_region_controller_entry(fixture)
        [ip] = await create_test_staticipaddress_entry(fixture, subnet=subnet)
        await create_test_interface_entry(
            fixture, node=region_controller, ips=[ip]
        )
        configure_activities = ConfigureAgentActivity(
            db, connection=db_connection
        )

        result = await configure_activities.get_region_controller_endpoints()

        endpoint = f"http://{ip['ip']}:5240/MAAS/"
        if ip["ip"].version == 6:
            endpoint = f"http://[{ip['ip']}]:5240/MAAS/"

        assert result == GetRegionControllerEndpointsResult([endpoint])

    async def test_get_region_controller_endpoints_missing_links(
        self, db: Database, db_connection: AsyncConnection, fixture: Fixture
    ):
        subnet = await create_test_subnet_entry(fixture)
        region_controller = await create_test_region_controller_entry(fixture)
        [ip] = await create_test_staticipaddress_entry(fixture, subnet=subnet)
        await create_test_interface_entry(
            fixture, node=region_controller, ips=[ip]
        )
        await create_test_interface_entry(
            fixture, node=region_controller, ips=[]
        )
        configure_activities = ConfigureAgentActivity(
            db, connection=db_connection
        )

        result = await configure_activities.get_region_controller_endpoints()

        endpoint = f"http://{ip['ip']}:5240/MAAS/"
        if ip["ip"].version == 6:
            endpoint = f"http://[{ip['ip']}]:5240/MAAS/"

        assert result == GetRegionControllerEndpointsResult([endpoint])

    async def test_get_region_controller_endpoints_two_region_controllers(
        self, db: Database, db_connection: AsyncConnection, fixture: Fixture
    ):
        subnet1 = await create_test_subnet_entry(fixture)
        subnet2 = await create_test_subnet_entry(fixture)
        region_controller = await create_test_region_controller_entry(fixture)
        current_node_config = await create_test_node_config_entry(
            fixture, node=region_controller
        )
        region_controller["current_config_id"] = current_node_config["id"]
        [ip1] = await create_test_staticipaddress_entry(
            fixture, subnet=subnet1
        )
        [ip2] = await create_test_staticipaddress_entry(
            fixture, subnet=subnet2
        )
        await create_test_interface_entry(
            fixture, node=region_controller, ips=[ip1]
        )
        await create_test_interface_entry(
            fixture, node=region_controller, ips=[ip2]
        )
        configure_activities = ConfigureAgentActivity(
            db, connection=db_connection
        )

        result = await configure_activities.get_region_controller_endpoints()

        endpoint1 = f"http://{ip1['ip']}:5240/MAAS/"
        if ip1["ip"].version == 6:
            endpoint1 = f"http://[{ip1['ip']}]:5240/MAAS/"

        endpoint2 = f"http://{ip2['ip']}:5240/MAAS/"
        if ip2["ip"].version == 6:
            endpoint2 = f"http://[{ip2['ip']}]:5240/MAAS/"

        assert isinstance(result, GetRegionControllerEndpointsResult)
        assert set(result.endpoints) == set([endpoint1, endpoint2])
