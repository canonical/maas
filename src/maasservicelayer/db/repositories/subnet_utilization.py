#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass, field
from ipaddress import ip_address
from operator import eq
from typing import Self

from netaddr import IPNetwork
from sqlalchemy import and_, literal, not_, Select, select, union
from sqlalchemy.dialects.postgresql import array_agg

from maascommon.enums.ipaddress import IpAddressType
from maascommon.enums.ipranges import IPRangeType
from maascommon.utils.network import (
    IPRANGE_PURPOSE,
    MAASIPRange,
    MAASIPSet,
    make_iprange,
)
from maasservicelayer.db.repositories.base import Repository
from maasservicelayer.db.tables import (
    DiscoveryView,
    IPRangeTable,
    StaticIPAddressTable,
    StaticRouteTable,
)
from maasservicelayer.models.fields import IPv4v6Network
from maasservicelayer.models.subnets import Subnet


@dataclass
class SubnetUtilizationQueryBuilder:
    _subnet: Subnet
    statements: list[Select] = field(default_factory=list)

    def with_reserved_ipranges(
        self, exclude_ip_range_id: int | None = None
    ) -> Self:
        stmt = (
            select(
                IPRangeTable.c.start_ip,
                IPRangeTable.c.end_ip,
                IPRangeTable.c.type.label("purpose"),
            )
            .select_from(IPRangeTable)
            .where(
                and_(
                    eq(IPRangeTable.c.subnet_id, self._subnet.id),
                    eq(IPRangeTable.c.type, IPRangeType.RESERVED),
                )
            )
        )
        if exclude_ip_range_id is not None:
            stmt = stmt.where(not_(eq(IPRangeTable.c.id, exclude_ip_range_id)))
        self.statements.append(stmt)
        return self

    def with_dynamic_ipranges(
        self, exclude_ip_range_id: int | None = None
    ) -> Self:
        stmt = (
            select(
                IPRangeTable.c.start_ip,
                IPRangeTable.c.end_ip,
                IPRangeTable.c.type.label("purpose"),
            )
            .select_from(IPRangeTable)
            .where(
                and_(
                    eq(IPRangeTable.c.subnet_id, self._subnet.id),
                    eq(IPRangeTable.c.type, IPRangeType.DYNAMIC),
                )
            )
        )
        if exclude_ip_range_id is not None:
            stmt = stmt.where(not_(eq(IPRangeTable.c.id, exclude_ip_range_id)))
        self.statements.append(stmt)
        return self

    def with_staticroute_gateway_ip(self) -> Self:
        stmt = (
            select(
                StaticRouteTable.c.gateway_ip.label("start_ip"),
                StaticRouteTable.c.gateway_ip.label("end_ip"),
                literal(IPRANGE_PURPOSE.GATEWAY_IP).label("purpose"),
            )
            .select_from(StaticRouteTable)
            .where(
                and_(
                    eq(StaticRouteTable.c.source_id, self._subnet.id),
                    StaticRouteTable.c.gateway_ip.op("<<")(self._subnet.cidr),
                )
            )
        )
        self.statements.append(stmt)
        return self

    def with_allocated_ips(self, include_discovered_ips: bool = True) -> Self:
        stmt = (
            select(
                StaticIPAddressTable.c.ip.label("start_ip"),
                StaticIPAddressTable.c.ip.label("end_ip"),
                literal(IPRANGE_PURPOSE.ASSIGNED_IP).label("purpose"),
            )
            .select_from(StaticIPAddressTable)
            .where(
                and_(
                    not_(eq(StaticIPAddressTable.c.ip, None)),
                    eq(StaticIPAddressTable.c.subnet_id, self._subnet.id),
                )
            )
        )
        if not include_discovered_ips:
            stmt = stmt.where(
                not_(
                    eq(
                        StaticIPAddressTable.c.alloc_type,
                        IpAddressType.DISCOVERED,
                    )
                )
            )
        self.statements.append(stmt)
        return self

    def with_neighbours(self) -> Self:
        stmt = (
            select(
                DiscoveryView.c.ip.label("start_ip"),
                DiscoveryView.c.ip.label("end_ip"),
                literal(IPRANGE_PURPOSE.NEIGHBOUR).label("purpose"),
            )
            .select_from(DiscoveryView)
            .where(
                and_(
                    eq(DiscoveryView.c.subnet_id, self._subnet.id),
                    not_(DiscoveryView.c.ip.is_(None)),
                )
            )
        )
        self.statements.append(stmt)
        return self

    def build_stmt(self) -> Select:
        subquery = union(*self.statements).subquery()
        return (
            select(
                subquery.c.start_ip,
                subquery.c.end_ip,
                array_agg(subquery.c.purpose).label("purpose"),
            )
            .select_from(subquery)
            .group_by(subquery.c.start_ip, subquery.c.end_ip)
            .order_by(subquery.c.start_ip, subquery.c.end_ip)
        )


