# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime
import time
from unittest.mock import Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.interface import InterfaceType
from maascommon.enums.ipaddress import IpAddressFamily, IpAddressType
from maasservicelayer.db.repositories.dnsresources import DNSResourceRepository
from maasservicelayer.db.repositories.domains import DomainsRepository
from maasservicelayer.db.repositories.interfaces import InterfaceRepository
from maasservicelayer.db.repositories.ipranges import IPRangesRepository
from maasservicelayer.db.repositories.nodes import NodesRepository
from maasservicelayer.db.repositories.staticipaddress import (
    StaticIPAddressRepository,
)
from maasservicelayer.db.repositories.subnets import SubnetsRepository
from maasservicelayer.models.interfaces import Interface
from maasservicelayer.models.staticipaddress import StaticIPAddress
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.services.configurations import ConfigurationsService
from maasservicelayer.services.dnsresources import DNSResourcesService
from maasservicelayer.services.domains import DomainsService
from maasservicelayer.services.interfaces import InterfacesService
from maasservicelayer.services.ipranges import IPRangesService
from maasservicelayer.services.leases import LeasesService, LeaseUpdateError
from maasservicelayer.services.nodes import NodesService
from maasservicelayer.services.secrets import SecretsServiceFactory
from maasservicelayer.services.staticipaddress import StaticIPAddressService
from maasservicelayer.services.subnets import SubnetsService


