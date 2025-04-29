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
from maascommon.enums.ipranges import IPRangeType
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.dnsresources import (
    DNSResourceClauseFactory,
)
from maasservicelayer.db.repositories.interfaces import InterfaceClauseFactory
from maasservicelayer.db.repositories.staticipaddress import (
    StaticIPAddressClauseFactory,
)
from maasservicelayer.models.interfaces import Interface
from maasservicelayer.models.leases import Lease
from maasservicelayer.models.staticipaddress import StaticIPAddress
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.dnsresources import DNSResourcesService
from maasservicelayer.services.interfaces import InterfacesService
from maasservicelayer.services.ipranges import IPRangesService
from maasservicelayer.services.leases import LeasesService, LeaseUpdateError
from maasservicelayer.services.nodes import NodesService
from maasservicelayer.services.staticipaddress import StaticIPAddressService
from maasservicelayer.services.subnets import SubnetsService
from maasservicelayer.utils.date import utcnow
from tests.fixtures.factories.interface import (
    create_test_interface_dict,
    create_test_interface_ip_addresses_entry,
)
from tests.fixtures.factories.iprange import create_test_ip_range_entry
from tests.fixtures.factories.node import create_test_machine_entry
from tests.fixtures.factories.staticipaddress import (
    create_test_staticipaddress_entry,
)
from tests.fixtures.factories.subnet import create_test_subnet_entry
from tests.maasapiserver.fixtures.db import Fixture