def _ipset_for_ipv6_subnets(network: IPv4v6Network) -> MAASIPSet:
    """Automatically reserve some IP ranges for IPv6 networks."""
    ranges = []
    if network.version == 6:
        # For most IPv6 networks, automatically reserve the range:
        #     ::1 - ::ffff:ffff
        # We expect the administrator will be using ::1 through ::ffff.
        # We plan to reserve ::1:0 through ::ffff:ffff for use by MAAS,
        # so that we can allocate addresses in the form:
        #     ::<node>:<child>
        # For now, just make sure IPv6 addresses are allocated from
        # *outside* both ranges, so that they won't conflict with addresses
        # reserved from this scheme in the future.
        first = network[0]
        first_plus_one = network[0] + 1
        second = network[0] + 0xFFFFFFFF
        if network.prefixlen == 64:
            ranges.append(
                make_iprange(
                    str(first_plus_one),
                    str(second),
                    purpose=IPRANGE_PURPOSE.RESERVED,
                )
            )
        # Reserve the subnet router anycast address, except for /127 and
        # /128 networks. (See RFC 6164, and RFC 4291 section 2.6.1.)
        if network.prefixlen < 127:
            ranges.append(
                make_iprange(
                    str(first), str(first), purpose=IPRANGE_PURPOSE.RFC_4291
                )
            )
    return MAASIPSet(ranges)


def _ipset_for_subnet_ips(subnet: Subnet) -> MAASIPSet:
    """Returns an `MAASIPSet` containing the subnet's gateway IP and DNS servers."""
    ips = []
    if subnet.dns_servers is not None:
        ips.extend(
            [
                make_iprange(s, purpose=IPRANGE_PURPOSE.DNS_SERVER)
                for s in subnet.dns_servers
                if ip_address(s) in subnet.cidr
            ]
        )
    if subnet.gateway_ip is not None:
        ips.append(
            make_iprange(
                str(subnet.gateway_ip), purpose=IPRANGE_PURPOSE.GATEWAY_IP
            )
        )
    return MAASIPSet(ips)


