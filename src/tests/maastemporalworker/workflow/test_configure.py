# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.node import NodeTypeEnum
from maasservicelayer.db import Database
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.vlans import VlansClauseFactory
from maasservicelayer.models.vlans import Vlan
from maasservicelayer.services import ServiceCollectionV3, VlansService
from maasservicelayer.utils.date import utcnow
import maastemporalworker.workflow.activity as activity_module
from maastemporalworker.workflow.configure import (
    ConfigureAgentActivity,
    GetRackControllerVLANsInput,
    GetRackControllerVLANsResult,
    GetRegionControllerEndpointsResult,
)
from tests.fixtures.factories.interface import create_test_interface_entry
from tests.fixtures.factories.node import create_test_region_controller_entry
from tests.fixtures.factories.node_config import create_test_node_config_entry
from tests.fixtures.factories.staticipaddress import (
    create_test_staticipaddress_entry,
)
from tests.fixtures.factories.subnet import create_test_subnet_entry
from tests.maasapiserver.fixtures.db import Fixture


@pytest.mark.asyncio
@pytest.mark.usefixtures("maasdb")
class TestConfigureAgentActivity:
    async def test_get_rack_controller(self, monkeypatch):
        mock_services = Mock(ServiceCollectionV3)
        mock_services.vlans = Mock(VlansService)
        mock_services.vlans.get_node_vlans = AsyncMock(
            return_value=[
                Vlan(
                    id=1,
                    vid=0,
                    description="",
                    mtu=1500,
                    dhcp_on=False,
                    fabric_id=0,
                    created=utcnow(),
                    updated=utcnow(),
                )
            ]
        )
        mock_services.produce = AsyncMock(return_value=mock_services)
        monkeypatch.setattr(
            activity_module, "ServiceCollectionV3", mock_services
        )

        configure_activities = ConfigureAgentActivity(
            Mock(Database), connection=Mock(AsyncConnection)
        )

        result = await configure_activities.get_rack_controller_vlans(
            GetRackControllerVLANsInput(system_id="abc")
        )
        assert result == GetRackControllerVLANsResult([1])
        mock_services.vlans.get_node_vlans.assert_called_once_with(
            query=QuerySpec(
                where=VlansClauseFactory.and_clauses(
                    [
                        VlansClauseFactory.with_system_id("abc"),
                        VlansClauseFactory.or_clauses(
                            [
                                VlansClauseFactory.with_node_type(
                                    NodeTypeEnum.RACK_CONTROLLER
                                ),
                                VlansClauseFactory.with_node_type(
                                    NodeTypeEnum.REGION_AND_RACK_CONTROLLER
                                ),
                            ]
                        ),
                    ]
                )
            )
        )

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
