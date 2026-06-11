# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import asyncio
from dataclasses import dataclass
from datetime import timedelta
from ipaddress import IPv4Address, IPv6Address
from itertools import groupby
import os
from typing import Any, Optional
from urllib.parse import urlparse

from netaddr import IPAddress, IPNetwork
from pydantic import IPvAnyAddress
from sqlalchemy import and_, or_, select, true
from sqlalchemy.ext.asyncio import AsyncConnection
import structlog
from temporalio import workflow
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from maascommon.enums.ipaddress import IpAddressType
from maascommon.enums.ipranges import IPRangeType
from maascommon.enums.node import NodeTypeEnum
from maascommon.workflows.dhcp import (
    CONFIGURE_DHCP_FOR_AGENT_WORKFLOW_NAME,
    CONFIGURE_DHCP_WORKFLOW_NAME,
    ConfigureDHCPForAgentParam,
    ConfigureDHCPParam,
)
from maasservicelayer.db.filters import (
    OrderByClause,
    OrderByClauseFactory,
    QuerySpec,
)
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
    InterfaceIPAddressTable,
    InterfaceTable,
    IPRangeTable,
    NodeTable,
    ReservedIPTable,
    StaticIPAddressTable,
    SubnetTable,
    VlanTable,
)
from maasservicelayer.models.interfaces import Interface, InterfaceType
from maasservicelayer.models.nodes import Node
from maasservicelayer.models.secrets import OMAPIKeySecret
from maasservicelayer.models.staticipaddress import StaticIPAddress
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.models.vlans import Vlan
from maasservicelayer.services import ServiceCollectionV3
from maastemporalworker.workflow.activity import ActivityBase
from maastemporalworker.workflow.utils import (
    activity_defn_with_context,
    workflow_run_with_context,
)

from provisioningserver.boot.pxe import PXEBootMethod  # noqa:E402 isort:skip
from provisioningserver.utils.env import MAAS_ID
from provisioningserver.utils.network import (
    get_source_address,
    resolve_hostname,
)
from provisioningserver.utils.text import split_string_list

FIND_AGENTS_FOR_UPDATE_TIMEOUT = timedelta(minutes=5)
APPLY_DHCP_CONFIG_VIA_FILE_TIMEOUT = timedelta(minutes=5)
FETCH_HOSTS_FOR_UPDATE_TIMEOUT = timedelta(minutes=5)
GET_OMAPI_KEY_TIMEOUT = timedelta(minutes=5)
APPLY_DHCP_CONFIG_VIA_OMAPI_TIMEOUT = timedelta(minutes=5)
RESTART_DHCP_SERVICE_TIMEOUT = timedelta(minutes=5)

# Activities names
FIND_AGENTS_FOR_UPDATE_ACTIVITY_NAME = "find-agents-for-update"
FETCH_HOSTS_FOR_UPDATE_ACTIVITY_NAME = "fetch-hosts-for-update"
GET_OMAPI_KEY_ACTIVITY_NAME = "get-omapi-key"
GET_ACTIVE_INTERFACES_FOR_AGENT_NAME = "get-active-interfaces-for-agent"

# Executed on maasagent
APPLY_DHCP_CONFIG_VIA_FILE_ACTIVITY_NAME = "apply-dhcp-config-via-file"
RESTART_DHCP_SERVICE_ACTIVITY_NAME = "restart-dhcp-service"
APPLY_DHCP_CONFIG_VIA_OMAPI_ACTIVITY_NAME = "apply-dhcp-config-via-omapi"


logger = structlog.get_logger()


# Activities parameters
@dataclass
class AgentsForUpdateResult:
    agent_system_ids: list[str]


@dataclass
class DHCPDConfigResult:
    dhcpd: str
    dhcpd6: str


@dataclass
class FetchHostsForUpdateParam:
    system_id: str
    static_ip_addr_ids: list[int] | None = None
    reserved_ip_ids: list[int] | None = None


@dataclass
class Host:
    ip: Optional[str]
    mac: Optional[str]
    hostname: Optional[str]


@dataclass
class HostsForUpdateResult:
    hosts: list[Host]


@dataclass
class ApplyConfigViaOmapiParam:
    secret: str
    hosts: list[Host]


@dataclass
class OMAPIKeyResult:
    key: str


@dataclass
class GetActiveInterfacesForAgentParam:
    system_id: str


@dataclass
class SetActiveInterfacesParam:
    ifaces: list[str]


@dataclass
class ActiveInterfacesForAgentResult:
    ifaces: list[str]


@dataclass
class VlanData:
    id: int
    vid: int
    relayed_vlan_id: int | None
    mtu: int


@dataclass
class IPRangeData:
    id: int
    subnet_id: int
    dynamic: bool
    start_ip: str
    end_ip: str


@dataclass
class SubnetData:
    id: int
    ip_version: int
    cidr: str
    gateway_ip: str
    dns_servers: list[str] | None
    allow_dns: bool
    vlan_id: int
    vlan_mtu: int
    mask: str
    broadcast_ip: str
    domain_name: str
    search_list: list[str] | None
    ntp_servers: list[str] | None
    next_server: str
    pools: list[IPRangeData]


@dataclass
class InterfaceData:
    id: int
    vlan_id: int
    name: str


@dataclass
class HostReservationData:
    ip: str
    subnet_id: int
    mac_address: Optional[str] = None
    duid: Optional[str] = None
    domain: Optional[str] = None
    hostname: Optional[str] = None
    domain_search: Optional[list[str]] = None


@dataclass
class DHCPDataForAgent:
    vlans: list[VlanData]
    subnets: list[SubnetData]
    ipranges: list[IPRangeData]
    interfaces: list[InterfaceData]
    host_reservations: list[HostReservationData]
    default_dns_servers: list[str]
    ntp_servers: list[str]


@dataclass
class GetDHCPDataForAgentParam:
    system_id: str


