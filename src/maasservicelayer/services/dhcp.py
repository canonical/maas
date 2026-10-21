# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import asyncio
from dataclasses import dataclass, field
from ipaddress import ip_address, IPv4Address, IPv6Address
from urllib.parse import urlparse

from netaddr import IPNetwork
import structlog

from maascommon.enums.interface import InterfaceType
from maascommon.enums.ipaddress import IpAddressType
from maascommon.enums.ipranges import IPRangeType
from maascommon.enums.node import NodeTypeEnum
from maasservicelayer.context import Context
from maasservicelayer.db.filters import OrderByClause, QuerySpec
from maasservicelayer.db.repositories.domains import DomainsClauseFactory
from maasservicelayer.db.repositories.interfaces import InterfaceClauseFactory
from maasservicelayer.db.repositories.ipranges import IPRangeClauseFactory
from maasservicelayer.db.repositories.nodes import NodeClauseFactory
from maasservicelayer.db.repositories.reservedips import (
    ReservedIPsClauseFactory,
)
from maasservicelayer.db.repositories.staticipaddress import (
    StaticIPAddressClauseFactory,
)
from maasservicelayer.db.repositories.subnets import SubnetClauseFactory
from maasservicelayer.db.repositories.vlans import VlansClauseFactory
from maasservicelayer.db.tables import (
    DomainTable,
    IPRangeTable,
    ReservedIPTable,
    StaticIPAddressTable,
    VlanTable,
)
from maasservicelayer.exceptions.catalog import (
    NotFoundException,
    ValidationException,
)
from maasservicelayer.models.dhcp import (
    DHCPDataForAgent,
    HostReservationData,
    InterfaceData,
    IPRangeData,
    KeaHAConfig,
    SubnetData,
    VlanData,
)
from maasservicelayer.models.interfaces import Interface
from maasservicelayer.models.nodes import Node
from maasservicelayer.models.staticipaddress import StaticIPAddress
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.models.vlans import Vlan
from maasservicelayer.services.base import Service
from maasservicelayer.services.configurations import ConfigurationsService
from maasservicelayer.services.domains import DomainsService
from maasservicelayer.services.interfaces import InterfacesService
from maasservicelayer.services.ipranges import IPRangesService
from maasservicelayer.services.nodes import NodesService
from maasservicelayer.services.reservedips import ReservedIPsService
from maasservicelayer.services.staticipaddress import StaticIPAddressService
from maasservicelayer.services.subnets import SubnetsService
from maasservicelayer.services.vlans import VlansService
from provisioningserver.utils.env import MAAS_ID
from provisioningserver.utils.network import (
    get_source_address,
    resolve_hostname,
)
from provisioningserver.utils.text import split_string_list

logger = structlog.get_logger()


@dataclass
class _DHCPQueryCache:
    """Per-request caches that memoize lookups to avoid N+1 queries."""

    ips_by_interface: dict[int, list[StaticIPAddress]] = field(
        default_factory=dict
    )
    subnet_by_id: dict[int, Subnet | None] = field(default_factory=dict)
    vlan_by_id: dict[int, Vlan | None] = field(default_factory=dict)
    node_by_id: dict[int, Node | None] = field(default_factory=dict)
    interfaces_by_config: dict[int, list[Interface]] = field(
        default_factory=dict
    )
    dynamic_count_by_subnet: dict[int, int] = field(default_factory=dict)