@pytest.mark.asyncio
class TestLeasesService:
    async def create_service(
        self,
        connection: AsyncConnection,
        dnsresource_repo: DNSResourceRepository | None = None,
        domains_repo: DomainsRepository | None = None,
        nodes_repo: NodesRepository | None = None,
        staticipaddress_repo: StaticIPAddressRepository | None = None,
        subnets_repo: SubnetsRepository | None = None,
        interfaces_repo: InterfaceRepository | None = None,
        ipranges_repo: IPRangesRepository | None = None,
    ) -> LeasesService:
        configurations = ConfigurationsService(connection)
        secrets = await SecretsServiceFactory.produce(
            connection=connection, config_service=configurations
        )
        return LeasesService(
            connection,
            DNSResourcesService(
                connection,
                DomainsService(
                    connection,
                    domains_repo,
                ),
                dnsresource_repo,
            ),
            NodesService(connection, secrets, nodes_repo),
            StaticIPAddressService(connection, staticipaddress_repo),
            SubnetsService(connection, subnets_repo),
            InterfacesService(connection, interfaces_repo),
            IPRangesService(connection, ipranges_repo),
        )

    async def test_store_lease_info_invalid_action(
        self, db_connection: AsyncConnection
    ):
        mock_dnsresource_repo = Mock(DNSResourceRepository)
        mock_domains_repo = Mock(DomainsRepository)
        mock_nodes_repo = Mock(NodesRepository)
        mock_staticipaddress_repo = Mock(StaticIPAddressRepository)
        mock_subnets_repo = Mock(SubnetsRepository)
        mock_interfaces_repo = Mock(InterfaceRepository)
        mock_ipranges_repo = Mock(IPRangesRepository)
        service = await self.create_service(
            db_connection,
            dnsresource_repo=mock_dnsresource_repo,
            domains_repo=mock_domains_repo,
            nodes_repo=mock_nodes_repo,
            staticipaddress_repo=mock_staticipaddress_repo,
            subnets_repo=mock_subnets_repo,
            interfaces_repo=mock_interfaces_repo,
            ipranges_repo=mock_ipranges_repo,
        )

        try:
            await service.store_lease_info(
                "notvalid",
                "ipv4",
                "10.0.0.2",
                "00:11:22:33:44:55",
                "hostname",
                int(time.time()),
                30,
            )
        except Exception as e:
            assert isinstance(e, LeaseUpdateError)

    async def test_store_lease_info_no_subnet(
        self, db_connection: AsyncConnection
    ):
        mock_dnsresource_repo = Mock(DNSResourceRepository)
        mock_domains_repo = Mock(DomainsRepository)
        mock_nodes_repo = Mock(NodesRepository)
        mock_staticipaddress_repo = Mock(StaticIPAddressRepository)
        mock_subnets_repo = Mock(SubnetsRepository)
        mock_subnets_repo.find_best_subnet_for_ip.return_value = None

        mock_interfaces_repo = Mock(InterfaceRepository)
        mock_ipranges_repo = Mock(IPRangesRepository)
        service = await self.create_service(
            db_connection,
            dnsresource_repo=mock_dnsresource_repo,
            domains_repo=mock_domains_repo,
            nodes_repo=mock_nodes_repo,
            staticipaddress_repo=mock_staticipaddress_repo,
            subnets_repo=mock_subnets_repo,
            interfaces_repo=mock_interfaces_repo,
            ipranges_repo=mock_ipranges_repo,
        )

        try:
            await service.store_lease_info(
                "commit",
                "ipv4",
                "10.0.0.2",
                "00:11:22:33:44:55",
                "hostname",
                int(time.time()),
                30,
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

        mock_dnsresource_repo = Mock(DNSResourceRepository)
        mock_domains_repo = Mock(DomainsRepository)
        mock_nodes_repo = Mock(NodesRepository)

        mock_staticipaddress_repo = Mock(StaticIPAddressRepository)
        mock_staticipaddress_repo.create.return_value = sip

        mock_subnets_repo = Mock(SubnetsRepository)
        mock_subnets_repo.find_best_subnet_for_ip.return_value = subnet

        mock_interfaces_repo = Mock(InterfaceRepository)
        mock_interfaces_repo.get_interfaces_for_mac.return_value = [interface]

        mock_ipranges_repo = Mock(IPRangesRepository)

        service = await self.create_service(
            db_connection,
            dnsresource_repo=mock_dnsresource_repo,
            domains_repo=mock_domains_repo,
            nodes_repo=mock_nodes_repo,
            staticipaddress_repo=mock_staticipaddress_repo,
            subnets_repo=mock_subnets_repo,
            interfaces_repo=mock_interfaces_repo,
            ipranges_repo=mock_ipranges_repo,
        )
        await service.store_lease_info(
            "commit",
            "ipv4",
            "10.0.0.2",
            interface.mac_address,
            "hostname",
            int(time.time()),
            30,
        )

        mock_subnets_repo.find_best_subnet_for_ip.assert_called_once_with(
            "10.0.0.2"
        )
        mock_ipranges_repo.get_dynamic_range_for_ip.assert_called_once_with(
            subnet, "10.0.0.2"
        )
        mock_interfaces_repo.get_interfaces_for_mac.assert_called_once_with(
            "00:11:22:33:44:55"
        )
        mock_staticipaddress_repo.get_discovered_ips_in_family_for_interfaces(
            [interface], IpAddressFamily.IPV4
        )
        mock_interfaces_repo.add_ip.assert_called_once_with(interface, sip)

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

        mock_dnsresource_repo = Mock(DNSResourceRepository)
        mock_domains_repo = Mock(DomainsRepository)
        mock_nodes_repo = Mock(NodesRepository)

        mock_staticipaddress_repo = Mock(StaticIPAddressRepository)
        mock_staticipaddress_repo.create.return_value = sip

        mock_subnets_repo = Mock(SubnetsRepository)
        mock_subnets_repo.find_best_subnet_for_ip.return_value = subnet

        mock_interfaces_repo = Mock(InterfaceRepository)
        mock_interfaces_repo.get_interfaces_for_mac.return_value = [interface]

        mock_ipranges_repo = Mock(IPRangesRepository)

        service = await self.create_service(
            db_connection,
            dnsresource_repo=mock_dnsresource_repo,
            domains_repo=mock_domains_repo,
            nodes_repo=mock_nodes_repo,
            staticipaddress_repo=mock_staticipaddress_repo,
            subnets_repo=mock_subnets_repo,
            interfaces_repo=mock_interfaces_repo,
            ipranges_repo=mock_ipranges_repo,
        )
        await service.store_lease_info(
            "commit",
            "ipv6",
            "fd42:be3f:b08a:3d6c::2",
            interface.mac_address,
            "hostname",
            int(time.time()),
            30,
        )

        mock_subnets_repo.find_best_subnet_for_ip.assert_called_once_with(
            "fd42:be3f:b08a:3d6c::2"
        )
        mock_ipranges_repo.get_dynamic_range_for_ip.assert_called_once_with(
            subnet, "fd42:be3f:b08a:3d6c::2"
        )
        mock_interfaces_repo.get_interfaces_for_mac.assert_called_once_with(
            "00:11:22:33:44:55"
        )
        mock_staticipaddress_repo.get_discovered_ips_in_family_for_interfaces(
            [interface], IpAddressFamily.IPV6
        )
        mock_interfaces_repo.add_ip.assert_called_once_with(interface, sip)

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

        mock_dnsresource_repo = Mock(DNSResourceRepository)
        mock_domains_repo = Mock(DomainsRepository)
        mock_nodes_repo = Mock(NodesRepository)

        mock_staticipaddress_repo = Mock(StaticIPAddressRepository)
        mock_staticipaddress_repo.get_discovered_ips_in_family_for_interfaces.return_value = [
            sip
        ]
        mock_staticipaddress_repo.get_for_interfaces.return_value = sip

        mock_subnets_repo = Mock(SubnetsRepository)
        mock_subnets_repo.find_best_subnet_for_ip.return_value = subnet

        mock_interfaces_repo = Mock(InterfaceRepository)
        mock_interfaces_repo.get_interfaces_for_mac.return_value = [interface]

        mock_ipranges_repo = Mock(IPRangesRepository)

        service = await self.create_service(
            db_connection,
            dnsresource_repo=mock_dnsresource_repo,
            domains_repo=mock_domains_repo,
            nodes_repo=mock_nodes_repo,
            staticipaddress_repo=mock_staticipaddress_repo,
            subnets_repo=mock_subnets_repo,
            interfaces_repo=mock_interfaces_repo,
            ipranges_repo=mock_ipranges_repo,
        )
        await service.store_lease_info(
            "expiry",
            "ipv4",
            "10.0.0.2",
            interface.mac_address,
            "hostname",
            int(time.time()),
            30,
        )

        mock_subnets_repo.find_best_subnet_for_ip.assert_called_once_with(
            "10.0.0.2"
        )
        mock_ipranges_repo.get_dynamic_range_for_ip.assert_called_once_with(
            subnet, "10.0.0.2"
        )
        mock_interfaces_repo.get_interfaces_for_mac.assert_called_once_with(
            "00:11:22:33:44:55"
        )
        mock_staticipaddress_repo.get_discovered_ips_in_family_for_interfaces(
            [interface], family=IpAddressFamily.IPV4
        )
        sip.ip = None
        mock_interfaces_repo.add_ip.assert_called_once_with(interface, sip)

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

        mock_dnsresource_repo = Mock(DNSResourceRepository)
        mock_domains_repo = Mock(DomainsRepository)
        mock_nodes_repo = Mock(NodesRepository)

        mock_staticipaddress_repo = Mock(StaticIPAddressRepository)
        mock_staticipaddress_repo.get_discovered_ips_in_family_for_interfaces.return_value = [
            sip
        ]
        mock_staticipaddress_repo.get_for_interfaces.return_value = sip

        mock_subnets_repo = Mock(SubnetsRepository)
        mock_subnets_repo.find_best_subnet_for_ip.return_value = subnet

        mock_interfaces_repo = Mock(InterfaceRepository)
        mock_interfaces_repo.get_interfaces_for_mac.return_value = [interface]

        mock_ipranges_repo = Mock(IPRangesRepository)

        service = await self.create_service(
            db_connection,
            dnsresource_repo=mock_dnsresource_repo,
            domains_repo=mock_domains_repo,
            nodes_repo=mock_nodes_repo,
            staticipaddress_repo=mock_staticipaddress_repo,
            subnets_repo=mock_subnets_repo,
            interfaces_repo=mock_interfaces_repo,
            ipranges_repo=mock_ipranges_repo,
        )
        await service.store_lease_info(
            "release",
            "ipv4",
            "10.0.0.2",
            interface.mac_address,
            "hostname",
            int(time.time()),
            30,
        )

        mock_subnets_repo.find_best_subnet_for_ip.assert_called_once_with(
            "10.0.0.2"
        )
        mock_ipranges_repo.get_dynamic_range_for_ip.assert_called_once_with(
            subnet, "10.0.0.2"
        )
        mock_interfaces_repo.get_interfaces_for_mac.assert_called_once_with(
            "00:11:22:33:44:55"
        )
        mock_staticipaddress_repo.get_discovered_ips_in_family_for_interfaces(
            [interface], family=IpAddressFamily.IPV4
        )
        sip.ip = None
        mock_interfaces_repo.add_ip.assert_called_once_with(interface, sip)