class DHCPConfigActivity(ActivityBase):
    OMAPI_KEY_SECRET = OMAPIKeySecret()

    async def _get_agents_for_vlans(
        self, tx: AsyncConnection, vlan_ids: set[int]
    ) -> set[str]:
        relay_stmt = (
            select(VlanTable.c.id, VlanTable.c.relay_vlan_id)
            .select_from(VlanTable)
            .filter(
                and_(
                    VlanTable.c.id.in_(vlan_ids),
                    VlanTable.c.relay_vlan_id.is_not(None),
                )
            )
        )

        relays_result = (await tx.execute(relay_stmt)).all()

        vlan_ids -= {r[0] for r in relays_result}
        vlan_ids |= {r[1] for r in relays_result}

        stmt = (
            select(NodeTable.c.system_id)
            .select_from(VlanTable)
            .join(
                NodeTable,
                (NodeTable.c.id == VlanTable.c.primary_rack_id)
                | (NodeTable.c.id == VlanTable.c.secondary_rack_id),
            )
            .filter(
                and_(
                    VlanTable.c.id.in_(vlan_ids), VlanTable.c.dhcp_on == true()
                )
            )
        )
        result = await tx.execute(stmt)
        return {r[0] for r in result.all()}

    async def _get_vlans_for_subnets(
        self, tx: AsyncConnection, subnet_ids: list[int]
    ) -> set[int]:
        stmt = (
            select(VlanTable.c.id)
            .select_from(SubnetTable)
            .join(
                VlanTable,
                VlanTable.c.id == SubnetTable.c.vlan_id,
            )
            .filter(
                and_(
                    SubnetTable.c.id.in_(subnet_ids),
                    or_(
                        VlanTable.c.dhcp_on == true(),
                        VlanTable.c.relay_vlan_id.is_not(None),
                    ),
                ),
            )
        )
        result = await tx.execute(stmt)
        return {r[0] for r in result.all()}

    async def _get_vlans_for_ip_ranges(
        self, tx: AsyncConnection, ip_ranges_ids: list[int]
    ) -> set[int]:
        stmt = (
            select(VlanTable.c.id)
            .select_from(IPRangeTable)
            .join(
                SubnetTable,
                SubnetTable.c.id == IPRangeTable.c.subnet_id,
            )
            .join(
                VlanTable,
                VlanTable.c.id == SubnetTable.c.vlan_id,
            )
            .filter(
                and_(
                    IPRangeTable.c.id.in_(ip_ranges_ids),
                    or_(
                        VlanTable.c.dhcp_on == true(),
                        VlanTable.c.relay_vlan_id.is_not(None),
                    ),
                ),
            )
        )
        result = await tx.execute(stmt)
        return {r[0] for r in result.all()}

    async def _get_vlans_for_static_ip_addrs(
        self, tx: AsyncConnection, static_ip_addr_ids: list[int]
    ) -> set[int]:
        stmt = (
            select(VlanTable.c.id)
            .select_from(StaticIPAddressTable)
            .join(
                SubnetTable,
                SubnetTable.c.id == StaticIPAddressTable.c.subnet_id,
            )
            .join(
                VlanTable,
                VlanTable.c.id == SubnetTable.c.vlan_id,
            )
            .filter(
                and_(
                    StaticIPAddressTable.c.id.in_(static_ip_addr_ids),
                    or_(
                        VlanTable.c.dhcp_on == true(),
                        VlanTable.c.relay_vlan_id.is_not(None),
                    ),
                ),
            )
        )
        result = await tx.execute(stmt)
        return {r[0] for r in result.all()}

    async def _get_vlans_for_reserved_ips(
        self, tx: AsyncConnection, reserved_ip_ids: list[int]
    ) -> set[int]:
        stmt = (
            select(VlanTable.c.id)
            .select_from(SubnetTable)
            .join(
                ReservedIPTable,
                ReservedIPTable.c.subnet_id == SubnetTable.c.id,
            )
            .join(
                VlanTable,
                VlanTable.c.id == SubnetTable.c.vlan_id,
            )
            .filter(
                and_(
                    ReservedIPTable.c.id.in_(reserved_ip_ids),
                    or_(
                        VlanTable.c.dhcp_on == true(),
                        VlanTable.c.relay_vlan_id.is_not(None),
                    ),
                ),
            )
        )
        result = await tx.execute(stmt)
        return {r[0] for r in result.all()}

    @activity_defn_with_context(name=FIND_AGENTS_FOR_UPDATE_ACTIVITY_NAME)
    async def find_agents_for_updates(
        self, param: ConfigureDHCPParam
    ) -> AgentsForUpdateResult:
        async with self._start_transaction() as tx:
            system_ids = set(
                [] if param.system_ids is None else param.system_ids
            )
            vlan_ids = set([] if param.vlan_ids is None else param.vlan_ids)

            if param.reserved_ip_ids:
                vlan_ids |= await self._get_vlans_for_reserved_ips(
                    tx, param.reserved_ip_ids
                )

            if param.static_ip_addr_ids:
                vlan_ids |= await self._get_vlans_for_static_ip_addrs(
                    tx, param.static_ip_addr_ids
                )

            if param.ip_range_ids:
                vlan_ids |= await self._get_vlans_for_ip_ranges(
                    tx, param.ip_range_ids
                )

            if param.subnet_ids:
                vlan_ids |= await self._get_vlans_for_subnets(
                    tx, param.subnet_ids
                )

            if vlan_ids:
                system_ids |= await self._get_agents_for_vlans(tx, vlan_ids)

            return AgentsForUpdateResult(agent_system_ids=list(system_ids))

    async def _get_hosts_for_static_ip_addresses(
        self,
        tx: AsyncConnection,
        system_id: str,
        static_ip_addr_ids: list[int],
    ) -> list[Host]:
        rack_stmt = (
            select(NodeTable.c.id)
            .select_from(NodeTable)
            .filter(NodeTable.c.system_id == system_id)
        )

        [rack_id] = (await tx.execute(rack_stmt)).one()

        stmt = (
            select(
                StaticIPAddressTable.c.ip,
                InterfaceTable.c.mac_address,
                NodeTable.c.hostname,
            )
            .select_from(StaticIPAddressTable)
            .join(
                InterfaceIPAddressTable,
                InterfaceIPAddressTable.c.staticipaddress_id
                == StaticIPAddressTable.c.id,
            )
            .join(
                InterfaceTable,
                InterfaceTable.c.id == InterfaceIPAddressTable.c.interface_id,
            )
            .join(
                VlanTable,
                VlanTable.c.id == InterfaceTable.c.vlan_id,
            )
            .join(
                NodeTable,
                NodeTable.c.current_config_id
                == InterfaceTable.c.node_config_id,
            )
            .filter(
                and_(
                    StaticIPAddressTable.c.id.in_(static_ip_addr_ids),
                    or_(
                        VlanTable.c.primary_rack_id == rack_id,
                        VlanTable.c.secondary_rack_id == rack_id,
                    ),
                ),
            )
        )
        result = await tx.execute(stmt)
        return [
            Host(ip=str(r[0]), mac=str(r[1]), hostname=str(r[2]))
            for r in result.all()
        ]

    async def _get_hosts_for_reserved_ips(
        self, tx: AsyncConnection, system_id: str, reserved_ip_ids: list[int]
    ) -> list[Host]:
        rack_stmt = (
            select(NodeTable.c.id)
            .select_from(NodeTable)
            .filter(NodeTable.c.system_id == system_id)
        )

        [rack_id] = (await tx.execute(rack_stmt)).one()

        stmt = (
            select(
                ReservedIPTable.c.ip,
                ReservedIPTable.c.mac_address,
            )
            .select_from(ReservedIPTable)
            .join(
                SubnetTable,
                SubnetTable.c.id == ReservedIPTable.c.subnet_id,
            )
            .join(
                VlanTable,
                VlanTable.c.id == SubnetTable.c.vlan_id,
            )
            .filter(
                and_(
                    ReservedIPTable.c.id.in_(reserved_ip_ids),
                    or_(
                        VlanTable.c.primary_rack_id == rack_id,
                        VlanTable.c.secondary_rack_id == rack_id,
                    ),
                ),
            )
        )
        result = await tx.execute(stmt)
        return [
            Host(ip=str(r[0]), mac=str(r[1]) if r[1] else None, hostname="")
            for r in result.all()
        ]

    @activity_defn_with_context(name=FETCH_HOSTS_FOR_UPDATE_ACTIVITY_NAME)
    async def fetch_hosts_for_update(
        self, param: FetchHostsForUpdateParam
    ) -> HostsForUpdateResult:
        async with self._start_transaction() as tx:
            hosts = []
            if param.static_ip_addr_ids:
                hosts += await self._get_hosts_for_static_ip_addresses(
                    tx, param.system_id, param.static_ip_addr_ids
                )

            if param.reserved_ip_ids:
                hosts += await self._get_hosts_for_reserved_ips(
                    tx, param.system_id, param.reserved_ip_ids
                )

            return HostsForUpdateResult(hosts=hosts)

    @activity_defn_with_context(name=GET_OMAPI_KEY_ACTIVITY_NAME)
    async def get_omapi_key(self) -> OMAPIKeyResult:
        async with self.start_transaction() as services:
            key = await services.secrets.get_simple_secret(
                self.OMAPI_KEY_SECRET
            )
            return OMAPIKeyResult(key=key)

    async def _get_active_vlans_for_agent(
        self, svc: ServiceCollectionV3, system_id: str
    ) -> list[Vlan]:
        return await svc.vlans.get_node_vlans(
            QuerySpec(
                where=VlansClauseFactory.and_clauses(
                    clauses=[
                        VlansClauseFactory.with_system_id(system_id),
                        VlansClauseFactory.with_dhcp_on(True),
                    ],
                ),
            ),
        )

    @activity_defn_with_context(name=GET_ACTIVE_INTERFACES_FOR_AGENT_NAME)
    async def get_active_interfaces_for_agent(
        self, param: GetActiveInterfacesForAgentParam
    ) -> ActiveInterfacesForAgentResult:
        async with self.start_transaction() as svc:
            vlans = await self._get_active_vlans_for_agent(
                svc, param.system_id
            )
            node = await svc.nodes.get_one(
                query=QuerySpec(
                    where=NodeClauseFactory.with_system_id(param.system_id)
                )
            )
            assert node is not None
            assert node.current_config_id is not None
            ifaces = await svc.interfaces.get_many(
                query=QuerySpec(
                    where=InterfaceClauseFactory.and_clauses(
                        clauses=[
                            InterfaceClauseFactory.with_node_config_id(
                                node.current_config_id
                            ),
                            InterfaceClauseFactory.with_vlan_id_in(
                                [vlan.id for vlan in vlans]
                            ),
                        ]
                    )
                )
            )
            return ActiveInterfacesForAgentResult(
                ifaces=[
                    iface.name
                    for iface in ifaces
                    if iface.vlan_id in [vlan.id for vlan in vlans]
                ]
            )

    async def _get_dhcp_host_reservations(
        self, svc: ServiceCollectionV3, subnets: list[Subnet]
    ) -> list[HostReservationData]:
        sips = []
        reserved_ips = []

        for subnet in subnets:
            sips += await svc.staticipaddress.get_many(
                query=QuerySpec(
                    where=StaticIPAddressClauseFactory.and_clauses(
                        [
                            StaticIPAddressClauseFactory.with_subnet_id(
                                subnet.id
                            ),
                            StaticIPAddressClauseFactory.or_clauses(
                                [
                                    StaticIPAddressClauseFactory.with_alloc_type(
                                        IpAddressType.AUTO
                                    ),
                                    StaticIPAddressClauseFactory.with_alloc_type(
                                        IpAddressType.USER_RESERVED
                                    ),
                                    StaticIPAddressClauseFactory.with_alloc_type(
                                        IpAddressType.STICKY
                                    ),
                                ]
                            ),
                        ]
                    )
                )
            )
            reserved_ips += await svc.reservedips.get_many(
                query=QuerySpec(
                    where=ReservedIPsClauseFactory.with_subnet_id(subnet.id)
                )
            )

        domains = await svc.domains.get_many(
            query=QuerySpec(
                where=DomainsClauseFactory.with_authoritative(True)
            )
        )
        domain_search_list = [domain.name for domain in domains]

        hosts = []
        seen_domains = {}
        seen_nodes = {}

        for sip in sips:
            interfaces = await svc.interfaces.get_for_ip(sip)
            if not interfaces:
                continue

            for interface in interfaces:
                if not interface.node_config_id:
                    continue

                node = None

                if interface.node_config_id in seen_nodes:
                    node = seen_nodes[interface.node_config_id]
                else:
                    node = await svc.nodes.get_one(
                        query=QuerySpec(
                            where=NodeClauseFactory.with_node_config_id(
                                interface.node_config_id
                            )
                        )
                    )
                    assert node is not None
                    if node.node_type in (
                        NodeTypeEnum.RACK_CONTROLLER,
                        NodeTypeEnum.REGION_CONTROLLER,
                        NodeTypeEnum.REGION_AND_RACK_CONTROLLER,
                    ):
                        continue

                    seen_nodes[interface.node_config_id] = node

                domain = None

                if node.domain_id is not None:
                    if node.domain_id in seen_domains:
                        domain = seen_domains[node.domain_id]
                    else:
                        domain = await svc.domains.get_by_id(node.domain_id)
                        seen_domains[node.domain_id] = domain

                assert node.hostname is not None
                hosts.append(
                    HostReservationData(
                        mac_address=interface.mac_address,
                        ip=str(sip.ip),
                        hostname=node.hostname,
                        domain=domain.name if domain else None,
                        domain_search=domain_search_list,
                        subnet_id=sip.subnet_id,
                    )
                )

        hosts += [
            HostReservationData(
                ip=reserved_ip.ip,
                mac_address=reserved_ip.mac_address,
                subnet_id=reserved_ip.subnet_id,
            )
            for reserved_ip in reserved_ips
        ]

        return hosts

    async def _get_default_dns_servers_for_subnet(
        self,
        subnet: Subnet,
        maas_server_host: str | None,
        svc: ServiceCollectionV3,
    ) -> list[str]:
        if not subnet.allow_dns:
            return []

        def get_IPvAnyAddress_from_IPAddress(ip: IPAddress) -> IPvAnyAddress:
            return (
                IPv4Address(str(ip))
                if ip.version == 4
                else IPv6Address(str(ip))
            )

        use_rack_proxy = await svc.configurations.get("use_rack_proxy")
        dns_servers = []
        network = IPNetwork(str(subnet.cidr))
        src_addr = get_source_address(network)
        if src_addr and IPAddress(src_addr).version == network.version:
            default_region_ip = get_IPvAnyAddress_from_IPAddress(
                IPAddress(src_addr)
            )
        else:
            default_region_ip = None
        try:
            maas_server_addresses = resolve_hostname(
                maas_server_host, network.version
            )
        except OSError:
            return []
        if not maas_server_addresses:
            return []
        dns_servers = [
            get_IPvAnyAddress_from_IPAddress(ip)
            for ip in maas_server_addresses
            if not ip.is_link_local()
        ]

        if MAAS_ID.get():
            regions = set()
            alternate_ips: list[IPvAnyAddress] = []
            for ip in dns_servers:
                best_subnet = await svc.subnets.find_best_subnet_for_ip(ip)
                if best_subnet and not best_subnet.allow_dns:
                    continue
                region_ips = await svc.staticipaddress.get_many(
                    query=QuerySpec(
                        where=StaticIPAddressClauseFactory.and_clauses(
                            [
                                StaticIPAddressClauseFactory.with_ip_not_null(),
                                StaticIPAddressClauseFactory.or_clauses(
                                    [
                                        StaticIPAddressClauseFactory.with_node_type(
                                            NodeTypeEnum.REGION_AND_RACK_CONTROLLER
                                        ),
                                        StaticIPAddressClauseFactory.with_node_type(
                                            NodeTypeEnum.REGION_CONTROLLER
                                        ),
                                    ]
                                ),
                            ]
                        ),
                        order_by=[
                            OrderByClause(column=StaticIPAddressTable.c.ip)
                        ],
                    )
                )
                for region_ip in region_ips:
                    if region_ip.ip:
                        interfaces = await svc.interfaces.get_for_ip(region_ip)
                        if interfaces:
                            for iface in interfaces:
                                if iface.node_config_id:
                                    region_node = await svc.nodes.get_one(
                                        query=QuerySpec(
                                            where=NodeClauseFactory.with_node_config_id(
                                                iface.node_config_id
                                            )
                                        )
                                    )
                                    if region_node:
                                        id_plus_family = (
                                            region_node.system_id,
                                            region_ip.ip.version,
                                        )
                                        if id_plus_family not in regions:
                                            regions.add(id_plus_family)
                                            alternate_ips.append(region_ip.ip)

            for address in alternate_ips:
                if address not in dns_servers and not address.is_loopback:
                    dns_servers.append(address)
        if use_rack_proxy:
            rack_ips = await self._get_boot_rack_controller_ips(subnet, svc)
            if dns_servers:
                dns_servers = rack_ips + [
                    server
                    for server in dns_servers
                    if server not in rack_ips and server != default_region_ip
                ]
            else:
                dns_servers = rack_ips
        if default_region_ip in dns_servers:
            # Make sure the region DNS server comes last
            dns_servers = [
                server for server in dns_servers if server != default_region_ip
            ] + [default_region_ip]

        # If no DNS servers were found give the region IP. This won't go through
        # the rack but its better than nothing.
        if not dns_servers:
            if default_region_ip:
                logger.warn(
                    "No DNS servers found, DHCP defaulting to region IP."
                )
                dns_servers = [default_region_ip]
            else:
                logger.warn("No DNS servers found.")

        if subnet.gateway_ip is None:
            # If there's no gateway, only provide in-subnet dns servers
            dns_servers = [
                ip for ip in dns_servers if IPAddress(str(ip)) in network
            ]
        return [str(a) for a in dns_servers] + (
            subnet.dns_servers if subnet.dns_servers else []
        )

    async def _get_boot_rack_controller_ips(
        self, subnet: Subnet, svc: ServiceCollectionV3
    ) -> list[IPvAnyAddress]:
        network = subnet.cidr
        vlan = await svc.vlans.get_by_id(subnet.vlan_id)
        if vlan is None:
            return []
        if vlan.relay_vlan_id is None:
            dhcp_vlan = vlan
        else:
            dhcp_vlan = await svc.vlans.get_by_id(vlan.relay_vlan_id)
            assert dhcp_vlan is not None
        if not dhcp_vlan.dhcp_on or dhcp_vlan.primary_rack_id is None:
            dhcp_vlan = None
            return []
        primary_rack = await svc.nodes.get_by_id(dhcp_vlan.primary_rack_id)
        assert primary_rack is not None
        assert primary_rack.current_config_id is not None
        node_cfgs = [primary_rack.current_config_id]
        if dhcp_vlan.secondary_rack_id:
            secondary_rack = await svc.nodes.get_by_id(
                dhcp_vlan.secondary_rack_id
            )
            assert secondary_rack is not None
            assert secondary_rack.current_config_id is not None
            node_cfgs.append(secondary_rack.current_config_id)
        dhcp_vlan_subnet = await svc.subnets.get_one(
            query=QuerySpec(
                where=SubnetClauseFactory.with_vlan_id(dhcp_vlan.id)
            )
        )
        assert dhcp_vlan_subnet is not None
        ips = await svc.staticipaddress.get_for_nodes(
            query=QuerySpec(
                where=StaticIPAddressClauseFactory.and_clauses(
                    [
                        StaticIPAddressClauseFactory.with_ip_not_null(),
                        StaticIPAddressClauseFactory.with_alloc_type_not_in(
                            [IpAddressType.DISCOVERED]
                        ),
                        StaticIPAddressClauseFactory.with_subnet_id(
                            dhcp_vlan_subnet.id
                        ),
                        NodeClauseFactory.with_node_config_id_in(node_cfgs),
                    ]
                )
            )
        )

        def rank_ip(ip: IPvAnyAddress):
            val = 2
            unaware_ip = IPAddress(str(ip))
            if unaware_ip in network:
                val = 1
            return val

        return sorted(
            [
                ip.ip
                for ip in ips
                if ip.ip is not None and ip.ip.version == network.version
            ],
            key=rank_ip,
        )

    async def _get_best_interface_with_ip_on_vlan(
        self,
        svc: ServiceCollectionV3,
        subnet: Subnet,
        vlan: Vlan,
        ifaces: list[Interface],
    ) -> tuple[Interface | None, list[StaticIPAddress] | None]:
        ip_version = subnet.cidr.version

        async def _ip_version_on_vlan(
            ip_address: StaticIPAddress, sn: Subnet
        ) -> bool:
            """Return True when the `ip_address` is the same `ip_version` and is on
            the same `vlan` or relay VLAN's for the `vlan."""
            relay_vlans = await svc.vlans.get_many(
                query=QuerySpec(
                    where=VlansClauseFactory.with_relay_vlan_id(vlan.id)
                )
            )
            return (
                ip_address.ip is not None
                and ip_address.ip.version == ip_version
                and ip_address.subnet_id == sn.id
                and (sn.vlan_id == vlan.id or vlan in relay_vlans)
            )

        interfaces = []
        ifaces_with_static: list[
            tuple[Interface, list[StaticIPAddress], int]
        ] = []
        ifaces_with_discovered: list[
            tuple[Interface, list[StaticIPAddress], int]
        ] = []
        ifaces_on_vlan = [i for i in ifaces if i.vlan_id == subnet.vlan_id]
        for iface in ifaces_on_vlan:
            ips = await svc.staticipaddress.get_for_interfaces([iface.id])
            for ip in ips:
                if ip.subnet_id is None:
                    continue
                sn = await svc.subnets.get_by_id(ip.subnet_id)
                assert sn is not None
                if ip.alloc_type in [IpAddressType.AUTO, IpAddressType.STICKY]:
                    if await _ip_version_on_vlan(ip, sn):
                        dynamic_ranges = await svc.ipranges.get_many(
                            query=QuerySpec(
                                where=IPRangeClauseFactory.and_clauses(
                                    [
                                        IPRangeClauseFactory.with_subnet_id(
                                            sn.id
                                        ),
                                        IPRangeClauseFactory.with_type(
                                            IPRangeType.DYNAMIC
                                        ),
                                    ]
                                )
                            )
                        )
                        ifaces_with_static.append(
                            (iface, ips, len(dynamic_ranges))
                        )
                        break
                else:
                    if await _ip_version_on_vlan(ip, sn):
                        dynamic_ranges = await svc.ipranges.get_many(
                            query=QuerySpec(
                                where=IPRangeClauseFactory.and_clauses(
                                    [
                                        IPRangeClauseFactory.with_subnet_id(
                                            sn.id
                                        ),
                                        IPRangeClauseFactory.with_type(
                                            IPRangeType.DYNAMIC
                                        ),
                                    ]
                                )
                            )
                        )
                        ifaces_with_discovered.append(
                            (iface, ips, len(dynamic_ranges))
                        )
                        break
        if len(ifaces_with_static) == 1:
            interfaces = ifaces_with_static
        elif len(ifaces_with_static) > 1:
            interfaces = sorted(
                ifaces_with_static, key=lambda t: t[2], reverse=True
            )
        elif len(ifaces_with_discovered) == 1:
            interfaces = ifaces_with_discovered
        elif len(ifaces_with_discovered) > 1:
            interfaces = sorted(
                ifaces_with_discovered, key=lambda t: t[2], reverse=True
            )
        else:
            interfaces = []
        best_interface: Interface | None = None
        best_interface_ips: list[StaticIPAddress] | None = None
        for interface, interface_ips, _ in interfaces:
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
                best_interface_ips = interface_ips
        return best_interface, best_interface_ips

    async def _get_ntp_servers_for_rack(
        self, svc: ServiceCollectionV3, rack: Node
    ) -> dict[tuple[int, int], str]:
        rack_addresses = await svc.staticipaddress.get_for_nodes_join_vlan(
            query=QuerySpec(
                where=StaticIPAddressClauseFactory.and_clauses(
                    [
                        StaticIPAddressClauseFactory.with_interface_enabled(
                            True
                        ),
                        StaticIPAddressClauseFactory.with_node_system_id(
                            rack.system_id
                        ),
                        StaticIPAddressClauseFactory.with_alloc_type_in(
                            [IpAddressType.STICKY, IpAddressType.USER_RESERVED]
                        ),
                        StaticIPAddressClauseFactory.with_subnet_id_not_null(),
                    ]
                ),
                order_by=[
                    OrderByClauseFactory.desc_clause(
                        OrderByClause(column=VlanTable.c.dhcp_on)
                    ),
                    OrderByClause(VlanTable.c.space_id),
                    OrderByClause(SubnetTable.c.cidr),
                    OrderByClause(StaticIPAddressTable.c.ip),
                ],
            )
        )

        addr_info: list[tuple[bool, int, int, IPvAnyAddress]] = []
        for ip in rack_addresses:
            assert ip.subnet_id is not None
            subnet = await svc.subnets.get_by_id(ip.subnet_id)
            assert subnet is not None
            vlan = await svc.vlans.get_by_id(subnet.vlan_id)
            assert vlan is not None
            assert vlan.space_id is not None
            assert ip.ip is not None
            addr_info.append(
                (vlan.dhcp_on, vlan.space_id, subnet.cidr.version, ip.ip)
            )

        def get_space_id_and_family(
            record: tuple[bool, int, int, IPvAnyAddress],
        ) -> tuple[int, int]:
            _, space_id, ip_version, _ = record
            return space_id, ip_version

        def sort_key__dhcp_on__ip(
            record: tuple[bool, int, int, IPvAnyAddress],
        ) -> tuple[int, IPvAnyAddress]:
            dhcp_on, _, _, ip = record
            return -int(dhcp_on), ip

        groups = groupby(addr_info, get_space_id_and_family)
        best_ntp_servers = {
            space_id_and_family: min(group, key=sort_key__dhcp_on__ip)
            for space_id_and_family, group in groups
        }
        return {key: str(value[3]) for key, value in best_ntp_servers.items()}

    @activity_defn_with_context(name="get_dhcp_data_for_agent")
    async def get_dhcp_data_for_agent(
        self, param: GetDHCPDataForAgentParam
    ) -> DHCPDataForAgent:
        async with self.start_transaction() as svc:
            vlans = await self._get_active_vlans_for_agent(
                svc, param.system_id
            )
            node = await svc.nodes.get_one(
                query=QuerySpec(
                    where=NodeClauseFactory.with_system_id(param.system_id)
                )
            )
            rack_url = await svc.nodes.get_url(param.system_id)
            if rack_url is None:
                maas_server_host = urlparse(
                    str(await svc.configurations.get("maas_url"))
                ).hostname
            else:
                maas_server_host = urlparse(rack_url).hostname
            assert node is not None
            assert node.current_config_id is not None

            default_domain = await svc.domains.get_default_domain()
            search_list = await svc.domains.get_many(
                query=QuerySpec(
                    where=DomainsClauseFactory.and_clauses(
                        [
                            DomainsClauseFactory.not_clause(
                                DomainsClauseFactory.with_name(
                                    default_domain.name
                                )
                            ),
                            DomainsClauseFactory.with_authoritative(True),
                        ]
                    ),
                    order_by=[OrderByClause(DomainTable.c.name)],
                )
            )

            ntp_external_only = await svc.configurations.get(
                "ntp_external_only"
            )
            if ntp_external_only:
                ntp_servers = await svc.configurations.get("ntp_servers")
                ntp_servers = list(split_string_list(ntp_servers))
            else:
                ntp_servers = await self._get_ntp_servers_for_rack(svc, node)

            ifaces = await svc.interfaces.get_many(
                query=QuerySpec(
                    where=InterfaceClauseFactory.and_clauses(
                        clauses=[
                            InterfaceClauseFactory.with_node_config_id(
                                node.current_config_id
                            ),
                            InterfaceClauseFactory.with_vlan_id_in(
                                [vlan.id for vlan in vlans]
                            ),
                        ]
                    )
                )
            )
            subnets = await svc.subnets.get_many(
                query=QuerySpec(
                    where=SubnetClauseFactory.with_vlan_id_in(
                        [vlan.id for vlan in vlans]
                    )
                )
            )
            ipranges = await svc.ipranges.get_many(
                query=QuerySpec(
                    where=IPRangeClauseFactory.with_subnet_ids(
                        [subnet.id for subnet in subnets]
                    )
                )
            )

            assert node.system_id is not None
            rack_ips = await svc.staticipaddress.get_for_nodes(
                query=QuerySpec(
                    where=StaticIPAddressClauseFactory.and_clauses(
                        [
                            StaticIPAddressClauseFactory.with_node_system_id(
                                system_id=node.system_id
                            ),
                            StaticIPAddressClauseFactory.or_clauses(
                                [
                                    StaticIPAddressClauseFactory.with_alloc_type(
                                        IpAddressType.STICKY
                                    ),
                                    StaticIPAddressClauseFactory.with_alloc_type(
                                        IpAddressType.USER_RESERVED
                                    ),
                                ]
                            ),
                        ]
                    )
                )
            )
            configured_subnet_ids = [subnet.id for subnet in subnets]

            default_dns_servers = [
                str(dns_ip.ip)
                for dns_ip in rack_ips
                if dns_ip.subnet_id in configured_subnet_ids
            ]

            subnet_data = []
            for subnet in subnets:
                dns_servers = await self._get_default_dns_servers_for_subnet(
                    subnet, maas_server_host, svc
                )

                # guaranteed for one vlan to exist here because of subnets query above
                vlan = [v for v in vlans if v.id == subnet.vlan_id][0]

                (
                    best_iface,
                    iface_ips,
                ) = await self._get_best_interface_with_ip_on_vlan(
                    svc, subnet, vlan, ifaces
                )
                ips = (
                    [
                        ip
                        for ip in iface_ips
                        if ip.ip and ip.ip.version == subnet.cidr.version
                    ]
                    if iface_ips
                    else []
                )
                next_server = ""
                for i in ips:
                    if i.ip and i.ip in subnet.cidr:
                        next_server = str(i.ip)
                        break
                else:
                    if ips:
                        next_server = str(ips[0].ip)

                if isinstance(ntp_servers, dict):
                    assert vlan.space_id is not None
                    ntp_server = ntp_servers.get(
                        (vlan.space_id, subnet.cidr.version)
                    )
                    if ntp_server is None:
                        ntp = []
                    else:
                        ntp = [ntp_server]
                else:
                    ntp = ntp_servers

                subnet_data.append(
                    SubnetData(
                        id=subnet.id,
                        ip_version=subnet.cidr.version,
                        cidr=str(subnet.cidr),
                        vlan_id=subnet.vlan_id,
                        vlan_mtu=vlan.mtu,
                        gateway_ip=str(subnet.gateway_ip)
                        if subnet.gateway_ip
                        else "",
                        dns_servers=dns_servers,
                        allow_dns=subnet.allow_dns,
                        mask=str(subnet.cidr.netmask),
                        broadcast_ip=str(subnet.cidr.broadcast_address),
                        domain_name=default_domain.name,
                        search_list=[default_domain.name]
                        + [s.name for s in search_list],
                        ntp_servers=ntp,
                        next_server=next_server,
                        pools=[
                            IPRangeData(
                                id=iprange.id,
                                subnet_id=subnet.id,
                                dynamic=iprange.type == IPRangeType.DYNAMIC,
                                start_ip=str(iprange.start_ip),
                                end_ip=str(iprange.end_ip),
                            )
                            for iprange in ipranges
                            if iprange.subnet_id == subnet.id
                        ],
                    )
                )

            global_ntp_servers = []
            if ntp_external_only:
                global_ntp_servers = await svc.configurations.get(
                    "ntp_servers", default=[]
                )
            else:
                global_ntp_servers = [
                    str(ntp_ip.ip)
                    for ntp_ip in rack_ips
                    if ntp_ip.subnet_id in configured_subnet_ids
                ]

            hosts = await self._get_dhcp_host_reservations(svc, subnets)

            return DHCPDataForAgent(
                interfaces=[
                    InterfaceData(
                        id=iface.id, name=iface.name, vlan_id=iface.vlan_id
                    )
                    for iface in ifaces
                    if iface.vlan_id is not None
                ],
                vlans=[
                    VlanData(
                        id=vlan.id,
                        vid=vlan.vid,
                        relayed_vlan_id=vlan.relayed_vlan_id,
                        mtu=vlan.mtu,
                    )
                    for vlan in vlans
                ],
                subnets=subnet_data,
                ipranges=[
                    IPRangeData(
                        id=iprange.id,
                        subnet_id=iprange.subnet_id,
                        start_ip=str(iprange.start_ip),
                        end_ip=str(iprange.end_ip),
                        dynamic=iprange.type == IPRangeType.DYNAMIC,
                    )
                    for iprange in ipranges
                ],
                host_reservations=hosts,
                ntp_servers=global_ntp_servers,
                default_dns_servers=default_dns_servers,
            )

    async def get_kea_shared_networks_config_ipv4(
        self, data: DHCPDataForAgent, rack_ip: str
    ):
        cfg = {"shared-networks": []}
        pxe_method = PXEBootMethod()

        def group_by_vlan(subnet: SubnetData):
            return subnet.vlan_id

        vlans = groupby(data.subnets, key=group_by_vlan)

        for vlan_id, sns in vlans:
            network: dict[str, Any] = {"name": f"vlan-{vlan_id}"}
            subnets = []
            for subnet in sns:
                option_data = [
                    {"name": "subnet-mask", "data": subnet.mask},
                    {"name": "broadcast-address", "data": subnet.broadcast_ip},
                    {"name": "domain-name", "data": subnet.domain_name},
                    {
                        "name": "path-prefix",
                        "data": f"http://{rack_ip}:5248/",
                        "always-send": pxe_method.path_prefix_force,
                    },
                ]
                if subnet.dns_servers:
                    option_data.append(
                        {
                            "name": "domain-name-servers",
                            "data": ", ".join(subnet.dns_servers),
                        }
                    )
                if subnet.search_list:
                    option_data.append(
                        {
                            "name": "domain-search",
                            "data": ", ".join(subnet.search_list),
                        }
                    )
                if subnet.gateway_ip:
                    option_data.append(
                        {"name": "routers", "data": subnet.gateway_ip}
                    )
                if subnet.ntp_servers:
                    option_data.append(
                        {
                            "name": "ntp-servers",
                            "data": ", ".join(subnet.ntp_servers),
                        }
                    )
                sn = {
                    "subnet": subnet.cidr,
                    "match-client-id": False,
                    "pools": [
                        {"pool": f"{pool.start_ip} - {pool.end_ip}"}
                        for pool in subnet.pools
                    ],
                    "boot-file-name": pxe_method.bootloader_path,
                    "option-data": option_data,
                }
                if subnet.next_server:
                    sn["next-server"] = subnet.next_server
                subnets.append(sn)
            network["subnet4"] = subnets
            cfg["shared-networks"].append(network)
        return cfg

    async def get_kea_shared_networks_config_ipv6(
        self, data: DHCPDataForAgent, rack_ip: str
    ):
        cfg = {"shared-networks": []}
        pxe_method = PXEBootMethod()

        def group_by_vlan(subnet: SubnetData):
            return subnet.vlan_id

        vlans = groupby(data.subnets, key=group_by_vlan)

        for vlan_id, sns in vlans:
            network: dict[str, Any] = {"name": f"vlan-{vlan_id}"}
            subnets = []
            for subnet in sns:
                option_data = [
                    {"name": "domain-name", "data": subnet.domain_name},
                    {
                        "name": "path-prefix",
                        "data": f"http://[{rack_ip}]:5248/",
                        "always-send": pxe_method.path_prefix_force,
                    },
                ]
                if subnet.dns_servers:
                    option_data.append(
                        {
                            "name": "dns-servers",
                            "data": ", ".join(subnet.dns_servers),
                        }
                    )
                if subnet.search_list:
                    option_data.append(
                        {
                            "name": "domain-search",
                            "data": ", ".join(subnet.search_list),
                        }
                    )
                if subnet.ntp_servers:
                    option_data.append(
                        {
                            "name": "ntp-servers",
                            "data": ", ".join(subnet.ntp_servers),
                        }
                    )
                sn = {
                    "subnet": subnet.cidr,
                    "match-client-id": False,
                    "pools": [
                        {"pool": f"{pool.start_ip} - {pool.end_ip}"}
                        for pool in subnet.pools
                    ],
                    "boot-file-name": pxe_method.bootloader_path,
                    "option-data": option_data,
                }
                if subnet.next_server:
                    sn["next-server"] = subnet.next_server
                subnets.append(sn)
            network["subnet6"] = subnets
            cfg["shared-networks"].append(network)
        return cfg