@pytest.mark.asyncio
class TestIntegrationLeasesService:
    """Integration tests for leases service"""

    async def test_create_ignores_none_hostname(
        self, fixture: Fixture, services: ServiceCollectionV3
    ):
        subnet = await create_test_subnet_entry(fixture, cidr="10.0.0.0/24")
        await create_test_ip_range_entry(
            fixture,
            subnet,
            type=IPRangeType.DYNAMIC,
            start_ip="10.0.0.100",
            end_ip="10.0.0.200",
        )
        ip = "10.0.0.150"
        mac_address = "00:11:22:33:44:55"
        await services.leases.store_lease_info(
            Lease(
                action=LeaseAction.COMMIT,
                ip_family=IpAddressFamily.IPV4,
                hostname="(none)",
                mac=mac_address,
                ip=IPv4Address(ip),
                timestamp_epoch=0,
                lease_time_seconds=30,
            )
        )

        unknown_interface = await services.interfaces.get_one(
            query=QuerySpec(
                where=InterfaceClauseFactory.with_mac_address(mac_address)
            )
        )
        assert unknown_interface.type == InterfaceType.UNKNOWN

        ip_address = await services.staticipaddress.get_one(
            query=QuerySpec(
                where=StaticIPAddressClauseFactory.with_ip(IPv4Address(ip))
            )
        )
        assert ip_address.alloc_type == IpAddressType.DISCOVERED
        assert ip_address.ip == IPv4Address(ip)
        assert ip_address.subnet_id == subnet["id"]
        assert ip_address.lease_time == 30

        linked_ip_address = await fixture.get(
            "maasserver_interface_ip_addresses"
        )
        assert len(linked_ip_address) == 1
        assert linked_ip_address[0]["interface_id"] == unknown_interface.id
        assert linked_ip_address[0]["staticipaddress_id"] == ip_address.id

        dnsresource_exists = await services.dnsresources.exists(
            query=QuerySpec()
        )
        assert dnsresource_exists is False

    async def test_creates_dns_record_for_hostname(
        self, fixture: Fixture, services: ServiceCollectionV3
    ):
        subnet = await create_test_subnet_entry(fixture, cidr="10.0.0.0/24")
        await create_test_ip_range_entry(
            fixture,
            subnet,
            type=IPRangeType.DYNAMIC,
            start_ip="10.0.0.100",
            end_ip="10.0.0.200",
        )
        ip = "10.0.0.150"
        hostname = "ubuntu"
        mac_address = "00:11:22:33:44:55"
        await services.leases.store_lease_info(
            Lease(
                action=LeaseAction.COMMIT,
                ip_family=IpAddressFamily.IPV4,
                hostname=hostname,
                mac=mac_address,
                ip=IPv4Address(ip),
                timestamp_epoch=0,
                lease_time_seconds=30,
            )
        )
        unknown_interface = await services.interfaces.get_one(
            query=QuerySpec(
                where=InterfaceClauseFactory.with_mac_address(mac_address)
            )
        )
        assert unknown_interface is not None
        assert unknown_interface.type == InterfaceType.UNKNOWN
        ip_address = await services.staticipaddress.get_one(
            query=QuerySpec(
                where=StaticIPAddressClauseFactory.with_ip(IPv4Address(ip))
            )
        )
        assert ip_address is not None

        dnsresource = await services.dnsresources.get_one(
            query=QuerySpec(where=DNSResourceClauseFactory.with_name(hostname))
        )
        assert dnsresource is not None

        dnsresource_ip_link = await fixture.get(
            "maasserver_dnsresource_ip_addresses"
        )
        assert len(dnsresource_ip_link) == 1
        assert dnsresource_ip_link[0]["dnsresource_id"] == dnsresource.id
        assert dnsresource_ip_link[0]["staticipaddress_id"] == ip_address.id

    async def test_mutiple_calls_reuse_existing_staticipaddress_records(
        self, fixture: Fixture, services: ServiceCollectionV3
    ):
        subnet = await create_test_subnet_entry(fixture, cidr="10.0.0.0/24")
        await create_test_ip_range_entry(
            fixture,
            subnet,
            type=IPRangeType.DYNAMIC,
            start_ip="10.0.0.100",
            end_ip="10.0.0.200",
        )
        ip = "10.0.0.150"
        hostname = "ubuntu"
        mac_address = "00:11:22:33:44:55"
        await services.leases.store_lease_info(
            Lease(
                action=LeaseAction.COMMIT,
                ip_family=IpAddressFamily.IPV4,
                hostname=hostname,
                mac=mac_address,
                ip=IPv4Address(ip),
                timestamp_epoch=0,
                lease_time_seconds=30,
            )
        )
        sip1 = await services.staticipaddress.get_one(
            query=QuerySpec(
                where=StaticIPAddressClauseFactory.with_ip(IPv4Address(ip))
            )
        )

        await services.leases.store_lease_info(
            Lease(
                action=LeaseAction.COMMIT,
                ip_family=IpAddressFamily.IPV4,
                hostname=hostname,
                mac=mac_address,
                ip=IPv4Address(ip),
                timestamp_epoch=0,
                lease_time_seconds=30,
            )
        )

        sip2 = await services.staticipaddress.get_one(
            query=QuerySpec(
                where=StaticIPAddressClauseFactory.with_ip(IPv4Address(ip))
            )
        )
        assert sip1.ip == sip2.ip

    async def test_skips_dns_record_for_hostname_from_existing_node(
        self, fixture: Fixture, services: ServiceCollectionV3
    ):
        subnet = await create_test_subnet_entry(fixture, cidr="10.0.0.0/24")
        await create_test_ip_range_entry(
            fixture,
            subnet,
            type=IPRangeType.DYNAMIC,
            start_ip="10.0.0.100",
            end_ip="10.0.0.200",
        )
        hostname = "ubuntu"
        await create_test_machine_entry(fixture, hostname=hostname)
        ip = "10.0.0.150"
        mac_address = "00:11:22:33:44:55"
        await services.leases.store_lease_info(
            Lease(
                action=LeaseAction.COMMIT,
                ip_family=IpAddressFamily.IPV4,
                hostname=hostname,
                mac=mac_address,
                ip=IPv4Address(ip),
                timestamp_epoch=0,
                lease_time_seconds=30,
            )
        )
        sip = await services.staticipaddress.get_one(
            query=QuerySpec(
                where=StaticIPAddressClauseFactory.with_ip(IPv4Address(ip))
            )
        )
        assert sip is not None
        dnsresource_exists = await services.dnsresources.exists(
            query=QuerySpec()
        )
        assert dnsresource_exists is False

    async def test_skips_dns_record_for_coerced_hostname_from_existing_node(
        self, fixture: Fixture, services: ServiceCollectionV3
    ):
        subnet = await create_test_subnet_entry(fixture, cidr="10.0.0.0/24")
        await create_test_ip_range_entry(
            fixture,
            subnet,
            type=IPRangeType.DYNAMIC,
            start_ip="10.0.0.100",
            end_ip="10.0.0.200",
        )
        hostname = "gaming device"
        await create_test_machine_entry(fixture, hostname="gaming-device")
        ip = "10.0.0.150"
        mac_address = "00:11:22:33:44:55"
        await services.leases.store_lease_info(
            Lease(
                action=LeaseAction.COMMIT,
                ip_family=IpAddressFamily.IPV4,
                hostname=hostname,
                mac=mac_address,
                ip=IPv4Address(ip),
                timestamp_epoch=0,
                lease_time_seconds=30,
            )
        )
        sip = await services.staticipaddress.get_one(
            query=QuerySpec(
                where=StaticIPAddressClauseFactory.with_ip(IPv4Address(ip))
            )
        )
        assert sip is not None
        dnsresource_exists = await services.dnsresources.exists(
            query=QuerySpec()
        )
        assert dnsresource_exists is False

    async def test_creates_lease_for_physical_interface(
        self, fixture: Fixture, services: ServiceCollectionV3
    ):
        subnet = await create_test_subnet_entry(fixture, cidr="10.0.0.0/24")
        await create_test_ip_range_entry(
            fixture,
            subnet,
            type=IPRangeType.DYNAMIC,
            start_ip="10.0.0.100",
            end_ip="10.0.0.200",
        )
        hostname = "ubuntu"
        mac_address = "00:11:22:33:44:55"
        machine = await create_test_machine_entry(
            fixture, hostname="gaming-device"
        )
        boot_iface = await create_test_interface_dict(
            fixture, node=machine, mac_address=mac_address, boot_iface=True
        )
        ip = "10.0.0.150"
        await services.leases.store_lease_info(
            Lease(
                action=LeaseAction.COMMIT,
                ip_family=IpAddressFamily.IPV4,
                hostname=hostname,
                mac=mac_address,
                ip=IPv4Address(ip),
                timestamp_epoch=0,
                lease_time_seconds=30,
            )
        )
        sip = await services.staticipaddress.get_one(
            query=QuerySpec(
                where=StaticIPAddressClauseFactory.and_clauses(
                    [
                        StaticIPAddressClauseFactory.with_ip(IPv4Address(ip)),
                        StaticIPAddressClauseFactory.with_alloc_type(
                            IpAddressType.DISCOVERED
                        ),
                    ]
                )
            )
        )
        assert sip is not None
        assert sip.subnet_id == subnet["id"]
        assert sip.lease_time == 30
        linked_ip_address = await fixture.get(
            "maasserver_interface_ip_addresses"
        )
        assert len(linked_ip_address) == 1
        assert linked_ip_address[0]["interface_id"] == boot_iface["id"]
        assert linked_ip_address[0]["staticipaddress_id"] == sip.id

        iface = await services.interfaces.get_one(
            query=QuerySpec(InterfaceClauseFactory.with_id(boot_iface["id"]))
        )
        discovered_ips = await services.staticipaddress.get_discovered_ips_in_family_for_interfaces(
            interfaces=[iface], family=IpAddressFamily.IPV4
        )
        assert len(discovered_ips) == 1, (
            "Interface should only have one DISCOVERED IP address."
        )

    async def test_creates_lease_for_physical_interface_keeps_other_ip_family(
        self, fixture: Fixture, services: ServiceCollectionV3
    ):
        subnet = await create_test_subnet_entry(fixture, cidr="10.0.0.0/24")
        await create_test_ip_range_entry(
            fixture,
            subnet,
            type=IPRangeType.DYNAMIC,
            start_ip="10.0.0.100",
            end_ip="10.0.0.200",
        )
        hostname = "ubuntu"
        mac_address = "00:11:22:33:44:55"
        machine = await create_test_machine_entry(
            fixture, hostname="gaming-device"
        )
        boot_iface = await create_test_interface_dict(
            fixture, node=machine, mac_address=mac_address, boot_iface=True
        )

        subnet = await create_test_subnet_entry(
            fixture, cidr="fc8a:81e6:f287:fc70::/61"
        )
        sip = await create_test_staticipaddress_entry(fixture, subnet=subnet)
        await create_test_interface_ip_addresses_entry(
            fixture, interface_id=boot_iface["id"], ip_id=sip[0]["id"]
        )
        ip = "10.0.0.150"

        await services.leases.store_lease_info(
            Lease(
                action=LeaseAction.COMMIT,
                ip_family=IpAddressFamily.IPV4,
                hostname=hostname,
                mac=mac_address,
                ip=IPv4Address(ip),
                timestamp_epoch=0,
                lease_time_seconds=30,
            )
        )
        sips = await services.staticipaddress.get_many(
            query=QuerySpec(
                where=StaticIPAddressClauseFactory.with_interface_ids(
                    [boot_iface["id"]]
                )
            )
        )
        assert len(sips) == 2

    async def test_creates_lease_for_bond_interface(
        self, fixture: Fixture, services: ServiceCollectionV3
    ):
        pass

    async def test_release_removes_lease_keeps_discovered_subnet(
        self, fixture: Fixture, services: ServiceCollectionV3
    ):
        subnet = await create_test_subnet_entry(fixture, cidr="10.0.0.0/24")
        await create_test_ip_range_entry(
            fixture,
            subnet,
            type=IPRangeType.DYNAMIC,
            start_ip="10.0.0.100",
            end_ip="10.0.0.200",
        )
        hostname = "ubuntu"
        mac_address = "00:11:22:33:44:55"
        machine = await create_test_machine_entry(
            fixture, hostname="gaming-device"
        )
        boot_iface = await create_test_interface_dict(
            fixture, node=machine, mac_address=mac_address, boot_iface=True
        )

        ip = "10.0.0.150"

        await services.leases.store_lease_info(
            Lease(
                action=LeaseAction.RELEASE,
                ip_family=IpAddressFamily.IPV4,
                hostname=hostname,
                mac=mac_address,
                ip=IPv4Address(ip),
                timestamp_epoch=0,
                lease_time_seconds=30,
            )
        )
        sips = await services.staticipaddress.get_many(
            query=QuerySpec(
                where=StaticIPAddressClauseFactory.and_clauses(
                    [
                        StaticIPAddressClauseFactory.with_interface_ids(
                            [boot_iface["id"]]
                        ),
                        StaticIPAddressClauseFactory.with_alloc_type(
                            IpAddressType.DISCOVERED
                        ),
                        StaticIPAddressClauseFactory.with_ip(None),
                        StaticIPAddressClauseFactory.with_subnet_id(
                            subnet["id"]
                        ),
                    ]
                )
            )
        )
        assert len(sips) == 1
        linked_ip_address = await fixture.get(
            "maasserver_interface_ip_addresses"
        )
        assert len(linked_ip_address) == 1
        assert linked_ip_address[0]["interface_id"] == boot_iface["id"]
        assert linked_ip_address[0]["staticipaddress_id"] == sips[0].id


