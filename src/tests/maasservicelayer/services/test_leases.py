# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime
from ipaddress import IPv4Address, IPv6Address
import time
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.interface import InterfaceType
from maascommon.enums.ipaddress import (
    IpAddressFamily,
    IpAddressType,
    LeaseAction,
)
from maasservicelayer.models.interfaces import Interface
from maasservicelayer.models.leases import Lease
from maasservicelayer.models.staticipaddress import StaticIPAddress
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.services.dnsresources import DNSResourcesService
from maasservicelayer.services.interfaces import InterfacesService
from maasservicelayer.services.ipranges import IPRangesService
from maasservicelayer.services.leases import LeasesService, LeaseUpdateError
from maasservicelayer.services.nodes import NodesService
from maasservicelayer.services.staticipaddress import StaticIPAddressService
from maasservicelayer.services.subnets import SubnetsService


@pytest.mark.asyncio
class TestLeasesService:
    async def test_store_lease_info_no_subnet(self):
        mock_dns_resources_service = Mock(DNSResourcesService)
        mock_nodes_service = Mock(NodesService)
        mock_static_ip_address_service = Mock(StaticIPAddressService)
        mock_subnets_service = Mock(SubnetsService)
        mock_interfaces_service = Mock(InterfacesService)
        mock_ip_ranges_service = Mock(IPRangesService)
        leases_service = LeasesService(
            Mock(AsyncConnection),
            dnsresource_service=mock_dns_resources_service,
            node_service=mock_nodes_service,
            staticipaddress_service=mock_static_ip_address_service,
            subnet_service=mock_subnets_service,
            interface_service=mock_interfaces_service,
            iprange_service=mock_ip_ranges_service,
        )
        mock_subnets_service.find_best_subnet_for_ip = AsyncMock(
            return_value=None
        )
        try:
            await leases_service.store_lease_info(
                Lease(
                    action=LeaseAction.COMMIT,
                    ip_family=IpAddressFamily.IPV4,
                    hostname="hostname",
                    mac="00:11:22:33:44:55",
                    ip=IPv4Address("10.0.0.2"),
                    timestamp_epoch=int(time.time()),
                    lease_time_seconds=30,
                )
            )
        except Exception as e:
            assert isinstance(e, LeaseUpdateError)

    async def test_store_lease_info_commit_v4(
        self, db_connection: AsyncConnection
    ) -> None:
        subnet = Subnet(
            id=1,
            cidr="10.0.0.0/24",
            created=datetime.utcnow(),
            updated=datetime.utcnow(),
            rdns_mode=1,
            allow_dns=True,
            allow_proxy=True,
            active_discovery=True,
            managed=True,
            disabled_boot_architectures=[],
        )
        interface = Interface(
            id=2,
            mac_address="00:11:22:33:44:55",
            type=InterfaceType.PHYSICAL,
            name="eth0",
            created=datetime.utcnow(),
            updated=datetime.utcnow(),
        )
        sip = StaticIPAddress(
            id=3,
            ip="10.0.0.2",
            alloc_type=IpAddressType.DISCOVERED,
            lease_time=600,
            subnet_id=subnet.id,
            created=datetime.utcnow(),
            updated=datetime.utcnow(),
        )

        mock_dns_resources_service = Mock(DNSResourcesService)
        mock_nodes_service = Mock(NodesService)
        mock_static_ip_address_service = Mock(StaticIPAddressService)
        mock_subnets_service = Mock(SubnetsService)
        mock_interfaces_service = Mock(InterfacesService)
        mock_ip_ranges_service = Mock(IPRangesService)
        leases_service = LeasesService(
            Mock(AsyncConnection),
            dnsresource_service=mock_dns_resources_service,
            node_service=mock_nodes_service,
            staticipaddress_service=mock_static_ip_address_service,
            subnet_service=mock_subnets_service,
            interface_service=mock_interfaces_service,
            iprange_service=mock_ip_ranges_service,
        )
        mock_static_ip_address_service.create_or_update = AsyncMock(
            return_value=sip
        )
        mock_subnets_service.find_best_subnet_for_ip = AsyncMock(
            return_value=subnet
        )
        mock_interfaces_service.get_interfaces_for_mac = AsyncMock(
            return_value=[interface]
        )

        ip = IPv4Address("10.0.0.2")
        await leases_service.store_lease_info(
            Lease(
                action=LeaseAction.COMMIT,
                ip_family=IpAddressFamily.IPV4,
                hostname="hostname",
                mac="00:11:22:33:44:55",
                ip=ip,
                timestamp_epoch=int(time.time()),
                lease_time_seconds=30,
            )
        )

        mock_subnets_service.find_best_subnet_for_ip.assert_called_once_with(
            ip
        )
        mock_ip_ranges_service.get_dynamic_range_for_ip.assert_called_once_with(
            subnet, ip
        )
        mock_interfaces_service.get_interfaces_for_mac.assert_called_once_with(
            "00:11:22:33:44:55"
        )
        mock_static_ip_address_service.get_discovered_ips_in_family_for_interfaces(
            [interface], IpAddressFamily.IPV4
        )
        mock_interfaces_service.add_ip.assert_called_once_with(interface, sip)

    async def test_store_lease_info_commit_v6(
        self, db_connection: AsyncConnection
    ) -> None:
        subnet = Subnet(
            id=1,
            cidr="fd42:be3f:b08a:3d6c::/64",
            created=datetime.utcnow(),
            updated=datetime.utcnow(),
            rdns_mode=1,
            allow_dns=True,
            allow_proxy=True,
            active_discovery=True,
            managed=True,
            disabled_boot_architectures=[],
        )
        interface = Interface(
            id=2,
            mac_address="00:11:22:33:44:55",
            type=InterfaceType.PHYSICAL,
            name="eth0",
            created=datetime.utcnow(),
            updated=datetime.utcnow(),
        )
        sip = StaticIPAddress(
            id=3,
            ip="fd42:be3f:b08a:3d6c::2",
            alloc_type=IpAddressType.DISCOVERED,
            lease_time=600,
            subnet_id=subnet.id,
            created=datetime.utcnow(),
            updated=datetime.utcnow(),
        )

        mock_dns_resources_service = Mock(DNSResourcesService)
        mock_nodes_service = Mock(NodesService)
        mock_static_ip_address_service = Mock(StaticIPAddressService)
        mock_subnets_service = Mock(SubnetsService)
        mock_interfaces_service = Mock(InterfacesService)
        mock_ip_ranges_service = Mock(IPRangesService)
        leases_service = LeasesService(
            Mock(AsyncConnection),
            dnsresource_service=mock_dns_resources_service,
            node_service=mock_nodes_service,
            staticipaddress_service=mock_static_ip_address_service,
            subnet_service=mock_subnets_service,
            interface_service=mock_interfaces_service,
            iprange_service=mock_ip_ranges_service,
        )
        mock_static_ip_address_service.create_or_update = AsyncMock(
            return_value=sip
        )
        mock_subnets_service.find_best_subnet_for_ip = AsyncMock(
            return_value=subnet
        )
        mock_interfaces_service.get_interfaces_for_mac = AsyncMock(
            return_value=[interface]
        )

        ip = IPv6Address("fd42:be3f:b08a:3d6c::2")
        await leases_service.store_lease_info(
            Lease(
                action=LeaseAction.COMMIT,
                ip_family=IpAddressFamily.IPV6,
                hostname="hostname",
                mac=interface.mac_address,
                ip=IPv6Address("fd42:be3f:b08a:3d6c::2"),
                timestamp_epoch=int(time.time()),
                lease_time_seconds=30,
            )
        )

        mock_subnets_service.find_best_subnet_for_ip.assert_called_once_with(
            ip
        )
        mock_ip_ranges_service.get_dynamic_range_for_ip.assert_called_once_with(
            subnet, ip
        )
        mock_interfaces_service.get_interfaces_for_mac.assert_called_once_with(
            "00:11:22:33:44:55"
        )
        mock_static_ip_address_service.get_discovered_ips_in_family_for_interfaces(
            [interface], IpAddressFamily.IPV6
        )
        mock_interfaces_service.add_ip.assert_called_once_with(interface, sip)

    async def test_store_lease_info_expiry(
        self, db_connection: AsyncConnection
    ):
        subnet = Subnet(
            id=1,
            cidr="10.0.0.0/24",
            created=datetime.utcnow(),
            updated=datetime.utcnow(),
            rdns_mode=1,
            allow_dns=True,
            allow_proxy=True,
            active_discovery=True,
            managed=True,
            disabled_boot_architectures=[],
        )
        interface = Interface(
            id=2,
            mac_address="00:11:22:33:44:55",
            type=InterfaceType.PHYSICAL,
            name="eth0",
            created=datetime.utcnow(),
            updated=datetime.utcnow(),
        )
        sip = StaticIPAddress(
            id=3,
            ip="10.0.0.2",
            alloc_type=IpAddressType.DISCOVERED,
            lease_time=600,
            subnet_id=subnet.id,
            created=datetime.utcnow(),
            updated=datetime.utcnow(),
        )

        mock_dns_resources_service = Mock(DNSResourcesService)
        mock_nodes_service = Mock(NodesService)
        mock_static_ip_address_service = Mock(StaticIPAddressService)
        mock_subnets_service = Mock(SubnetsService)
        mock_interfaces_service = Mock(InterfacesService)
        mock_ip_ranges_service = Mock(IPRangesService)
        leases_service = LeasesService(
            Mock(AsyncConnection),
            dnsresource_service=mock_dns_resources_service,
            node_service=mock_nodes_service,
            staticipaddress_service=mock_static_ip_address_service,
            subnet_service=mock_subnets_service,
            interface_service=mock_interfaces_service,
            iprange_service=mock_ip_ranges_service,
        )
        mock_static_ip_address_service.get_discovered_ips_in_family_for_interfaces = AsyncMock(
            return_value=[sip]
        )
        mock_static_ip_address_service.get_for_interfaces = AsyncMock(
            return_value=sip
        )
        mock_subnets_service.find_best_subnet_for_ip = AsyncMock(
            return_value=subnet
        )
        mock_interfaces_service.get_interfaces_for_mac = AsyncMock(
            return_value=[interface]
        )
        mock_interfaces_service.bulk_link_ip = AsyncMock(return_value=None)

        ip = IPv4Address("10.0.0.2")
        await leases_service.store_lease_info(
            Lease(
                action=LeaseAction.EXPIRY,
                ip_family=IpAddressFamily.IPV4,
                hostname="hostname",
                mac=interface.mac_address,
                ip=ip,
                timestamp_epoch=int(time.time()),
                lease_time_seconds=30,
            )
        )

        mock_subnets_service.find_best_subnet_for_ip.assert_called_once_with(
            ip
        )
        mock_ip_ranges_service.get_dynamic_range_for_ip.assert_called_once_with(
            subnet, ip
        )
        mock_interfaces_service.get_interfaces_for_mac.assert_called_once_with(
            "00:11:22:33:44:55"
        )
        mock_static_ip_address_service.get_discovered_ips_in_family_for_interfaces(
            [interface], family=IpAddressFamily.IPV4
        )
        sip.ip = None
        mock_interfaces_service.bulk_link_ip.assert_called_once_with(
            sip, [interface]
        )

    async def test_store_lease_info_release(
        self, db_connection: AsyncConnection
    ):
        subnet = Subnet(
            id=1,
            cidr="10.0.0.0/24",
            created=datetime.utcnow(),
            updated=datetime.utcnow(),
            rdns_mode=1,
            allow_dns=True,
            allow_proxy=True,
            active_discovery=True,
            managed=True,
            disabled_boot_architectures=[],
        )
        interface = Interface(
            id=2,
            mac_address="00:11:22:33:44:55",
            type=InterfaceType.PHYSICAL,
            name="eth0",
            created=datetime.utcnow(),
            updated=datetime.utcnow(),
        )
        sip = StaticIPAddress(
            id=3,
            ip="10.0.0.2",
            alloc_type=IpAddressType.DISCOVERED,
            lease_time=600,
            subnet_id=subnet.id,
            created=datetime.utcnow(),
            updated=datetime.utcnow(),
        )

        mock_dns_resources_service = Mock(DNSResourcesService)
        mock_nodes_service = Mock(NodesService)
        mock_static_ip_address_service = Mock(StaticIPAddressService)
        mock_subnets_service = Mock(SubnetsService)
        mock_interfaces_service = Mock(InterfacesService)
        mock_ip_ranges_service = Mock(IPRangesService)
        leases_service = LeasesService(
            Mock(AsyncConnection),
            dnsresource_service=mock_dns_resources_service,
            node_service=mock_nodes_service,
            staticipaddress_service=mock_static_ip_address_service,
            subnet_service=mock_subnets_service,
            interface_service=mock_interfaces_service,
            iprange_service=mock_ip_ranges_service,
        )
        mock_static_ip_address_service.get_discovered_ips_in_family_for_interfaces = AsyncMock(
            return_value=[sip]
        )
        mock_static_ip_address_service.get_for_interfaces = AsyncMock(
            return_value=sip
        )
        mock_subnets_service.find_best_subnet_for_ip = AsyncMock(
            return_value=subnet
        )
        mock_interfaces_service.get_interfaces_for_mac = AsyncMock(
            return_value=[interface]
        )
        mock_interfaces_service.bulk_link_ip = AsyncMock(return_value=None)

        ip = IPv4Address("10.0.0.2")
        await leases_service.store_lease_info(
            Lease(
                action=LeaseAction.RELEASE,
                ip_family=IpAddressFamily.IPV4,
                hostname="hostname",
                mac=interface.mac_address,
                ip=IPv4Address("10.0.0.2"),
                timestamp_epoch=int(time.time()),
                lease_time_seconds=30,
            )
        )

        mock_subnets_service.find_best_subnet_for_ip.assert_called_once_with(
            ip
        )
        mock_ip_ranges_service.get_dynamic_range_for_ip.assert_called_once_with(
            subnet, ip
        )
        mock_interfaces_service.get_interfaces_for_mac.assert_called_once_with(
            "00:11:22:33:44:55"
        )
        mock_static_ip_address_service.get_discovered_ips_in_family_for_interfaces(
            [interface], family=IpAddressFamily.IPV4
        )
        sip.ip = None
        mock_interfaces_service.bulk_link_ip.assert_called_once_with(
            sip, [interface]
        )
