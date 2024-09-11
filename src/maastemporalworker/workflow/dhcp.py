import asyncio
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import and_, or_, select, true
from sqlalchemy.ext.asyncio import AsyncConnection
from temporalio import activity, workflow

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
from maastemporalworker.workflow.activity import ActivityBase


@dataclass
class ConfigureDHCPParam:
    system_ids: Optional[list[str]]
    vlan_ids: Optional[list[int]]
    subnet_ids: Optional[list[int]]
    static_ip_addr_ids: Optional[list[int]]
    ip_range_ids: Optional[list[int]]
    reserved_ip_ids: Optional[list[int]]


@dataclass
class AgentsForUpdateResult:
    agent_system_ids: list[str]


@dataclass
class ConfigureDHCPForAgentParam:
    system_id: str
    full_reload: bool
    static_ip_addr_ids: list[int]
    reserved_ip_ids: list[int]


@dataclass
class FetchDHCPDConfigParam:
    system_id: str


@dataclass
class DHCPDConfigResult:
    dhcpd: str
    dhcpd6: str


@dataclass
class FetchHostsForUpdateParam:
    system_id: str
    static_ip_addr_ids: list[int]
    reserved_ip_ids: list[int]


@dataclass
class Host:
    ip: Optional[str]
    mac: Optional[str]
    hostname: Optional[str]


@dataclass
class HostsForUpdateResult:
    hosts: list[Host]


@dataclass
class ApplyConfigViaFileParam:
    dhcpd: str
    dhcpd6: str


@dataclass
class ApplyConfigViaOmapiParam:
    secret: str
    hosts: list[Host]


@dataclass
class OMAPIKeyResult:
    key: str


class DHCPConfigActivity(ActivityBase):
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
            .select_from(ReservedIPTable)
            .join(
                VlanTable,
                VlanTable.c.id == ReservedIPTable.c.vlan_id,
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

    @activity.defn(name="find-agents-for-update")
    async def find_agents_for_updates(
        self, param: ConfigureDHCPParam
    ) -> AgentsForUpdateResult:
        async with self.start_transaction() as tx:
            system_ids = set(param.system_ids)
            vlan_ids = set(param.vlan_ids)

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

    # TODO to be implemented when config endpoint is available
    @activity.defn(name="fetch-dhcpd-config")
    async def fetch_dhcpd_config(
        self, param: FetchDHCPDConfigParam
    ) -> DHCPDConfigResult:
        pass

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
                VlanTable,
                VlanTable.c.id == ReservedIPTable.c.vlan_id,
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

    @activity.defn(name="fetch-hosts-for-update")
    async def fetch_hosts_for_update(
        self, param: FetchHostsForUpdateParam
    ) -> HostsForUpdateResult:
        async with self.start_transaction() as tx:
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

    @activity.defn(name="get-omapi-key")
    async def get_omapi_key(self) -> OMAPIKeyResult:
        key = await self.get_simple_secret("omapi-key")
        return OMAPIKeyResult(key=key)


@workflow.defn(name="configure-dhcp-for-agent")
class ConfigureDHCPForAgentWorkflow:

    @workflow.run
    async def run(self, param: ConfigureDHCPForAgentParam) -> None:
        if param.full_reload:
            cfg = await workflow.execute_activity(
                "fetch-dhcpd-config",
                FetchDHCPDConfigParam(system_id=param.system_id),
            )

            await workflow.execute_activity(
                "apply-dhcp-config-via-file",
                ApplyConfigViaFileParam(dhcpd=cfg.dhcpd, dhcpd6=cfg.dhcpd6),
                task_queue=f"{param.system_id}@agent:main",
            )
        else:
            hosts = await workflow.execute_activity(
                "fetch-hosts-for-update",
                FetchHostsForUpdateParam(
                    system_id=param.system_id,
                    static_ip_addr_ids=param.static_ip_addr_ids,
                    reserved_ip_ids=param.reserved_ip_ids,
                ),
            )
            omapi_key = await workflow.execute_activity("get-omapi-key")

            await workflow.execute_activity(
                "apply-dhcp-config-via-omapi",
                ApplyConfigViaOmapiParam(
                    hosts=hosts["hosts"],
                    secret=omapi_key,
                    task_queue=f"{param.system_id}@agent:main",
                ),
            )


@workflow.defn(name="configure-dhcp")
class ConfigureDHCPWorkflow:

    @workflow.run
    async def run(self, param: ConfigureDHCPParam) -> None:
        agent_system_ids_for_update = await workflow.execute_activity(
            "find-agents-for-update", param
        )

        full_reload = bool(
            param.system_ids
            or param.vlan_ids
            or param.subnet_ids
            or param.ip_range_ids
        )  # determine if a config file write is needed

        children = []

        for system_id in agent_system_ids_for_update:
            cfg_child = await workflow.start_child_workflow(
                "configure-dhcp-for-agent",
                ConfigureDHCPForAgentParam(
                    system_id=system_id,
                    full_reload=full_reload,
                    static_ip_addr_ids=param.static_ip_addr_ids,
                    reserved_ip_ids=param.reserved_ip_ids,
                ),
                workflow_id=f"configure-dhcp:{system_id}",
            )
            children.append(cfg_child)

        asyncio.gather(*children)
