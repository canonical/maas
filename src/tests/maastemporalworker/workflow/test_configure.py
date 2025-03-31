# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv4Address, IPv6Address
from unittest.mock import Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection
from temporalio.testing import ActivityEnvironment

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
    CacheForServices,
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
    GetResolverConfigInput,
)
from tests.fixtures.factories.interface import create_test_interface_entry
from tests.fixtures.factories.node import (
    create_test_rack_and_region_controller_entry,
    create_test_rack_controller_entry,
    create_test_region_controller_entry,
)
from tests.fixtures.factories.staticipaddress import (
    create_test_staticipaddress_entry,
)
from tests.fixtures.factories.subnet import create_test_subnet_entry
from tests.fixtures.factories.vlan import create_test_vlan_entry
from tests.maasapiserver.fixtures.db import Fixture


@pytest.mark.asyncio
@pytest.mark.usefixtures("maasdb")
class TestConfigureAgentActivity:
    async def test_get_rack_controller(self, monkeypatch):
        mock_services = Mock(ServiceCollectionV3)
        mock_services.vlans = Mock(VlansService)
        mock_services.vlans.get_node_vlans.return_value = [
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
        mock_services.produce.return_value = mock_services
        monkeypatch.setattr(
            activity_module, "ServiceCollectionV3", mock_services
        )

        services_cache = CacheForServices()
        configure_activities = ConfigureAgentActivity(
            Mock(Database), services_cache, connection=Mock(AsyncConnection)
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

        services_cache = CacheForServices()
        configure_activities = ConfigureAgentActivity(
            Mock(Database), services_cache, connection=Mock(AsyncConnection)
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

    async def test_get_resolver_config_rack_and_region(
        self, fixture: Fixture, db_connection: AsyncConnection, db: Database
    ):
        env = ActivityEnvironment()

        agent_node = await create_test_rack_and_region_controller_entry(
            fixture
        )

        services_cache = CacheForServices()
        activities = ConfigureAgentActivity(
            db, services_cache, connection=db_connection
        )

        result = await env.run(
            activities.get_resolver_config,
            GetResolverConfigInput(
                system_id=agent_node["system_id"],
            ),
        )

        assert not result.enabled
        assert not result.bind_ips
        assert not result.authoritative_ips

    async def test_get_resolver_config_region(
        self, fixture: Fixture, db_connection: AsyncConnection, db: Database
    ):
        env = ActivityEnvironment()

        agent_node = await create_test_region_controller_entry(fixture)

        services_cache = CacheForServices()
        activities = ConfigureAgentActivity(
            db, services_cache, connection=db_connection
        )

        result = await env.run(
            activities.get_resolver_config,
            GetResolverConfigInput(
                system_id=agent_node["system_id"],
            ),
        )

        assert not result.enabled
        assert not result.bind_ips
        assert not result.authoritative_ips

    async def test_get_resolver_config_rack(
        self, fixture: Fixture, db_connection: AsyncConnection, db: Database
    ):
        env = ActivityEnvironment()

        vlan = await create_test_vlan_entry(fixture)
        dns_subnet = await create_test_subnet_entry(
            fixture, allow_dns=True, vlan=vlan
        )
        no_dns_subnet = await create_test_subnet_entry(
            fixture, allow_dns=False, vlan=vlan
        )
        regions = [
            await create_test_region_controller_entry(fixture)
            for _ in range(3)
        ]
        sips = [
            (await create_test_staticipaddress_entry(fixture, subnet=subnet))[
                0
            ]
            for subnet in [dns_subnet, no_dns_subnet]
            for _ in regions
        ]
        [
            await create_test_interface_entry(
                fixture, node=regions[i % len(regions)], ips=[sip]
            )
            for i, sip in enumerate(sips)
        ]

        agent_node = await create_test_rack_controller_entry(fixture)
        agent_ips = [
            (await create_test_staticipaddress_entry(fixture, subnet=subnet))[
                0
            ]
            for subnet in [dns_subnet, no_dns_subnet]
        ]
        [
            await create_test_interface_entry(
                fixture, node=agent_node, ips=[sip]
            )
            for sip in agent_ips
        ]

        services_cache = CacheForServices()
        activities = ConfigureAgentActivity(
            db, services_cache, connection=db_connection
        )

        result = await env.run(
            activities.get_resolver_config,
            GetResolverConfigInput(
                system_id=agent_node["system_id"],
            ),
        )

        assert result.enabled
        assert set(result.bind_ips) == set(
            [
                str(sip["ip"])
                for sip in agent_ips
                if sip["subnet_id"] == dns_subnet["id"]
            ]
        )
        assert set(result.authoritative_ips) == set(
            [
                str(sip["ip"])
                for sip in sips
                if sip["subnet_id"] == dns_subnet["id"]
            ]
        )
