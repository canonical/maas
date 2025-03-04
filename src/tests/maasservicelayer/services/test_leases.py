# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv4Address, IPv6Address
import time
from unittest.mock import Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.interface import InterfaceType
from maascommon.enums.ipaddress import (
    IpAddressFamily,
    IpAddressType,
    LeaseAction,
)
from maasservicelayer.context import Context
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
from maasservicelayer.utils.date import utcnow


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
            context=Context(),
            dnsresource_service=mock_dns_resources_service,
            node_service=mock_nodes_service,
            staticipaddress_service=mock_static_ip_address_service,
            subnet_service=mock_subnets_service,
            interface_service=mock_interfaces_service,
            iprange_service=mock_ip_ranges_service,
        )
        mock_subnets_service.find_best_subnet_for_ip.return_value = None
        with pytest.raises(LeaseUpdateError):
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

    async def test_store_lease_info_creates_unkwnown_interface(
        self, db_connection: AsyncConnection
    ) -> None:
        subnet = Subnet(
            id=1,
            cidr="10.0.0.0/24",
            created=utcnow(),
            updated=utcnow(),
            rdns_mode=1,
            allow_dns=True,
            allow_proxy=True,
            active_discovery=True,
            managed=True,
            vlan_id=1,
            disabled_boot_architectures=[],
        )
        sip = StaticIPAddress(
            id=3,
            ip="10.0.0.2",
            alloc_type=IpAddressType.DISCOVERED,
            lease_time=600,
            subnet_id=subnet.id,
            created=utcnow(),
            updated=utcnow(),
        )

        mock_dns_resources_service = Mock(DNSResourcesService)
        mock_nodes_service = Mock(NodesService)
        mock_static_ip_address_service = Mock(StaticIPAddressService)
        mock_subnets_service = Mock(SubnetsService)
        mock_interfaces_service = Mock(InterfacesService)
        mock_ip_ranges_service = Mock(IPRangesService)
        leases_service = LeasesService(
            context=Context(),
            dnsresource_service=mock_dns_resources_service,
            node_service=mock_nodes_service,
            staticipaddress_service=mock_static_ip_address_service,
            subnet_service=mock_subnets_service,
            interface_service=mock_interfaces_service,
            iprange_service=mock_ip_ranges_service,
        )
        mock_static_ip_address_service.create_or_update.return_value = sip
        mock_subnets_service.find_best_subnet_for_ip.return_value = subnet
        # No known interfaces
        mock_interfaces_service.get_interfaces_for_mac.return_value = []

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
            subnet.id, ip
        )
        mock_interfaces_service.get_interfaces_for_mac.assert_called_once_with(
            "00:11:22:33:44:55"
        )
        mock_interfaces_service.create_unkwnown_interface.assert_called_once_with(
            "00:11:22:33:44:55", subnet.vlan_id
        )

    async def test_store_lease_info_commit_v4(
        self, db_connection: AsyncConnection
    ) -> None:
        subnet = Subnet(
            id=1,
            cidr="10.0.0.0/24",
            created=utcnow(),
            updated=utcnow(),
            rdns_mode=1,
            allow_dns=True,
            allow_proxy=True,
            active_discovery=True,
            managed=True,
            vlan_id=1,
            disabled_boot_architectures=[],
        )
        interface = Interface(
            id=2,
            mac_address="00:11:22:33:44:55",
            type=InterfaceType.PHYSICAL,
            name="eth0",
            created=utcnow(),
            updated=utcnow(),
        )
        sip = StaticIPAddress(
            id=3,
            ip="10.0.0.2",
            alloc_type=IpAddressType.DISCOVERED,
            lease_time=600,
            subnet_id=subnet.id,
            created=utcnow(),
            updated=utcnow(),
        )

        mock_dns_resources_service = Mock(DNSResourcesService)
        mock_nodes_service = Mock(NodesService)
        mock_static_ip_address_service = Mock(StaticIPAddressService)
        mock_subnets_service = Mock(SubnetsService)
        mock_interfaces_service = Mock(InterfacesService)
        mock_ip_ranges_service = Mock(IPRangesService)
        leases_service = LeasesService(
            context=Context(),
            dnsresource_service=mock_dns_resources_service,
            node_service=mock_nodes_service,
            staticipaddress_service=mock_static_ip_address_service,
            subnet_service=mock_subnets_service,
            interface_service=mock_interfaces_service,
            iprange_service=mock_ip_ranges_service,
        )
        mock_static_ip_address_service.create_or_update.return_value = sip
        mock_subnets_service.find_best_subnet_for_ip.return_value = subnet
        mock_interfaces_service.get_interfaces_for_mac.return_value = [
            interface
        ]

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
            subnet.id, ip
        )
        mock_interfaces_service.get_interfaces_for_mac.assert_called_once_with(
            "00:11:22:33:44:55"
        )
        mock_static_ip_address_service.get_discovered_ips_in_family_for_interfaces.assert_called_once_with(
            [interface], family=IpAddressFamily.IPV4
        )
        mock_interfaces_service.link_ip.assert_called_once_with(
            [interface], sip
        )

    async def test_store_lease_info_commit_v6(
        self, db_connection: AsyncConnection
    ) -> None:
        subnet = Subnet(
            id=1,
            cidr="fd42:be3f:b08a:3d6c::/64",
            created=utcnow(),
            updated=utcnow(),
            rdns_mode=1,
            allow_dns=True,
            allow_proxy=True,
            active_discovery=True,
            managed=True,
            vlan_id=1,
            disabled_boot_architectures=[],
        )
        interface = Interface(
            id=2,
            mac_address="00:11:22:33:44:55",
            type=InterfaceType.PHYSICAL,
            name="eth0",
            created=utcnow(),
            updated=utcnow(),
        )
        sip = StaticIPAddress(
            id=3,
            ip="fd42:be3f:b08a:3d6c::2",
            alloc_type=IpAddressType.DISCOVERED,
            lease_time=600,
            subnet_id=subnet.id,
            created=utcnow(),
            updated=utcnow(),
        )

        mock_dns_resources_service = Mock(DNSResourcesService)
        mock_nodes_service = Mock(NodesService)
        mock_static_ip_address_service = Mock(StaticIPAddressService)
        mock_subnets_service = Mock(SubnetsService)
        mock_interfaces_service = Mock(InterfacesService)
        mock_ip_ranges_service = Mock(IPRangesService)
        leases_service = LeasesService(
            context=Context(),
            dnsresource_service=mock_dns_resources_service,
            node_service=mock_nodes_service,
            staticipaddress_service=mock_static_ip_address_service,
            subnet_service=mock_subnets_service,
            interface_service=mock_interfaces_service,
            iprange_service=mock_ip_ranges_service,
        )
        mock_static_ip_address_service.create_or_update.return_value = sip
        mock_subnets_service.find_best_subnet_for_ip.return_value = subnet
        mock_interfaces_service.get_interfaces_for_mac.return_value = [
            interface
        ]

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
            subnet.id, ip
        )
        mock_interfaces_service.get_interfaces_for_mac.assert_called_once_with(
            "00:11:22:33:44:55"
        )
        mock_static_ip_address_service.get_discovered_ips_in_family_for_interfaces.assert_called_once_with(
            [interface], family=IpAddressFamily.IPV6
        )
        mock_interfaces_service.link_ip.assert_called_once_with(
            [interface], sip
        )

    async def test_store_lease_info_expiry(
        self, db_connection: AsyncConnection
    ):
        subnet = Subnet(
            id=1,
            cidr="10.0.0.0/24",
            created=utcnow(),
            updated=utcnow(),
            rdns_mode=1,
            allow_dns=True,
            allow_proxy=True,
            active_discovery=True,
            managed=True,
            vlan_id=1,
            disabled_boot_architectures=[],
        )
        interface = Interface(
            id=2,
            mac_address="00:11:22:33:44:55",
            type=InterfaceType.PHYSICAL,
            name="eth0",
            created=utcnow(),
            updated=utcnow(),
        )
        sip = StaticIPAddress(
            id=3,
            ip="10.0.0.2",
            alloc_type=IpAddressType.DISCOVERED,
            lease_time=600,
            subnet_id=subnet.id,
            created=utcnow(),
            updated=utcnow(),
        )

        mock_dns_resources_service = Mock(DNSResourcesService)
        mock_nodes_service = Mock(NodesService)
        mock_static_ip_address_service = Mock(StaticIPAddressService)
        mock_subnets_service = Mock(SubnetsService)
        mock_interfaces_service = Mock(InterfacesService)
        mock_ip_ranges_service = Mock(IPRangesService)
        leases_service = LeasesService(
            context=Context(),
            dnsresource_service=mock_dns_resources_service,
            node_service=mock_nodes_service,
            staticipaddress_service=mock_static_ip_address_service,
            subnet_service=mock_subnets_service,
            interface_service=mock_interfaces_service,
            iprange_service=mock_ip_ranges_service,
        )
        mock_static_ip_address_service.get_discovered_ips_in_family_for_interfaces.return_value = [
            sip
        ]
        mock_static_ip_address_service.get_one.return_value = sip
        mock_subnets_service.find_best_subnet_for_ip.return_value = subnet
        mock_interfaces_service.get_interfaces_for_mac.return_value = [
            interface
        ]
        mock_interfaces_service.link_ip.return_value = None

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
            subnet.id, ip
        )
        mock_interfaces_service.get_interfaces_for_mac.assert_called_once_with(
            "00:11:22:33:44:55"
        )
        mock_static_ip_address_service.get_discovered_ips_in_family_for_interfaces.assert_called_once_with(
            [interface], family=IpAddressFamily.IPV4
        )
        sip.ip = None
        mock_interfaces_service.link_ip.assert_called_once_with(
            [interface], sip
        )

    async def test_store_lease_info_release(
        self, db_connection: AsyncConnection
    ):
        subnet = Subnet(
            id=1,
            cidr="10.0.0.0/24",
            created=utcnow(),
            updated=utcnow(),
            rdns_mode=1,
            allow_dns=True,
            allow_proxy=True,
            active_discovery=True,
            managed=True,
            vlan_id=1,
            disabled_boot_architectures=[],
        )
        interface = Interface(
            id=2,
            mac_address="00:11:22:33:44:55",
            type=InterfaceType.PHYSICAL,
            name="eth0",
            created=utcnow(),
            updated=utcnow(),
        )
        sip = StaticIPAddress(
            id=3,
            ip="10.0.0.2",
            alloc_type=IpAddressType.DISCOVERED,
            lease_time=600,
            subnet_id=subnet.id,
            created=utcnow(),
            updated=utcnow(),
        )

        mock_dns_resources_service = Mock(DNSResourcesService)
        mock_nodes_service = Mock(NodesService)
        mock_static_ip_address_service = Mock(StaticIPAddressService)
        mock_subnets_service = Mock(SubnetsService)
        mock_interfaces_service = Mock(InterfacesService)
        mock_ip_ranges_service = Mock(IPRangesService)
        leases_service = LeasesService(
            context=Context(),
            dnsresource_service=mock_dns_resources_service,
            node_service=mock_nodes_service,
            staticipaddress_service=mock_static_ip_address_service,
            subnet_service=mock_subnets_service,
            interface_service=mock_interfaces_service,
            iprange_service=mock_ip_ranges_service,
        )
        mock_static_ip_address_service.get_discovered_ips_in_family_for_interfaces.return_value = [
            sip
        ]
        mock_static_ip_address_service.get_one.return_value = sip
        mock_subnets_service.find_best_subnet_for_ip.return_value = subnet
        mock_interfaces_service.get_interfaces_for_mac.return_value = [
            interface
        ]
        mock_interfaces_service.link_ip.return_value = None

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
            subnet.id, ip
        )
        mock_interfaces_service.get_interfaces_for_mac.assert_called_once_with(
            "00:11:22:33:44:55"
        )
        mock_static_ip_address_service.get_discovered_ips_in_family_for_interfaces.assert_called_once_with(
            [interface], family=IpAddressFamily.IPV4
        )
        sip.ip = None
        mock_interfaces_service.link_ip.assert_called_once_with(
            [interface], sip
        )
