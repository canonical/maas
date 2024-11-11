# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv4Address, IPv6Address
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.ipaddress import IpAddressType
from maascommon.enums.node import NodeTypeEnum
from maasservicelayer.db import Database
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.staticipaddress import (
    StaticIPAddressClauseFactory,
)
from maasservicelayer.db.repositories.vlans import VlansClauseFactory
from maasservicelayer.models.staticipaddress import StaticIPAddress
from maasservicelayer.models.vlans import Vlan
from maasservicelayer.services import (
    ServiceCollectionV3,
    StaticIPAddressService,
    VlansService,
)
from maasservicelayer.utils.date import utcnow
import maastemporalworker.workflow.activity as activity_module
from maastemporalworker.workflow.configure import (
    ConfigureAgentActivity,
    GetRackControllerVLANsInput,
    GetRackControllerVLANsResult,
    GetRegionControllerEndpointsResult,
)


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

    async def test_get_region_controller_endpoints(self, monkeypatch):
        mock_services = Mock(ServiceCollectionV3)
        mock_services.staticipaddress = Mock(StaticIPAddressService)
        mock_services.staticipaddress.get_for_nodes.return_value = [
            StaticIPAddress(
                id=0,
                ip=IPv4Address("10.0.0.1"),
                alloc_type=IpAddressType.STICKY,
                lease_time=0,
                temp_expires_on=None,
                subnet_id=0,
            ),
            StaticIPAddress(
                id=0,
                ip=IPv6Address("2001:0:130f::9c0:876a:130b"),
                alloc_type=IpAddressType.STICKY,
                lease_time=0,
                temp_expires_on=None,
                subnet_id=0,
            ),
        ]

        mock_services.produce.return_value = mock_services
        monkeypatch.setattr(
            activity_module, "ServiceCollectionV3", mock_services
        )

        configure_activities = ConfigureAgentActivity(
            Mock(Database), connection=Mock(AsyncConnection)
        )

        result = await configure_activities.get_region_controller_endpoints()
        assert result == GetRegionControllerEndpointsResult(
            [
                "http://10.0.0.1:5240/MAAS/",
                "http://[2001:0:130f::9c0:876a:130b]:5240/MAAS/",
            ]
        )
        mock_services.staticipaddress.get_for_nodes.assert_called_once_with(
            query=QuerySpec(
                where=StaticIPAddressClauseFactory.or_clauses(
                    [
                        StaticIPAddressClauseFactory.with_node_type(
                            NodeTypeEnum.REGION_CONTROLLER
                        ),
                        StaticIPAddressClauseFactory.with_node_type(
                            NodeTypeEnum.REGION_AND_RACK_CONTROLLER
                        ),
                    ]
                )
            )
        )
