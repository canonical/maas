# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import os
from typing import Optional

from sqlalchemy import and_, or_, select, true
from sqlalchemy.ext.asyncio import AsyncConnection
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
from maasservicelayer.db.filters import QuerySpec
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
    InterfaceIPAddressTable,
    InterfaceTable,
    IPRangeTable,
    NodeTable,
    ReservedIPTable,
    StaticIPAddressTable,
    SubnetTable,
    VlanTable,
)
from maasservicelayer.models.secrets import OMAPIKeySecret
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.models.vlans import Vlan
from maasservicelayer.services import ServiceCollectionV3
from maastemporalworker.workflow.activity import ActivityBase
from maastemporalworker.workflow.utils import (
    activity_defn_with_context,
    workflow_run_with_context,
)

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
class SubnetData:
    id: int
    cidr: str
    gateway_ip: str
    dns_servers: list[str] | None
    allow_dns: bool
    vlan_id: int


@dataclass
class InterfaceData:
    id: int
    vlan_id: int
    name: str


@dataclass
class IPRangeData:
    id: int
    subnet_id: int
    dynamic: bool
    start_ip: str
    end_ip: str


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


@dataclass
class ConfigDQLiteParam:
    vlans: list[VlanData]
    subnets: list[SubnetData]
    ipranges: list[IPRangeData]
    interfaces: list[InterfaceData]
    host_reservations: list[HostReservationData]
    default_dns_servers: list[str]
    ntp_servers: list[str]


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

            dns_servers = [
                str(dns_ip.ip)
                for dns_ip in rack_ips
                if dns_ip.subnet_id in configured_subnet_ids
            ]

            ntp_servers = []
            use_external_ntp_only = await svc.configurations.get(
                "use_external_ntp_only"
            )
            if use_external_ntp_only:
                ntp_servers = await svc.configurations.get(
                    "ntp_servers", default=[]
                )
            else:
                ntp_servers = [
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
                subnets=[
                    SubnetData(
                        id=subnet.id,
                        cidr=str(subnet.cidr),
                        vlan_id=subnet.vlan_id,
                        gateway_ip=str(subnet.gateway_ip),
                        dns_servers=subnet.dns_servers,
                        allow_dns=subnet.allow_dns,
                    )
                    for subnet in subnets
                ],
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
                ntp_servers=ntp_servers,
                default_dns_servers=dns_servers,
            )


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

        await workflow.execute_activity(
            "apply-dhcp-config-via-dqlite",
            ConfigDQLiteParam(
                vlans=[VlanData(**vlan) for vlan in data["vlans"]],
                subnets=[SubnetData(**subnet) for subnet in data["subnets"]],
                interfaces=[
                    InterfaceData(**interface)
                    for interface in data["interfaces"]
                ],
                ipranges=[
                    IPRangeData(**iprange) for iprange in data["ipranges"]
                ],
                host_reservations=[
                    HostReservationData(**host)
                    for host in data["host_reservations"]
                ],
                ntp_servers=data["ntp_servers"],
                default_dns_servers=data["default_dns_servers"],
            ),
            task_queue=f"{param.system_id}@agent:main",
            start_to_close_timeout=APPLY_DHCP_CONFIG_VIA_FILE_TIMEOUT,
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