class SubnetUtilizationRepository(Repository):
    async def get_ipranges_available_for_reserved_range(
        self, subnet: Subnet, exclude_ip_range_id: int | None = None
    ) -> MAASIPSet:
        """Returns all the IP ranges available to allocate a RESERVED range.

        Params:
            subnet: the relevant subnet
            exclude_ip_range: an optional IP range to not be considered as "in use".
                Mainly used when validating IP range during creation/update.
        """
        if subnet.managed:
            return (
                await self._get_ipranges_available_for_reserved_range_managed(
                    subnet, exclude_ip_range_id
                )
            )
        else:
            return await self._get_ipranges_available_for_reserved_range_unmanaged(
                subnet, exclude_ip_range_id
            )

    async def _get_ipranges_available_for_reserved_range_managed(
        self, subnet: Subnet, exclude_ip_range_id: int | None = None
    ) -> MAASIPSet:
        """Only consider RESERVED and DYNAMIC IP ranges as "in use"."""
        ip_set = _ipset_for_ipv6_subnets(subnet.cidr)
        query_builder = (
            SubnetUtilizationQueryBuilder(subnet)
            .with_reserved_ipranges(exclude_ip_range_id=exclude_ip_range_id)
            .with_dynamic_ipranges(exclude_ip_range_id=exclude_ip_range_id)
        )
        stmt = query_builder.build_stmt()
        result = (await self.execute_stmt(stmt)).all()
        ip_set |= MAASIPSet(
            [MAASIPRange.from_db(**row._asdict()) for row in result]
        )
        return ip_set.get_unused_ranges_for_network(
            IPNetwork(str(subnet.cidr))
        )

    async def _get_ipranges_available_for_reserved_range_unmanaged(
        self, subnet: Subnet, exclude_ip_range_id: int | None = None
    ) -> MAASIPSet:
        """Returns all the IP ranges that aren't RESERVED ranges.

        In an unmanaged subnet we can assign IPs only inside reserved ranges.
        Hence, if we are creating a RESERVED range we are free to choose from
        every range that is not already reserved.
        """
        ip_set = _ipset_for_ipv6_subnets(subnet.cidr)
        query_builder = SubnetUtilizationQueryBuilder(
            subnet
        ).with_reserved_ipranges(exclude_ip_range_id=exclude_ip_range_id)
        stmt = query_builder.build_stmt()
        result = (await self.execute_stmt(stmt)).all()
        ip_set |= MAASIPSet(
            [MAASIPRange.from_db(**row._asdict()) for row in result]
        )
        return ip_set.get_unused_ranges_for_network(
            IPNetwork(str(subnet.cidr))
        )

    async def get_ipranges_available_for_dynamic_range(
        self, subnet: Subnet, exclude_ip_range_id: int | None = None
    ) -> MAASIPSet:
        """Returns all the IP ranges available to allocate a DYNAMIC range.

        Params:
            subnet: the relevant subnet
            exclude_ip_range_id: an optional IP range to not be considered as "in use".
                Mainly used when validating IP range during creation/update.

        """

        if subnet.managed:
            return (
                await self._get_ipranges_available_for_dynamic_range_managed(
                    subnet, exclude_ip_range_id
                )
            )
        else:
            return (
                await self._get_ipranges_available_for_dynamic_range_unmanaged(
                    subnet, exclude_ip_range_id
                )
            )

    async def _get_ipranges_available_for_dynamic_range_managed(
        self, subnet: Subnet, exclude_ip_range_id: int | None = None
    ) -> MAASIPSet:
        """
        Considers the following as "in use" ranges:
            - RESERVED and DYNAMIC IP ranges
            - Subnet's gateway IP and DNS servers
            - Staticroute's gateway IP that have this subnet as the source
            - Allocated IPs BUT NOT discovered IPs

        Returns all the unused ranges.
        """
        ip_set = _ipset_for_ipv6_subnets(subnet.cidr)
        ip_set |= _ipset_for_subnet_ips(subnet)
        query_builder = (
            SubnetUtilizationQueryBuilder(subnet)
            .with_reserved_ipranges(exclude_ip_range_id=exclude_ip_range_id)
            .with_dynamic_ipranges(exclude_ip_range_id=exclude_ip_range_id)
            .with_staticroute_gateway_ip()
            .with_allocated_ips(include_discovered_ips=False)
        )
        stmt = query_builder.build_stmt()
        result = (await self.execute_stmt(stmt)).all()
        ip_set |= MAASIPSet(
            [MAASIPRange.from_db(**row._asdict()) for row in result]
        )
        return ip_set.get_unused_ranges_for_network(
            IPNetwork(str(subnet.cidr))
        )

    async def _get_ipranges_available_for_dynamic_range_unmanaged(
        self, subnet: Subnet, exclude_ip_range_id: int | None = None
    ) -> MAASIPSet:
        """Returns all the free IP ranges within RESERVED ranges.

        In an unmanaged subnet we can assign IPs only inside RESERVED ranges.
        Hence, if we are creating a DYNAMIC IP range we can only choose ranges
        inside RESERVED ranges.
        """
        ip_set = _ipset_for_ipv6_subnets(subnet.cidr)
        ip_set |= _ipset_for_subnet_ips(subnet)
        query_builder = (
            SubnetUtilizationQueryBuilder(subnet)
            .with_allocated_ips(include_discovered_ips=False)
            .with_staticroute_gateway_ip()
            .with_dynamic_ipranges(exclude_ip_range_id)
        )
        stmt = query_builder.build_stmt()
        result = (await self.execute_stmt(stmt)).all()
        ip_set |= MAASIPSet(
            [MAASIPRange.from_db(**row._asdict()) for row in result]
        )

        reserved_ranges = await self._get_reserved_range_unmanaged(subnet)
        return ip_set.get_unused_ranges_for_range(reserved_ranges)

    async def get_ipranges_for_ip_allocation(
        self,
        subnet: Subnet,
        exclude_addresses: list[str] | None = None,
    ) -> MAASIPSet:
        """Returns all the free IP ranges for IP allocation.

        Params:
            subnet: the relevant subnet.
            exclude_addresses: additional addresses to be treated as "in use".
        """
        if exclude_addresses is None:
            exclude_addresses = []

        if subnet.managed:
            return await self._get_ipranges_for_ip_allocation_managed(
                subnet=subnet,
                exclude_addresses=exclude_addresses,
            )

        else:
            return await self._get_ipranges_for_ip_allocation_unmanaged(
                subnet=subnet,
                exclude_addresses=exclude_addresses,
            )

    async def _get_ipranges_for_ip_allocation_managed(
        self,
        subnet: Subnet,
        exclude_addresses: list[str],
    ) -> MAASIPSet:
        """Returns all the free IP ranges for a managed subnet.

        Considers the following as "in use" ranges:
            - Subnet's gateway IP and DNS servers
            - Staticroute's gateway IP that have this subnet as the source
            - Allocated IPs
            - RESERVED and DYNAMIC IP ranges
            - IPs from neighbour observation
        """
        ip_set = _ipset_for_ipv6_subnets(subnet.cidr)
        ip_set |= MAASIPSet(
            [
                make_iprange(address, purpose=IPRANGE_PURPOSE.EXCLUDED)
                for address in exclude_addresses
                if ip_address(address) in subnet.cidr
            ]
        )
        ip_set |= _ipset_for_subnet_ips(subnet)
        query_builder = (
            SubnetUtilizationQueryBuilder(subnet)
            .with_allocated_ips()
            .with_staticroute_gateway_ip()
            .with_reserved_ipranges()
            .with_dynamic_ipranges()
            .with_neighbours()
        )
        stmt = query_builder.build_stmt()
        result = (await self.execute_stmt(stmt)).all()
        ip_set |= MAASIPSet(
            [MAASIPRange.from_db(**row._asdict()) for row in result]
        )
        unused_ip_set = ip_set.get_unused_ranges_for_network(
            IPNetwork(str(subnet.cidr))
        )
        return unused_ip_set

    async def _get_ipranges_for_ip_allocation_unmanaged(
        self,
        subnet: Subnet,
        exclude_addresses: list[str],
    ) -> MAASIPSet:
        """Returns all the free IP ranges within reserved ranges.

        In an unmanaged subnets we can only assign IPs inside reserved ranges.
        The unused IP ranges are the ones that are inside a RESERVED range and
        not used. We first get all the IP ranges in use and the we calculate the
        unused ones against the RESERVED ranges.
        """
        ip_set = _ipset_for_ipv6_subnets(subnet.cidr)
        ip_set |= MAASIPSet(
            [
                make_iprange(address, purpose=IPRANGE_PURPOSE.EXCLUDED)
                for address in exclude_addresses
                if ip_address(address) in subnet.cidr
            ]
        )
        ip_set |= _ipset_for_subnet_ips(subnet)
        query_builder = (
            SubnetUtilizationQueryBuilder(subnet)
            .with_allocated_ips()
            .with_staticroute_gateway_ip()
            .with_dynamic_ipranges()
            .with_neighbours()
        )
        stmt = query_builder.build_stmt()
        result = (await self.execute_stmt(stmt)).all()
        ip_set |= MAASIPSet(
            [MAASIPRange.from_db(**row._asdict()) for row in result]
        )

        reserved_ranges = await self._get_reserved_range_unmanaged(subnet)
        return ip_set.get_unused_ranges_for_range(reserved_ranges)

    async def get_free_ipranges(
        self,
        subnet: Subnet,
    ) -> MAASIPSet:
        """Returns all the free IP ranges."""
        if subnet.managed:
            used_ip_set = await self._get_ipranges_in_use_managed(
                subnet=subnet,
            )
            unused_ip_set = used_ip_set.get_unused_ranges_for_network(
                IPNetwork(str(subnet.cidr))
            )
            return unused_ip_set

        else:
            used_ip_set = await self._get_ipranges_in_use_unmanaged(
                subnet=subnet, include_reserved_ranges=False
            )

            reserved_ranges = await self._get_reserved_range_unmanaged(subnet)
            return used_ip_set.get_unused_ranges_for_range(reserved_ranges)

    async def get_subnet_utilization(self, subnet: Subnet) -> MAASIPSet:
        """Returns a MAASIPset containing both the used and unused IP ranges."""
        if subnet.managed:
            used_ip_set = await self._get_ipranges_in_use_managed(
                subnet=subnet,
            )

        else:
            used_ip_set = await self._get_ipranges_in_use_unmanaged(
                subnet=subnet, include_reserved_ranges=True
            )

        return used_ip_set.get_full_range(IPNetwork(str(subnet.cidr)))

    async def get_ipranges_in_use(self, subnet: Subnet) -> MAASIPSet:
        if subnet.managed:
            return await self._get_ipranges_in_use_managed(
                subnet=subnet,
            )

        else:
            return await self._get_ipranges_in_use_unmanaged(
                subnet=subnet, include_reserved_ranges=True
            )

    async def _get_ipranges_in_use_managed(
        self,
        subnet: Subnet,
    ) -> MAASIPSet:
        ip_set = _ipset_for_ipv6_subnets(subnet.cidr)
        ip_set |= _ipset_for_subnet_ips(subnet)
        query_builder = (
            SubnetUtilizationQueryBuilder(subnet)
            .with_allocated_ips()
            .with_staticroute_gateway_ip()
            .with_reserved_ipranges()
            .with_dynamic_ipranges()
        )
        stmt = query_builder.build_stmt()
        result = (await self.execute_stmt(stmt)).all()
        ip_set |= MAASIPSet(
            [MAASIPRange.from_db(**row._asdict()) for row in result]
        )
        return ip_set

    async def _get_ipranges_in_use_unmanaged(
        self, subnet: Subnet, include_reserved_ranges: bool
    ) -> MAASIPSet:
        ip_set = _ipset_for_ipv6_subnets(subnet.cidr)
        ip_set |= _ipset_for_subnet_ips(subnet)
        query_builder = (
            SubnetUtilizationQueryBuilder(subnet)
            .with_allocated_ips()
            .with_staticroute_gateway_ip()
            .with_dynamic_ipranges()
        )
        if include_reserved_ranges:
            query_builder.with_reserved_ipranges()
        stmt = query_builder.build_stmt()
        result = (await self.execute_stmt(stmt)).all()
        ip_set |= MAASIPSet(
            [MAASIPRange.from_db(**row._asdict()) for row in result]
        )
        return ip_set

    async def _get_reserved_range_unmanaged(
        self, subnet: Subnet
    ) -> list[MAASIPRange]:
        reserved_range_stmt = (
            SubnetUtilizationQueryBuilder(subnet)
            .with_reserved_ipranges()
            .build_stmt()
        )
        result = (await self.execute_stmt(reserved_range_stmt)).all()
        reserved_ranges = [
            MAASIPRange.from_db(**row._asdict()) for row in result
        ]
        return reserved_ranges
