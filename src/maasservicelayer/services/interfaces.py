#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import List

from maascommon.enums.dns import DnsUpdateAction
from maascommon.enums.ipaddress import IpAddressType
from maascommon.workflows.dhcp import (
    CONFIGURE_DHCP_WORKFLOW_NAME,
    ConfigureDHCPParam,
    merge_configure_dhcp_param,
)
from maasservicelayer.builders.interfaces import InterfaceBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.interfaces import InterfaceRepository
from maasservicelayer.db.repositories.nodes import NodeClauseFactory
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.interfaces import Interface
from maasservicelayer.models.nodes import Node
from maasservicelayer.models.staticipaddress import StaticIPAddress
from maasservicelayer.services.base import BaseService
from maasservicelayer.services.dnspublications import DNSPublicationsService
from maasservicelayer.services.dnsresources import (
    DNSResourcesService,
    NoDNSResourceException,
)
from maasservicelayer.services.domains import DomainsService
from maasservicelayer.services.nodes import NodesService
from maasservicelayer.services.temporal import TemporalService


class InterfacesService(
    BaseService[Interface, InterfaceRepository, InterfaceBuilder]
):
    """
    WIP: We are rethinking the way we model interfaces and storage in the new LST.
    In this service we have to add only what's really needed until we figure out the new model.
    """

    def __init__(
        self,
        context: Context,
        temporal_service: TemporalService,
        dnsresource_service: DNSResourcesService,
        dnspublication_service: DNSPublicationsService,
        domain_service: DomainsService,
        node_service: NodesService,
        interface_repository: InterfaceRepository,
    ):
        super().__init__(context, interface_repository)
        self.temporal_service = temporal_service
        self.dnsresource_service = dnsresource_service
        self.dnspublication_service = dnspublication_service
        self.domain_service = domain_service
        self.node_service = node_service
        self.interface_repository = interface_repository

    async def list_for_node(
        self, node_id: int, page: int, size: int
    ) -> ListResult[Interface]:
        return await self.interface_repository.list_for_node(
            node_id=node_id, page=page, size=size
        )

    async def get_interfaces_for_mac(self, mac: str) -> List[Interface]:
        return await self.interface_repository.get_interfaces_for_mac(mac)

    async def get_interfaces_in_fabric(
        self, fabric_id: int
    ) -> List[Interface]:
        return await self.interface_repository.get_interfaces_in_fabric(
            fabric_id=fabric_id
        )

    async def link_ip(
        self, interfaces: List[Interface], sip: StaticIPAddress
    ) -> None:
        for interface in interfaces:
            await self.add_ip(interface, sip)

    def _get_dns_label_for_interface(
        self, interface: Interface, node: Node
    ) -> str:
        if node.boot_interface_id == interface.id:
            return node.hostname
        else:
            return f"{interface.name}.{node.hostname}"

    async def create_unkwnown_interface(
        self, mac: str, vlan_id: int
    ) -> Interface:
        return await self.interface_repository.create_unknwown_interface(
            mac, vlan_id
        )

    async def add_ip(self, interface: Interface, sip: StaticIPAddress) -> None:
        await self.interface_repository.add_ip(interface, sip.id)

        if sip.alloc_type in (
            IpAddressType.AUTO,
            IpAddressType.STICKY,
            IpAddressType.USER_RESERVED,
        ):
            self.temporal_service.register_or_update_workflow_call(
                CONFIGURE_DHCP_WORKFLOW_NAME,
                ConfigureDHCPParam(static_ip_addr_ids=[sip.id]),
                parameter_merge_func=merge_configure_dhcp_param,
                wait=False,
            )

        if not interface.node_config_id:
            return

        node = await self.node_service.get_one(
            query=QuerySpec(
                where=NodeClauseFactory.with_node_config_id(
                    interface.node_config_id
                )
            ),
        )
        if not node:
            return

        dns_label = self._get_dns_label_for_interface(interface, node)
        domain = await self.domain_service.get_domain_for_node(node)

        if sip.ip:
            await self.dnsresource_service.add_ip(sip, dns_label, domain)
        else:
            try:
                await self.dnsresource_service.remove_ip(
                    sip, dns_label, domain
                )
            except (
                NoDNSResourceException
            ):  # if a DNSResource doesn't exist, we can ignore this
                pass

        await self.dnspublication_service.create_for_config_update(
            source=f"ip {sip.ip} connected to {node.hostname} on {interface.name}",
            action=DnsUpdateAction.INSERT,
            label=dns_label,
            rtype="A",
            zone=domain.name,
        )

    async def remove_ip(
        self, interface: Interface, sip: StaticIPAddress
    ) -> None:
        await self.interface_repository.remove_ip(interface, sip)

        if (
            sip.alloc_type
            in (
                IpAddressType.AUTO,
                IpAddressType.STICKY,
                IpAddressType.USER_RESERVED,
            )
            and sip.subnet_id
        ):
            self.temporal_service.register_or_update_workflow_call(
                CONFIGURE_DHCP_WORKFLOW_NAME,
                ConfigureDHCPParam(subnet_ids=[sip.subnet_id]),
                parameter_merge_func=merge_configure_dhcp_param,
                wait=False,
            )

        if not interface.node_config_id:
            return

        node = await self.node_service.get_one(
            query=QuerySpec(
                where=NodeClauseFactory.with_node_config_id(
                    interface.node_config_id
                )
            ),
        )
        if not node:
            return

        dns_label = self._get_dns_label_for_interface(interface, node)
        domain = await self.domain_service.get_domain_for_node(node)

        dnsresource_deleted = await self.dnsresource_service.remove_ip(
            sip, dns_label, domain
        )

        await self.dnspublication_service.create_for_config_update(
            source=f"ip {sip.ip} disconnected from {node.hostname} on {interface.name}",
            action=(
                DnsUpdateAction.DELETE
                if dnsresource_deleted
                else DnsUpdateAction.UPDATE
            ),
            label=dns_label,
            rtype="A",
            zone=domain.name,
        )