class DHCPService(Service):
    """Collect network data needed to configure DHCP on a rack controller."""

    def __init__(
        self,
        context: Context,
        configurations_service: ConfigurationsService,
        domains_service: DomainsService,
        interfaces_service: InterfacesService,
        ipranges_service: IPRangesService,
        nodes_service: NodesService,
        reservedips_service: ReservedIPsService,
        staticipaddress_service: StaticIPAddressService,
        subnets_service: SubnetsService,
        vlans_service: VlansService,
    ):
        super().__init__(context)
        self.configurations_service = configurations_service
        self.domains_service = domains_service
        self.interfaces_service = interfaces_service
        self.ipranges_service = ipranges_service
        self.nodes_service = nodes_service
        self.reservedips_service = reservedips_service
        self.staticipaddress_service = staticipaddress_service
        self.subnets_service = subnets_service
        self.vlans_service = vlans_service

    async def get_kea_dhcp_data_for_agent(
        self, system_id: str
    ) -> DHCPDataForAgent:
        """Retrieve Kea configuration inputs for a rack controller system ID."""
        rack = await self.nodes_service.get_one(
            query=QuerySpec(where=NodeClauseFactory.with_system_id(system_id))
        )
        if rack is None:
            raise NotFoundException()
        if rack.node_type not in (
            NodeTypeEnum.RACK_CONTROLLER,
            NodeTypeEnum.REGION_AND_RACK_CONTROLLER,
        ):
            raise ValidationException.build_for_field(
                "system_id", "The node must be a rack controller."
            )
        if rack.current_config_id is None:
            raise ValidationException.build_for_field(
                "system_id",
                "The rack controller has no current configuration.",
            )

        cache = _DHCPQueryCache()
        cache.node_by_id[rack.id] = rack

        # Retrieve relevant VLANs for this rack
        active_vlans = await self.vlans_service.get_many(
            QuerySpec(
                where=VlansClauseFactory.and_clauses(
                    [
                        VlansClauseFactory.with_dhcp_on(True),
                        VlansClauseFactory.with_primary_or_secondary_rack_id(
                            rack.id
                        ),
                    ]
                ),
                order_by=[OrderByClause(VlanTable.c.id)],
            )
        )
        interfaces = await self._get_rack_interfaces(rack, cache)
        interface_vlan_ids = {
            interface.vlan_id
            for interface in interfaces
            if interface.vlan_id is not None
        }
        active_vlans = [
            vlan for vlan in active_vlans if vlan.id in interface_vlan_ids
        ]
        vlans = {vlan.id: vlan for vlan in active_vlans}
        if vlans:
            relay_vlans = await self.vlans_service.get_many(
                query=QuerySpec(
                    where=VlansClauseFactory.with_relay_vlan_id_in(list(vlans))
                )
            )
            for relay in relay_vlans:
                vlans[relay.id] = relay
        cache.vlan_by_id.update(vlans)

        # Retrieve relevant subnets for this rack
        subnets = await self.subnets_service.get_many(
            query=QuerySpec(
                where=SubnetClauseFactory.and_clauses(
                    [
                        SubnetClauseFactory.with_vlan_id_in(list(vlans)),
                        SubnetClauseFactory.with_managed(True),
                    ]
                )
            )
        )
        subnets.sort(
            key=lambda subnet: (
                subnet.vlan_id,
                subnet.cidr.version,
                str(subnet.cidr.network_address),
            )
        )
        cache.subnet_by_id.update({subnet.id: subnet for subnet in subnets})

        # Retrieve relevant IP ranges for this rack
        ipranges = await self.ipranges_service.get_many(
            query=QuerySpec(
                where=IPRangeClauseFactory.with_subnet_ids(
                    [subnet.id for subnet in subnets]
                ),
                order_by=[OrderByClause(IPRangeTable.c.id)],
            )
        )
        dynamic_counts = {subnet.id: 0 for subnet in subnets}
        for iprange in ipranges:
            if iprange.type == IPRangeType.DYNAMIC:
                dynamic_counts[iprange.subnet_id] += 1
        cache.dynamic_count_by_subnet.update(dynamic_counts)
        ranges = [
            IPRangeData(
                id=iprange.id,
                subnet_id=iprange.subnet_id,
                dynamic=iprange.type == IPRangeType.DYNAMIC,
                start_ip=str(iprange.start_ip),
                end_ip=str(iprange.end_ip),
            )
            for iprange in ipranges
        ]

        # Retrieve dns & ntp addresses, domains
        rack_url = await self.nodes_service.get_url(system_id)
        default_domain = await self.domains_service.get_default_domain()
        search_domains = await self.domains_service.get_many(
            query=QuerySpec(
                where=DomainsClauseFactory.and_clauses(
                    [
                        DomainsClauseFactory.not_clause(
                            DomainsClauseFactory.with_name(default_domain.name)
                        ),
                        DomainsClauseFactory.with_authoritative(True),
                    ]
                ),
                order_by=[OrderByClause(DomainTable.c.name)],
            )
        )
        external_only = await self.configurations_service.get(
            "ntp_external_only"
        )
        external_ntp = (
            list(
                split_string_list(
                    await self.configurations_service.get("ntp_servers")
                )
            )
            if external_only
            else []
        )
        ntp_by_space = (
            {}
            if external_only
            else await self._get_ntp_servers_for_rack(rack, cache)
        )
        rack_ips = await self.staticipaddress_service.get_for_nodes(
            query=QuerySpec(
                where=StaticIPAddressClauseFactory.and_clauses(
                    [
                        StaticIPAddressClauseFactory.with_node_system_id(
                            system_id
                        ),
                        StaticIPAddressClauseFactory.with_alloc_type_in(
                            [IpAddressType.STICKY, IpAddressType.USER_RESERVED]
                        ),
                        StaticIPAddressClauseFactory.with_ip_not_null(),
                    ]
                )
            )
        )
        subnet_ids = {subnet.id for subnet in subnets}
        default_dns_ntp_servers = list(
            dict.fromkeys(
                str(ip.ip)
                for ip in rack_ips
                if ip.ip is not None and ip.subnet_id in subnet_ids
            )
        )
        dhcp_interfaces: dict[int, InterfaceData] = {}
        configured_ip_versions: set[int] = set()
        subnet_data = []
        # Dict used as an insertion-ordered set to dedupe HA configs shared by
        # multiple subnets on the same VLAN.
        ha_data: dict[KeaHAConfig, None] = {}
        host_reservations: dict[int, list[HostReservationData]] = {}
        for grouped_subnets in self._group_subnets(subnets).values():
            host_reservations.update(
                await self._get_dhcp_host_reservations(
                    [subnet.id for subnet in grouped_subnets]
                )
            )
        peer_ntp_by_rack: dict[int, dict[tuple[int | None, int], str]] = {}
        for subnet in subnets:
            vlan = vlans[subnet.vlan_id]
            # A subnet on a relay VLAN is served by the HA pair of the target
            # VLAN; relay VLANs don't hold the rack controller identifiers.
            dhcp_vlan = vlan
            if vlan.relay_vlan_id is not None:
                dhcp_vlan = vlans.get(vlan.relay_vlan_id, vlan)
            iface, ips = await self._get_best_interface_with_ip_on_vlan(
                subnet, vlan, interfaces, cache
            )
            if iface is not None and iface.vlan_id is not None:
                configured_ip_versions.add(subnet.cidr.version)
                dhcp_interfaces[iface.id] = InterfaceData(
                    id=iface.id, vlan_id=iface.vlan_id, name=iface.name
                )
            next_server = self._get_next_server(subnet, ips)
            primary_system_id = system_id
            secondary_system_id = None
            peer_rack_id = None
            if dhcp_vlan.secondary_rack_id is not None:
                ha = await self._get_ha_config(subnet, dhcp_vlan, cache)
                primary_system_id = ha.primary_rack_system_id
                secondary_system_id = ha.secondary_rack_system_id
                ha_data[ha] = None
                peer_rack_id = (
                    dhcp_vlan.secondary_rack_id
                    if dhcp_vlan.primary_rack_id == rack.id
                    else dhcp_vlan.primary_rack_id
                )
                # guaranteed to not be None by _get_ha_config above
                assert peer_rack_id is not None
                if peer_rack_id not in peer_ntp_by_rack:
                    peer_rack = await self._cached_node(cache, peer_rack_id)
                    assert peer_rack is not None
                    peer_ntp_by_rack[
                        peer_rack_id
                    ] = await self._get_ntp_servers_for_rack(peer_rack, cache)
            ntp_server = ntp_by_space.get((vlan.space_id, subnet.cidr.version))
            peer_ntp_server = (
                peer_ntp_by_rack.get(peer_rack_id, {}).get(
                    (vlan.space_id, subnet.cidr.version)
                )
                if peer_rack_id is not None
                else None
            )
            subnet_ntp_servers = (
                external_ntp
                if external_only
                else [
                    server
                    for server in (ntp_server, peer_ntp_server)
                    if server is not None
                ]
            )
            subnet_data.append(
                SubnetData(
                    id=subnet.id,
                    rack_system_id=primary_system_id,
                    secondary_rack_system_id=secondary_system_id,
                    ip_version=subnet.cidr.version,
                    cidr=str(subnet.cidr),
                    gateway_ip=str(subnet.gateway_ip)
                    if subnet.gateway_ip is not None
                    else "",
                    dns_servers=await self._get_default_dns_servers_for_subnet(
                        subnet, rack_url, cache
                    ),
                    allow_dns=subnet.allow_dns,
                    vlan_id=subnet.vlan_id,
                    vlan_mtu=vlan.mtu,
                    mask=str(subnet.cidr.netmask),
                    broadcast_ip=str(subnet.cidr.broadcast_address),
                    domain_name=default_domain.name,
                    search_list=[default_domain.name]
                    + [domain.name for domain in search_domains],
                    ntp_servers=subnet_ntp_servers,
                    next_server=next_server,
                    pools=[
                        r
                        for r in ranges
                        if r.subnet_id == subnet.id and r.dynamic
                    ],
                    host_reservations=host_reservations.get(subnet.id, []),
                )
            )
        subnet_data = [
            subnet
            for subnet in subnet_data
            if subnet.ip_version in configured_ip_versions
        ]
        ranges = [
            iprange
            for iprange in ranges
            if iprange.subnet_id in {subnet.id for subnet in subnet_data}
        ]
        return DHCPDataForAgent(
            vlans=[
                VlanData(
                    id=vlan.id,
                    vid=vlan.vid,
                    relayed_vlan_id=vlan.relay_vlan_id,
                    mtu=vlan.mtu,
                )
                for vlan in sorted(vlans.values(), key=lambda item: item.id)
            ],
            subnets=subnet_data,
            ipranges=ranges,
            interfaces=sorted(
                dhcp_interfaces.values(), key=lambda iface: iface.name
            ),
            default_dns_servers=default_dns_ntp_servers,
            ntp_servers=external_ntp
            if external_only
            else default_dns_ntp_servers,
            ha_data=list(ha_data),
        )

    async def _get_rack_interfaces(
        self, rack: Node, cache: _DHCPQueryCache
    ) -> list[Interface]:
        if rack.current_config_id is None:
            raise ValidationException.build_for_field(
                "system_id",
                f"Rack controller {rack.system_id} has no current configuration.",
            )
        if rack.current_config_id in cache.interfaces_by_config:
            return cache.interfaces_by_config[rack.current_config_id]
        interfaces = await self.interfaces_service.get_many(
            query=QuerySpec(
                where=InterfaceClauseFactory.with_node_config_id(
                    rack.current_config_id
                )
            )
        )
        sorted_interfaces = sorted(
            interfaces, key=lambda interface: interface.created
        )
        cache.interfaces_by_config[rack.current_config_id] = sorted_interfaces
        return sorted_interfaces

    async def _cached_node(
        self, cache: _DHCPQueryCache, node_id: int
    ) -> Node | None:
        if node_id not in cache.node_by_id:
            cache.node_by_id[node_id] = await self.nodes_service.get_by_id(
                node_id
            )
        return cache.node_by_id[node_id]

    async def _cached_subnet(
        self, cache: _DHCPQueryCache, subnet_id: int
    ) -> Subnet | None:
        if subnet_id not in cache.subnet_by_id:
            cache.subnet_by_id[
                subnet_id
            ] = await self.subnets_service.get_by_id(subnet_id)
        return cache.subnet_by_id[subnet_id]

    async def _cached_vlan(
        self, cache: _DHCPQueryCache, vlan_id: int
    ) -> Vlan | None:
        if vlan_id not in cache.vlan_by_id:
            cache.vlan_by_id[vlan_id] = await self.vlans_service.get_by_id(
                vlan_id
            )
        return cache.vlan_by_id[vlan_id]

    async def _cache_ips_for_interfaces(
        self, cache: _DHCPQueryCache, interface_ids: list[int]
    ) -> None:
        missing = set(interface_ids) - set(cache.ips_by_interface.keys())
        # unfortunately we can't bulk query since the returned StaticIPAddress
        # objects have no interface_id field
        for interface_id in missing:
            cache.ips_by_interface[
                interface_id
            ] = await self.staticipaddress_service.get_for_interfaces(
                [interface_id]
            )

    async def _cached_dynamic_range_count(
        self, cache: _DHCPQueryCache, subnet_id: int
    ) -> int:
        if subnet_id not in cache.dynamic_count_by_subnet:
            ranges = await self.ipranges_service.get_many(
                query=QuerySpec(
                    where=IPRangeClauseFactory.and_clauses(
                        [
                            IPRangeClauseFactory.with_subnet_id(subnet_id),
                            IPRangeClauseFactory.with_type(
                                IPRangeType.DYNAMIC
                            ),
                        ]
                    ),
                    order_by=[OrderByClause(IPRangeTable.c.id)],
                )
            )
            cache.dynamic_count_by_subnet[subnet_id] = len(ranges)
        return cache.dynamic_count_by_subnet[subnet_id]

    @staticmethod
    def _group_subnets(
        subnets: list[Subnet],
    ) -> dict[tuple[int, int], list[Subnet]]:
        groups: dict[tuple[int, int], list[Subnet]] = {}
        for subnet in subnets:
            groups.setdefault(
                (subnet.vlan_id, subnet.cidr.version), []
            ).append(subnet)
        return groups

    async def _get_best_interface_with_ip_on_vlan(
        self,
        subnet: Subnet,
        vlan: Vlan,
        interfaces: list[Interface],
        cache: _DHCPQueryCache,
    ) -> tuple[Interface | None, list[StaticIPAddress]]:
        """Choose the legacy preferred interface and its addresses by family."""
        eligible_vlans = {vlan.id}
        if vlan.relay_vlan_id is not None:
            eligible_vlans.add(vlan.relay_vlan_id)
        static_interfaces: list[
            tuple[Interface, list[StaticIPAddress], int]
        ] = []
        discovered_interfaces: list[
            tuple[Interface, list[StaticIPAddress], int]
        ] = []
        interfaces = sorted(interfaces, key=lambda item: item.created)
        await self._cache_ips_for_interfaces(cache, [i.id for i in interfaces])
        for interface in interfaces:
            ips = cache.ips_by_interface.get(interface.id, [])
            static_match = False
            discovered_match = False
            dynamic_count = 0
            for ip in ips:
                if ip.subnet_id is None:
                    continue
                ip_subnet = await self._cached_subnet(cache, ip.subnet_id)
                assert ip_subnet is not None
                dynamic_count += await self._cached_dynamic_range_count(
                    cache, ip_subnet.id
                )
                if (
                    ip.ip is None
                    or ip.ip.version != subnet.cidr.version
                    or ip_subnet.vlan_id not in eligible_vlans
                ):
                    continue
                if ip.alloc_type in (IpAddressType.AUTO, IpAddressType.STICKY):
                    static_match = True
                elif ip.alloc_type == IpAddressType.DISCOVERED:
                    discovered_match = True
            if static_match:
                static_interfaces.append((interface, ips, dynamic_count))
            elif discovered_match:
                discovered_interfaces.append((interface, ips, dynamic_count))

        candidates = static_interfaces or discovered_interfaces
        candidates.sort(key=lambda item: item[2], reverse=True)
        best_interface = None
        for interface, _, _ in candidates:
            if (
                best_interface is None
                or (
                    best_interface.type == InterfaceType.PHYSICAL
                    and interface.type == InterfaceType.BOND
                )
                or (
                    best_interface.type == InterfaceType.VLAN
                    and interface.type == InterfaceType.PHYSICAL
                )
            ):
                best_interface = interface
        if best_interface is None:
            return None, []
        best_ips = cache.ips_by_interface[best_interface.id]
        return best_interface, sorted(
            [
                ip
                for ip in best_ips
                if ip.ip is not None and ip.ip.version == subnet.cidr.version
            ],
            key=lambda address: address.id,
        )

    @staticmethod
    def _get_next_server(subnet: Subnet, ips: list[StaticIPAddress]) -> str:
        addresses = [
            ip.ip
            for ip in ips
            if ip.ip is not None and ip.ip.version == subnet.cidr.version
        ]
        address = next(
            (ip for ip in addresses if ip in subnet.cidr),
            addresses[0] if addresses else None,
        )
        return str(address) if address is not None else ""

    async def _get_ha_config(
        self,
        subnet: Subnet,
        vlan: Vlan,
        cache: _DHCPQueryCache,
    ) -> KeaHAConfig:
        addresses = []
        racks = []
        for rack_id in (vlan.primary_rack_id, vlan.secondary_rack_id):
            rack = (
                await self._cached_node(cache, rack_id)
                if rack_id is not None
                else None
            )
            if rack is None:
                raise ValidationException.build_for_field(
                    "system_id", f"VLAN {vlan.id} has a missing HA rack."
                )
            address = await self._get_ip_address_for_rack_controller(
                rack, subnet, vlan, cache
            )
            if not address:
                raise ValidationException.build_for_field(
                    "system_id",
                    f"Rack {rack.system_id} has no IPv{subnet.cidr.version} "
                    f"address for HA on VLAN {vlan.id}.",
                )
            racks.append(rack)
            addresses.append(address)
        return KeaHAConfig(
            primary_rack_system_id=racks[0].system_id,
            secondary_rack_system_id=racks[1].system_id,
            primary_rack_ip=addresses[0],
            secondary_rack_ip=addresses[1],
        )

    async def _get_ip_address_for_rack_controller(
        self,
        rack: Node,
        subnet: Subnet,
        vlan: Vlan,
        cache: _DHCPQueryCache,
    ) -> str | None:
        interface, ips = await self._get_best_interface_with_ip_on_vlan(
            subnet, vlan, await self._get_rack_interfaces(rack, cache), cache
        )
        if interface is None:
            return None
        for ip in ips:
            if (
                ip.ip is None
                or ip.ip.version != subnet.cidr.version
                or ip.alloc_type
                not in (IpAddressType.STICKY, IpAddressType.AUTO)
                or ip.subnet_id is None
            ):
                continue
            ip_subnet = await self._cached_subnet(cache, ip.subnet_id)
            if ip_subnet is not None and ip_subnet.vlan_id == vlan.id:
                return str(ip.ip)
        return None

    async def _get_dhcp_host_reservations(
        self, subnet_ids: list[int]
    ) -> dict[int, list[HostReservationData]]:
        hosts_by_subnet = {subnet_id: [] for subnet_id in subnet_ids}
        if not subnet_ids:
            return hosts_by_subnet
        ips = await self.staticipaddress_service.get_many(
            query=QuerySpec(
                where=StaticIPAddressClauseFactory.and_clauses(
                    [
                        StaticIPAddressClauseFactory.with_subnet_id_in(
                            subnet_ids
                        ),
                        StaticIPAddressClauseFactory.with_alloc_type_in(
                            [
                                IpAddressType.AUTO,
                                IpAddressType.STICKY,
                                IpAddressType.USER_RESERVED,
                            ]
                        ),
                        StaticIPAddressClauseFactory.with_ip_not_null(),
                        StaticIPAddressClauseFactory.with_temp_expires_on_is_null(),
                    ]
                ),
                order_by=[OrderByClause(StaticIPAddressTable.c.id)],
            )
        )
        seen_interfaces: set[int] = set()
        interfaces_by_ip = await self.interfaces_service.get_for_ips(ips)
        parents_cache: dict[int, list[Interface]] = {}
        hostname_cache: dict[int, str] = {}
        for ip in ips:
            if ip.ip is None or ip.subnet_id is None:
                continue
            interfaces = interfaces_by_ip.get(ip.id)
            for interface in sorted(
                interfaces or [], key=lambda item: item.created
            ):
                parents = []
                if interface.type == InterfaceType.BOND:
                    if interface.id not in parents_cache:
                        parents_cache[interface.id] = sorted(
                            await self.interfaces_service.get_parents(
                                interface.id
                            ),
                            key=lambda item: item.created,
                        )
                    parents = parents_cache[interface.id]
                for parent in parents:
                    if parent.id in seen_interfaces:
                        continue
                    seen_interfaces.add(parent.id)
                    if parent.mac_address == interface.mac_address:
                        continue
                    if parent.mac_address is not None:
                        hosts_by_subnet[ip.subnet_id].append(
                            HostReservationData(
                                ip=str(ip.ip),
                                mac_address=parent.mac_address,
                                hostname=await self._make_interface_hostname(
                                    parent, hostname_cache
                                ),
                            ),
                        )
                if interface.id in seen_interfaces:
                    continue
                seen_interfaces.add(interface.id)
                if interface.mac_address is not None:
                    hosts_by_subnet[ip.subnet_id].append(
                        HostReservationData(
                            ip=str(ip.ip),
                            mac_address=interface.mac_address,
                            hostname=await self._make_interface_hostname(
                                interface, hostname_cache
                            ),
                        )
                    )
        reserved_ips = await self.reservedips_service.get_many(
            query=QuerySpec(
                where=ReservedIPsClauseFactory.with_subnet_id_in(subnet_ids),
                order_by=[OrderByClause(ReservedIPTable.c.id)],
            )
        )
        known_macs = {
            host.mac_address
            for hosts in hosts_by_subnet.values()
            for host in hosts
        }
        for reserved_ip in reserved_ips:
            if reserved_ip.mac_address not in known_macs:
                hosts_by_subnet[reserved_ip.subnet_id].append(
                    HostReservationData(
                        ip=str(reserved_ip.ip),
                        mac_address=reserved_ip.mac_address,
                        hostname=f"rsvd-{reserved_ip.id}",
                    )
                )
        return hosts_by_subnet

    async def _make_interface_hostname(
        self,
        interface: Interface,
        hostname_cache: dict[int, str] | None = None,
    ) -> str:
        if hostname_cache is not None and interface.id in hostname_cache:
            return hostname_cache[interface.id]
        name = interface.name.replace(".", "-")
        if interface.node_config_id is None:
            hostname = f"unknown-{interface.id}-{name}"
        else:
            node = await self.nodes_service.get_one(
                query=QuerySpec(
                    where=NodeClauseFactory.with_node_config_id(
                        interface.node_config_id
                    )
                )
            )
            assert node is not None
            hostname = f"{node.hostname}-{name}"
        if hostname_cache is not None:
            hostname_cache[interface.id] = hostname
        return hostname

    async def _get_ntp_servers_for_rack(
        self, rack: Node, cache: _DHCPQueryCache
    ) -> dict[tuple[int | None, int], str]:
        addresses = await self.staticipaddress_service.get_for_nodes(
            query=QuerySpec(
                where=StaticIPAddressClauseFactory.and_clauses(
                    [
                        StaticIPAddressClauseFactory.with_node_system_id(
                            rack.system_id
                        ),
                        StaticIPAddressClauseFactory.with_interface_enabled(
                            True
                        ),
                        StaticIPAddressClauseFactory.with_alloc_type_in(
                            [IpAddressType.STICKY, IpAddressType.USER_RESERVED]
                        ),
                        StaticIPAddressClauseFactory.with_ip_not_null(),
                    ]
                )
            )
        )
        best: dict[tuple[int | None, int], tuple[bool, int, str]] = {}
        for address in addresses:
            if address.ip is None or address.subnet_id is None:
                continue
            subnet = await self._cached_subnet(cache, address.subnet_id)
            assert subnet is not None
            vlan = await self._cached_vlan(cache, subnet.vlan_id)
            assert vlan is not None
            key = (vlan.space_id, address.ip.version)
            rank = (
                not vlan.dhcp_on,
                int(ip_address(str(address.ip))),
                str(address.ip),
            )
            if key not in best or rank < best[key]:
                best[key] = rank
        return {key: rank[2] for key, rank in best.items()}

    async def _get_boot_rack_controller_ips(
        self, subnet: Subnet, cache: _DHCPQueryCache
    ) -> list[IPv4Address | IPv6Address]:
        vlan = await self._cached_vlan(cache, subnet.vlan_id)
        assert vlan is not None
        if vlan.relay_vlan_id is not None:
            vlan = await self._cached_vlan(cache, vlan.relay_vlan_id)
            assert vlan is not None
        if not vlan.dhcp_on or vlan.primary_rack_id is None:
            return []
        addresses: list[IPv4Address | IPv6Address] = []
        vlan_subnets = await self.subnets_service.get_many(
            query=QuerySpec(where=SubnetClauseFactory.with_vlan_id(vlan.id))
        )
        rack_ids = [
            rack_id
            for rack_id in (vlan.primary_rack_id, vlan.secondary_rack_id)
            if rack_id is not None
        ]
        for rack_id in rack_ids:
            rack = await self._cached_node(cache, rack_id)
            assert rack is not None
            ips = await self.staticipaddress_service.get_for_nodes(
                query=QuerySpec(
                    where=StaticIPAddressClauseFactory.and_clauses(
                        [
                            StaticIPAddressClauseFactory.with_node_system_id(
                                rack.system_id
                            ),
                            StaticIPAddressClauseFactory.with_subnet_id_in(
                                [sn.id for sn in vlan_subnets]
                            ),
                            StaticIPAddressClauseFactory.with_ip_not_null(),
                            StaticIPAddressClauseFactory.with_alloc_type_not_in(
                                [IpAddressType.DISCOVERED]
                            ),
                        ]
                    )
                )
            )
            for ip in ips:
                if (
                    ip.ip is not None
                    and ip.ip.version == subnet.cidr.version
                    and ip.ip not in addresses
                ):
                    addresses.append(ip_address(str(ip.ip)))
        return sorted(addresses, key=lambda ip: ip not in subnet.cidr)

    async def _get_alt_region_ips_for_dns(
        self, dns_servers: list[IPv4Address | IPv6Address]
    ) -> list[IPv4Address | IPv6Address]:
        addresses: list[IPv4Address | IPv6Address] = []
        regions = await self.nodes_service.get_many(
            query=QuerySpec(
                where=NodeClauseFactory.or_clauses(
                    [
                        NodeClauseFactory.with_type(
                            NodeTypeEnum.REGION_CONTROLLER
                        ),
                        NodeClauseFactory.with_type(
                            NodeTypeEnum.REGION_AND_RACK_CONTROLLER
                        ),
                    ]
                )
            )
        )
        regions_by_id = {region.id: region for region in regions}
        seen_regions: set[tuple[int, int]] = set()
        best_subnet_cache: dict[str, Subnet | None] = {}
        region_ips_cache: dict[tuple[int, int], list[StaticIPAddress]] = {}

        async def _best_subnet(ip: IPv4Address | IPv6Address) -> Subnet | None:
            key = str(ip)
            if key not in best_subnet_cache:
                best_subnet_cache[
                    key
                ] = await self.subnets_service.find_best_subnet_for_ip(ip)
            return best_subnet_cache[key]

        async def _region_ips(
            region: Node, subnet: Subnet
        ) -> list[StaticIPAddress]:
            key = (region.id, subnet.id)
            if key not in region_ips_cache:
                region_ips_cache[
                    key
                ] = await self.staticipaddress_service.get_for_nodes(
                    query=QuerySpec(
                        where=StaticIPAddressClauseFactory.and_clauses(
                            [
                                StaticIPAddressClauseFactory.with_node_system_id(
                                    region.system_id
                                ),
                                StaticIPAddressClauseFactory.with_subnet_id(
                                    subnet.id
                                ),
                                StaticIPAddressClauseFactory.with_ip_not_null(),
                            ]
                        ),
                        order_by=[OrderByClause(StaticIPAddressTable.c.ip)],
                    )
                )
            return region_ips_cache[key]

        for server in dns_servers:
            subnet = await _best_subnet(server)
            if subnet is None:
                continue
            for region in regions_by_id.values():
                if region.current_config_id is None:
                    continue
                ips = await _region_ips(region, subnet)
                if (region.id, server.version) in seen_regions:
                    continue
                for ip in ips:
                    if (
                        ip.ip is None
                        or ip.ip.version != server.version
                        or ip.ip in dns_servers
                    ):
                        continue
                    alternate_subnet = await _best_subnet(
                        ip_address(str(ip.ip))
                    )
                    if (
                        alternate_subnet is not None
                        and not alternate_subnet.allow_dns
                    ):
                        continue
                    if ip.ip not in addresses:
                        addresses.append(ip_address(str(ip.ip)))
                    seen_regions.add((region.id, server.version))
                    break
        return addresses

    async def _get_default_dns_servers_for_subnet(
        self,
        subnet: Subnet,
        rack_url: str | None,
        cache: _DHCPQueryCache,
    ) -> list[str]:
        explicit_servers = subnet.dns_servers or []
        if not subnet.allow_dns:
            return list(explicit_servers)
        network = IPNetwork(str(subnet.cidr))
        source = await asyncio.to_thread(get_source_address, network)
        default_region_ip = (
            ip_address(str(source)) if source is not None else None
        )
        if (
            default_region_ip is not None
            and default_region_ip.version != subnet.cidr.version
        ):
            default_region_ip = None
        if rack_url:
            maas_server_host = urlparse(rack_url).hostname
        elif default_region_ip is not None:
            maas_server_host = str(default_region_ip)
        else:
            maas_server_host = urlparse(
                await self.configurations_service.get("maas_url")
            ).hostname
        servers: list[IPv4Address | IPv6Address] = []
        if maas_server_host is not None:
            try:
                resolved = await asyncio.to_thread(
                    resolve_hostname, maas_server_host, subnet.cidr.version
                )
            except OSError:
                logger.warning(
                    "Unable to resolve MAAS host for DHCP DNS.",
                    hostname=maas_server_host,
                    exc_info=True,
                )
            else:
                servers = [
                    ip_address(str(ip))
                    for ip in resolved
                    if not ip.is_link_local()
                ]
                allowed_dns_servers = []
                for server in servers:
                    server_subnet = (
                        await self.subnets_service.find_best_subnet_for_ip(
                            server
                        )
                    )
                    if server_subnet is None or server_subnet.allow_dns:
                        allowed_dns_servers.append(server)
                servers = sorted(allowed_dns_servers)
                non_loopback = [
                    server for server in servers if not server.is_loopback
                ]
                if non_loopback:
                    servers = non_loopback
        if MAAS_ID.get():
            servers.extend(await self._get_alt_region_ips_for_dns(servers))
        if await self.configurations_service.get("use_rack_proxy"):
            rack_ips = await self._get_boot_rack_controller_ips(subnet, cache)
            servers = rack_ips + [
                ip
                for ip in servers
                if ip not in rack_ips and ip != default_region_ip
            ]
        if default_region_ip is not None and default_region_ip in servers:
            servers = [ip for ip in servers if ip != default_region_ip] + [
                default_region_ip
            ]
        if not servers:
            if default_region_ip is not None:
                logger.warning(
                    "No DNS servers found, DHCP defaulting to region IP."
                )
                servers = [default_region_ip]
            else:
                logger.warning("No DNS servers found.")
        if subnet.gateway_ip is None:
            servers = [ip for ip in servers if ip in subnet.cidr]
        return list(
            dict.fromkeys([str(ip) for ip in servers] + explicit_servers)
        )
