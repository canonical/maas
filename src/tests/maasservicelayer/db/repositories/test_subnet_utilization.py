# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.ipaddress import IpAddressType
from maascommon.enums.ipranges import IPRangeType
from maascommon.enums.subnet import RdnsMode
from maascommon.utils.network import IPRANGE_PURPOSE, MAASIPRange, MAASIPSet
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.subnet_utilization import (
    SubnetUtilizationQueryBuilder,
    SubnetUtilizationRepository,
)
from maasservicelayer.models.subnets import Subnet
from tests.fixtures.factories.interface import create_test_interface_entry
from tests.fixtures.factories.iprange import create_test_ip_range_entry
from tests.fixtures.factories.neighbours import create_test_neighbour_entry
from tests.fixtures.factories.node import create_test_rack_controller_entry
from tests.fixtures.factories.staticipaddress import (
    create_test_staticipaddress_entry,
)
from tests.fixtures.factories.staticroutes import create_test_staticroute_entry
from tests.fixtures.factories.subnet import create_test_subnet_entry
from tests.fixtures.factories.vlan import create_test_vlan_entry
from tests.maasapiserver.fixtures.db import Fixture

TEST_SUBNET = Subnet(
    id=1,
    name="test-subnet",
    cidr="10.0.0.0/24",
    description="test description",
    rdns_mode=RdnsMode.DEFAULT,
    gateway_ip="10.0.0.1",
    dns_servers=["10.0.0.100", "8.8.8.8"],
    allow_dns=False,
    allow_proxy=False,
    active_discovery=False,
    managed=True,
    disabled_boot_architectures=[],
    vlan_id=1,
)