@workflow.defn(name=CONFIGURE_DHCP_FOR_AGENT_WORKFLOW_NAME, sandboxed=False)
class ConfigureDHCPForAgentWorkflow:
    async def _run_internal(self, param: ConfigureDHCPForAgentParam) -> None:
        data = await workflow.execute_activity(
            "get_dhcp_data_for_agent",
            GetDHCPDataForAgentParam(
                system_id=param.system_id,
            ),
            start_to_close_timeout=FETCH_HOSTS_FOR_UPDATE_TIMEOUT,
        )

        await workflow.execute_activity(
            "set-active-interfaces",
            SetActiveInterfacesParam(
                ifaces=[iface["name"] for iface in data["interfaces"]]
            ),
            task_queue=f"{param.system_id}@agent:main",
            start_to_close_timeout=FETCH_HOSTS_FOR_UPDATE_TIMEOUT,
        )

    @workflow_run_with_context
    async def run(self, param: ConfigureDHCPForAgentParam) -> None:
        if os.environ.get("MAAS_INTERNAL_DHCP") == "1":
            await self._run_internal(param)
            return
        # When dhcpd restarts the static leases are lost unless they are present in the dhcpd config. This is why in every
        # scenario we want to update the dhcpd config.
        await workflow.execute_activity(
            APPLY_DHCP_CONFIG_VIA_FILE_ACTIVITY_NAME,
            task_queue=f"{param.system_id}@agent:main",
            start_to_close_timeout=APPLY_DHCP_CONFIG_VIA_FILE_TIMEOUT,
        )
        if param.full_reload:
            await workflow.execute_activity(
                RESTART_DHCP_SERVICE_ACTIVITY_NAME,
                task_queue=f"{param.system_id}@agent:main",
                start_to_close_timeout=RESTART_DHCP_SERVICE_TIMEOUT,
            )
            # TODO call get_active_interfaces_for_agent and set config
            # directly on the agent
        else:
            hosts = await workflow.execute_activity(
                FETCH_HOSTS_FOR_UPDATE_ACTIVITY_NAME,
                FetchHostsForUpdateParam(
                    system_id=param.system_id,
                    static_ip_addr_ids=param.static_ip_addr_ids,
                    reserved_ip_ids=param.reserved_ip_ids,
                ),
                start_to_close_timeout=FETCH_HOSTS_FOR_UPDATE_TIMEOUT,
            )

            omapi_key = await workflow.execute_activity(
                GET_OMAPI_KEY_ACTIVITY_NAME,
                start_to_close_timeout=GET_OMAPI_KEY_TIMEOUT,
            )

            await workflow.execute_activity(
                APPLY_DHCP_CONFIG_VIA_OMAPI_ACTIVITY_NAME,
                ApplyConfigViaOmapiParam(
                    hosts=hosts["hosts"],
                    secret=omapi_key["key"],
                ),
                task_queue=f"{param.system_id}@agent:main",
                start_to_close_timeout=APPLY_DHCP_CONFIG_VIA_OMAPI_TIMEOUT,
            )