@pytest.mark.asyncio
class TestLeasesService:
    def setup(self):
        self.mock_dns_resources_service = Mock(DNSResourcesService)
        self.mock_nodes_service = Mock(NodesService)
        self.mock_static_ip_address_service = Mock(StaticIPAddressService)
        self.mock_subnets_service = Mock(SubnetsService)
        self.mock_interfaces_service = Mock(InterfacesService)
        self.mock_ip_ranges_service = Mock(IPRangesService)
        self.leases_service = LeasesService(
            context=Context(),
            dnsresource_service=self.mock_dns_resources_service,
            node_service=self.mock_nodes_service,
            staticipaddress_service=self.mock_static_ip_address_service,
            subnet_service=self.mock_subnets_service,
            interface_service=self.mock_interfaces_service,
            iprange_service=self.mock_ip_ranges_service,
        )

    async def test_store_lease_info_no_subnet(self):
        self.setup()
        self.mock_subnets_service.find_best_subnet_for_ip.return_value = None
        with pytest.raises(LeaseUpdateError):
            await self.leases_service.store_lease_info(
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

    async def test_raises_for_ipv4_mismatch(self):
        self.setup()
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
        self.mock_subnets_service.find_best_subnet_for_ip.return_value = subnet
        with pytest.raises(LeaseUpdateError):
            await self.leases_service.store_lease_info(
                Lease(
                    action=LeaseAction.COMMIT,
                    ip_family=IpAddressFamily.IPV6,
                    hostname="hostname",
                    mac="00:11:22:33:44:55",
                    ip=IPv4Address("10.0.0.2"),
                    timestamp_epoch=int(time.time()),
                    lease_time_seconds=30,
                )
            )

    async def test_does_nothing_if_expiry_for_unknown_mac(self):
        self.setup()
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
        self.mock_subnets_service.find_best_subnet_for_ip.return_value = subnet
        self.mock_interfaces_service.get_interfaces_for_mac.return_value = []
        await self.leases_service.store_lease_info(
            Lease(
                action=LeaseAction.EXPIRY,
                ip_family=IpAddressFamily.IPV4,
                hostname="hostname",
                mac="00:11:22:33:44:55",
                ip=IPv4Address("10.0.0.2"),
                timestamp_epoch=int(time.time()),
                lease_time_seconds=30,
            )
        )
        self.mock_static_ip_address_service.delete_by_id.assert_not_called()

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

        self.setup()
        self.mock_static_ip_address_service.create_or_update.return_value = sip
        self.mock_subnets_service.find_best_subnet_for_ip.return_value = subnet
        # No known interfaces
        self.mock_interfaces_service.get_interfaces_for_mac.return_value = []

        ip = IPv4Address("10.0.0.2")
        await self.leases_service.store_lease_info(
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

        self.mock_subnets_service.find_best_subnet_for_ip.assert_called_once_with(
            ip
        )
        self.mock_ip_ranges_service.get_dynamic_range_for_ip.assert_called_once_with(
            subnet.id, ip
        )
        self.mock_interfaces_service.get_interfaces_for_mac.assert_called_once_with(
            "00:11:22:33:44:55"
        )
        self.mock_interfaces_service.create_unkwnown_interface.assert_called_once_with(
            mac="00:11:22:33:44:55", vlan_id=subnet.vlan_id
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
            node_config_id=1,
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

        self.mock_static_ip_address_service.create_or_update.return_value = sip
        self.mock_subnets_service.find_best_subnet_for_ip.return_value = subnet
        self.mock_interfaces_service.get_interfaces_for_mac.return_value = [
            interface
        ]

        ip = IPv4Address("10.0.0.2")
        await self.leases_service.store_lease_info(
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

        self.mock_subnets_service.find_best_subnet_for_ip.assert_called_once_with(
            ip
        )
        self.mock_ip_ranges_service.get_dynamic_range_for_ip.assert_called_once_with(
            subnet.id, ip
        )
        self.mock_interfaces_service.get_interfaces_for_mac.assert_called_once_with(
            "00:11:22:33:44:55"
        )
        self.mock_static_ip_address_service.get_discovered_ips_in_family_for_interfaces.assert_called_once_with(
            [interface], family=IpAddressFamily.IPV4
        )
        self.mock_interfaces_service.link_ip.assert_called_once_with(
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
            node_config_id=1,
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

        self.mock_static_ip_address_service.create_or_update.return_value = sip
        self.mock_subnets_service.find_best_subnet_for_ip.return_value = subnet
        self.mock_interfaces_service.get_interfaces_for_mac.return_value = [
            interface
        ]

        ip = IPv6Address("fd42:be3f:b08a:3d6c::2")
        await self.leases_service.store_lease_info(
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

        self.mock_subnets_service.find_best_subnet_for_ip.assert_called_once_with(
            ip
        )
        self.mock_ip_ranges_service.get_dynamic_range_for_ip.assert_called_once_with(
            subnet.id, ip
        )
        self.mock_interfaces_service.get_interfaces_for_mac.assert_called_once_with(
            "00:11:22:33:44:55"
        )
        self.mock_static_ip_address_service.get_discovered_ips_in_family_for_interfaces.assert_called_once_with(
            [interface], family=IpAddressFamily.IPV6
        )
        self.mock_interfaces_service.link_ip.assert_called_once_with(
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

        self.mock_static_ip_address_service.get_discovered_ips_in_family_for_interfaces.return_value = [
            sip
        ]
        self.mock_static_ip_address_service.get_many.return_value = [sip]
        self.mock_subnets_service.find_best_subnet_for_ip.return_value = subnet
        self.mock_interfaces_service.get_interfaces_for_mac.return_value = [
            interface
        ]
        self.mock_interfaces_service.link_ip.return_value = None

        ip = IPv4Address("10.0.0.2")
        await self.leases_service.store_lease_info(
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

        self.mock_subnets_service.find_best_subnet_for_ip.assert_called_once_with(
            ip
        )
        self.mock_ip_ranges_service.get_dynamic_range_for_ip.assert_called_once_with(
            subnet.id, ip
        )
        self.mock_interfaces_service.get_interfaces_for_mac.assert_called_once_with(
            "00:11:22:33:44:55"
        )
        self.mock_static_ip_address_service.get_discovered_ips_in_family_for_interfaces.assert_called_once_with(
            [interface], family=IpAddressFamily.IPV4
        )
        sip.ip = None
        self.mock_interfaces_service.link_ip.assert_called_once_with(
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

        self.mock_static_ip_address_service.get_discovered_ips_in_family_for_interfaces.return_value = [
            sip
        ]
        self.mock_static_ip_address_service.get_many.return_value = [sip]
        self.mock_subnets_service.find_best_subnet_for_ip.return_value = subnet
        self.mock_interfaces_service.get_interfaces_for_mac.return_value = [
            interface
        ]
        self.mock_interfaces_service.link_ip.return_value = None

        ip = IPv4Address("10.0.0.2")
        await self.leases_service.store_lease_info(
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

        self.mock_subnets_service.find_best_subnet_for_ip.assert_called_once_with(
            ip
        )
        self.mock_ip_ranges_service.get_dynamic_range_for_ip.assert_called_once_with(
            subnet.id, ip
        )
        self.mock_interfaces_service.get_interfaces_for_mac.assert_called_once_with(
            "00:11:22:33:44:55"
        )
        self.mock_static_ip_address_service.get_discovered_ips_in_family_for_interfaces.assert_called_once_with(
            [interface], family=IpAddressFamily.IPV4
        )
        sip.ip = None
        self.mock_interfaces_service.link_ip.assert_called_once_with(
            [interface], sip
        )