class TestSubnetUtilizationQueryBuilder:
    def test_with_reserved_ipranges(self) -> None:
        qb = SubnetUtilizationQueryBuilder(
            TEST_SUBNET
        ).with_reserved_ipranges()
        assert len(qb.statements) == 1
        stmt = qb.statements.pop()
        assert str(stmt.compile(compile_kwargs={"literal_binds": True})) == (
            "SELECT maasserver_iprange.start_ip, maasserver_iprange.end_ip, maasserver_iprange.type AS purpose \n"
            "FROM maasserver_iprange \n"
            "WHERE maasserver_iprange.subnet_id = 1 AND maasserver_iprange.type = 'reserved'"
        )

    def test_with_reserved_ipranges_exclude_ip_range(self) -> None:
        qb = SubnetUtilizationQueryBuilder(TEST_SUBNET).with_reserved_ipranges(
            exclude_ip_range_id=100
        )
        assert len(qb.statements) == 1
        stmt = qb.statements.pop()
        assert str(stmt.compile(compile_kwargs={"literal_binds": True})) == (
            "SELECT maasserver_iprange.start_ip, maasserver_iprange.end_ip, maasserver_iprange.type AS purpose \n"
            "FROM maasserver_iprange \n"
            "WHERE maasserver_iprange.subnet_id = 1 AND maasserver_iprange.type = 'reserved' AND maasserver_iprange.id != 100"
        )

    def test_with_dynamic_ipranges(self) -> None:
        qb = SubnetUtilizationQueryBuilder(TEST_SUBNET).with_dynamic_ipranges()
        assert len(qb.statements) == 1
        stmt = qb.statements.pop()
        assert str(stmt.compile(compile_kwargs={"literal_binds": True})) == (
            "SELECT maasserver_iprange.start_ip, maasserver_iprange.end_ip, maasserver_iprange.type AS purpose \n"
            "FROM maasserver_iprange \n"
            "WHERE maasserver_iprange.subnet_id = 1 AND maasserver_iprange.type = 'dynamic'"
        )

    def test_with_dynamic_ipranges_exclude_ip_range(self) -> None:
        qb = SubnetUtilizationQueryBuilder(TEST_SUBNET).with_dynamic_ipranges(
            exclude_ip_range_id=100
        )
        assert len(qb.statements) == 1
        stmt = qb.statements.pop()
        assert str(stmt.compile(compile_kwargs={"literal_binds": True})) == (
            "SELECT maasserver_iprange.start_ip, maasserver_iprange.end_ip, maasserver_iprange.type AS purpose \n"
            "FROM maasserver_iprange \n"
            "WHERE maasserver_iprange.subnet_id = 1 AND maasserver_iprange.type = 'dynamic' AND maasserver_iprange.id != 100"
        )

    def test_with_staticroute_gateway_ip(self) -> None:
        qb = SubnetUtilizationQueryBuilder(
            TEST_SUBNET
        ).with_staticroute_gateway_ip()
        assert len(qb.statements) == 1
        stmt = qb.statements.pop()
        # We can't compile the statement with literal binds because they don't
        # exist for INET and CIDR types.
        assert str(stmt.compile()) == (
            "SELECT maasserver_staticroute.gateway_ip AS start_ip, maasserver_staticroute.gateway_ip AS end_ip, :param_1 AS purpose \n"
            "FROM maasserver_staticroute \n"
            "WHERE maasserver_staticroute.source_id = :source_id_1 AND (maasserver_staticroute.gateway_ip << :gateway_ip_1)"
        )

    def test_with_allocated_ips(self) -> None:
        qb = SubnetUtilizationQueryBuilder(TEST_SUBNET).with_allocated_ips()
        assert len(qb.statements) == 1
        stmt = qb.statements.pop()
        assert str(
            stmt.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        ) == (
            "SELECT maasserver_staticipaddress.ip AS start_ip, maasserver_staticipaddress.ip AS end_ip, 'assigned-ip' AS purpose \n"
            "FROM maasserver_staticipaddress \n"
            "WHERE maasserver_staticipaddress.ip IS NOT NULL AND maasserver_staticipaddress.subnet_id = 1"
        )

    def test_with_allocated_ips_excludes_discovered_ips(self) -> None:
        qb = SubnetUtilizationQueryBuilder(TEST_SUBNET).with_allocated_ips(
            include_discovered_ips=False
        )
        assert len(qb.statements) == 1
        stmt = qb.statements.pop()
        assert str(
            stmt.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        ) == (
            "SELECT maasserver_staticipaddress.ip AS start_ip, maasserver_staticipaddress.ip AS end_ip, 'assigned-ip' AS purpose \n"
            "FROM maasserver_staticipaddress \n"
            "WHERE maasserver_staticipaddress.ip IS NOT NULL AND maasserver_staticipaddress.subnet_id = 1 "
            f"AND maasserver_staticipaddress.alloc_type != {IpAddressType.DISCOVERED}"
        )

    def test_with_neighbours(self) -> None:
        qb = SubnetUtilizationQueryBuilder(TEST_SUBNET).with_neighbours()
        assert len(qb.statements) == 1
        stmt = qb.statements.pop()
        assert str(
            stmt.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        ) == (
            "SELECT maasserver_discovery.ip AS start_ip, maasserver_discovery.ip AS end_ip, 'neighbour' AS purpose \n"
            "FROM maasserver_discovery \n"
            "WHERE maasserver_discovery.subnet_id = 1 AND maasserver_discovery.ip IS NOT NULL"
        )


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestSubnetUtilizationRepositoryManaged:
    @pytest.fixture
    async def subnet(self, fixture: Fixture) -> Subnet:
        """Setup for managed subnet utilization.

        Subnet: 10.0.0.0/24
        Subnet gateway ip:      10.0.0.1
        Subnet DNS servers:     10.0.0.2, 8.8.8.8
        Reserved IP Ranges:     (10.0.0.5, 10.0.0.6), (10.0.0.11, 10.0.0.12)
        Dynamic IP Ranges:      (10.0.0.7, 10.0.0.10), (10.0.0.13, 10.0.0.15)
        Static IP addresses:    10.0.0.20 (auto), 10.0.0.21 (discovered)
        Staticroute gateway IP: 10.0.0.30
        Neighbours:             10.0.0.40
        """
        vlan = await create_test_vlan_entry(fixture)
        subnet = await create_test_subnet_entry(
            fixture,
            vlan_id=vlan["id"],
            cidr="10.0.0.0/24",
            gateway_ip="10.0.0.1",
            dns_servers=["10.0.0.2", "8.8.8.8"],
        )
        await create_test_ip_range_entry(
            fixture,
            subnet,
            start_ip="10.0.0.5",
            end_ip="10.0.0.6",
            type=IPRangeType.RESERVED,
        )
        await create_test_ip_range_entry(
            fixture,
            subnet,
            start_ip="10.0.0.11",
            end_ip="10.0.0.12",
            type=IPRangeType.RESERVED,
        )
        await create_test_ip_range_entry(
            fixture,
            subnet,
            start_ip="10.0.0.7",
            end_ip="10.0.0.10",
            type=IPRangeType.DYNAMIC,
        )
        await create_test_ip_range_entry(
            fixture,
            subnet,
            start_ip="10.0.0.13",
            end_ip="10.0.0.15",
            type=IPRangeType.DYNAMIC,
        )
        await create_test_staticipaddress_entry(
            fixture,
            subnet_id=subnet["id"],
            ip="10.0.0.20",
            alloc_type=IpAddressType.AUTO,
        )
        await create_test_staticipaddress_entry(
            fixture,
            subnet_id=subnet["id"],
            ip="10.0.0.21",
            alloc_type=IpAddressType.DISCOVERED,
        )
        destination_subnet = await create_test_subnet_entry(
            fixture, cidr="12.0.0.0/24"
        )
        await create_test_staticroute_entry(
            fixture,
            source_subnet=Subnet(**subnet),
            destination_subnet=Subnet(**destination_subnet),
            gateway_ip="10.0.0.30",
        )
        rack_controller = await create_test_rack_controller_entry(fixture)
        interface = await create_test_interface_entry(
            fixture, node=rack_controller, vlan=vlan
        )
        await create_test_neighbour_entry(
            fixture, interface.id, ip="10.0.0.40"
        )
        return Subnet(**subnet)

    @pytest.fixture
    def repository(
        self, db_connection: AsyncConnection
    ) -> SubnetUtilizationRepository:
        r = SubnetUtilizationRepository(
            context=Context(connection=db_connection)
        )
        return r

    async def test_get_ipranges_available_for_reserved_range(
        self, repository: SubnetUtilizationRepository, subnet: Subnet
    ) -> None:
        """Only RESERVED and DYNAMIC IP ranges are considered "in use"."""
        ipset = await repository.get_ipranges_available_for_reserved_range(
            subnet=subnet
        )
        assert ipset == MAASIPSet(
            [
                MAASIPRange("10.0.0.1", "10.0.0.4"),
                MAASIPRange("10.0.0.16", "10.0.0.254"),
            ]
        )

    async def test_get_ipranges_available_for_reserved_range_exclude_ip_range(
        self,
        repository: SubnetUtilizationRepository,
        subnet: Subnet,
        fixture: Fixture,
    ) -> None:
        iprange_to_exclude = await create_test_ip_range_entry(
            fixture,
            subnet.dict(),
            start_ip="10.0.0.100",
            end_ip="10.0.0.200",
            type=IPRangeType.RESERVED,
        )
        ipset = await repository.get_ipranges_available_for_reserved_range(
            subnet=subnet, exclude_ip_range_id=iprange_to_exclude["id"]
        )
        assert ipset == MAASIPSet(
            [
                MAASIPRange("10.0.0.1", "10.0.0.4"),
                MAASIPRange("10.0.0.16", "10.0.0.254"),
            ]
        )

    async def test_get_ipranges_available_for_dynamic_range(
        self, repository: SubnetUtilizationRepository, subnet: Subnet
    ) -> None:
        """
        Considers the following as "in use" ranges:
            - RESERVED and DYNAMIC IP ranges
            - Subnet's gateway IP and DNS servers
            - Staticroute's gateway IP that have this subnet as the source
            - Allocated IPs BUT NOT discovered IPs
        """
        ipset = await repository.get_ipranges_available_for_dynamic_range(
            subnet=subnet
        )
        assert ipset == MAASIPSet(
            [
                MAASIPRange("10.0.0.3", "10.0.0.4"),
                MAASIPRange("10.0.0.16", "10.0.0.19"),
                MAASIPRange("10.0.0.21", "10.0.0.29"),
                MAASIPRange("10.0.0.31", "10.0.0.254"),
            ]
        )

    async def test_get_ipranges_available_for_dynamic_range_exclude_ip_range(
        self,
        repository: SubnetUtilizationRepository,
        subnet: Subnet,
        fixture: Fixture,
    ) -> None:
        iprange_to_exclude = await create_test_ip_range_entry(
            fixture,
            subnet.dict(),
            start_ip="10.0.0.100",
            end_ip="10.0.0.200",
            type=IPRangeType.RESERVED,
        )
        ipset = await repository.get_ipranges_available_for_dynamic_range(
            subnet=subnet, exclude_ip_range_id=iprange_to_exclude["id"]
        )
        assert ipset == MAASIPSet(
            [
                MAASIPRange("10.0.0.3", "10.0.0.4"),
                MAASIPRange("10.0.0.16", "10.0.0.19"),
                MAASIPRange("10.0.0.21", "10.0.0.29"),
                MAASIPRange("10.0.0.31", "10.0.0.254"),
            ]
        )

    async def test_get_ipranges_for_ip_allocation(
        self, repository: SubnetUtilizationRepository, subnet: Subnet
    ) -> None:
        """
        Considers the following as "in use" ranges:
            - Subnet's gateway IP and DNS servers
            - Staticroute's gateway IP that have this subnet as the source
            - Allocated IPs
            - RESERVED and DYNAMIC IP ranges
            - IPs from neighbour observation
        """
        ipset = await repository.get_ipranges_for_ip_allocation(subnet=subnet)
        assert ipset == MAASIPSet(
            [
                MAASIPRange("10.0.0.3", "10.0.0.4"),
                MAASIPRange("10.0.0.16", "10.0.0.19"),
                MAASIPRange("10.0.0.22", "10.0.0.29"),
                MAASIPRange("10.0.0.31", "10.0.0.39"),
                MAASIPRange("10.0.0.41", "10.0.0.254"),
            ]
        )

    async def test_get_free_ipranges(
        self, repository: SubnetUtilizationRepository, subnet: Subnet
    ) -> None:
        """
        Considers the following as "in use" ranges:
            - Subnet's gateway IP and DNS servers
            - Staticroute's gateway IP that have this subnet as the source
            - Allocated IPs
            - RESERVED and DYNAMIC IP ranges
        """
        ipset = await repository.get_free_ipranges(subnet=subnet)
        assert ipset == MAASIPSet(
            [
                MAASIPRange("10.0.0.3", "10.0.0.4"),
                MAASIPRange("10.0.0.16", "10.0.0.19"),
                MAASIPRange("10.0.0.22", "10.0.0.29"),
                MAASIPRange("10.0.0.31", "10.0.0.254"),
            ]
        )

    async def test_get_ipranges_in_use(
        self, repository: SubnetUtilizationRepository, subnet: Subnet
    ) -> None:
        """
        Considers the following as "in use" ranges:
            - Subnet's gateway IP and DNS servers
            - Staticroute's gateway IP that have this subnet as the source
            - Allocated IPs
            - RESERVED and DYNAMIC IP ranges
        """
        ipset = await repository.get_ipranges_in_use(subnet=subnet)
        assert ipset == MAASIPSet(
            [
                MAASIPRange(
                    "10.0.0.1", "10.0.0.1", purpose=IPRANGE_PURPOSE.GATEWAY_IP
                ),
                MAASIPRange(
                    "10.0.0.2", "10.0.0.2", purpose=IPRANGE_PURPOSE.DNS_SERVER
                ),
                MAASIPRange(
                    "10.0.0.5", "10.0.0.6", purpose=IPRANGE_PURPOSE.RESERVED
                ),
                MAASIPRange(
                    "10.0.0.7", "10.0.0.10", purpose=IPRANGE_PURPOSE.DYNAMIC
                ),
                MAASIPRange(
                    "10.0.0.11", "10.0.0.12", purpose=IPRANGE_PURPOSE.RESERVED
                ),
                MAASIPRange(
                    "10.0.0.13", "10.0.0.15", purpose=IPRANGE_PURPOSE.DYNAMIC
                ),
                MAASIPRange(
                    "10.0.0.20",
                    "10.0.0.21",
                    purpose=IPRANGE_PURPOSE.ASSIGNED_IP,
                ),
                MAASIPRange(
                    "10.0.0.30",
                    "10.0.0.30",
                    purpose=IPRANGE_PURPOSE.GATEWAY_IP,
                ),
            ]
        )

    async def test_get_subnet_utilization(
        self, repository: SubnetUtilizationRepository, subnet: Subnet
    ) -> None:
        """
        Considers the following as "in use" ranges:
            - Subnet's gateway IP and DNS servers
            - Staticroute's gateway IP that have this subnet as the source
            - Allocated IPs
            - RESERVED and DYNAMIC IP ranges
        """
        ipset = await repository.get_subnet_utilization(subnet=subnet)
        assert ipset == MAASIPSet(
            [
                MAASIPRange(
                    "10.0.0.1", "10.0.0.1", purpose=IPRANGE_PURPOSE.GATEWAY_IP
                ),
                MAASIPRange(
                    "10.0.0.2", "10.0.0.2", purpose=IPRANGE_PURPOSE.DNS_SERVER
                ),
                MAASIPRange(
                    "10.0.0.3", "10.0.0.4", purpose=IPRANGE_PURPOSE.UNUSED
                ),
                MAASIPRange(
                    "10.0.0.5", "10.0.0.6", purpose=IPRANGE_PURPOSE.RESERVED
                ),
                MAASIPRange(
                    "10.0.0.7", "10.0.0.10", purpose=IPRANGE_PURPOSE.DYNAMIC
                ),
                MAASIPRange(
                    "10.0.0.11", "10.0.0.12", purpose=IPRANGE_PURPOSE.RESERVED
                ),
                MAASIPRange(
                    "10.0.0.13", "10.0.0.15", purpose=IPRANGE_PURPOSE.DYNAMIC
                ),
                MAASIPRange(
                    "10.0.0.16", "10.0.0.19", purpose=IPRANGE_PURPOSE.UNUSED
                ),
                MAASIPRange(
                    "10.0.0.20",
                    "10.0.0.21",
                    purpose=IPRANGE_PURPOSE.ASSIGNED_IP,
                ),
                MAASIPRange(
                    "10.0.0.22", "10.0.0.29", purpose=IPRANGE_PURPOSE.UNUSED
                ),
                MAASIPRange(
                    "10.0.0.30",
                    "10.0.0.30",
                    purpose=IPRANGE_PURPOSE.GATEWAY_IP,
                ),
                MAASIPRange(
                    "10.0.0.31", "10.0.0.254", purpose=IPRANGE_PURPOSE.UNUSED
                ),
            ]
        )


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestSubnetUtilizationRepositoryUnmanaged:
    @pytest.fixture
    async def subnet(self, fixture: Fixture) -> Subnet:
        """Setup for managed subnet utilization.

        Subnet: 10.0.0.0/24
        Subnet gateway ip:      10.0.0.1
        Subnet DNS servers:     10.0.0.2, 8.8.8.8
        Reserved IP Ranges:     (10.0.0.1, 10.0.0.100)
        Dynamic IP Ranges:      (10.0.0.7, 10.0.0.10), (10.0.0.13, 10.0.0.15)
        Static IP addresses:    10.0.0.20 (auto), 10.0.0.21 (discovered)
        Staticroute gateway IP: 10.0.0.30
        Neighbours:             10.0.0.40
        """
        vlan = await create_test_vlan_entry(fixture)
        subnet = await create_test_subnet_entry(
            fixture,
            vlan_id=vlan["id"],
            cidr="10.0.0.0/24",
            gateway_ip="10.0.0.1",
            dns_servers=["10.0.0.2", "8.8.8.8"],
            managed=False,
        )
        await create_test_ip_range_entry(
            fixture,
            subnet,
            start_ip="10.0.0.1",
            end_ip="10.0.0.100",
            type=IPRangeType.RESERVED,
        )
        await create_test_ip_range_entry(
            fixture,
            subnet,
            start_ip="10.0.0.7",
            end_ip="10.0.0.10",
            type=IPRangeType.DYNAMIC,
        )
        await create_test_ip_range_entry(
            fixture,
            subnet,
            start_ip="10.0.0.13",
            end_ip="10.0.0.15",
            type=IPRangeType.DYNAMIC,
        )
        await create_test_staticipaddress_entry(
            fixture,
            subnet_id=subnet["id"],
            ip="10.0.0.20",
            alloc_type=IpAddressType.AUTO,
        )
        await create_test_staticipaddress_entry(
            fixture,
            subnet_id=subnet["id"],
            ip="10.0.0.21",
            alloc_type=IpAddressType.DISCOVERED,
        )
        destination_subnet = await create_test_subnet_entry(
            fixture, cidr="12.0.0.0/24"
        )
        await create_test_staticroute_entry(
            fixture,
            source_subnet=Subnet(**subnet),
            destination_subnet=Subnet(**destination_subnet),
            gateway_ip="10.0.0.30",
        )
        rack_controller = await create_test_rack_controller_entry(fixture)
        interface = await create_test_interface_entry(
            fixture, node=rack_controller, vlan=vlan
        )
        await create_test_neighbour_entry(
            fixture, interface.id, ip="10.0.0.40"
        )
        return Subnet(**subnet)

    @pytest.fixture
    def repository(
        self, db_connection: AsyncConnection
    ) -> SubnetUtilizationRepository:
        r = SubnetUtilizationRepository(
            context=Context(connection=db_connection)
        )
        return r

    async def test_get_ipranges_available_for_reserved_range(
        self, repository: SubnetUtilizationRepository, subnet: Subnet
    ) -> None:
        ipset = await repository.get_ipranges_available_for_reserved_range(
            subnet=subnet
        )
        assert ipset == MAASIPSet(
            [
                MAASIPRange("10.0.0.101", "10.0.0.254"),
            ]
        )

    async def test_get_ipranges_available_for_reserved_range_exclude_ip_range(
        self,
        repository: SubnetUtilizationRepository,
        subnet: Subnet,
        fixture: Fixture,
    ) -> None:
        iprange_to_exclude = await create_test_ip_range_entry(
            fixture,
            subnet.dict(),
            start_ip="10.0.0.101",
            end_ip="10.0.0.200",
            type=IPRangeType.RESERVED,
        )
        ipset = await repository.get_ipranges_available_for_reserved_range(
            subnet=subnet, exclude_ip_range_id=iprange_to_exclude["id"]
        )
        assert ipset == MAASIPSet(
            [
                MAASIPRange("10.0.0.101", "10.0.0.254"),
            ]
        )

    async def test_get_ipranges_available_for_dynamic_range(
        self, repository: SubnetUtilizationRepository, subnet: Subnet
    ) -> None:
        """
        We can only create DYNAMIC IP ranges inside RESERVED IP ranges.
        """
        ipset = await repository.get_ipranges_available_for_dynamic_range(
            subnet=subnet
        )
        assert ipset == MAASIPSet(
            [
                MAASIPRange("10.0.0.3", "10.0.0.6"),
                MAASIPRange("10.0.0.11", "10.0.0.12"),
                MAASIPRange("10.0.0.16", "10.0.0.19"),
                MAASIPRange("10.0.0.21", "10.0.0.29"),
                MAASIPRange("10.0.0.31", "10.0.0.100"),
            ]
        )

    async def test_get_ipranges_available_for_dynamic_range_exclude_ip_range(
        self,
        repository: SubnetUtilizationRepository,
        subnet: Subnet,
        fixture: Fixture,
    ) -> None:
        iprange_to_exclude = await create_test_ip_range_entry(
            fixture,
            subnet.dict(),
            start_ip="10.0.0.91",
            end_ip="10.0.0.100",
            type=IPRangeType.DYNAMIC,
        )
        ipset = await repository.get_ipranges_available_for_dynamic_range(
            subnet=subnet, exclude_ip_range_id=iprange_to_exclude["id"]
        )
        assert ipset == MAASIPSet(
            [
                MAASIPRange("10.0.0.3", "10.0.0.6"),
                MAASIPRange("10.0.0.11", "10.0.0.12"),
                MAASIPRange("10.0.0.16", "10.0.0.19"),
                MAASIPRange("10.0.0.21", "10.0.0.29"),
                MAASIPRange("10.0.0.31", "10.0.0.100"),
            ]
        )

    async def test_get_ipranges_for_ip_allocation(
        self, repository: SubnetUtilizationRepository, subnet: Subnet
    ) -> None:
        """
        Considers the following as "in use" ranges:
            - Subnet's gateway IP and DNS servers
            - Staticroute's gateway IP that have this subnet as the source
            - Allocated IPs
            - DYNAMIC IP ranges
            - IPs from neighbour observation
        """
        ipset = await repository.get_ipranges_for_ip_allocation(subnet=subnet)
        assert ipset == MAASIPSet(
            [
                MAASIPRange("10.0.0.3", "10.0.0.6"),
                MAASIPRange("10.0.0.11", "10.0.0.12"),
                MAASIPRange("10.0.0.16", "10.0.0.19"),
                MAASIPRange("10.0.0.22", "10.0.0.29"),
                MAASIPRange("10.0.0.31", "10.0.0.39"),
                MAASIPRange("10.0.0.41", "10.0.0.100"),
            ]
        )

    async def test_get_free_ipranges(
        self, repository: SubnetUtilizationRepository, subnet: Subnet
    ) -> None:
        """
        Considers the following as "in use" ranges:
            - Subnet's gateway IP and DNS servers
            - Staticroute's gateway IP that have this subnet as the source
            - Allocated IPs
            - DYNAMIC IP ranges
        """
        ipset = await repository.get_free_ipranges(subnet=subnet)
        assert ipset == MAASIPSet(
            [
                MAASIPRange("10.0.0.3", "10.0.0.6"),
                MAASIPRange("10.0.0.11", "10.0.0.12"),
                MAASIPRange("10.0.0.16", "10.0.0.19"),
                MAASIPRange("10.0.0.22", "10.0.0.29"),
                MAASIPRange("10.0.0.31", "10.0.0.100"),
            ]
        )

    async def test_get_ipranges_in_use(
        self, repository: SubnetUtilizationRepository, subnet: Subnet
    ) -> None:
        """
        Considers the following as "in use" ranges:
            - Subnet's gateway IP and DNS servers
            - Staticroute's gateway IP that have this subnet as the source
            - Allocated IPs
            - RESERVED and DYNAMIC IP ranges
        """
        ipset = await repository.get_ipranges_in_use(subnet=subnet)
        assert ipset == MAASIPSet(
            [
                MAASIPRange(
                    "10.0.0.1", "10.0.0.100", purpose=IPRANGE_PURPOSE.RESERVED
                ),
                MAASIPRange(
                    "10.0.0.1", "10.0.0.1", purpose=IPRANGE_PURPOSE.GATEWAY_IP
                ),
                MAASIPRange(
                    "10.0.0.2", "10.0.0.2", purpose=IPRANGE_PURPOSE.DNS_SERVER
                ),
                MAASIPRange(
                    "10.0.0.3", "10.0.0.6", purpose=IPRANGE_PURPOSE.RESERVED
                ),
                MAASIPRange(
                    "10.0.0.7", "10.0.0.10", purpose=IPRANGE_PURPOSE.DYNAMIC
                ),
                MAASIPRange(
                    "10.0.0.11", "10.0.0.12", purpose=IPRANGE_PURPOSE.RESERVED
                ),
                MAASIPRange(
                    "10.0.0.13", "10.0.0.15", purpose=IPRANGE_PURPOSE.DYNAMIC
                ),
                MAASIPRange(
                    "10.0.0.16", "10.0.0.19", purpose=IPRANGE_PURPOSE.RESERVED
                ),
                MAASIPRange(
                    "10.0.0.20",
                    "10.0.0.21",
                    purpose=IPRANGE_PURPOSE.ASSIGNED_IP,
                ),
                MAASIPRange(
                    "10.0.0.22", "10.0.0.29", purpose=IPRANGE_PURPOSE.RESERVED
                ),
                MAASIPRange(
                    "10.0.0.30",
                    "10.0.0.30",
                    purpose=IPRANGE_PURPOSE.GATEWAY_IP,
                ),
                MAASIPRange(
                    "10.0.0.31", "10.0.0.100", purpose=IPRANGE_PURPOSE.RESERVED
                ),
            ]
        )

    async def test_get_subnet_utilization(
        self, repository: SubnetUtilizationRepository, subnet: Subnet
    ) -> None:
        """
        Considers the following as "in use" ranges:
            - Subnet's gateway IP and DNS servers
            - Staticroute's gateway IP that have this subnet as the source
            - Allocated IPs
            - RESERVED and DYNAMIC IP ranges
        """
        ipset = await repository.get_subnet_utilization(subnet=subnet)
        assert ipset == MAASIPSet(
            [
                MAASIPRange(
                    "10.0.0.1", "10.0.0.100", purpose=IPRANGE_PURPOSE.RESERVED
                ),
                MAASIPRange(
                    "10.0.0.1", "10.0.0.1", purpose=IPRANGE_PURPOSE.GATEWAY_IP
                ),
                MAASIPRange(
                    "10.0.0.2", "10.0.0.2", purpose=IPRANGE_PURPOSE.DNS_SERVER
                ),
                MAASIPRange(
                    "10.0.0.3", "10.0.0.6", purpose=IPRANGE_PURPOSE.RESERVED
                ),
                MAASIPRange(
                    "10.0.0.7", "10.0.0.10", purpose=IPRANGE_PURPOSE.DYNAMIC
                ),
                MAASIPRange(
                    "10.0.0.11", "10.0.0.12", purpose=IPRANGE_PURPOSE.RESERVED
                ),
                MAASIPRange(
                    "10.0.0.13", "10.0.0.15", purpose=IPRANGE_PURPOSE.DYNAMIC
                ),
                MAASIPRange(
                    "10.0.0.16", "10.0.0.19", purpose=IPRANGE_PURPOSE.RESERVED
                ),
                MAASIPRange(
                    "10.0.0.20",
                    "10.0.0.21",
                    purpose=IPRANGE_PURPOSE.ASSIGNED_IP,
                ),
                MAASIPRange(
                    "10.0.0.22", "10.0.0.29", purpose=IPRANGE_PURPOSE.RESERVED
                ),
                MAASIPRange(
                    "10.0.0.30",
                    "10.0.0.30",
                    purpose=IPRANGE_PURPOSE.GATEWAY_IP,
                ),
                MAASIPRange(
                    "10.0.0.31", "10.0.0.100", purpose=IPRANGE_PURPOSE.RESERVED
                ),
                MAASIPRange(
                    "10.0.0.101", "10.0.0.254", purpose=IPRANGE_PURPOSE.UNUSED
                ),
            ]
        )