@workflow.defn(name=CONFIGURE_DHCP_WORKFLOW_NAME, sandboxed=False)
class ConfigureDHCPWorkflow:
    @workflow_run_with_context
    async def run(self, param: ConfigureDHCPParam) -> None:
        agent_system_ids_for_update = await workflow.execute_activity(
            FIND_AGENTS_FOR_UPDATE_ACTIVITY_NAME,
            param,
            start_to_close_timeout=FIND_AGENTS_FOR_UPDATE_TIMEOUT,
        )

        full_reload = bool(
            param.system_ids
            or param.vlan_ids
            or param.subnet_ids
            or param.ip_range_ids
        )  # determine if a config file write is needed

        children = []

        for system_id in agent_system_ids_for_update["agent_system_ids"]:
            try:
                cfg_child = await workflow.start_child_workflow(
                    CONFIGURE_DHCP_FOR_AGENT_WORKFLOW_NAME,
                    ConfigureDHCPForAgentParam(
                        system_id=system_id,
                        full_reload=full_reload,
                        static_ip_addr_ids=param.static_ip_addr_ids,
                        reserved_ip_ids=param.reserved_ip_ids,
                    ),
                    id=f"configure-dhcp:{system_id}",
                )
            # If there is already something running, we have to fallback and turn the request into a full reload and terminate
            # the running workflow.
            # This is because only temporal signals are guaranteed to be processed in sequence as they arrive.
            except WorkflowAlreadyStartedError:
                cfg_child = await workflow.start_child_workflow(
                    CONFIGURE_DHCP_FOR_AGENT_WORKFLOW_NAME,
                    ConfigureDHCPForAgentParam(
                        system_id=system_id,
                        full_reload=True,
                    ),
                    id=f"configure-dhcp:{system_id}",
                    id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
                )
            children.append(cfg_child)

        await asyncio.gather(*children)
